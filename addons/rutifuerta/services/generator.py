"""Generador de rutinas por reglas: junta vídeos del catálogo hasta completar el tiempo pedido."""
import random
import re
from datetime import timedelta

from . import catalog
from .catalog import COOLDOWN_TYPE, SIDE_TYPES, WARMUP_TYPE
from .dates import today

# Para la vuelta a la calma preferimos estiramientos/yoga antes que meditación.
COOLDOWN_TITLES = re.compile(r"calma|estira|yoga|movilidad|pilates", re.IGNORECASE)
# Para que calentamiento y estiramiento encajen con la zona del día.
UPPER_RX = re.compile(r"superior|torso|brazo|pecho|espalda|hombro", re.IGNORECASE)
LOWER_RX = re.compile(r"inferior|pierna|gl[uú]te", re.IGNORECASE)


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
        ranked = sorted(main_pool, key=lambda it: w[it["id"]], reverse=True)
        if len(groups) > 1:
            shares = [remaining * 0.6] + [remaining * 0.4 / (len(groups) - 1)] * (len(groups) - 1)
            passes = [([it for it in ranked if it["group"] == g], share) for g, share in zip(groups, shares)]
            ranked = sorted(ranked, key=lambda it: it["group"] != groups[0])  # estable: mantiene el azar dentro
        else:
            passes = []
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
        score = abs(total - minutes) * 10 + len(blocks)
        if best is None or score < best[0]:
            best = (score, blocks)
        if total == minutes:
            break

    blocks = best[1] if best else []
    return {
        "minutes": minutes,
        "total": sum(b["durationMinutes"] for b in blocks),
        "blocks": blocks,
        "poolSize": len(main_pool),
    }
