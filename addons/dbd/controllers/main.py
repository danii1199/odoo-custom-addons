"""Portal web de Dead by Daylight (/dbd): páginas del sitio web de Odoo, públicas y de solo lectura.
Los visitantes sin sesión leen el catálogo gracias al permiso de lectura de `base.group_public` (security/ir.access.csv)."""
import json
from pathlib import Path
from urllib.parse import quote

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "src"
# Odoo cachea los estáticos una semana: la versión (fecha del archivo más nuevo) fuerza a recargarlos tras cambiarlos.
VERSION = str(int(max(p.stat().st_mtime for p in STATIC_DIR.rglob("*") if p.is_file())))


def page(path, **kw):
    return http.route(path, type="http", auth="public", methods=["GET"], website=True, **kw)


def _img(rec, field="image"):
    """URL de la imagen o None. Leer con bin_size=True da el tamaño en vez del contenido (no carga los binarios)."""
    return f"/web/image/{rec._name}/{rec.id}/{field}" if rec[field] else None


def _json(data, status=200):
    return request.make_json_response(data, status=status)


def _can_save():
    """Pueden tener builds: los usuarios internos con el grupo del módulo y los de portal (invitados: el registro
    libre está cerrado porque Odoo está abierto a internet)."""
    user = request.env.user
    return user.has_group("dbd.group_dbd_user") or user.has_group("base.group_portal")


def _post_json(handler):
    """POST con cuerpo JSON (sin token CSRF: un formulario de otra web no puede mandar JSON sin permiso del navegador)."""
    hr = request.httprequest
    if hr.mimetype != "application/json":
        return _json({"error": "Se esperaba JSON"}, 415)
    if not _can_save():
        return _json({"error": "No tienes acceso a las builds"}, 403)
    try:
        return _json(handler(json.loads(hr.get_data() or b"{}")))
    except (ValidationError, AccessError, ValueError, TypeError, KeyError) as e:
        request.env.cr.rollback()
        return _json({"error": str(e.args[0] if getattr(e, "args", None) else e)}, 400)


def catalog(env):
    """Todo lo que necesitan el editor de builds y la ruleta, en una sola respuesta."""
    env = env(context=dict(env.context, bin_size=True))
    survivors, killers = env["dbd.survivor"].search([]), env["dbd.killer"].search([])
    return {
        "survivors": [{"id": c.id, "name": c.name, "img": _img(c)} for c in survivors],
        "killers": [{"id": c.id, "name": c.name, "img": _img(c), "power": c.power_name or "",
                     "powerImg": _img(c, "power_image")} for c in killers],
        "perks": [{"id": p.id, "name": p.name, "role": p.role, "img": _img(p), "owner": p.owner_name,
                   "ownerId": (p.survivor_id or p.killer_id).id or None, "desc": p.description or "",
                   "tags": p.tag_ids.mapped("name")} for p in env["dbd.perk"].search([])],
        "items": [{"id": i.id, "name": i.name, "type": i.item_type, "rarity": i.rarity, "img": _img(i),
                   "event": bool(i.event), "desc": i.description or ""} for i in env["dbd.item"].search([])],
        "addons": [{"id": a.id, "name": a.name, "role": a.role, "type": a.item_type or None,
                    "killer": a.killer_id.id or None, "rarity": a.rarity, "img": _img(a), "desc": a.description or ""}
                   for a in env["dbd.addon"].search([])],
        "offerings": [{"id": o.id, "name": o.name, "role": o.role, "rarity": o.rarity, "img": _img(o),
                       "desc": o.description or ""} for o in env["dbd.offering"].search([])],
        "rarities": dict(env["dbd.addon"]._fields["rarity"].selection),
        "itemTypes": dict(env["dbd.item"]._fields["item_type"].selection),
    }


class DbdWeb(http.Controller):

    def _render(self, template, section, **values):
        return request.render(template, {"v": VERSION, "section": section, **values})

    @page("/dbd")
    def home(self, **kw):
        env = request.env
        counts = {
            "survivors": env["dbd.survivor"].search_count([]),
            "killers": env["dbd.killer"].search_count([]),
            "perks": env["dbd.perk"].search_count([]),
            "addons": env["dbd.addon"].search_count([]),
            "offerings": env["dbd.offering"].search_count([]),
            "maps": env["dbd.map"].search_count([]),
        }
        return self._render("dbd.home_page", "home", counts=counts)

    # ---------- personajes ----------
    @page("/dbd/supervivientes")
    def survivors(self, **kw):
        return self._render("dbd.characters_page", "survivors", characters=request.env["dbd.survivor"].search([]),
                            title="Supervivientes", base_url="/dbd/supervivientes", model="dbd.survivor")

    @page("/dbd/supervivientes/<model('dbd.survivor'):survivor>")
    def survivor(self, survivor, **kw):
        return self._render("dbd.character_page", "survivors", character=survivor, killer=False,
                            back_url="/dbd/supervivientes", back_title="Supervivientes", model="dbd.survivor")

    @page("/dbd/asesinos")
    def killers(self, **kw):
        return self._render("dbd.characters_page", "killers", characters=request.env["dbd.killer"].search([]),
                            title="Asesinos", base_url="/dbd/asesinos", model="dbd.killer")

    @page("/dbd/asesinos/<model('dbd.killer'):killer>")
    def killer(self, killer, **kw):
        return self._render("dbd.character_page", "killers", character=killer, killer=True,
                            back_url="/dbd/asesinos", back_title="Asesinos", model="dbd.killer")

    # ---------- catálogos ----------
    @page("/dbd/perks")
    def perks(self, **kw):
        perks = request.env["dbd.perk"].search([])
        return self._render("dbd.perks_page", "perks", perks=perks, tags=perks.tag_ids.sorted("name"))

    @page("/dbd/complementos")
    def addons(self, **kw):
        addons = request.env["dbd.addon"].search([])
        return self._render("dbd.addons_page", "addons", addons=addons, killers=addons.killer_id,
                            rarities=request.env["dbd.addon"]._fields["rarity"].selection,
                            item_types=request.env["dbd.addon"]._fields["item_type"].selection)

    @page("/dbd/ofrendas")
    def offerings(self, **kw):
        model = request.env["dbd.offering"]
        return self._render("dbd.offerings_page", "offerings", offerings=model.search([]),
                            rarities=model._fields["rarity"].selection, categories=model._fields["category"].selection)

    @page("/dbd/mapas")
    def maps(self, **kw):
        return self._render("dbd.maps_page", "maps", realms=request.env["dbd.realm"].search([]))

    # ---------- builds ----------
    def _build_values(self):
        user = request.env.user
        return {"logged": not user._is_public(), "can_save": _can_save()}

    @page("/dbd/build")
    def build(self, **kw):
        # Crear builds exige sesión: al login y de vuelta aquí con los mismos parámetros
        if request.env.user._is_public():
            return request.redirect("/web/login?redirect=" + quote(request.httprequest.full_path.rstrip("?"), safe=""))
        return self._render("dbd.build_page", "build", **self._build_values())

    @page("/dbd/aleatoria")
    def random_build(self, **kw):
        return self._render("dbd.random_page", "random", **self._build_values())

    @page("/dbd/builds")
    def builds(self, **kw):
        return self._render("dbd.builds_page", "builds", **self._build_values())

    @page("/dbd/builds/ver")
    def build_view(self, **kw):
        return self._render("dbd.build_view_page", "builds", **self._build_values())

    @http.route("/dbd/api/catalogo", type="http", auth="public", methods=["GET"])
    def api_catalog(self, **kw):
        return _json(catalog(request.env))

    @http.route("/dbd/api/builds", type="http", auth="user", methods=["GET"])
    def api_builds(self, **kw):
        if not _can_save():
            return _json({"error": "No tienes acceso a las builds"}, 403)
        builds = request.env["dbd.build"].search([("user_id", "=", request.env.uid)])
        return _json([b.to_web() for b in builds])

    @http.route("/dbd/api/builds/publicas", type="http", auth="public", methods=["GET"])
    def api_public_builds(self, **kw):
        domain = [("is_public", "=", True)]
        if kw.get("role") in ("survivor", "killer"):
            domain.append(("role", "=", kw["role"]))
        builds = request.env["dbd.build"].search(domain, limit=300)
        return _json([b.to_web() for b in builds])

    @http.route("/dbd/api/builds/<int:build_id>", type="http", auth="public", methods=["GET"])
    def api_build(self, build_id, **kw):
        # search aplica los permisos: públicas para todos, privadas solo para su autor
        build = request.env["dbd.build"].search([("id", "=", build_id)])
        if not build:
            return _json({"error": "Esa build no existe o es privada"}, 404)
        return _json(build.to_web())

    @http.route("/dbd/api/builds/guardar", type="http", auth="user", methods=["POST"], csrf=False)
    def api_build_save(self, **kw):
        return _post_json(lambda data: request.env["dbd.build"].save_from_web(data).to_web())

    @http.route("/dbd/api/builds/borrar", type="http", auth="user", methods=["POST"], csrf=False)
    def api_build_delete(self, **kw):
        def handler(data):
            request.env["dbd.build"].search([("id", "=", int(data.get("id"))), ("user_id", "=", request.env.uid)]).unlink()
            return {"ok": True}
        return _post_json(handler)

    @http.route("/dbd/api/aleatoria/prefs", type="http", auth="user", methods=["GET"])
    def api_random_prefs(self, **kw):
        if not _can_save():
            return _json({"survivors": [], "killers": []})
        return _json(request.env["dbd.random.pref"].get_for_web())

    @http.route("/dbd/api/aleatoria/prefs/guardar", type="http", auth="user", methods=["POST"], csrf=False)
    def api_random_prefs_save(self, **kw):
        return _post_json(lambda data: request.env["dbd.random.pref"].save_from_web(data))
