"""Web /overwatch en el sitio web de Odoo: pantalla de selección de héroes (como la del juego) y ficha/galería de
cada héroe. Pública (decisión del usuario, 2026-11-03): cualquiera, también sin sesión, la ve; solo los usuarios con
el grupo overwatch.group_ow_user marcan favoritos (si no, no salen los botones). El backend queda para editar el
catálogo. Los datos van en un JSON dentro de la página."""
import json
from pathlib import Path

from markupsafe import Markup

from odoo import http
from odoo.http import request

from ..models.cosmetic import RARITIES, TYPES
from ..models.hero import ROLES

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "src"
# Odoo cachea los estáticos una semana: la versión (fecha del archivo más nuevo) fuerza a recargarlos tras cambiarlos.
VERSION = str(int(max(p.stat().st_mtime for p in STATIC_DIR.rglob("*") if p.is_file())))
GROUP = "overwatch.group_ow_user"


def _json_script(data):
    """JSON seguro dentro de <script type="application/json"> (sin «</script>» que lo corte)."""
    return Markup(json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


def _portrait(hero):
    if hero.portrait:
        return f"/web/image/ow.hero/{hero.id}/portrait?unique={int(hero.write_date.timestamp())}"
    return hero.portrait_url or ""


def _cosmetic_media(c):
    if c.image:
        return f"/web/image/ow.cosmetic/{c.id}/image?unique={int(c.write_date.timestamp())}", "image"
    return c.media_url or "", c.media_kind


class OverwatchWeb(http.Controller):

    def _can_fav(self):
        return request.env.user.has_group(GROUP)

    def _fav_ids(self):
        if not self._can_fav():
            return set()
        pref = request.env["ow.pref"].search([("user_id", "=", request.env.uid)], limit=1)
        return set(pref.favorite_ids.ids)

    @http.route("/overwatch", type="http", auth="public", methods=["GET"], website=True)
    def select(self, **kw):
        env = request.env(context=dict(request.env.context, bin_size=True))
        favs = self._fav_ids()
        heroes = env["ow.hero"].search([])
        data = {
            "can_fav": self._can_fav(),
            "roles": [{"key": k, "name": n} for k, n in ROLES],
            "heroes": [{
                "id": h.id, "key": h.key, "name": h.name, "role": h.role, "subrole": h.subrole_name or "",
                "description": h.description or "", "health": h.health, "armor": h.armor, "shields": h.shields,
                "portrait": _portrait(h), "background": h.background_url or "", "fav": h.id in favs,
                "abilities": [{"name": a.name, "icon": a.icon_url or ""} for a in h.ability_ids if a.kind == "ability"],
            } for h in heroes],
        }
        return request.render("overwatch.select_page", {
            "v": VERSION, "data": _json_script(data), "can_fav": data["can_fav"], "is_manager": request.env.user.has_group("overwatch.group_ow_manager"),
        })

    @http.route("/overwatch/heroe/<string:key>", type="http", auth="public", methods=["GET"], website=True)
    def hero(self, key, **kw):
        env = request.env(context=dict(request.env.context, bin_size=True))
        hero = env["ow.hero"].search([("key", "=", key)], limit=1)
        if not hero:
            raise request.not_found()
        cosmetics = {}
        for c in hero.cosmetic_ids:
            url, kind = _cosmetic_media(c)
            cosmetics.setdefault(c.type, []).append({
                "id": c.id, "name": c.name, "rarity": c.rarity, "source": c.source or "", "url": url, "kind": kind})
        data = {
            "can_fav": self._can_fav(),
            "hero": {"id": hero.id, "key": hero.key, "name": hero.name, "fav": hero.id in self._fav_ids()},
            "abilities": [{"name": a.name, "kind": a.kind, "description": a.description or "", "icon": a.icon_url or "",
                           "video": a.video_url or "", "webm": a.video_webm_url or "", "thumb": a.thumbnail_url or ""}
                          for a in hero.ability_ids],
            "types": [{"key": k, "name": n} for k, n in TYPES],
            "rarities": [{"key": k, "name": n} for k, n in RARITIES],
            "cosmetics": cosmetics,
        }
        return request.render("overwatch.hero_page", {
            "v": VERSION, "hero": hero, "portrait": _portrait(hero), "data": _json_script(data),
            "role_name": dict(ROLES).get(hero.role), "types": TYPES,
            "counts": {k: len(cosmetics.get(k, [])) for k, _n in TYPES}, "can_fav": data["can_fav"],
            "is_manager": request.env.user.has_group("overwatch.group_ow_manager"),
        })

    @http.route("/overwatch/api/favorito", type="http", auth="user", methods=["POST"], csrf=False)
    def favorite(self, **kw):
        """Marca/desmarca un favorito. POST con cuerpo JSON {hero_id, fav} (sin token CSRF: un formulario de otra web
        no puede mandar JSON sin permiso del navegador)."""
        hr = request.httprequest
        if hr.mimetype != "application/json":
            return request.make_json_response({"error": "Se esperaba JSON"}, status=415)
        if not request.env.user.has_group(GROUP):
            return request.make_json_response({"error": "Sin acceso"}, status=403)
        try:
            body = json.loads(hr.get_data() or b"{}")
            hero = request.env["ow.hero"].browse(int(body["hero_id"])).exists()
        except (ValueError, KeyError, TypeError):
            return request.make_json_response({"error": "Petición incorrecta"}, status=400)
        if not hero:
            return request.make_json_response({"error": "No existe ese héroe"}, status=404)
        pref = request.env["ow.pref"].mine()
        pref.favorite_ids = [(4 if body.get("fav") else 3, hero.id)]
        return request.make_json_response({"favorites": pref.favorite_ids.ids})
