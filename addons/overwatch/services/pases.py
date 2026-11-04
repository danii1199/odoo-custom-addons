"""Todas las recompensas de cada pase de batalla, nivel a nivel, desde la wiki (solo su API).

Páginas: «List of previous Battle Passes/2022-2026» (temporadas 1-20 de Overwatch 2), «List of previous Battle
Passes/<año>» (arcos anuales) y «Battle Pass» (el pase que la wiki tiene como actual). Cada temporada es un apartado
«==Season N[: Nombre]==» con una tabla de niveles:
    |-            fila
    |12           nivel
    |{{rl|r|Summer Festimari|icon}}           gratis (puede estar vacía o tener varias líneas)
    |{{rl|e|Blade Stance|intro|Genji}}        prémium
y, tras «! colspan=… | Prestige Tiers», filas de prestigio con una sola celda («| colspan="2" | {{rl|p|Nomad|title}}»).
Desde la Temporada 4 de 2026 el pase son varios caminos («tracks») y la wiki pone una tabla por cada uno:
«! colspan="4" |Season 5: … Battle Pass (1)», «(2)»… «(Mythic)»: cada recompensa lleva su `section` (SECCIONES) y el
nivel cuenta dentro de su camino.
{{rl|rareza|Nombre|tipo|Héroe}}; también texto («{{Credits}} 250», «Unlock [[Kiriko]]», «+20% XP All Season»).

Imágenes: si es un cosmético de un héroe que está en la galería, la suya; si no, se prueban los nombres de archivo de
la wiki para ese tipo (ARCHIVOS) y se piden sus URLs de 50 en 50 (enlazadas, como el resto del catálogo)."""
import re
import unicodedata

from . import wiki

PAGINA_ACTUAL = "Battle Pass"
PAGINA_OW2 = "List of previous Battle Passes/2022-2026"
PAGINA_ANYO = "List of previous Battle Passes/{}"

RAREZAS = {"c": "common", "r": "rare", "e": "epic", "l": "legendary", "m": "mythic"}
TIPOS = {"skin": "skin", "icon": "icon", "spray": "spray", "voice": "voice", "title": "title", "card": "card",
         "pose": "victory_pose", "vp": "victory_pose", "emote": "emote", "charm": "charm", "wc": "charm",
         "intro": "highlight_intro", "souvenir": "souvenir"}
CATALOGO = {"skin", "spray", "victory_pose", "emote", "highlight_intro"}  # tipos que están en la galería del héroe
ARCHIVOS = {  # nombres de archivo de la wiki que se prueban, en orden
    "skin": ["{hero} Skin {name}.png"],
    "icon": ["PI {name}.png"],
    "card": ["NameCard {name}.png"],
    "charm": ["WeaponCharm {name}.png"],
    "spray": ["Spray {hero} {name}.png", "Spray {name}.png", "{hero} Spray {name}.png"],
    "souvenir": ["Souvenir {name}.png"],
    "weapon": ["{hero} Weapon Skin {name}.png"],
}
CABECERA = re.compile(r"^==(?!=)\s*Season\s+(\d+)\s*(?::\s*([^=]*?))?\s*==\s*$", re.M)
TEXTOS = [
    (r"\{\{\s*Credits\s*\}\}\s*([\d.,]+)", r"\1 créditos"), (r"\{\{\s*coins\s*\}\}\s*([\d.,]+)", r"\1 monedas"),
    (r"\{\{\s*Mythic Prisms\s*\}\}\s*([\d.,]+)", r"\1 prismas míticos"), (r"\bUnlock\b", "Desbloquea a"),
    (r"\bAll Season\b", "toda la temporada"), (r"\bLegendary Loot Box(es)?\b", "Caja de botín legendaria"),
    (r"\bLoot Box(es)?\b", "Caja de botín"), (r"Battle Pass XP Boost", "de experiencia del pase"),
]


def _norm(t):
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in unicodedata.normalize("NFKD", t or "")
                                              if not unicodedata.combining(c)).lower())


def _texto(t):
    for patron, es in TEXTOS:
        t = re.sub(patron, es, t, flags=re.I)
    t = re.sub(r"\{\{[^}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"<[^>]+>|'{2,}", "", t)
    return re.sub(r"\s+", " ", t).strip(" ·-")


def _objetos(celda):
    """Recompensas de una celda: [{rarity, kind, name, hero}]."""
    res = []
    for linea in celda.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        rls = list(re.finditer(r"\{\{\s*rl\s*\|([^{}]*)\}\}", linea))
        if not rls:
            t = _texto(linea)
            if t:
                res.append({"rarity": False, "kind": "other", "name": t, "hero": ""})
            continue
        for m in rls:
            p = [x.strip() for x in m.group(1).split("|")]
            rareza = RAREZAS.get((p[0] or "").lower()[:1], False)
            nombre = p[1] if len(p) > 1 else ""
            tipo = TIPOS.get((p[2] if len(p) > 2 else "").lower(), "other")
            if not nombre:
                continue
            if tipo == "other":
                nombre = _texto(nombre)
            res.append({"rarity": rareza, "kind": tipo, "name": nombre, "hero": p[3] if len(p) > 3 else ""})
    return res


def seccion(titulo):
    """Nombre del camino de un pase por partes, de la cabecera de su tabla («… Battle Pass (3)» → «Camino 2»)."""
    m = re.search(r"Battle Pass\s*\(([^)]+)\)", titulo or "", re.I)
    if not m:
        return ""
    parte = m.group(1).strip()
    if parte == "1":
        return "Camino inicial"
    if parte.isdigit():
        return f"Camino {int(parte) - 1}"
    return {"mythic": "Camino de prismas"}.get(parte.lower(), parte)


def parsear_tabla(cuerpo):
    """[{tier, track: free|premium|prestige, section, rarity, kind, name, hero}] de las tablas de niveles de un apartado."""
    items, prestigio = [], False
    for tabla in re.split(r"^\{\|", cuerpo, flags=re.M)[1:]:  # cada tabla, con su cabecera (un camino del pase)
        cab = re.search(r"^!\s*colspan[^|]*\|(.*)$", tabla, re.M)
        nombre_seccion = seccion(cab.group(1)) if cab and "prestige" not in cab.group(1).lower() else ""
        items += _filas(tabla, nombre_seccion, prestigio)
        prestigio = prestigio or bool(re.search(r"^!.*Prestige", tabla, re.M | re.I))
    return items


def _filas(tabla, nombre_seccion, prestigio):
    """Las recompensas de una tabla de niveles; las filas tras «Prestige Tiers» son de prestigio."""
    items = []
    for fila in re.split(r"^\|-.*$", tabla, flags=re.M):
        if re.search(r"^!.*Prestige", fila, re.M | re.I):
            prestigio = True
        celdas, actual = [], None
        for linea in fila.splitlines():
            if linea.startswith("|}") or linea.startswith("{|") or linea.startswith("!"):
                continue
            if linea.startswith("|"):
                contenido = linea[1:]
                # atributos de celda: «colspan="2" | contenido»
                m = re.match(r'\s*(?:colspan|rowspan|style)\s*=\s*"[^"]*"\s*\|(.*)', contenido)
                if m:
                    contenido = m.group(1)
                actual = [contenido]
                celdas.append(actual)
            elif actual is not None:
                actual.append(linea)
        if len(celdas) < 2 or not re.match(r"^\s*\d+\s*$", celdas[0][0]):
            continue
        nivel = int(celdas[0][0])
        pistas = [("prestige", celdas[1])] if prestigio or len(celdas) == 2 else \
            [("free", celdas[1]), ("premium", celdas[2] if len(celdas) > 2 else [])]
        for pista, celda in pistas:
            for o in _objetos("\n".join(celda)):
                items.append({"tier": nivel, "track": pista,
                              "section": "Prestigio" if pista == "prestige" and nombre_seccion else nombre_seccion, **o})
    return items


def parsear_pagina(wikitext):
    """[(número, nombre, items)] de cada apartado «==Season N…==» que tenga tabla de niveles."""
    res = []
    cabeceras = list(CABECERA.finditer(wikitext))
    for i, cab in enumerate(cabeceras):
        fin = cabeceras[i + 1].start() if i + 1 < len(cabeceras) else len(wikitext)
        cuerpo = re.split(r"^==(?!=)", wikitext[cab.end():fin], maxsplit=1, flags=re.M)[0]
        items = parsear_tabla(cuerpo)
        if items:
            res.append((int(cab.group(1)), (cab.group(2) or "").strip(), items))
    return res


def descargar(session, temporadas):
    """{key de temporada: items} para las temporadas de `temporadas` (las de seasons.descargar) que tengan tabla."""
    def texto(pagina):
        data = wiki._api(session, action="parse", page=pagina, prop="wikitext", redirects=1)
        return None if "error" in data else data["parse"]["wikitext"]

    por_clave = {t["key"]: t for t in temporadas}
    por_nombre = {_norm(t["subtitle"]): t["key"] for t in temporadas if t["subtitle"]}
    res = {}
    for numero, _nombre, items in parsear_pagina(texto(PAGINA_OW2) or ""):
        if f"ow2-s{numero}" in por_clave:
            res[f"ow2-s{numero}"] = items
    for anyo in sorted({t["year"] for t in temporadas if t["year"]}):
        for numero, _nombre, items in parsear_pagina(texto(PAGINA_ANYO.format(anyo)) or ""):
            if f"{anyo}-s{numero}" in por_clave:
                res[f"{anyo}-s{numero}"] = items
    # el pase «actual» de la wiki: se reconoce por el nombre de la temporada (no dice el año)
    for numero, nombre, items in parsear_pagina(texto(PAGINA_ACTUAL) or ""):
        clave = por_nombre.get(_norm(nombre))
        if clave and clave not in res:
            res[clave] = items
    return res


ALIAS = {"Soldier 76": ["S76"], "Lúcio": ["Lucio"], "Torbjörn": ["Torbjorn"]}  # otros prefijos que usa la wiki


def candidatos(kind, name, hero):
    """Nombres de archivo («File:…») que pueden ser la imagen de una recompensa."""
    hero = (hero or "").replace(":", "")
    res = []
    for h in [hero] + ALIAS.get(hero, []):
        res += [f"File:{p.format(hero=h, name=name)}".replace("  ", " ")
                for p in ARCHIVOS.get(kind, []) if h or "{hero}" not in p]
    return list(dict.fromkeys(res))


def resolver_imagenes(session, peticiones):
    """{clave: url} para peticiones = {clave: [archivos candidatos]} (el primero que exista)."""
    todos = [f for lista in peticiones.values() for f in lista]
    urls = wiki.urls_archivos(session, todos) if todos else {}
    return {k: next((urls[f] for f in lista if f in urls), "") for k, lista in peticiones.items()}
