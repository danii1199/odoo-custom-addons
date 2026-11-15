"""Web /solicitudes-ig (página del sitio), sus archivos (/solicitudes-ig/web/*) y su API JSON. Para quien no tenga el
grupo, nada de esto existe: 404, igual que una dirección inventada (como en rutifuerta). Por eso los archivos no van en
static/, que Odoo sirve a cualquiera."""
import json
import mimetypes
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from odoo import fields, http
from odoo.http import request
from werkzeug.exceptions import NotFound

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
VERSION = str(int(max(p.stat().st_mtime for p in WEB_DIR.rglob("*") if p.is_file())))
GROUP = "solicitudes_ig.group_ig_user"
MADRID = ZoneInfo("Europe/Madrid")
MAX_BYTES = 30 * 1024 * 1024


def _allowed():
    return request.env.user.has_group(GROUP)


def _estado(env):
    Sol = env["ig.solicitud"]
    mias = Sol.search([("user_id", "=", env.uid)])
    inicio = datetime.combine(datetime.now(MADRID).date(), time.min, MADRID).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return {
        "items": [{"id": s.id, "username": s.username, "url": s.url, "state": s.state} for s in mias],
        "hoy": len(mias.filtered(lambda s: s.state == "hecha" and s.done_at and s.done_at >= inicio)),
    }


class SolicitudesWeb(http.Controller):

    @http.route("/solicitudes-ig", type="http", auth="public", methods=["GET"], website=True)
    def index(self, **kw):
        if not _allowed():
            raise NotFound()
        return request.render("solicitudes_ig.app_page", {"v": VERSION})

    @http.route("/solicitudes-ig/web/<path:ruta>", type="http", auth="public", methods=["GET"], website=True)
    def archivo(self, ruta, **kw):
        f = (WEB_DIR / ruta).resolve()
        if not _allowed() or not f.is_relative_to(WEB_DIR) or not f.is_file():
            raise NotFound()
        tipo = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        return request.make_response(f.read_bytes(), [("Content-Type", tipo), ("Cache-Control", "private, max-age=604800")])

    @http.route("/solicitudes-ig/api/<string:accion>", type="http", auth="public", methods=["GET", "POST"],
                csrf=False, website=True)
    def api(self, accion, **kw):
        """estado (GET); importar {contenido, completa} y marcar {ids, state} (POST JSON: un formulario de otra web no
        puede mandar JSON sin permiso del navegador, por eso no llevan token CSRF)."""
        if not _allowed():
            raise NotFound()
        hr = request.httprequest
        env = request.env
        if accion == "estado" and hr.method == "GET":
            return request.make_json_response(_estado(env))
        if hr.method != "POST" or accion not in ("importar", "marcar"):
            raise NotFound()
        if hr.mimetype != "application/json":
            return request.make_json_response({"error": "Se esperaba JSON"}, status=415)
        if (hr.content_length or 0) > MAX_BYTES:
            return request.make_json_response({"error": "Archivo demasiado grande"}, status=413)
        try:
            body = json.loads(hr.get_data() or b"{}")
            if accion == "importar":
                stats = env["ig.solicitud"].importar(str(body["contenido"]), completa=bool(body.get("completa", True)))
                return request.make_json_response({**_estado(env), "stats": stats})
            state = body["state"]
            if state not in ("pendiente", "abierta", "hecha"):
                raise ValueError(state)
            ids = [int(i) for i in body["ids"]][:200]
        except (ValueError, KeyError, TypeError):
            return request.make_json_response({"error": "Petición no válida"}, status=400)
        env["ig.solicitud"].search([("id", "in", ids), ("user_id", "=", env.uid)]).marcar(state)
        return request.make_json_response(_estado(env))
