"""Copia local del catálogo (datos/ del módulo): exportarlo de una base y cargarlo en otra sin tirar de internet.

datos/catalogo.json  {"exportado": fecha, "heroes": [{campos del héroe, "abilities": [...], "chapters": [...],
                     "cosmetics": [...]}]}  (sin la imagen propia de los cosméticos ni los favoritos de nadie)
                     + "seasons": [temporadas con sus míticos (héroe por clave, aspecto por archivo de la wiki)]
datos/retratos/<clave>.png  retrato de cada héroe
Cargar actualiza por clave (héroes) y por (héroe, tipo, archivo de la wiki) (cosméticos), como el importador:
nunca borra; rehace habilidades y capítulos; no pisa la imagen propia de un cosmético."""
import base64
import json
from pathlib import Path

from odoo import fields

DATOS = Path(__file__).resolve().parent.parent / "datos"
HERO_FIELDS = ["key", "name", "wiki_name", "role", "subrole", "description", "location", "birthday", "age", "health",
               "armor", "shields", "portrait_url", "background_url", "story_summary", "story_video_url"]
ABILITY_FIELDS = ["sequence", "kind", "name", "description", "icon_url", "video_url", "video_webm_url", "thumbnail_url",
                  "stats"]
CHAPTER_FIELDS = ["sequence", "title", "content", "picture_url"]
COSMETIC_FIELDS = ["type", "sequence", "name", "rarity", "source", "media_kind", "media_url", "wiki_file"]
SEASON_FIELDS = ["key", "sequence", "arc", "year", "number", "subtitle", "date_start", "date_end", "dates_text", "theme",
                 "image_url", "new_heroes_text", "wiki_page"]
REWARD_FIELDS = ["sequence", "kind", "name", "hero_text", "media_url"]
ITEM_FIELDS = ["tier", "track", "section", "sequence", "kind", "rarity", "name", "hero_text", "media_url"]


def _vals(rec, campos):
    return {c: (rec[c].isoformat() if hasattr(rec[c], "isoformat") else rec[c]) if rec[c] is not False else None
            for c in campos}


def _exportar_temporadas(env):
    """Temporadas con los héroes por clave y cada mítico con la clave de su héroe y el archivo de su aspecto."""
    res = []
    for t in env["ow.season"].search([], order="sequence"):
        d = _vals(t, SEASON_FIELDS)
        d["heroes"] = t.new_hero_ids.mapped("key")
        d["rewards"] = [{**_vals(r, REWARD_FIELDS), "hero": r.hero_id.key or None,
                         "cosmetic": r.cosmetic_id.wiki_file or None} for r in t.reward_ids]
        d["items"] = [{**_vals(i, ITEM_FIELDS), "hero": i.hero_id.key or None,
                       "cosmetic": i.cosmetic_id.wiki_file or None} for i in t.item_ids]
        res.append(d)
    return res


def _cargar_temporadas(env, temporadas):
    """Crea o actualiza por `key` (como el importador; nunca borra temporadas, rehace sus míticos)."""
    Hero = env["ow.hero"].with_context(active_test=False)
    Season = env["ow.season"]
    for d in temporadas:
        vals = {k: (d.get(k) if d.get(k) is not None else False) for k in SEASON_FIELDS}
        vals["new_hero_ids"] = [(6, 0, Hero.search([("key", "in", d.get("heroes") or [])]).ids)]
        rec = Season.search([("key", "=", d["key"])], limit=1)
        if rec:
            rec.write(vals)
        else:
            rec = Season.create(vals)
        rec.reward_ids.unlink()
        lineas = []
        for r in d.get("rewards") or []:
            hero = Hero.search([("key", "=", r.get("hero"))], limit=1) if r.get("hero") else Hero
            cos = hero.cosmetic_ids.filtered(lambda c, f=r.get("cosmetic"): f and c.wiki_file == f)[:1]
            lineas.append((0, 0, {**{k: (r.get(k) if r.get(k) is not None else False) for k in REWARD_FIELDS},
                                  "hero_id": hero.id or False, "cosmetic_id": cos.id or False}))
        rec.reward_ids = lineas
        if "items" in d:
            rec.item_ids.unlink()
            filas = []
            for it in d["items"]:
                hero = Hero.search([("key", "=", it.get("hero"))], limit=1) if it.get("hero") else Hero
                cos = hero.cosmetic_ids.filtered(lambda c, f=it.get("cosmetic"): f and c.wiki_file == f)[:1]
                filas.append({**{k: (it.get(k) if it.get(k) is not None else False) for k in ITEM_FIELDS},
                              "season_id": rec.id, "hero_id": hero.id or False, "cosmetic_id": cos.id or False})
            env["ow.season.item"].create(filas)
    return len(temporadas)


def exportar(env, destino):
    """Escribe catalogo.json y retratos/ en `destino` (carpeta). Devuelve el número de héroes y cosméticos."""
    destino = Path(destino)
    (destino / "retratos").mkdir(parents=True, exist_ok=True)
    heroes, n_cos = [], 0
    for h in env["ow.hero"].with_context(active_test=False).search([], order="key"):
        d = _vals(h, HERO_FIELDS)
        d["active"] = h.active
        d["abilities"] = [_vals(a, ABILITY_FIELDS) for a in h.ability_ids]
        d["chapters"] = [_vals(c, CHAPTER_FIELDS) for c in h.chapter_ids]
        d["cosmetics"] = [_vals(c, COSMETIC_FIELDS) for c in h.cosmetic_ids]
        n_cos += len(d["cosmetics"])
        if h.portrait:
            (destino / "retratos" / f"{h.key}.png").write_bytes(h.portrait.content)
        heroes.append(d)
    data = {"exportado": fields.Datetime.now().isoformat(), "heroes": heroes, "seasons": _exportar_temporadas(env)}
    (destino / "catalogo.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(heroes), n_cos


def cargar(env, origen=DATOS):
    """Carga la copia de `origen` en la base. Devuelve estadísticas como el importador."""
    origen = Path(origen)
    data = json.loads((origen / "catalogo.json").read_text(encoding="utf-8"))
    Hero = env["ow.hero"].with_context(active_test=False)
    s = {"heroes_new": 0, "heroes_updated": 0, "portraits": 0, "cosmetics_new": 0, "cosmetics_updated": 0}
    limpio = lambda d, campos: {k: (d.get(k) if d.get(k) is not None else False) for k in campos}  # noqa: E731
    for d in data["heroes"]:
        vals = limpio(d, HERO_FIELDS)
        vals["active"] = d.get("active", True)
        hero = Hero.search([("key", "=", d["key"])], limit=1)
        if hero:
            hero.write(vals)
            s["heroes_updated"] += 1
        else:
            hero = Hero.create(vals)
            s["heroes_new"] += 1
        hero.ability_ids.unlink()
        hero.chapter_ids.unlink()
        hero.write({"ability_ids": [(0, 0, limpio(a, ABILITY_FIELDS)) for a in d["abilities"]],
                    "chapter_ids": [(0, 0, limpio(c, CHAPTER_FIELDS)) for c in d["chapters"]]})
        retrato = origen / "retratos" / f"{d['key']}.png"
        if not hero.portrait and retrato.exists():
            hero.portrait = base64.b64encode(retrato.read_bytes()).decode()
            s["portraits"] += 1
        existentes = {(c.type, c.wiki_file): c for c in hero.cosmetic_ids}
        nuevos = []
        for c in d["cosmetics"]:
            v = limpio(c, COSMETIC_FIELDS)
            actual = existentes.get((v["type"], v["wiki_file"]))
            if actual:
                actual.write(v)
                s["cosmetics_updated"] += 1
            else:
                nuevos.append({**v, "hero_id": hero.id})
        env["ow.cosmetic"].create(nuevos)
        s["cosmetics_new"] += len(nuevos)
    s["seasons"] = _cargar_temporadas(env, data.get("seasons") or [])
    return s
