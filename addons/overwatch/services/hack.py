"""Tier Hack de cada pase: los aspectos legendarios por los que se puede cambiar uno del pase (desde la Temporada 4
de 2026), del apartado «=== Tier Hack ===» de la página «Battle Pass» de la wiki.

La wiki solo da la lista del pase actual («Current Skin Pool is:») y reescribe la página en cada temporada. Las de
temporadas ya terminadas se sacan de la revisión de esa página al final de cada una (`rvstart`); la temporada de la
revisión se reconoce por su primera cabecera «==Season N: Nombre==». Una temporada terminada que ya tiene su lista
no se vuelve a pedir: así, a diario, solo se lee la actual.
"""
import re
from datetime import date, datetime, time, timedelta

from . import pases, wiki

PAGINA = "Battle Pass"
DESDE = date(2026, 8, 1)  # el Tier Hack llegó con la Temporada 4 de 2026 (11 de agosto)
APARTADO = re.compile(r"^===\s*Tier Hack\s*===\s*$(.*?)(?=^==)", re.M | re.S)
TEMPORADA = re.compile(r"^==(?!=)\s*Season\s+(\d+)\s*(?::\s*([^=]*?))?\s*==\s*$", re.M)


def parsear(wikitext):
    """(nombre de la temporada de la página, [{name, hero}]) o (None, []) si no hay Tier Hack."""
    ap = APARTADO.search(wikitext or "")
    cab = TEMPORADA.search(wikitext or "")
    if not ap or not cab:
        return None, []
    lista = [o for o in pases._objetos(ap.group(1)) if o["kind"] == "skin" and o["name"].upper() != "TBA"]
    return (cab.group(2) or "").strip(), [{"name": o["name"], "hero": o["hero"]} for o in lista]


def _revision(session, hasta=None):
    """Texto de la página «Battle Pass» tal y como estaba en `hasta` (datetime UTC) o ahora."""
    params = {"action": "query", "prop": "revisions", "titles": PAGINA, "rvlimit": 1, "rvprop": "content",
              "rvslots": "main"}
    if hasta:
        params.update(rvstart=hasta.strftime("%Y-%m-%dT%H:%M:%SZ"), rvdir="older")
    data = wiki._api(session, **params)
    try:
        return data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""


def descargar(session, temporadas, con_lista=(), hoy=None):
    """{key de temporada: [{name, hero}]} de las temporadas con Tier Hack. `con_lista`: claves que ya la tienen
    (si su temporada ya acabó, no se piden). Solo se acepta la lista si la revisión es de esa temporada."""
    hoy = hoy or date.today()
    por_nombre = {pases._norm(t["subtitle"]): t["key"] for t in temporadas if t.get("subtitle")}
    res = {}
    for t in temporadas:
        ini, fin = t.get("date_start"), t.get("date_end")
        if not ini or ini < DESDE or ini > hoy:
            continue
        terminada = bool(fin and fin < hoy)
        if terminada and t["key"] in con_lista:
            continue
        # la última versión de la página mientras duraba la temporada (hasta la víspera de su fin: el último día ya
        # se reescribe para la siguiente), o la actual
        hasta = datetime.combine(fin - timedelta(days=1), time.max) if terminada else None
        nombre, lista = parsear(_revision(session, hasta))
        if lista and por_nombre.get(pases._norm(nombre or "")) == t["key"]:
            res[t["key"]] = lista
    return res
