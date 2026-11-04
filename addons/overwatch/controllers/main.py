"""Web /overwatch en el sitio web de Odoo: pantalla de selección de héroes (como la del juego) y ficha/galería de
cada héroe. Pública (decisión del usuario, 2026-11-03): cualquiera, también sin sesión, la ve; solo los usuarios con
el grupo overwatch.group_ow_user marcan favoritos (si no, no salen los botones). El backend queda para editar el
catálogo. Los datos van en un JSON dentro de la página."""
import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from markupsafe import Markup

from odoo import fields, http
from odoo.http import request

from ..models.cosmetic import RARITIES, TYPES
from ..models.hero import ROLES
from ..services import countdown

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


SLUGS = {"skin": "aspectos", "emote": "gestos", "victory_pose": "poses", "highlight_intro": "presentaciones", "spray": "grafitis"}  # pestañas de la galería (hero.js)


def _cosmetic_link(c):
    """Enlace a un cosmético en la galería de su héroe: abre la pestaña de su tipo con él seleccionado."""
    return f"/overwatch/heroe/{c.hero_id.key}#{SLUGS.get(c.type, 'aspectos')}/{c.id}" if c else ""


def _eventos(Event, pasados=0):
    """{estado: [evento]} con el estado exacto (los de Overwatch Countdown cambian a una hora, no al empezar el día),
    en el orden de su cuenta atrás: los activos por cuándo acaban, los próximos por cuándo empiezan."""
    vivos = Event.search([("state", "in", ["active", "upcoming", "unconfirmed"])])
    res = {k: vivos.filtered(lambda e, k=k: e.state == k) for k in ("active", "upcoming", "unconfirmed", "past")}
    if pasados:
        res["past"] = (res["past"] | Event.search([("state", "=", "past")], order="date_end desc", limit=pasados)) \
            .sorted(lambda e: fields.Datetime.to_datetime(e.end_at or e.date_end) or datetime.min, reverse=True)
    clave = {"active": lambda e: (e.end_at or fields.Datetime.to_datetime(e.date_end) or datetime.max),
             "upcoming": lambda e: (e.start_at or fields.Datetime.to_datetime(e.date_start) or datetime.max),
             "unconfirmed": lambda e: (e.date_start or date.min)}
    return {k: [_evento(e) for e in (v.sorted(clave[k]) if k in clave else v)] for k, v in res.items()}


def _evento(e):
    """Datos de un evento para las plantillas (fechas en español y días que faltan o quedan). Con hora exacta (Overwatch
    Countdown) lleva `cuenta_iso` y `cuenta_modo`: seasons.js pone la cuenta atrás al segundo, como en la wiki."""
    hoy = fields.Date.context_today(e)
    fmt = lambda d: f"{d.day} de {MESES_ES[d.month - 1]}" if d else "?"  # noqa: E731
    objetivo = e.start_at if e.state == "upcoming" else e.end_at if e.state == "active" else None
    if objetivo:
        resta = objetivo - fields.Datetime.now()
        horas = resta.seconds // 3600
        cuenta = ("empieza en " if e.state == "upcoming" else "acaba en ") + (
            f"{resta.days} d {horas} h" if resta.days else f"{horas} h {resta.seconds % 3600 // 60} min")
    elif e.state == "upcoming" and e.date_start:
        cuenta = (e.date_start - hoy).days
        cuenta = "empieza mañana" if cuenta == 1 else f"empieza en {cuenta} días"
    elif e.state == "active" and e.date_end:
        cuenta = (e.date_end - hoy).days
        cuenta = "acaba hoy" if cuenta == 0 else "acaba mañana" if cuenta == 1 else f"quedan {cuenta} días"
    else:
        cuenta = ""
    imagen = (f"/web/image/ow.event/{e.id}/image?unique={int(e.write_date.timestamp())}" if e.image
              else e.image_url or "")
    if e.start_at or e.end_at:  # con hora: en la de Madrid, como el resto del sitio
        local = lambda d: d.replace(tzinfo=timezone.utc).astimezone(MADRID) if d else None  # noqa: E731
        fmt_h = lambda d: f"{fmt(d)}, {d:%H:%M}" if d else "?"  # noqa: E731
        fechas = f"{fmt_h(local(e.start_at))} – {fmt_h(local(e.end_at))}"
    else:
        fechas = f"{fmt(e.date_start)} – {fmt(e.date_end)}"
    return {"rec": e, "imagen": imagen, "fechas": fechas, "cuenta": cuenta,
            "tipo": dict(e._fields["kind"].selection).get(e.kind), "season_key": e.season_id.key or "",
            "wiki": f"https://overwatch.weirdgloop.org/w/{e.wiki_page.replace(' ', '_')}" if e.wiki_page else "",
            "cuenta_iso": objetivo.isoformat() + "Z" if objetivo else "",
            "cuenta_modo": "start" if e.state == "upcoming" else "end",
            "etiquetas": e.tags or "", "descripcion": e.description or "", "fuente": e.source_url or "",
            "countdown": countdown.WEB if e.countdown_id else ""}


MADRID = ZoneInfo("Europe/Madrid")
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
            "noviembre", "diciembre"]


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
                           "video": a.video_url or "", "webm": a.video_webm_url or "", "thumb": a.thumbnail_url or "",
                           "stats": a.stats or []}
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

    @http.route("/overwatch/pases", type="http", auth="public", methods=["GET"], website=True)
    def seasons(self, **kw):
        """Todos los pases de batalla: el actual arriba, destacado, y debajo los anteriores (y la próxima temporada si
        la wiki ya la anuncia)."""
        env = request.env(context=dict(request.env.context, bin_size=True))
        temporadas = env["ow.season"].search([])
        actual = temporadas.current()

        def ficha(t):
            imagen = (f"/web/image/ow.season/{t.id}/image?unique={int(t.write_date.timestamp())}" if t.image
                      else t.image_url or "")
            return {
                "rec": t, "imagen": imagen,
                "heroes": [{"name": h.name, "key": h.key, "portrait": _portrait(h)} for h in t.new_hero_ids],
                "rewards": [{"name": r.name, "kind": r.kind, "kind_name": dict(r._fields["kind"].selection).get(r.kind),
                             "hero": r.hero_id.name or r.hero_text or "", "hero_key": r.hero_id.key or "",
                             "media": _cosmetic_media(r.cosmetic_id) if r.cosmetic_id else (r.media_url or "", "image"),
                             "link": _cosmetic_link(r.cosmetic_id)}
                            for r in t.reward_ids],
                "item_count": t.item_count,
            }
        ev = _eventos(env["ow.event"])
        return request.render("overwatch.seasons_page", {
            "v": VERSION, "data": _json_script({}),
            "eventos_activos": ev["active"], "eventos_proximos": ev["upcoming"], "eventos_sin_fechas": ev["unconfirmed"],
            "actual": ficha(actual) if actual else None,
            "proximas": [ficha(t) for t in temporadas if t.state == "upcoming"],
            "anteriores": [ficha(t) for t in temporadas if t.state == "past"],
            "is_manager": request.env.user.has_group("overwatch.group_ow_manager"),
        })

    @http.route("/overwatch/pases/<string:key>", type="http", auth="public", methods=["GET"], website=True)
    def season(self, key, **kw):
        """Todas las recompensas de un pase, nivel a nivel (gratis y prémium) y las de prestigio."""
        env = request.env(context=dict(request.env.context, bin_size=True))
        t = env["ow.season"].search([("key", "=", key)], limit=1)
        if not t:
            raise request.not_found()
        tipos = dict(t.item_ids._fields["kind"].selection)
        niveles, prestigio, caminos = {}, [], {}
        for it in t.item_ids:
            url, kind = _cosmetic_media(it.cosmetic_id) if it.cosmetic_id else (it.media_url or "", "image")
            d = {"name": it.name, "kind": it.kind, "kind_name": tipos.get(it.kind), "rarity": it.rarity or "",
                 "hero": it.hero_id.name or it.hero_text or "", "hero_key": it.hero_id.key or "",
                 "url": url, "media_kind": kind, "tier": it.tier, "link": _cosmetic_link(it.cosmetic_id)}
            if it.track == "prestige":
                prestigio.append(d)
            elif it.section:  # pase por caminos: cada camino con sus niveles
                caminos.setdefault(it.section, {}).setdefault(it.tier, {"free": [], "premium": []})[it.track].append(d)
            else:
                niveles.setdefault(it.tier, {"free": [], "premium": []})[it.track].append(d)
        hack = []
        for h in t.hack_ids:
            url, kind = _cosmetic_media(h.cosmetic_id) if h.cosmetic_id else (h.media_url or "", "image")
            hack.append({"name": h.name, "kind": "skin", "kind_name": tipos.get("skin"), "rarity": "legendary",
                         "hero": h.hero_id.name or h.hero_text or "", "hero_key": h.hero_id.key or "", "url": url,
                         "media_kind": kind, "tier": 0, "link": _cosmetic_link(h.cosmetic_id)})
        resumen = {}
        for it in t.item_ids:
            resumen[it.kind] = resumen.get(it.kind, 0) + 1
        return request.render("overwatch.season_page", {
            "v": VERSION, "data": _json_script({}), "t": t,
            "niveles": sorted(niveles.items()), "prestigio": prestigio, "hack": hack,
            "caminos": [(nombre, sorted(filas.items())) for nombre, filas in caminos.items()],
            "resumen": [(k, tipos.get(k), n) for k, n in sorted(resumen.items(), key=lambda x: -x[1])],
            "imagen": (f"/web/image/ow.season/{t.id}/image?unique={int(t.write_date.timestamp())}" if t.image
                       else t.image_url or ""),
            "is_manager": request.env.user.has_group("overwatch.group_ow_manager"),
        })

    @http.route("/overwatch/eventos", type="http", auth="public", methods=["GET"], website=True)
    def events(self, **kw):
        """Eventos y colaboraciones: activos, por empezar y los terminados de las temporadas recientes."""
        ev = _eventos(request.env(context=dict(request.env.context, bin_size=True))["ow.event"], pasados=40)
        return request.render("overwatch.events_page", {
            "v": VERSION, "data": _json_script({}),
            "activos": ev["active"], "proximos": ev["upcoming"], "sin_fechas": ev["unconfirmed"], "pasados": ev["past"],
            "is_manager": request.env.user.has_group("overwatch.group_ow_manager"),
        })

    @http.route("/overwatch/novedades", type="http", auth="public", methods=["GET"], website=True)
    def changes(self, **kw):
        """Lo que ha cambiado en cada búsqueda de actualizaciones (las últimas 300), agrupado por búsqueda."""
        cambios = request.env["ow.change"].search([], limit=300)
        tipos = dict(cambios._fields["kind"].selection)
        grupos = []
        for c in cambios:
            if not grupos or grupos[-1]["batch"] != c.batch:
                hora = fields.Datetime.context_timestamp(c.with_context(tz="Europe/Madrid"), c.create_date)
                grupos.append({"batch": c.batch, "fecha": hora.strftime("%d/%m/%Y %H:%M"), "items": []})
            grupos[-1]["items"].append({
                "kind": c.kind, "kind_name": tipos.get(c.kind), "what": c.what, "old": c.old_value or "",
                "new": c.new_value or "", "hero": c.hero_id.name or "", "hero_key": c.hero_id.key or "",
                "season_key": c.season_id.key or ""})
        return request.render("overwatch.changes_page", {
            "v": VERSION, "data": _json_script({}), "grupos": grupos,
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
