"""Generador de rutinas por reglas: junta vídeos del catálogo hasta completar el tiempo pedido."""
import random
import re
from datetime import timedelta

from . import catalog
from .catalog import CARDIO_TYPE, COOLDOWN_TYPE, SIDE_TYPES, STRENGTH_TYPES, WARMUP_TYPE
from .dates import today

# Para la vuelta a la calma preferimos estiramientos/yoga antes que meditación.
COOLDOWN_TITLES = re.compile(r"calma|estira|yoga|movilidad|pilates", re.IGNORECASE)
# Para que calentamiento y estiramiento encajen con la zona del día.
UPPER_RX = re.compile(r"superior|torso|brazo|pecho|espalda|hombro", re.IGNORECASE)
LOWER_RX = re.compile(r"inferior|pierna|gl[uú]te", re.IGNORECASE)
# Días de fuerza en los que también valen los Fullbody de fuerza (Cardio-Fuerza, híbridos…) para rellenar.
STRENGTH_GROUPS = {"Torso", "Pierna y glúteo"}
# Cardio como grupo secundario: mínimo de minutos (el cardio intenso de FuertaFit es casi todo de 15-20 min).
CARDIO_MIN = 20


def generate(env, params):
    cat = catalog.get(env)
    minutes = max(5, int(params.get("minutes", 30)))
    tolerance = int(params.get("tolerance", 5))
    cooldown = bool(params.get("cooldown", False))
    warmup = bool(params.get("warmup", False))
    avoid_days = int(params.get("avoidDays", 14))
    exclude = set(params.get("exclude", []))
    types = params.get("types") or []
    groups = params.get("groups") or []
    intensities = params.get("intensities") or []
    mats = params.get("materials")
    rng = random.Random(params.get("seed"))

    hist = env["fuerta.history"].recent(avoid_days)
    recent_ids = {pid for pid, _ in hist}
    # Zona trabajada en los últimos 2 días -> se penaliza para alternar.
    two_days = (today(env) - timedelta(days=2)).isoformat()
    recent_zones = {
        cat.by_id[pid].get("methodology") for pid, d in hist if d >= two_days and pid in cat.by_id
    }

    pool = [it for it in cat.items
            if it["id"] not in recent_ids and it["id"] not in exclude and catalog.material_ok(it, mats)]
    def main_ok(it):
        tt = it.get("trainingType")
        if it["skip"] or (groups and it["group"] not in groups) or (types and tt not in types):
            return False
        if intensities and it.get("intensity") not in intensities:
            return False
        # Calentamientos y estiramientos solo como bloque principal si se piden expresamente.
        return bool(types) or tt not in SIDE_TYPES or it["group"] in groups

    main_pool = [it for it in pool if main_ok(it)]
    # Los Fullbody de fuerza cuentan como fuerza en un día de Torso o Pierna: solo rellenan, tras el bloque principal.
    extra_pool = [it for it in pool if it["group"] == "Fullbody" and it.get("trainingType") in STRENGTH_TYPES
                  and not it["skip"] and "Fullbody" not in groups and not types and not intensities] \
        if STRENGTH_GROUPS & set(groups) else []
    def side_fits(it):
        """Descarta calentamientos/estiramientos de la otra mitad del cuerpo (p. ej. «tren superior» en día de pierna)."""
        legs, upper = "Pierna y glúteo" in groups, "Torso" in groups
        if legs and not upper and UPPER_RX.search(it["title"]):
            return False
        return not (upper and not legs and LOWER_RX.search(it["title"]))

    short = [it for it in pool if it["durationMinutes"] <= 15 and not it["skip"]]
    warm_all = [it for it in short if it.get("trainingType") == WARMUP_TYPE]
    warm_pool = [it for it in warm_all if side_fits(it)] or warm_all
    cool_all = [it for it in short if it.get("trainingType") == COOLDOWN_TYPE
                and COOLDOWN_TITLES.search(it["title"])] \
        or [it for it in short if it.get("trainingType") == COOLDOWN_TYPE]
    cool_pool = [it for it in cool_all if side_fits(it)] or cool_all

    def weight(it):
        w = 1.0 + (it.get("valuation") or 3) / 5
        if it.get("methodology") in recent_zones:
            w *= 0.3
        return w * rng.random()

    def stem(it):
        # "Brazos 3" y "Brazos 7" son la misma serie: mejor no repetirla en una sesión.
        return re.sub(r"[\d\W_]+", " ", it["title"]).strip().lower()

    def fill(remaining, chosen):
        """Añade rutinas hasta completar el tiempo.

        Con varios grupos, el primero es el principal: se lleva ~60 % del tiempo y es el que rellena lo que sobre;
        los demás se reparten el resto con una rutina cada uno.
        """
        w = {it["id"]: weight(it) for it in main_pool}
        w.update({it["id"]: weight(it) * 0.6 for it in extra_pool})
        ranked = sorted(main_pool, key=lambda it: w[it["id"]], reverse=True)
        if len(groups) > 1:
            shares = [remaining * 0.6] + [remaining * 0.4 / (len(groups) - 1)] * (len(groups) - 1)
            # El cardio, intenso y de verdad (tipo Cardiovascular): necesita su rato aunque sea el grupo secundario.
            shares = [max(sh, min(CARDIO_MIN, remaining / 2)) if g == "Cardio" and i else sh
                      for i, (g, sh) in enumerate(zip(groups, shares))]
            passes = [([it for it in ranked if it["group"] == g and (g != "Cardio" or it.get("trainingType") == CARDIO_TYPE)],
                       share) for g, share in zip(groups, shares)]
        else:
            passes = []
        # Relleno: primero el grupo principal (con los Fullbody de fuerza, que cuentan como él), luego el resto.
        if groups:
            first = {groups[0]} | ({"Fullbody"} if groups[0] in STRENGTH_GROUPS else set())
            ranked = sorted(ranked + extra_pool, key=lambda it: (it["group"] not in first, -w[it["id"]]))
        used_zones, used_stems = set(), set()
        for candidates, limit in passes + [(ranked, None)]:
            for it in candidates:
                if remaining < 5:
                    return remaining
                d = it["durationMinutes"]
                # Los grupos secundarios no pueden pasarse de su parte; el principal sí, con la tolerancia.
                slack = 0 if limit is not None and it["group"] != groups[0] else tolerance
                if d > min(limit or remaining, remaining) + slack or it in chosen:
                    continue
                zone = it.get("methodology")
                if (zone and zone in used_zones or stem(it) in used_stems) and rng.random() < 0.8:
                    continue  # preferimos variar de zona y de serie dentro de la sesión
                chosen.append(it)
                used_zones.add(zone)
                used_stems.add(stem(it))
                remaining -= d
                if limit is not None:
                    break  # una por grupo en la primera pasada
        return remaining

    best = None
    for _ in range(300):
        head = [rng.choice(warm_pool)] if warmup and warm_pool and minutes >= 20 else []
        tail = [rng.choice(cool_pool)] if cooldown and cool_pool and minutes >= 25 else []
        remaining = minutes - sum(b["durationMinutes"] for b in head + tail)
        main = []
        fill(remaining, main)
        blocks = head + main + tail
        total = sum(b["durationMinutes"] for b in blocks)
        # Un grupo pedido que se queda sin rutina (p. ej. el cardio de un día de Torso + Cardio) pesa más que un minuto.
        missing = len(set(groups) - {b["group"] for b in main})
        score = abs(total - minutes) * 10 + missing * 100 + len(blocks)
        if best is None or score < best[0]:
            best = (score, blocks)
        if total == minutes and not missing:
            break

    blocks = best[1] if best else []
    return {
        "minutes": minutes,
        "total": sum(b["durationMinutes"] for b in blocks),
        "blocks": blocks,
        "poolSize": len(main_pool),
    }
