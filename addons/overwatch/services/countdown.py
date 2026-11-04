"""Eventos en curso y próximos desde Overwatch Countdown (owcountdown.com), la misma fuente que el recuadro
«Event Countdown» de la portada de la wiki (MediaWiki:Countdown.js la lee desde el navegador).

API pública y gratuita, sin clave: GET /api/events → lista de lo que está en curso o por empezar, con fecha y hora
exactas (UTC). No da los ya terminados ni imágenes: el historial y las imágenes siguen viniendo de la wiki
(eventos.py). Una petición por búsqueda (una al día).
"""
import json
import re
from datetime import datetime, timezone

import requests

from .wiki import USER_AGENT

APIS = ["https://www.owcountdown.com/api/events", "https://preview.owcountdown.com/api/events"]
WEB = "https://www.owcountdown.com"
# Etiquetas que no son un evento: la propia temporada ya sale como pase.
SIN_EVENTO = {"Season"}
FUENTE = re.compile(r"\n*\s*Source:\s*\[([^\]]*)\]\((https?://[^)\s]+)\)\s*$", re.I)


def _fecha(valor):
    """ISO con zona → datetime UTC sin zona (como guarda Odoo los Datetime)."""
    if not valor:
        return None
    d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


def _etiquetas(valor):
    if isinstance(valor, list):
        return [str(t) for t in valor]
    try:
        res = json.loads(valor or "[]")
    except ValueError:
        return [valor] if valor else []
    return [str(t) for t in res] if isinstance(res, list) else []


def convertir(datos):
    """Lista de la API → [{countdown_id, name, kind, tags, start_at, end_at, description, source_url}]."""
    res = []
    for e in datos or []:
        if not isinstance(e, dict) or not e.get("id") or not e.get("title"):
            continue
        tags = _etiquetas(e.get("tags"))
        if SIN_EVENTO & set(tags):
            continue
        desc = (e.get("description") or "").strip()
        m = FUENTE.search(desc)
        if m:
            desc = desc[:m.start()].strip()
        titulo = e["title"].strip()
        res.append({
            "countdown_id": int(e["id"]), "name": titulo,
            "kind": "collab" if re.search(r"\bx\b", titulo, re.I) else "event",
            "tags": ", ".join(tags), "start_at": _fecha(e.get("date")), "end_at": _fecha(e.get("end_date")),
            "description": desc, "source_url": m.group(2) if m else "",
        })
    return res


def descargar(session=None):
    """Eventos de la API (None si no responde: entonces no se toca nada)."""
    s = session or requests.Session()
    for url in APIS:
        try:
            r = s.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=30)
            if r.ok:
                return convertir(r.json())
        except (requests.RequestException, ValueError):
            continue
    return None
