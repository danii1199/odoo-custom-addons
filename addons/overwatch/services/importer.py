"""Importa o actualiza el catálogo: héroes de OverFast API (en español) y cosméticos de la wiki de Overwatch.

- Héroes: por `key`. Se actualizan sus datos y se rehacen sus habilidades y capítulos (vienen completos de la API).
  El retrato se descarga si falta (o siempre con `reload_images`). Nunca se borran héroes: los que ya no salen se
  dejan como están.
- Cosméticos: por (héroe, tipo, archivo de la wiki). Los nuevos se crean y los existentes se actualizan (rareza,
  origen, URL), sin tocar la imagen propia si la hay. Nunca se borran.
Gratis y sin claves. User-Agent honesto; sin saltarse ninguna protección."""
import base64
import logging
import time

import requests

from . import wiki

_logger = logging.getLogger(__name__)

OVERFAST = "https://overfast-api.tekrop.fr"
LOCALE = "es-es"
USER_AGENT = "Odoo-overwatch/1.0 (modulo personal de Odoo)"
# Nombre en la wiki cuando no coincide con el de OverFast (en inglés)
WIKI_NAMES = {"soldier-76": "Soldier: 76", "jetpack-cat": "Jetpack Cat"}


class Importer:
    def __init__(self, env, reload_images=False, cosmetics=True, heroes=None, log=None):
        self.env = env
        self.reload_images = reload_images
        self.cosmetics = cosmetics
        self.only = set(heroes or [])
        self.log = log or _logger.info
        self.http = requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT
        self.stats = {"heroes_new": 0, "heroes_updated": 0, "portraits": 0,
                      "cosmetics_new": 0, "cosmetics_updated": 0, "cosmetics_no_media": 0, "errors": []}

    def _get(self, path, **params):
        for intento in range(3):
            r = self.http.get(f"{OVERFAST}{path}", params=params, timeout=30)
            if r.status_code == 429:  # límite de peticiones: esperar lo que diga
                time.sleep(min(int(r.headers.get("Retry-After", 5)), 30))
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    def _download(self, url):
        r = self.http.get(url, timeout=30)
        r.raise_for_status()
        return base64.b64encode(r.content).decode()  # Odoo 20: str base64 o BinaryValue, no bytes

    # ------------------------------------------------------------------ héroes

    def run(self):
        lista_es = self._get("/heroes", locale=LOCALE)
        nombres_en = {h["key"]: h["name"] for h in self._get("/heroes")}
        Hero = self.env["ow.hero"].with_context(active_test=False)
        sesion_wiki = wiki.nueva_sesion() if self.cosmetics else None
        for resumen in lista_es:
            key = resumen["key"]
            if self.only and key not in self.only:
                continue
            try:
                with self.env.cr.savepoint():  # si falla, no queda el héroe a medias
                    hero = self._import_hero(Hero, key, resumen, nombres_en.get(key, resumen["name"]))
                    if sesion_wiki:
                        self._import_cosmetics(sesion_wiki, hero)
                if self.env.context.get("ow_commit"):
                    self.env.cr.commit()
            except Exception as e:  # un héroe que falle no para el resto
                _logger.exception("Error importando %s", key)
                self.stats["errors"].append(f"{key}: {e}")
        return self.stats

    @staticmethod
    def _fondo(fondos):
        """El fondo de tamaño medio (md/lg): pesa mucho menos que el de 2600 px y basta para pantalla completa."""
        medio = next((f for f in fondos if "md" in (f.get("sizes") or [])), None)
        return (medio or (fondos[-1] if fondos else {})).get("url") or False

    def _import_hero(self, Hero, key, resumen, nombre_en):
        d = self._get(f"/heroes/{key}", locale=LOCALE)
        hp = d.get("hitpoints") or {}
        story = d.get("story") or {}
        fondos = d.get("backgrounds") or []
        vals = {
            "key": key,
            "name": d.get("name") or resumen["name"],
            "role": d.get("role") or resumen["role"],
            "subrole": d.get("subrole") or resumen.get("subrole"),
            "description": d.get("description"),
            "location": d.get("location"),
            "birthday": d.get("birthday"),
            "age": d.get("age") or 0,
            "health": hp.get("health") or 0,
            "armor": hp.get("armor") or 0,
            "shields": hp.get("shields") or 0,
            "portrait_url": d.get("portrait") or resumen.get("portrait"),
            "background_url": self._fondo(fondos),
            "story_summary": story.get("summary"),
            "story_video_url": ((story.get("media") or {}).get("link")) or False,
        }
        habilidades = []
        for i, a in enumerate(d.get("abilities") or []):
            video = a.get("video") or {}
            link = video.get("link") or {}
            habilidades.append({"sequence": i, "kind": "ability", "name": a.get("name") or "?",
                                "description": a.get("description"), "icon_url": a.get("icon"),
                                "video_url": link.get("mp4"), "video_webm_url": link.get("webm"),
                                "thumbnail_url": video.get("thumbnail")})
        perks = d.get("perks") or {}
        for kind, clave in (("perk_minor", "minor"), ("perk_major", "major")):
            for i, p in enumerate(perks.get(clave) or []):
                habilidades.append({"sequence": i, "kind": kind, "name": p.get("name") or "?",
                                    "description": p.get("description"), "icon_url": p.get("icon")})
        capitulos = [{"sequence": i, "title": c.get("title") or "", "content": c.get("content"),
                      "picture_url": c.get("picture")} for i, c in enumerate(story.get("chapters") or [])]

        hero = Hero.search([("key", "=", key)], limit=1)
        if hero:
            vals.pop("key")
            hero.write(vals)
            self.stats["heroes_updated"] += 1
        else:
            vals["wiki_name"] = WIKI_NAMES.get(key, nombre_en)
            hero = Hero.create(vals)
            self.stats["heroes_new"] += 1
        hero.ability_ids.unlink()
        hero.chapter_ids.unlink()
        hero.write({"ability_ids": [(0, 0, v) for v in habilidades],
                    "chapter_ids": [(0, 0, v) for v in capitulos]})
        if vals.get("portrait_url") and (self.reload_images or not hero.portrait):
            try:
                hero.portrait = self._download(vals["portrait_url"])
                self.stats["portraits"] += 1
            except requests.RequestException as e:
                self.stats["errors"].append(f"retrato de {key}: {e}")
        self.log(f"Héroe {hero.name}: {len(habilidades)} habilidades, {len(capitulos)} capítulos")
        return hero

    # ------------------------------------------------------------------ cosméticos

    def _import_cosmetics(self, sesion, hero):
        nombre = hero.wiki_name or hero.name
        por_tipo = wiki.cosmeticos_heroe(sesion, nombre)
        if not por_tipo:
            self.log(f"  {hero.name}: sin cosméticos en la wiki (¿nombre «{nombre}»?)")
            return
        urls = wiki.urls_archivos(sesion, [i["file"] for items in por_tipo.values() for i in items])
        Cosmetic = self.env["ow.cosmetic"]
        existentes = {(c.type, c.wiki_file): c for c in hero.cosmetic_ids}
        nuevos, vistos = [], set()
        for tipo, items in por_tipo.items():
            for orden, it in enumerate(items):
                if (tipo, it["file"]) in vistos:  # la wiki a veces repite una celda
                    continue
                vistos.add((tipo, it["file"]))
                vals = {"name": it["name"], "rarity": it["rarity"], "source": it["source"] or False,
                        "media_kind": it["kind"], "sequence": orden}
                url = urls.get(it["file"])
                if url:
                    vals["media_url"] = url
                else:
                    self.stats["cosmetics_no_media"] += 1
                actual = existentes.get((tipo, it["file"]))
                if actual:
                    actual.write(vals)
                    self.stats["cosmetics_updated"] += 1
                else:
                    nuevos.append({**vals, "hero_id": hero.id, "type": tipo, "wiki_file": it["file"]})
        Cosmetic.create(nuevos)
        self.stats["cosmetics_new"] += len(nuevos)
        self.log(f"  {hero.name}: {sum(len(v) for v in por_tipo.values())} cosméticos ({len(nuevos)} nuevos)")
