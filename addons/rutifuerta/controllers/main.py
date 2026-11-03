"""Controlador: la web (/rutifuerta, página del sitio web de Odoo), sus archivos (/rutifuerta/web/*) y su API JSON
(/rutifuerta/api/*). Para quien no tenga el grupo, nada de esto existe: todo responde 404 (ni siquiera pide login,
para no delatar que el módulo está instalado). Por eso los archivos no van en static/, que Odoo sirve a cualquiera.
Trabaja con los datos del usuario que ha entrado (el catálogo es común)."""
import json
import logging
import mimetypes
from pathlib import Path

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from werkzeug.exceptions import NotFound

from ..services import calendar, catalog, coach, planner
from ..services.dates import today
from ..services.generator import generate
from . import serializers

_logger = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
# Odoo cachea los estáticos una semana: la versión (fecha del archivo más nuevo) fuerza a recargarlos tras cambiarlos.
VERSION = str(int(max(p.stat().st_mtime for p in WEB_DIR.rglob("*") if p.is_file())))


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Req:
    """Parámetros de la URL y cuerpo JSON de la petición."""

    def __init__(self, query, body):
        self.query, self.body = query, body

    def get(self, key, default=None):
        return self.query.get(key) or default

    def get_list(self, key):
        """Parámetro separado por comas ("a,b") como lista; None si viene vacío."""
        return [x for x in (self.query.get(key) or "").split(",") if x] or None

    def get_int(self, key, default=None):
        value = self.query.get(key)
        return int(value) if value else default


GROUP = "rutifuerta.group_fuerta_user"


def _allowed():
    """Solo quien está en «Rutifuerta / Usuario» (security/groups.xml) usa la web y la API."""
    return request.env.user.has_group(GROUP)


def _forbidden():
    """Sin permiso, la ruta «no existe»: la misma página 404 que una dirección inventada (por eso todas las rutas
    llevan website=True; sin él, Odoo da otra 404 más corta que delataría el módulo)."""
    raise NotFound()


def _page(name):
    """Página HTML suelta de web/ (sin el layout del sitio web): solo /rutifuerta/sync, la ventanita del marcador."""
    html = (WEB_DIR / name).read_text(encoding="utf-8").replace("__V__", VERSION)
    return request.make_response(html, [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-cache")])


def _api(handler):
    """Ejecuta `handler(env, req)` y responde en JSON. Los POST solo con Content-Type JSON: un formulario de otra
    web no puede mandarlo sin permiso del navegador (protección CSRF, ya que estas rutas no llevan token)."""
    hr = request.httprequest
    try:
        if not _allowed():
            _forbidden()
        body = {}
        if hr.method == "POST":
            if hr.mimetype != "application/json":
                raise HttpError(415, "Se esperaba JSON")
            try:
                body = json.loads(hr.get_data() or b"{}")
            except ValueError:
                raise HttpError(400, "JSON no válido")
            if not isinstance(body, dict):
                raise HttpError(400, "Formato no válido")
        return request.make_json_response(handler(request.env, Req(request.params, body)))
    except HttpError as e:
        request.env.cr.rollback()  # la respuesta normal confirmaría la transacción
        return request.make_json_response({"error": str(e)}, status=e.status)
    except UserError as e:  # mensajes pensados para el usuario (p. ej. nombre repetido)
        request.env.cr.rollback()
        return request.make_json_response({"error": str(e)}, status=400)
    except (KeyError, ValueError, TypeError) as e:  # faltan campos o fechas mal formadas
        request.env.cr.rollback()
        return request.make_json_response({"error": f"Petición no válida: {e}"}, status=400)


def get(path):
    return http.route(path, type="http", auth="public", methods=["GET"], website=True)


def post(path):
    return http.route(path, type="http", auth="public", methods=["POST"], csrf=False, website=True)


class FuertaWeb(http.Controller):
    # ---------- páginas ----------
    @http.route("/rutifuerta", type="http", auth="public", methods=["GET"], website=True)
    def index(self, **kw):
        if not _allowed():
            _forbidden()
        return request.render("rutifuerta.app_page", {"v": VERSION})

    @get("/rutifuerta/web/<path:ruta>")
    def archivo(self, ruta, **kw):
        """Los archivos de web/ (JS, CSS, icono), solo con permiso."""
        f = (WEB_DIR / ruta).resolve()
        if not _allowed() or not f.is_relative_to(WEB_DIR) or not f.is_file():
            _forbidden()
        tipo = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        return request.make_response(f.read_bytes(), [("Content-Type", tipo), ("Cache-Control", "private, max-age=604800")])

    @get("/rutifuerta/sync")
    def sync(self, **kw):
        if not _allowed():
            _forbidden()
        return _page("sync.html")

    # ---------- catálogo ----------
    @get("/rutifuerta/api/meta")
    def meta(self, **kw):
        return _api(lambda env, req: {**catalog.meta(catalog.get(env)), "bot": coach.available(),
                                      "model": coach.MODEL, "user": env.user.name, "today": today(env).isoformat()})

    @get("/rutifuerta/api/routines")
    def routines(self, **kw):
        def handler(env, req):
            res = catalog.search(catalog.get(env), q=req.get("q"), types=req.get_list("types"),
                                 groups=req.get_list("groups"), intensities=req.get_list("intensities"),
                                 materials=req.get_list("materials"), min_minutes=req.get_int("min"),
                                 max_minutes=req.get_int("max"), offset=req.get_int("offset", 0),
                                 limit=req.get_int("limit", 30))
            return {"total": res["total"], "items": [serializers.routine(it) for it in res["items"]]}
        return _api(handler)

    @get("/rutifuerta/api/catalog/ids")
    def catalog_ids(self, **kw):
        return _api(lambda env, req: env["fuerta.routine"].catalog_ids())

    @post("/rutifuerta/api/catalog/import")
    def catalog_import(self, **kw):
        def handler(env, req):
            items = req.body.get("items")
            if not isinstance(items, list):
                raise HttpError(400, "Formato no válido")
            res = env["fuerta.routine"].import_items(items)
            _logger.info("[catálogo] %s: +%s nuevas, %s actualizadas", env.user.login, res["added"], res["updated"])
            return res
        return _api(handler)

    # ---------- calendario y generación ----------
    @get("/rutifuerta/api/plans")
    def plans(self, **kw):
        def handler(env, req):
            start, end = req.get("from"), req.get("to")
            return serializers.calendar(catalog.get(env).by_id, env["fuerta.plan"].get_plans(start, end),
                                        env["fuerta.day.status"].get_status(start, end),
                                        env["fuerta.history"].between(start, end))
        return _api(handler)

    @post("/rutifuerta/api/generate")
    def generate(self, **kw):
        return _api(lambda env, req: generate(env, req.body))

    @post("/rutifuerta/api/plan")
    def plan_save(self, **kw):
        def handler(env, req):
            b = req.body
            ids = env["fuerta.plan"].save_plan(b["day"], b.get("postIds", []), b.get("note"), b.get("source", "manual"))
            return {"ok": True, "postIds": ids}
        return _api(handler)

    @post("/rutifuerta/api/plan/remove")
    def plan_remove(self, **kw):
        return _api(lambda env, req: env["fuerta.plan"].delete_plan(req.body["day"]) or {"ok": True})

    @post("/rutifuerta/api/plan/week")
    def plan_week(self, **kw):
        return _api(lambda env, req: planner.plan_week(env, req.body.get("start"), bool(req.body.get("overwrite"))))

    @post("/rutifuerta/api/plan/auto")
    def plan_auto(self, **kw):
        def handler(env, req):
            minutes = int(req.body["minutes"]) if req.body.get("minutes") else None
            return {"postIds": planner.plan_day(env, req.body["day"], minutes)}
        return _api(handler)

    # ---------- días especiales ----------
    @post("/rutifuerta/api/day/move")
    def day_move(self, **kw):
        def handler(env, req):
            try:
                return {"result": calendar.move_plan(env, req.body["from"], req.body["to"])}
            except ValueError as e:
                raise HttpError(400, str(e))
        return _api(handler)

    @post("/rutifuerta/api/day/skip")
    def day_skip(self, **kw):
        return _api(lambda env, req: calendar.skip_day(env, req.body["day"], req.body.get("note")) or {"ok": True})

    @post("/rutifuerta/api/day/clear")
    def day_clear(self, **kw):
        def handler(env, req):
            start = req.body["start"]
            env["fuerta.day.status"].clear_status(start, req.body.get("end") or start)
            return {"ok": True}
        return _api(handler)

    @get("/rutifuerta/api/away")
    def away_list(self, **kw):
        return _api(lambda env, req: calendar.away_ranges(env, req.get("since") or today(env).isoformat()))

    @post("/rutifuerta/api/away")
    def away_add(self, **kw):
        def handler(env, req):
            b = req.body
            calendar.set_away(env, b["start"], b["end"], b.get("note"), b.get("removePlans", True))
            return {"ok": True}
        return _api(handler)

    @post("/rutifuerta/api/away/update")
    def away_update(self, **kw):
        def handler(env, req):
            b = req.body
            calendar.update_away(env, b["oldStart"], b["oldEnd"], b["start"], b["end"], b.get("note"),
                                 b.get("removePlans", True))
            return {"ok": True}
        return _api(handler)

    # ---------- historial ----------
    @get("/rutifuerta/api/history")
    def history(self, **kw):
        def handler(env, req):
            by_id = catalog.get(env).by_id
            return [serializers.history_entry(by_id, pid, day) for pid, day in env["fuerta.history"].recent(60)]
        return _api(handler)

    @post("/rutifuerta/api/history")
    def history_mark(self, **kw):
        return _api(lambda env, req: env["fuerta.history"].mark_done(req.body.get("postIds", []),
                                                                     req.body.get("doneOn")) or {"ok": True})

    @post("/rutifuerta/api/history/remove")
    def history_unmark(self, **kw):
        return _api(lambda env, req: env["fuerta.history"].unmark_done(req.body.get("postIds", []),
                                                                       req.body.get("doneOn")) or {"ok": True})

    # ---------- ajustes y entrenador ----------
    @get("/rutifuerta/api/settings")
    def settings_get(self, **kw):
        return _api(lambda env, req: env["fuerta.settings"].get_settings())

    @post("/rutifuerta/api/settings")
    def settings_save(self, **kw):
        return _api(lambda env, req: env["fuerta.settings"].save_settings(req.body))

    # ---------- semanas tipo guardadas ----------
    @get("/rutifuerta/api/weeks")
    def weeks(self, **kw):
        return _api(lambda env, req: env["fuerta.week.plan"].get_weeks())

    @post("/rutifuerta/api/weeks")
    def weeks_save(self, **kw):
        def handler(env, req):
            b = req.body
            week_id = env["fuerta.week.plan"].save_week(b["name"], b["week"], b["minutes"], b.get("id"))
            return {"id": week_id, "weeks": env["fuerta.week.plan"].get_weeks()}
        return _api(handler)

    @post("/rutifuerta/api/weeks/remove")
    def weeks_remove(self, **kw):
        def handler(env, req):
            env["fuerta.week.plan"].delete_week(req.body["id"])
            return env["fuerta.week.plan"].get_weeks()
        return _api(handler)

    @post("/rutifuerta/api/bot/chat")
    def bot_chat(self, **kw):
        return _api(lambda env, req: coach.chat(env, req.body.get("history", []), req.body.get("message", "")))
