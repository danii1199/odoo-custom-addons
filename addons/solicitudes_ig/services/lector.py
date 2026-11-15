"""Lee los nombres de usuario de la exportación de datos de Instagram, sin Odoo (se prueba suelto).

Formatos (Centro de cuentas → Tu información y permisos → Descargar tu información):
- HTML: `connections/followers_and_following/pending_follow_requests.html`. Formato real (2026-11-15): cada cuenta es
  una tabla con filas «Nombre» / «Nombre de usuario» / a veces «URL» (la web de su biografía, que puede ser otro perfil
  de Instagram: no se usa) y debajo la fecha («nov. 15, 2026 4:05 am», en UTC). Sin esas filas (exportaciones antiguas),
  los enlaces `https://www.instagram.com/<usuario>`.
- JSON: lo mismo con `string_list_data: [{href, value, timestamp}]` (en exportaciones recientes el nombre va en `title`).
- Texto: un usuario por línea (con o sin @, o la URL del perfil); detrás puede ir una coma o un tabulador y más datos.
Devuelve [(usuario, fecha o None)] sin repetidos, en el orden del archivo. Instagram no distingue mayúsculas."""
import html
import json
import re
from datetime import datetime, timezone

USUARIO = re.compile(r"^[a-z0-9._]{1,30}$")
# Solo instagram.com y www.instagram.com (no help.instagram.com ni otros subdominios)
ENLACE = re.compile(r"(?<![\w.-])(?:www\.)?instagram\.com/(?:_u/)?([A-Za-z0-9._]{1,30})", re.I)
# Rutas de instagram.com que no son perfiles
RESERVADAS = {"accounts", "explore", "p", "reel", "reels", "stories", "direct", "about", "developer", "legal",
              "privacy", "web", "tv", "challenge", "help", "emails", "session", "_u"}


def _usuario(texto):
    u = (texto or "").strip().lstrip("@").strip("/").lower()
    return u if USUARIO.match(u) and u not in RESERVADAS and not u.startswith(".") else None


def _de_json(datos):
    salida = []

    def recorrer(x):
        if isinstance(x, dict):
            filas = x.get("string_list_data")
            if isinstance(filas, list):
                for f in filas:
                    if not isinstance(f, dict):
                        continue
                    m = ENLACE.search(f.get("href") or "")
                    u = _usuario(f.get("value")) or _usuario(x.get("title")) or (m and _usuario(m.group(1)))
                    ts = f.get("timestamp")
                    fecha = datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None) if isinstance(ts, (int, float)) and ts > 0 else None
                    if u:
                        salida.append((u, fecha))
                return
            for v in x.values():
                recorrer(v)
        elif isinstance(x, list):
            for v in x:
                recorrer(v)

    recorrer(datos)
    return salida


# Etiqueta de la fila con el usuario, según el idioma de la exportación
ETIQUETA = re.compile(r"<td[^>]*>\s*(?:Nombre de usuario|Username|Nom d['’]utilisateur|Nome utente|Nome de usuário)"
                      r"\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>", re.I)
FECHA = re.compile(r'<div class="[^"]*_a6-o[^"]*">\s*([^<]+?)\s*</div>')
MESES = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
         "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}


def _fecha(texto):
    """«nov. 15, 2026 4:05 am» o «Nov 15, 2026 4:05 pm» → datetime (UTC, como la exportación); si no, None."""
    m = re.match(r"([a-záé]+)\.?\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m", texto.strip(), re.I)
    if not m or m.group(1).lower() not in MESES:
        return None
    hora = int(m.group(4)) % 12 + (12 if m.group(6).lower() == "p" else 0)
    try:
        return datetime(int(m.group(3)), MESES[m.group(1).lower()], int(m.group(2)), hora, int(m.group(5)))
    except ValueError:
        return None


def _de_html(texto):
    filas = list(ETIQUETA.finditer(texto))
    if not filas:  # exportaciones antiguas: enlaces al perfil
        return [(u, None) for u in (_usuario(m) for m in ENLACE.findall(html.unescape(texto))) if u]
    salida = []
    for i, m in enumerate(filas):
        u = _usuario(html.unescape(m.group(1)))
        if not u:
            continue
        hasta = filas[i + 1].start() if i + 1 < len(filas) else len(texto)
        f = FECHA.search(texto, m.end(), hasta)
        salida.append((u, _fecha(html.unescape(f.group(1))) if f else None))
    return salida


def _de_texto(texto):
    salida = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        m = ENLACE.search(linea)
        # Sin enlace: el primer campo (antes de una coma o tabulador) tiene que ser una sola palabra; así un nombre
        # como «Juan Pérez» no se toma por la cuenta «juan»
        campo = re.split(r"[,\t]", linea, maxsplit=1)[0].strip()
        u = _usuario(m.group(1)) if m else (_usuario(campo) if " " not in campo else None)
        if u:
            salida.append((u, None))
    return salida


def leer(contenido):
    texto = (contenido or "").lstrip("﻿").strip()
    if not texto:
        return []
    if texto[0] in "[{":
        try:
            filas = _de_json(json.loads(texto))
        except ValueError:
            filas = _de_texto(texto)
    elif "<" in texto and ">" in texto:
        filas = _de_html(texto)
    else:
        filas = _de_texto(texto)
    vistos, salida = set(), []
    for u, fecha in filas:
        if u not in vistos:
            vistos.add(u)
            salida.append((u, fecha))
    return salida
