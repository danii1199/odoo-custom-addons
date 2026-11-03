"""Importa el catálogo de Dead by Daylight desde fuentes públicas y gratuitas:

- Datos: API de dbd.tricky.lol (`/api/characters`, `perks`, `addons`, `items`, `offerings`, `maps`, `dlc`).
  Solo la API: el resto de la web tiene protección anti-bots y no se toca.
- Imágenes: wiki oficial de la comunidad (deadbydaylight.wiki.gg, API de MediaWiki). Primero por el nombre del
  archivo del juego (`iconPerks_adrenaline` → `File:IconPerks_adrenaline.png`) y, si no está, la imagen principal de
  la página del elemento (p. ej. la página «Coal Tower»). La antigua wiki de Fandom bloquea las descargas que no
  vienen de un navegador: no usarla.

Cada registro guarda su clave externa (`dbd_key`): volver a importar actualiza en vez de duplicar. Los registros que
aún no la tienen (los datos de ejemplo o los creados a mano) se emparejan por nombre. Nunca borra nada.
"""
import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

_logger = logging.getLogger(__name__)

API = "https://dbd.tricky.lol/api/"
WIKI_API = "https://deadbydaylight.wiki.gg/api.php"
HEADERS = {"User-Agent": "proyectos-dbd/1.0 (modulo de Odoo de uso personal)"}
TIMEOUT = 60

RARITY = {"common": "common", "uncommon": "uncommon", "rare": "rare", "veryrare": "very_rare",
          "visceral": "ultra_rare", "none": "common"}
DIFFICULTY = {"easy": "easy", "intermediate": "intermediate", "hard": "hard", "veryhard": "very_hard"}
ITEM_TYPE = {"toolbox": "toolbox", "medkit": "medkit", "flashlight": "flashlight", "key": "key", "map": "map",
             "fogvial": "fog_vial", "firecracker": "firecracker"}
OFFERING_CATEGORY = {"points": "bloodpoints", "world": "realm", "luck": "luck", "atmosphere": "fog", "lighting": "fog",
                     "chest": "chest", "hook": "hook", "killing": "mori", "position": "shroud"}
# Categorías de perks de la API → etiquetas en español
PERK_CATEGORIES = {
    "adaptation": "Adaptación", "chasing": "Persecución", "concealment": "Ocultación", "cruelty": "Crueldad",
    "enhancement": "Mejora", "hinderance": "Entorpecimiento", "navigation": "Navegación", "obstruction": "Obstrucción",
    "perception": "Percepción", "safeguard": "Protección", "strategy": "Estrategia", "support": "Apoyo",
    "tracking": "Rastreo", "trickery": "Engaño",
}
ROMAN = {2: "II", 3: "III", 4: "IV", 5: "V"}
# Marcadores de botón de las descripciones ({Input.ActivatableButton1}…)
INPUTS = {"ActivatableButton1": "botón de habilidad activa", "ActivatableButton2": "botón de habilidad activa secundaria",
          "UseItem": "botón de usar objeto"}


# ---------------------------------------------------------------- utilidades

def _get_json(session, endpoint):
    resp = session.get(API + endpoint, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _clean(text):
    return (text or "").replace("\xa0", " ").strip()


def _valid_name(name):
    """La API trae algunos textos sin traducir del juego («@#Addon_..._NAME»)."""
    return bool(name) and not name.startswith("@#")


def _straight(name):
    """Comillas tipográficas → rectas (los títulos de la wiki usan las rectas)."""
    return re.sub(r"[’‘`´]", "'", name or "").replace("“", '"').replace("”", '"')


def _norm(name):
    """Nombre comparable: sin mayúsculas ni comillas tipográficas («We’ll» = «We'll»)."""
    return " ".join(_straight(name).split()).casefold()


def _split_camel(word):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", word)


def _number(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _input_name(placeholder):
    """{Input.ActivatableButton1} → «botón de habilidad activa»; los desconocidos, en palabras y sin el número."""
    key = placeholder.split(".")[-1]
    return INPUTS.get(key) or _split_camel(re.sub(r"\d+$", "", key))


def perk_description(perk):
    """Sustituye los marcadores de la API: {Tunable.X.Clave} → valores por nivel (I/II/III),
    {Keyword.Haste} → <b>Haste</b>, {Input.X} → <i>X</i>."""
    tunables = {k.lower(): v for k, v in (perk.get("tunables") or {}).items()}

    def repl(match):
        kind, rest = match.group(1), match.group(2)
        if kind == "Tunable":
            values = tunables.get(rest.split(".")[-1].lower())
            return f"<b>{'/'.join(_number(v) for v in values)}</b>" if values else "?"
        if kind == "Keyword":
            return f"<b>{_split_camel(rest[:1].upper() + rest[1:])}</b>"
        return f"<i>{_input_name(rest)}</i>"

    return re.sub(r"\{(Tunable|Keyword|Input)\.([^}]+)\}", repl, perk.get("description") or "")


def _image_titles(path):
    """Ruta de la API → nombres posibles del archivo en la wiki: '/Game/.../iconPerks_x' → ['File:IconPerks_x.png'].
    Los mapas acaban en el número de variante (iconMap_Ind_CoalTower1): se prueba también sin él."""
    if not path:
        return []
    base = path.rsplit("/", 1)[-1]
    base = base[:-4] if base.lower().endswith(".png") else base
    base = base.removeprefix("T_UI_")
    names = [base, re.sub(r"\d+$", "", base)]
    return list(dict.fromkeys(f"File:{n[:1].upper()}{n[1:]}.png" for n in names if n))


def _wiki_name_title(prefix, name):
    """Nombre del archivo que la wiki suele usar cuando no coincide con el del juego: prefijo + nombre en camelCase,
    respetando los guiones ('High-end Sapphire lens' → 'File:IconAddon_high-EndSapphireLens.png')."""
    words = re.sub(r"[^A-Za-z0-9\- ]", "", _straight(name)).split()
    if not words:
        return None
    camel = "".join(w if i == 0 else w[:1].upper() + w[1:] for i, w in enumerate(words))
    camel = re.sub(r"-([a-z])", lambda m: "-" + m.group(1).upper(), camel)
    return f"File:{prefix}{camel[:1].lower()}{camel[1:]}.png"


# ---------------------------------------------------------------- importador

class Importer:

    def __init__(self, env, log=None):
        self.env = env
        self.log = log or _logger.info
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.stats = {}
        self.images = []  # (registro, campo, [títulos de archivo], título de página)

    # ---------- genérico ----------
    def _upsert(self, model, key, vals, match=None):
        """Actualiza el registro con esa clave externa; si no hay, el que encaje con `match` y aún no tenga clave;
        si tampoco, lo crea."""
        Model = self.env[model].with_context(active_test=False)
        rec = Model.search([("dbd_key", "=", key)], limit=1)
        if not rec and match:
            # Mismo nombre sin tener en cuenta mayúsculas ni comillas tipográficas, y las demás condiciones exactas
            others = [cond for cond in match if cond[0] != "name"]
            name = next((cond[2] for cond in match if cond[0] == "name"), None)
            rec = next((r for r in Model.search(others + [("dbd_key", "=", False)])
                        if _norm(r.name) == _norm(name)), Model)
        vals = dict(vals, dbd_key=key)
        stats = self.stats.setdefault(model, {"nuevos": 0, "actualizados": 0})
        if rec:
            rec.write(vals)
            stats["actualizados"] += 1
        else:
            rec = Model.create(vals)
            stats["nuevos"] += 1
        return rec

    def _want_image(self, rec, field, path, page, force, prefix=None):
        if force or not rec[field]:
            titles = _image_titles(path)
            if prefix and page:
                titles.append(_wiki_name_title(prefix, page))
            self.images.append((rec, field, [t for t in titles if t], _straight(page) if page else None))

    # ---------- pasos ----------
    def run(self, images=True, force_images=False):
        get = lambda e: _get_json(self.session, e)
        self.log("Descargando datos de dbd.tricky.lol…")
        data = {e: get(e) for e in ("dlc", "characters", "items", "perks", "addons", "offerings", "maps")}

        self.tags = self._import_tags()
        realms = self._import_maps(data["maps"], force_images)
        characters = self._import_characters(data["characters"], data["items"], data["dlc"], force_images)
        self._import_perks(data["perks"], characters, force_images)
        self._import_items(data["items"], force_images)
        self._import_addons(data["addons"], characters, force_images)
        self._import_offerings(data["offerings"], realms, force_images)
        self.env.flush_all()
        if images:
            self._download_images()
        return self.stats

    def _import_tags(self):
        return {key: self._upsert("dbd.perk.tag", f"category:{key}", {"name": label}, [("name", "=", label)])
                for key, label in PERK_CATEGORIES.items()}

    def _import_maps(self, maps, force):
        realms, seen = {}, {}
        for key, m in maps.items():
            realm_name = _clean(m.get("realm"))
            name = _clean(m.get("name"))
            if not realm_name or not _valid_name(name):
                continue
            if realm_name not in realms:
                realms[realm_name] = self._upsert("dbd.realm", f"realm:{realm_name}", {"name": realm_name},
                                                  [("name", "=", realm_name)])
                self._want_image(realms[realm_name], "image", None, realm_name, force)
            # Variantes del mismo mapa (Coal Tower, Coal Tower II…): como en la wiki
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:
                name = f"{name} {ROMAN.get(seen[name], seen[name])}"
            rec = self._upsert("dbd.map", key, {"name": name, "realm_id": realms[realm_name].id,
                                                "description": m.get("description") or False},
                               [("name", "=", name)])
            self._want_image(rec, "image", m.get("image"), name, force)
        return realms

    def _import_characters(self, characters, items, dlcs, force):
        dlc_by_key = {k.lower(): v for k, v in dlcs.items()}
        result = {}
        for key, c in characters.items():
            name = _clean(c.get("name"))
            if not _valid_name(name):
                continue
            dlc = dlc_by_key.get((c.get("dlc") or "").lower()) or {}
            power = {}
            vals = {
                "name": name,
                "difficulty": DIFFICULTY.get(c.get("difficulty")) or False,
                "bio": c.get("bio") or False,
                "description": c.get("story") or False,
                "chapter": dlc.get("name") if _valid_name(dlc.get("name")) else False,
                "release_date": (datetime.fromtimestamp(dlc["time"], timezone.utc).date()
                                 if dlc.get("time") else False),
                "sequence": int(key) if key.isdigit() and int(key) < 100000 else 1000 + len(result),
            }
            if c["role"] == "killer":
                tun = c.get("tunables") or {}
                power = items.get(c.get("item") or "") or {}
                vals.update({
                    "height": c.get("height") if c.get("height") in ("short", "average", "tall") else False,
                    "speed": tun["MaxWalkSpeed"] / 100 if tun.get("MaxWalkSpeed") else 4.6,
                    "terror_radius": int(tun["TerrorRadius"] / 100) if tun.get("TerrorRadius") else 32,
                    "power_name": power.get("name") or False,
                    "power_description": power.get("description") or False,
                })
                model = "dbd.killer"
            else:
                model = "dbd.survivor"
            rec = self._upsert(model, f"character:{key}", vals, [("name", "=", name)])
            self._want_image(rec, "image", c.get("image"), name, force)
            if model == "dbd.killer" and power.get("image"):
                self._want_image(rec, "power_image", power["image"], power.get("name"), force)
            result[key] = {"rec": rec, "item": c.get("item")}
        return result

    def _import_perks(self, perks, characters, force):
        for key, p in perks.items():
            name = _clean(p.get("name"))
            if not _valid_name(name):
                continue
            owner = characters.get(str(p.get("character"))) if p.get("character") is not None else None
            owner = owner and owner["rec"]
            vals = {
                "name": name,
                "role": p["role"],
                "survivor_id": owner.id if owner and owner._name == "dbd.survivor" else False,
                "killer_id": owner.id if owner and owner._name == "dbd.killer" else False,
                "description": perk_description(p),
                "tag_ids": [(6, 0, [self.tags[c].id for c in (p.get("categories") or []) if c in self.tags])],
            }
            rec = self._upsert("dbd.perk", key, vals, [("name", "=", name), ("role", "=", p["role"])])
            self._want_image(rec, "image", p.get("image"), name, force, prefix="IconPerks_")

    def _import_items(self, items, force):
        """Objetos de superviviente (`type: item`); los poderes de asesino van en el asesino."""
        for key, it in items.items():
            name = _clean(it.get("name"))
            item_type = ITEM_TYPE.get(it.get("item_type"))
            if it.get("type") != "item" or not item_type or not _valid_name(name):
                continue
            vals = {"name": name, "item_type": item_type, "rarity": RARITY.get(it.get("rarity"), "common"),
                    "event": it.get("event") or False, "description": it.get("description") or False}
            rec = self._upsert("dbd.item", key, vals, [("name", "=", name)])
            self._want_image(rec, "image", it.get("image"), name, force, prefix="IconItems_")

    def _import_addons(self, addons, characters, force):
        killer_by_item = {c["item"]: c["rec"] for c in characters.values()
                          if c["item"] and c["rec"]._name == "dbd.killer"}
        for key, a in addons.items():
            name = _clean(a.get("name"))
            if not _valid_name(name):
                continue
            if a.get("role") == "killer":
                killer = next((killer_by_item[p] for p in a.get("parents") or [] if p in killer_by_item), None)
                if not killer:
                    continue
                vals = {"role": "killer", "killer_id": killer.id, "item_type": False}
                match = [("name", "=", name), ("killer_id", "=", killer.id)]
            else:
                item_type = ITEM_TYPE.get(a.get("item_type"))
                if not item_type:
                    continue
                vals = {"role": "survivor", "killer_id": False, "item_type": item_type}
                match = [("name", "=", name), ("item_type", "=", item_type)]
            vals.update(name=name, rarity=RARITY.get(a.get("rarity"), "common"),
                        description=a.get("description") or False)
            rec = self._upsert("dbd.addon", key, vals, match)
            self._want_image(rec, "image", a.get("image"), name, force, prefix="IconAddon_")

    def _import_offerings(self, offerings, realms, force):
        for key, o in offerings.items():
            name = _clean(o.get("name"))
            if not _valid_name(name):
                continue
            category = OFFERING_CATEGORY.get(o.get("type"), "other")
            realm = False
            if category == "realm":
                text = o.get("description") or ""
                realm = next((r for n, r in realms.items() if n in text), False)
            vals = {
                "name": name,
                "role": o.get("role") or "both",
                "category": category,
                "rarity": RARITY.get(o.get("rarity"), "common"),
                "realm_id": realm.id if realm else False,
                "description": o.get("description") or False,
            }
            rec = self._upsert("dbd.offering", key, vals, [("name", "=", name)])
            self._want_image(rec, "image", o.get("image"), name, force, prefix="IconFavors_")

    # ---------- imágenes ----------
    def _wiki_query(self, params, titles):
        """Consulta la API de la wiki en lotes de 50 títulos. Devuelve {título pedido: url}."""
        found = {}
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            resp = self.session.get(WIKI_API, params=dict(params, action="query", format="json",
                                                          titles="|".join(batch)), timeout=TIMEOUT)
            resp.raise_for_status()
            q = resp.json().get("query", {})
            alias = {}
            for step in ("normalized", "redirects"):
                for n in q.get(step, []):
                    alias[n["to"]] = alias.get(n["from"], n["from"])
            for page in q.get("pages", {}).values():
                url = ((page.get("imageinfo") or [{}])[0].get("url")
                       or (page.get("original") or {}).get("source"))
                if url:
                    title = page["title"]
                    while title in alias:
                        title = alias[title]
                    found[title] = url
        return found

    def _download_images(self):
        if not self.images:
            return
        self.log(f"Buscando {len(self.images)} imágenes en la wiki…")
        files = sorted({t for _r, _f, titles, _p in self.images for t in titles})
        by_file = self._wiki_query({"prop": "imageinfo", "iiprop": "url"}, files)
        pending = [(r, f, p) for r, f, titles, p in self.images if not any(t in by_file for t in titles) and p]
        pages = sorted({p for _r, _f, p in pending})
        by_page = self._wiki_query({"prop": "pageimages", "piprop": "original", "redirects": 1}, pages)

        jobs = []
        for rec, field, titles, page in self.images:
            url = next((by_file[t] for t in titles if t in by_file), None) or by_page.get(page)
            if url:
                jobs.append((rec, field, url))
        self.log(f"Descargando {len(jobs)} imágenes…")

        def fetch(url):
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.content
            except requests.RequestException as e:
                _logger.warning("Imagen no descargada %s: %s", url, e)
                return None

        with ThreadPoolExecutor(max_workers=6) as pool:
            contents = list(pool.map(fetch, [url for _r, _f, url in jobs]))
        ok = 0
        for (rec, field, _url), content in zip(jobs, contents):
            if content:
                rec[field] = base64.b64encode(content).decode()
                ok += 1
        self.stats["imágenes"] = {"descargadas": ok, "sin imagen": len(self.images) - ok}


def import_all(env, images=True, force_images=False, log=None):
    """Importa o actualiza todo el catálogo. `images`: descarga las que falten (o todas con `force_images`)."""
    return Importer(env, log).run(images=images, force_images=force_images)
