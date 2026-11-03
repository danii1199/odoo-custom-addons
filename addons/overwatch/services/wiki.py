"""Lectura del catálogo de cosméticos de la wiki de Overwatch (overwatch.fandom.com), solo por su API de MediaWiki
y con un User-Agent honesto. Las imágenes NO se descargan (su CDN no lo permite desde un servidor): se guarda la URL
y la carga el navegador de quien mira la página.

Cada héroe tiene plantillas «<Héroe> Skins», «<Héroe> Emotes», «<Héroe> VP», «<Héroe> Intros» y «<Héroe> Sprays»:
tablas con cabeceras {{CTS|n=…}} (rareza con {{rl|e|Evento}} y precio) y celdas {{CPB|h=Prefijo|n=Nombre|c=columnas}}
(imagen «Prefijo Nombre.png») o {{CVB|…}} (vídeo «Prefijo Nombre.webm»). Varias cabeceras seguidas se reparten las
columnas de las celdas que vienen debajo (c = ancho, 1 por defecto); una sola cabecera vale para toda la fila, y
las filas sin cabecera nueva siguen con la anterior."""
import re
import time

import requests

API = "https://overwatch.fandom.com/api.php"
USER_AGENT = "Odoo-overwatch/1.0 (modulo personal de Odoo; catalogo de cosmeticos)"

TIPOS = {  # tipo → sufijo de la plantilla
    "skin": "Skins",
    "emote": "Emotes",
    "victory_pose": "VP",
    "highlight_intro": "Intros",
    "spray": "Sprays",
}
RAREZAS_RL = {"c": "common", "r": "rare", "e": "epic", "l": "legendary", "m": "mythic"}
RAREZAS_TEXTO = {"common": "common", "rare": "rare", "epic": "epic", "legendary": "legendary", "mythic": "mythic"}


def _api(session, **params):
    """Petición a la API con una pausa corta (para no cargar la wiki) y reintentos si responde 5xx o 429."""
    for intento in range(4):
        time.sleep(0.15)
        try:
            r = session.get(API, params={"format": "json", "formatversion": 2, **params}, timeout=30)
        except requests.ConnectionError:
            if intento == 3:
                raise
            time.sleep(2 * (intento + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            if intento == 3:
                r.raise_for_status()
            time.sleep(min(int(r.headers.get("Retry-After") or 0) or 3 * (intento + 1), 30))
            continue
        r.raise_for_status()
        return r.json()


def _ancho(valor):
    """Ancho de columna (c=…): solo los dígitos (la wiki a veces trae «1\u200e» o «2)»)."""
    m = re.search(r"\d+", valor or "")
    return int(m.group(0)) if m else 1


def _partir(texto):
    """Separa los parámetros de una plantilla por '|' sin romper las {{…}} ni [[…]] anidadas."""
    partes, nivel, actual, i = [], 0, "", 0
    while i < len(texto):
        dos = texto[i:i + 2]
        if dos in ("{{", "[["):
            nivel += 1
            actual += dos
            i += 2
            continue
        if dos in ("}}", "]]"):
            nivel -= 1
            actual += dos
            i += 2
            continue
        if texto[i] == "|" and nivel == 0:
            partes.append(actual)
            actual = ""
        else:
            actual += texto[i]
        i += 1
    partes.append(actual)
    return partes


def _plantilla(linea):
    """'{{CPB|h=Ana Skin|n=Classic|c=2}}' → ('CPB', {'h': 'Ana Skin', 'n': 'Classic', 'c': '2'})."""
    linea = linea.strip()
    if not (linea.startswith("{{") and "}}" in linea):
        return None, {}
    # quita las llaves exteriores (lo que sigue al cierre, como un '|' suelto, se ignora)
    nivel, fin, i = 0, None, 0
    while i < len(linea) - 1:
        par = linea[i:i + 2]
        if par in ("{{", "}}"):
            nivel += 1 if par == "{{" else -1
            if nivel == 0:
                fin = i
                break
            i += 2  # sin solapar: en «}}}}» hay dos cierres, no tres
            continue
        i += 1
    if fin is None:
        return None, {}
    partes = _partir(linea[2:fin])
    params = {}
    for p in partes[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip()] = v.strip()
    return partes[0].strip(), params


def _limpiar(texto):
    """Texto legible de la cabecera: precio, evento o reto («750 créditos», «Battle Pass», «Ana's Bastet Challenge»)."""
    t = re.sub(r"[\u200e\u3164]", " ", texto)
    t = re.sub(r"\{\{\s*Credits\s*\}\}\s*(\d+)", r"\1 créditos", t)
    t = re.sub(r"\{\{\s*Coins\s*\}\}\s*(\d+)", r"\1 monedas", t)
    t = re.sub(r"\{\{\s*rl\s*\|[^}]*\}\}", " ", t)  # la rareza y el evento ya salen de {{rl}}
    t = re.sub(r"\{\{[^}]*\}\}", " ", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\((Free)\)|\bFree\b", "Gratis", t)
    t = re.sub(r"\b(Common|Rare|Epic|Legendary|Mythic)\b", "", t)
    t = re.sub(r"[‎ㅤ\s()\-–]+", " ", t).strip(" -")
    return t


def _cabecera(params):
    n = params.get("n", "")
    rl = re.search(r"\{\{\s*rl\s*\|\s*([crelm])\s*(?:\|([^}|]*))?", n)
    if rl:
        rareza = RAREZAS_RL[rl.group(1)]
        evento = (rl.group(2) or "").strip()
    else:
        palabra = re.search(r"Common|Rare|Epic|Legendary|Mythic", n)
        rareza = RAREZAS_TEXTO.get(palabra.group(0).lower(), "common") if palabra else "common"
        evento = ""
    resto = _limpiar(n)
    origen = " · ".join(x for x in (evento, resto) if x)
    return {"rarity": rareza, "source": origen, "span": _ancho(params.get("c"))}


def parsear_tabla(wikitext):
    """[{'name', 'file', 'kind': image|video, 'rarity', 'source'}] en el orden de la tabla."""
    items, cabeceras, ultima_fue_cabecera, col = [], [], False, 0
    for linea in wikitext.splitlines():
        linea = linea.strip()
        if linea.startswith("|-"):
            col = 0
            ultima_fue_cabecera = False
            continue
        nombre, params = _plantilla(linea)
        if nombre == "CTS":
            if not ultima_fue_cabecera:
                cabeceras = []
            cabeceras.append(_cabecera(params))
            ultima_fue_cabecera = True
            continue
        if nombre not in ("CPB", "CVB") or not params.get("n"):
            continue
        ultima_fue_cabecera = False
        span = _ancho(params.get("c"))
        cab = None
        if len(cabeceras) == 1:
            cab = cabeceras[0]
        elif cabeceras:
            acumulado = 0
            for c in cabeceras:
                acumulado += c["span"]
                if col < acumulado:
                    cab = c
                    break
            cab = cab or cabeceras[-1]
        col += span
        ext = "webm" if nombre == "CVB" else "png"
        items.append({
            "name": re.sub(r"\{\{[^}]*\}\}|'''|''|[\u200e\u3164]", "", params["n"]).strip() or params["n"],  # sin {{Locked}} ni negritas
            "file": f"File:{params.get('h', '')} {params.get('l') or params['n']}.{ext}",
            "kind": "video" if nombre == "CVB" else "image",
            "rarity": (cab or {}).get("rarity", "common"),
            "source": (cab or {}).get("source", ""),
        })
    return items


def nueva_sesion():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def cosmeticos_heroe(session, nombre_wiki):
    """{tipo: [items]} de un héroe. Las plantillas que no existen se saltan."""
    resultado = {}
    for tipo, sufijo in TIPOS.items():
        data = _api(session, action="parse", page=f"Template:{nombre_wiki} {sufijo}", prop="wikitext", redirects=1)
        if "error" in data:
            continue
        resultado[tipo] = parsear_tabla(data["parse"]["wikitext"])
    return resultado


def urls_archivos(session, titulos):
    """{'File:…': url} (sin los que no existen), de 50 en 50."""
    urls = {}
    titulos = list(dict.fromkeys(titulos))
    for i in range(0, len(titulos), 50):
        data = _api(session, action="query", titles="|".join(titulos[i:i + 50]), prop="imageinfo", iiprop="url")
        normal = {n["to"]: n["from"] for n in data.get("query", {}).get("normalized", [])}
        for page in data.get("query", {}).get("pages", []):
            info = page.get("imageinfo")
            if info:
                urls[normal.get(page["title"], page["title"])] = info[0]["url"]
    return urls
