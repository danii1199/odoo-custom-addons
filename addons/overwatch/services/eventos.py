"""Eventos de tiempo limitado y colaboraciones de cada temporada, desde la wiki (solo su API, como el resto).

- Qué eventos: los enlaces del apartado de cada temporada en «Season/<año>» y «Season/2022-2026» (seasons.py los deja
  en `t["events"]`): puntos «Events», «Collaborations», «Limited-Time Event»… y las líneas sueltas con un enlace
  «Overwatch x …» (así vienen las colaboraciones desde 2026).
- Sus fechas: de la página de cada evento. No hay una ficha fija: se buscan rangos de fechas en el texto
  («from February 10 to March 31, 2026», «*2026: October 6 to November 3», «October 6–November 2») y se elige el que
  cae dentro de su temporada. Si no hay ninguno, las fechas de la temporada y `approx` (se dice en la web).
- Solo se leen las temporadas recientes (RECIENTES días hacia atrás): las antiguas no cambian y así son pocas
  peticiones al día."""
import re
from datetime import date, timedelta

from . import wiki

RECIENTES = 120
MESES = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                     "september", "october", "november", "december"], 1)}
_M = "|".join(MESES)
_ORD = r"(?:st|nd|rd|th)?"
# «February 10 to March 31, 2026», «March 10 to 23, 2026», «October 6–November 2», «July 14th to 28th»
RANGO = re.compile(
    rf"\b({_M})\s+(\d{{1,2}}){_ORD}(?:,?\s*(\d{{4}}))?\s*(?:to|–|—|-|until|through)\s*(?:({_M})\s+)?(\d{{1,2}}){_ORD}(?:,?\s*(\d{{4}}))?",
    re.I)
# «10 February 2026 - 14 April 2026»
RANGO_DMY = re.compile(
    rf"\b(\d{{1,2}})\s+({_M})(?:\s+(\d{{4}}))?\s*(?:to|–|—|-)\s*(\d{{1,2}})\s+({_M})(?:\s+(\d{{4}}))?", re.I)
LINEA_ANYO = re.compile(r"^\*\s*(\d{4})\s*:\s*(.+)$", re.M)


def _fecha(anyo, mes, dia):
    try:
        return date(anyo, mes, dia)
    except (TypeError, ValueError):
        return None


def rangos(texto, anyo_defecto):
    """[(inicio, fin)] de los rangos de fechas del texto (el año que falte, del otro extremo o de `anyo_defecto`)."""
    texto = re.sub(r"<ref.*?(?:</ref>|/>)", "", texto or "", flags=re.S)
    texto = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", texto)
    res = []
    trozos = [(int(m.group(1)), m.group(2)) for m in LINEA_ANYO.finditer(texto)] + [(anyo_defecto, texto)]
    for anyo, trozo in trozos:
        for m in RANGO.finditer(trozo):
            m1, d1, y1 = MESES[m.group(1).lower()], int(m.group(2)), m.group(3)
            m2 = MESES[m.group(4).lower()] if m.group(4) else m1
            d2, y2 = int(m.group(5)), m.group(6)
            fin_y = int(y2 or y1 or anyo)
            ini_y = int(y1) if y1 else (fin_y if m1 <= m2 else fin_y - 1)
            ini, fin = _fecha(ini_y, m1, d1), _fecha(fin_y, m2, d2)
            if ini and fin and ini <= fin:
                res.append((ini, fin))
        for m in RANGO_DMY.finditer(trozo):
            d1, m1, y1 = int(m.group(1)), MESES[m.group(2).lower()], m.group(3)
            d2, m2, y2 = int(m.group(4)), MESES[m.group(5).lower()], m.group(6)
            fin_y = int(y2 or y1 or anyo)
            ini, fin = _fecha(int(y1) if y1 else fin_y, m1, d1), _fecha(fin_y, m2, d2)
            if ini and fin and ini <= fin:
                res.append((ini, fin))
    return res


def elegir(candidatos, inicio, fin):
    """El rango que cae en la temporada [inicio, fin] (con unos días de margen); None si ninguno."""
    if not inicio:
        return None
    hasta = (fin or inicio + timedelta(days=70)) + timedelta(days=10)
    desde = inicio - timedelta(days=10)
    dentro = [r for r in candidatos if desde <= r[0] <= hasta]
    return min(dentro, key=lambda r: (r[0], r[1])) if dentro else None


def enlaces_eventos(cuerpo):
    """Páginas de los eventos que enlaza el apartado de una temporada."""
    res, dentro = [], False
    for linea in cuerpo.splitlines():
        s = re.sub(r"<ref.*?(?:</ref>|/>)", "", linea.strip())
        if s.startswith("*") and not s.startswith("**"):
            enlaces = re.findall(r"\[\[([^\]|#]+)", s)
            dentro = bool(re.search(r"event|collab|crossover", s, re.I))
            # el evento en la propia línea («*'''[[Overwatch x Shadow Monarch]]'''», «… Limited-Time Event'''»)
            res += [e for e in enlaces if dentro or re.search(r"\bx\b", e, re.I)]
            continue
        if dentro and s.startswith("**"):
            res += re.findall(r"\[\[([^\]|#]+)", s)[:1]
    vistos, limpio = set(), []
    for e in (x.strip() for x in res):
        if e and e.lower() not in vistos and not re.match(r"(season|battle pass|limited-time event)\b", e, re.I):
            vistos.add(e.lower())
            limpio.append(e)
    return limpio


def descargar(session, temporadas, hoy=None):
    """[{key, name, season_key, kind, date_start, date_end, approx, image_url, wiki_page}] de las temporadas recientes."""
    hoy = hoy or date.today()
    limite = hoy - timedelta(days=RECIENTES)
    res, imagenes = [], {}
    for t in temporadas:
        if not t.get("events") or (t["date_end"] and t["date_end"] < limite) or \
                (not t["date_start"] and not t["date_end"] and t.get("year") and t["year"] < hoy.year):
            continue
        for pagina in t["events"]:
            data = wiki._api(session, action="parse", page=pagina, prop="wikitext", redirects=1)
            texto = "" if "error" in data else data["parse"]["wikitext"]
            titulo = pagina if "error" in data else data["parse"]["title"]
            anyo = (t["date_start"] or t["date_end"] or hoy).year
            r = elegir(rangos(texto, anyo), t["date_start"], t["date_end"])
            img = re.search(r"\[\[File:([^|\]]+)", texto)
            ev = {"key": f"{t['key']}:{titulo}", "name": titulo, "season_key": t["key"],
                  "kind": "collab" if re.search(r"\bx\b", titulo, re.I) else "event",
                  "date_start": r[0] if r else t["date_start"], "date_end": r[1] if r else t["date_end"],
                  "approx": not r, "image_url": "", "wiki_page": titulo}
            if img:
                imagenes[ev["key"]] = f"File:{img.group(1).strip()}"
            res.append(ev)
    urls = wiki.urls_archivos(session, list(imagenes.values())) if imagenes else {}
    for ev in res:
        ev["image_url"] = urls.get(imagenes.get(ev["key"], ""), "")
    return res
