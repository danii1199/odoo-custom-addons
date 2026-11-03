"""Catálogo de rutinas de FuertaFit en memoria: clasificación por grupo muscular, búsqueda y resumen.

Los datos están en el modelo `fuerta.routine` (común a todos los usuarios). `get(env)` devuelve el catálogo
ya clasificado y lo cachea por base de datos hasta que cambie la tabla.
"""
import re
import threading

# Tipos que no cuentan como "bloque principal" salvo que se pidan expresamente.
COOLDOWN_TYPE = "Cuerpo-Mente"
WARMUP_TYPE = "Calentamiento"
SIDE_TYPES = {COOLDOWN_TYPE, WARMUP_TYPE}

# Grupo muscular / enfoque de cada rutina, deducido del texto. Gana la primera regla que encaje.
GROUP_RULES = [
    ("Calentamiento", r"calentamiento"),
    ("Cuerpo-Mente", r"yoga|pilates|estira|medita|movilidad|relaja|respira|calma"),
    ("Core", r"abdom|\bcore\b|\babs\b"),
    ("Pierna y glúteo", r"pierna|gl[uú]te|tren inferior|inferior|cu[aá]dri"),
    ("Torso", r"torso|tren superior|superior|brazo|pecho|espalda|hombro|b[ií]ceps|tr[ií]ceps"),
    ("Fullbody", r"full ?body|cuerpo completo|todo el cuerpo|total body|amrap|emom|for time|cross house"),
    ("Cardio", r"hiit|cardio|t[aá]bata|combat|dance|music|energy|reacci|nonstop|intensity|quema|salta"),
]
GROUPS = [g for g, _ in GROUP_RULES]
# Rutinas que no son un entrenamiento normal (infantiles, tests, programas de embarazo/posparto):
# no se proponen nunca, pero siguen en el buscador.
SKIP_RX = re.compile(r"fuertakids|test de|embaraz|suelo p[eé]lvico|postparto|posparto|prenatal", re.IGNORECASE)

# Campos que se guardan de cada rutina (lo demás se calcula al cargar).
RAW_FIELDS = ["id", "title", "url", "durationMinutes", "format", "intensity", "location", "trainingType",
              "materials", "trainers", "tags", "summary", "description", "valuation", "totalViews",
              "publishDate", "previewImage"]
POST_URL = "https://webapp.fuertafit.com/#/post/"


def _group(it):
    head = " ".join([it["title"], it.get("summary") or "", it.get("methodology") or "", *(it.get("tags") or [])])
    # El título manda: algún resumen de FuertaFit está mal («Tren superior 3» dice «tren inferior»).
    for text in (it["title"], head):
        for name, rx in GROUP_RULES:
            if re.search(rx, text, re.IGNORECASE):
                return name
    # En la descripción larga "calentamiento" o "estiramientos" suelen ser parte de la sesión, no su tema.
    for name, rx in GROUP_RULES[2:]:
        if re.search(rx, it.get("description") or "", re.IGNORECASE):
            return name
    return {"Cardiovascular": "Cardio", "Cuerpo-Mente": "Cuerpo-Mente",
            "Calentamiento": "Calentamiento"}.get(it.get("trainingType"), "Fullbody")


def _field(desc, label):
    m = re.search(label + r"\s*:\s*(.+?)(?=\s*◽|$)", desc or "", re.IGNORECASE)
    if not m:
        return None
    # Algunas descripciones pegan detrás listas de canciones o ejercicios: nos quedamos con la etiqueta.
    value = re.split(r"[.\[👉🏋]|\s{2,}|CANCIONES", m.group(1))[0].strip()
    return value[:30] or None


def enrich(raw):
    """Rutina guardada -> rutina con metodología, grupo y marca de "no proponer"."""
    it = dict(raw)
    desc = it.get("description", "")
    it["methodology"] = _field(desc, "Metodología")
    it["methodologyDetail"] = _field(desc, "Metodología especifica")
    it["materials"] = it.get("materials") or ["No Material"]
    it["group"] = _group(it)
    it["skip"] = bool(SKIP_RX.search(" ".join([it["title"], it.get("summary") or "", *(it.get("tags") or [])])))
    return it


def usable(it):
    # Fuera vídeos sin duración y presentaciones de programas (no son entrenamientos).
    return bool(it.get("durationMinutes")) and not re.match(r"\s*(presentaci|introducci)", it["title"], re.IGNORECASE)


def clean_item(it):
    """Valida y limpia una rutina recibida del marcador. None si no vale."""
    if not isinstance(it, dict) or not isinstance(it.get("id"), int) or not isinstance(it.get("title"), str):
        return None
    clean = {k: it.get(k) for k in RAW_FIELDS}
    clean["url"] = POST_URL + str(it["id"])  # nunca confiamos en la URL que llega
    return clean


class Catalog:
    def __init__(self, items):
        self.items = items                         # rutinas usables, ya clasificadas
        self.by_id = {it["id"]: it for it in items}


_cache = {}  # base de datos -> (sello, Catalog)
_lock = threading.Lock()


def get(env):
    """Catálogo clasificado. Se recarga solo si cambió la tabla (nº de filas o última escritura)."""
    cr = env.cr
    cr.execute("SELECT count(*), max(write_date) FROM fuerta_routine")
    stamp = cr.fetchone()
    hit = _cache.get(cr.dbname)
    if hit and hit[0] == stamp:
        return hit[1]
    with _lock:
        cr.execute("SELECT data FROM fuerta_routine ORDER BY fuerta_id")
        cat = Catalog([it for it in (enrich(row[0]) for row in cr.fetchall()) if usable(it)])
        _cache[cr.dbname] = (stamp, cat)
    return cat


def material_ok(it, mats):
    # Las rutinas suelen listar alternativas ("Casero o Mancuernas"): basta con tener una.
    return mats is None or any(m in mats for m in it["materials"])


def _norm(text):
    return (text or "").lower()


def search(cat, q=None, types=None, groups=None, intensities=None, materials=None,
           min_minutes=None, max_minutes=None, methodology=None, offset=0, limit=30):
    words = _norm(q).split()
    out = []
    for it in cat.items:
        if types and it.get("trainingType") not in types:
            continue
        if groups and it["group"] not in groups:
            continue
        if intensities and it.get("intensity") not in intensities:
            continue
        if not material_ok(it, materials or None):
            continue
        d = it["durationMinutes"]
        if (min_minutes and d < min_minutes) or (max_minutes and d > max_minutes):
            continue
        if methodology and _norm(methodology) not in _norm(it.get("methodology")):
            continue
        if words:
            hay = _norm(" ".join([it["title"], it.get("summary") or "", it.get("methodology") or "", it["group"],
                                  it.get("trainingType") or "", " ".join(it.get("trainers") or [])]))
            if not all(w in hay for w in words):
                continue
        out.append(it)
    # Lo más reciente primero.
    out.sort(key=lambda it: it.get("publishDate") or "", reverse=True)
    return {"total": len(out), "items": out[offset:offset + limit]}


def meta(cat):
    def counts(key):
        out = {}
        for it in cat.items:
            vals = it.get(key)
            for v in (vals if isinstance(vals, list) else [vals]):
                if v:
                    out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    return {
        "total": len(cat.items),
        "types": counts("trainingType"),
        "intensities": counts("intensity"),
        "materials": counts("materials"),
        "methodologies": counts("methodology"),
        "groups": {g: sum(1 for it in cat.items if it["group"] == g) for g in GROUPS},
    }
