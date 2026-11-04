"""Temporadas y pases de batalla desde la wiki de Overwatch (solo su API, como los cosméticos).

Páginas: «Season/2022-2026» (Overwatch 2, temporadas 1-20) y una por arco anual desde 2026 («Season/2026»: Reign of
Talon, 6 temporadas). Cada temporada es un apartado «===Season N: Nombre===» con:
- las fechas entre paréntesis: «(4 October 2022 - 6 December 2022)», «(June 20, 2024 - August 20, 2024)»,
  «(February 18 - 22 April 2025)», «(6 October 2026 - December 2026)» (sin día: la fecha queda vacía y sale el texto);
- la primera imagen ([[File:…]]), que es la hoja de ruta;
- «*'''New Hero(es)'''» con «**[[Héroe]] (Rol)» debajo;
- «*'''New Battle Pass'''» con «** Mythic Skin ({{rl|m|Nombre}} [[Héroe]], Midseason)» y «Mythic Weapon Skin - …»
  (desde 2026: «*'''New {{Raritylink|m|text=Mythic}} Skins'''» con «{{Raritylink|m|text=Nombre}}»);
Se actualiza por `key` y nunca se borra nada; las recompensas de cada temporada se rehacen (vienen completas)."""
import re
import unicodedata
from datetime import date

from odoo import fields

from . import eventos, pases, wiki

PAGINAS = [("Season/2022-2026", "Overwatch 2", None)]  # (página, etapa, año del arco)
PRIMER_ARCO = 2026  # desde aquí, una página por año: «Season/<año>»; se para en la primera que no exista

MESES = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                     "september", "october", "november", "december"], 1)}
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
            "noviembre", "diciembre"]
CABECERA = re.compile(r"^===\s*Season\s+(\d+)\s*(?::\s*([^=<]*?))?\s*(?:<span[^>]*>\s*</span>)?\s*===\s*$", re.M)


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFKD", t or "") if not unicodedata.combining(c)).lower().strip()


def _enlace(texto):
    """Destino del primer [[enlace]] («[[Overwatch (group)|Overwatch]]» → «Overwatch (group)»)."""
    m = re.search(r"\[\[([^\]|#]+)", texto)
    return m.group(1).strip() if m else ""


def _fecha(parte):
    """«4 October 2022», «June 20, 2024», «February 18», «December 2026» → (día, mes, año) con None si falta."""
    t = parte.lower().replace(",", " ")
    mes = next((n for nombre, n in MESES.items() if nombre in t), None)
    anyo = re.search(r"\b(\d{4})\b", t)
    dia = re.search(r"\b(\d{1,2})\b", re.sub(r"\b\d{4}\b", " ", t))
    return (int(dia.group(1)) if dia else None, mes, int(anyo.group(1)) if anyo else None)


def fechas(texto):
    """(inicio, fin, texto en español) de lo que hay entre paréntesis. Las fechas sin día quedan en None."""
    m = re.search(r"\(([^()]*\d{4}[^()]*)\)", texto)
    if not m:
        return None, None, ""
    partes = re.split(r"\s+[-–]\s+", m.group(1).strip(), maxsplit=1)
    ini = _fecha(partes[0])
    fin = _fecha(partes[1]) if len(partes) > 1 else (None, None, None)
    if not ini[2] and fin[2]:
        ini = (ini[0], ini[1], fin[2] - (1 if ini[1] and fin[1] and ini[1] > fin[1] else 0))

    def a_fecha(d):
        return date(d[2], d[1], d[0]) if all(d) else None

    def a_texto(d):
        if not (d[1] and d[2]):
            return "?"
        return f"{d[0]} de {MESES_ES[d[1] - 1]} de {d[2]}" if d[0] else f"{MESES_ES[d[1] - 1]} de {d[2]}"

    return a_fecha(ini), a_fecha(fin), f"{a_texto(ini)} – {a_texto(fin)}" if len(partes) > 1 else a_texto(ini)


def _bloque(lineas, titulo):
    """Las líneas «**…» que cuelgan del punto «*'''<titulo>'''» (hasta el siguiente punto de primer nivel)."""
    dentro, res = False, []
    for linea in lineas:
        s = linea.strip()
        if s.startswith("*") and not s.startswith("**"):
            dentro = bool(re.search(titulo, re.sub(r"<ref.*?(?:</ref>|/>)", "", s), re.I))
            continue
        if dentro and s.startswith("**"):
            res.append(s)
    return res


def parsear_pagina(wikitext, etapa, anyo):
    """[{key, arc, year, number, subtitle, date_start, date_end, dates_text, theme, image_file, heroes, rewards}]."""
    temporadas = []
    cabeceras = list(CABECERA.finditer(wikitext))
    for i, cab in enumerate(cabeceras):
        fin = cabeceras[i + 1].start() if i + 1 < len(cabeceras) else len(wikitext)
        cuerpo = re.split(r"^==[^=]", wikitext[cab.end():fin], maxsplit=1, flags=re.M)[0]  # hasta el siguiente «==»
        lineas = cuerpo.splitlines()
        numero = int(cab.group(1))
        nombre = (cab.group(2) or "").strip()
        nombre = "" if nombre.upper() == "TBA" else nombre
        ini, fin_f, texto = fechas(cuerpo)
        imagen = re.search(r"\[\[File:([^|\]]+)", cuerpo)
        tema = re.search(r"Theme and [Ss]tory:?'*:?\s*(.*)", cuerpo)
        recompensas = []
        for linea in _bloque(lineas, r"New\W+(?:Battle\s*pass|.*Mythic.*Skins)"):
            rl = re.search(r"\{\{\s*rl\s*\|\s*m\s*\|([^}|]+)\}\}", linea) or \
                re.search(r"\{\{\s*Raritylink\s*\|\s*m\s*\|\s*text\s*=\s*([^}|]+)\}\}", linea, re.I)
            if not rl or rl.group(1).strip().upper() == "TBA":
                continue
            resto = linea[rl.end():]
            tipo = "weapon" if re.search(r"weapon", linea, re.I) else "midseason" if re.search(r"mid-?season", linea, re.I) else "skin"
            recompensas.append({"kind": tipo, "name": rl.group(1).strip(), "hero": _enlace(resto)})
        heroes = [_enlace(linea) for linea in _bloque(lineas, r"\bNew\s+Heroe?s?\b(?!\s+progression)")]
        temporadas.append({
            "key": f"{anyo}-s{numero}" if anyo else f"ow2-s{numero}",
            "arc": etapa, "year": anyo, "number": numero, "subtitle": nombre,
            "date_start": ini, "date_end": fin_f, "dates_text": texto,
            "theme": _limpiar_tema(tema.group(1)) if tema else "",
            "image_file": f"File:{imagen.group(1).strip()}" if imagen else "",
            "heroes": [h for h in heroes if h and not re.match(r"\d", h)],
            "rewards": recompensas,
            "events": eventos.enlaces_eventos(cuerpo),
        })
    return temporadas


def _limpiar_tema(t):
    t = re.sub(r"<ref.*?(?:</ref>|/>)", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    return re.sub(r"'{2,}|\{\{[^}]*\}\}", "", t).strip(" :")


def _wikitext(session, pagina):
    data = wiki._api(session, action="parse", page=pagina, prop="wikitext", redirects=1)
    return None if "error" in data else data["parse"]["wikitext"]


def descargar(session=None):
    """Todas las temporadas de la wiki, en orden cronológico."""
    session = session or wiki.nueva_sesion()
    paginas = list(PAGINAS)
    anyo = PRIMER_ARCO
    todas = []
    for pagina, etapa, a in paginas:
        todas += parsear_pagina(_wikitext(session, pagina) or "", etapa, a)
    while True:
        texto = _wikitext(session, f"Season/{anyo}")
        if not texto:
            break
        arco = re.search(r"'''''(.+?)'''''", texto)
        todas += parsear_pagina(texto, arco.group(1).strip() if arco else str(anyo), anyo)
        anyo += 1
    urls = wiki.urls_archivos(session, [t["image_file"] for t in todas if t["image_file"]])
    for t in todas:
        t["image_url"] = urls.get(t["image_file"], "")
    return todas


def _cosmetico(hero, kind, nombre):
    """El cosmético de la galería del héroe con ese tipo y nombre (sin tildes; también sin el nombre del héroe,
    que la wiki añade a veces en los grafitis: «Street Rebel Lucio»)."""
    if not hero or kind not in pases.CATALOGO:
        return hero.browse() if hero else None
    n = _sin_tildes(nombre)
    sin_heroe = _sin_tildes(re.sub(re.escape(hero.wiki_name or hero.name), "", nombre, flags=re.I))
    for c in hero.cosmetic_ids:
        if c.type == kind and _sin_tildes(c.name) in (n, sin_heroe):
            return c
    return hero.cosmetic_ids.browse()


def guardar_eventos(env, lista, batch, avisar):
    """Crea o actualiza los eventos (por `key`); con `avisar`, los nuevos quedan en Novedades. Devuelve cuántos nuevos."""
    Event, Season, Change = env["ow.event"], env["ow.season"], env["ow.change"]
    nuevos = 0
    for ev in lista:
        vals = {"name": ev["name"], "kind": ev["kind"], "date_start": ev["date_start"] or False,
                "date_end": ev["date_end"] or False, "approx": ev["approx"], "image_url": ev["image_url"] or False,
                "wiki_page": ev["wiki_page"],
                "season_id": Season.search([("key", "=", ev["season_key"])], limit=1).id or False}
        rec = Event.search([("key", "=", ev["key"])], limit=1)
        if rec:
            rec.write(vals)
            continue
        rec = Event.create({**vals, "key": ev["key"]})
        nuevos += 1
        if avisar:
            fechas = " – ".join(d.strftime("%d/%m/%Y") for d in (rec.date_start, rec.date_end) if d)
            Change.create({"batch": batch, "kind": "event_new", "season_id": rec.season_id.id,
                           "what": rec.name, "new_value": fechas + (" (aprox.)" if rec.approx else "")})
    return nuevos


def guardar(env, temporadas, batch=None, items=None, session=None, events=None):
    """Crea o actualiza las temporadas (por `key`). Devuelve {"new", "updated", "changes"}.

    Con temporadas ya cargadas, apunta en Novedades (ow.change, con `batch`) los pases nuevos y los míticos que
    aparecen en uno que ya existía (la wiki los publica poco a poco: el de mitad de temporada suele llegar después).
    `items` = {key: recompensas por nivel} (pases.descargar); con `session`, se piden a la wiki las imágenes de lo que
    no esté en la galería (armas míticas, iconos, tarjetas…) y, si la temporada no tiene, se usa la de su mítico."""
    Season = env["ow.season"]
    Change = env["ow.change"]
    batch = batch or fields.Datetime.to_string(fields.Datetime.now())
    habia = bool(Season.search_count([]))
    cambios = 0
    habia_items = bool(env["ow.season.item"].search_count([]))  # la primera carga de recompensas no es novedad
    peticiones = {}  # (tabla, id de temporada, posición) → archivos candidatos de la wiki
    creadas = set()  # las nuevas ya salen como «Pase nuevo»: sus recompensas no son otra novedad
    heroes = env["ow.hero"].with_context(active_test=False).search([])
    por_nombre = {}
    for h in heroes:
        for n in (h.wiki_name, h.name, h.key):
            if n:
                por_nombre.setdefault(_sin_tildes(n), h)
    s = {"new": 0, "updated": 0}
    for orden, t in enumerate(temporadas, 1):
        hs = [por_nombre.get(_sin_tildes(n)) for n in t["heroes"]]
        vals = {
            "sequence": orden, "arc": t["arc"], "year": t["year"] or False, "number": t["number"],
            "subtitle": t["subtitle"] or False, "date_start": t["date_start"] or False,
            "date_end": t["date_end"] or False, "dates_text": t["dates_text"] or False, "theme": t["theme"] or False,
            "image_url": t.get("image_url") or False,
            "wiki_page": f"Season/{t['year']}" if t["year"] else "Season/2022-2026",
            "new_hero_ids": [(6, 0, [h.id for h in hs if h])],
            "new_heroes_text": ", ".join(n for n, h in zip(t["heroes"], hs) if not h) or False,
        }
        rec = Season.search([("key", "=", t["key"])], limit=1)
        miticos_antes = set(rec.reward_ids.mapped("name"))
        if rec:
            rec.write(vals)
            s["updated"] += 1
        else:
            rec = Season.create({**vals, "key": t["key"]})
            s["new"] += 1
            creadas.add(rec.id)
            if habia:
                Change.create({"batch": batch, "kind": "season_new", "season_id": rec.id, "what": rec.name,
                               "new_value": rec.dates_text or ""})
                cambios += 1
        if rec and miticos_antes:
            for r in t["rewards"]:
                if r["name"] not in miticos_antes:
                    Change.create({"batch": batch, "kind": "season", "season_id": rec.id,
                                   "what": f"{rec.name} · nuevo mítico", "new_value": f"{r['name']} ({r['hero']})"})
                    cambios += 1
        rec.reward_ids.unlink()
        lineas = []
        for i, r in enumerate(t["rewards"]):
            hero = por_nombre.get(_sin_tildes(r["hero"]))
            cosmetico = _cosmetico(hero, "skin", r["name"]) if r["kind"] != "weapon" else None
            lineas.append((0, 0, {"sequence": i, "kind": r["kind"], "name": r["name"], "hero_text": r["hero"] or False,
                                  "hero_id": hero.id if hero else False,
                                  "cosmetic_id": cosmetico.id if cosmetico else False}))
            if not cosmetico:
                peticiones[("reward", rec.id, i)] = pases.candidatos(
                    "weapon" if r["kind"] == "weapon" else "skin", r["name"], (hero.wiki_name if hero else "") or r["hero"])
        rec.reward_ids = lineas
        nuevos = (items or {}).get(t["key"])
        if nuevos is not None:
            tenia = bool(rec.item_ids)
            rec.item_ids.unlink()
            filas = []
            for i, it in enumerate(nuevos):
                hero = por_nombre.get(_sin_tildes(it["hero"])) if it["hero"] else None
                cos = _cosmetico(hero, it["kind"], it["name"]) if hero else None
                filas.append({"season_id": rec.id, "tier": it["tier"], "track": it["track"], "sequence": i,
                              "section": it.get("section") or False,
                              "kind": it["kind"], "rarity": it["rarity"] or False, "name": it["name"],
                              "hero_id": hero.id if hero else False, "hero_text": it["hero"] or False,
                              "cosmetic_id": cos.id if cos else False})
                if not cos and pases.candidatos(it["kind"], it["name"], it["hero"]):
                    peticiones[("item", rec.id, i)] = pases.candidatos(
                        it["kind"], it["name"], (hero.wiki_name if hero else "") or it["hero"])
            env["ow.season.item"].create(filas)
            if habia_items and not tenia and nuevos and rec.id not in creadas:
                Change.create({"batch": batch, "kind": "season", "season_id": rec.id,
                               "what": f"{rec.name} · recompensas publicadas", "new_value": f"{len(nuevos)} recompensas"})
                cambios += 1
    if session and peticiones:
        urls = pases.resolver_imagenes(session, peticiones)
        for (tabla, season_id, pos), url in urls.items():
            if not url:
                continue
            modelo = env["ow.season.reward" if tabla == "reward" else "ow.season.item"]
            modelo.search([("season_id", "=", season_id), ("sequence", "=", pos)], limit=1).media_url = url
    for rec in Season.search([("image_url", "=", False)]):  # sin hoja de ruta: la imagen de su mítico
        r = rec.reward_ids[:1]
        rec.image_url = (r.cosmetic_id.media_url if r.cosmetic_id else r.media_url) or False
    if events is not None:
        habia_eventos = bool(env["ow.event"].search_count([]))  # la primera carga no es novedad
        n = guardar_eventos(env, events, batch, avisar=habia_eventos)
        cambios += n if habia_eventos else 0
        s["events"] = n
    s["changes"] = cambios
    return s


def importar(env, session=None, batch=None):
    session = session or wiki.nueva_sesion()
    temporadas = descargar(session)
    return guardar(env, temporadas, batch, items=pases.descargar(session, temporadas), session=session,
                   events=eventos.descargar(session, temporadas))
