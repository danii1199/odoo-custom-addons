"""Plan semanal automático: rellena el calendario según la semana tipo de los ajustes."""
import random
from datetime import date, timedelta

from .dates import today
from .generator import generate


def monday_of(day):
    d = date.fromisoformat(day) if isinstance(day, str) else day
    return d - timedelta(days=d.weekday())


def plan_week(env, start=None, overwrite=False):
    """Rellena la semana que empieza el lunes `start` según los ajustes del plan semanal.

    Solo toca días de hoy en adelante con grupos asignados; sin `overwrite` respeta los que ya tienen plan.
    Con `overwrite`, los días que ahora son de descanso pierden su plan automático (los manuales se quedan).
    Devuelve {día: [ids]} de lo generado.
    """
    s = env["fuerta.settings"].get_settings()
    plans, status = env["fuerta.plan"], env["fuerta.day.status"]
    now = today(env)
    monday = monday_of(start or now)
    days = [monday + timedelta(i) for i in range(7)]
    existing = plans.get_plans(days[0].isoformat(), days[-1].isoformat())
    blocked = status.get_status(days[0].isoformat(), days[-1].isoformat())  # saltados, movidos o fuera
    # No repetir rutinas dentro de la misma semana.
    used = {pid for d, p in existing.items() for pid in p["postIds"]
            if not overwrite or date.fromisoformat(d) < now}
    created = {}
    for d in days:
        key = d.isoformat()
        groups = s["week"].get(str(d.weekday())) or []
        if overwrite and not groups and d >= now and existing.get(key, {}).get("source") == "auto":
            plans.delete_plan(key)  # ahora es día de descanso: fuera lo que generó una semana tipo anterior
            continue
        if not groups or d < now or key in blocked or (key in existing and not overwrite):
            continue
        ids = _auto_day(env, key, groups, s, used)
        if ids:
            used.update(ids)
            created[key] = ids
    return created


def plan_day(env, day, minutes=None):
    """Genera un día suelto con los ajustes del plan semanal (en día de descanso: sin grupo fijo).

    `minutes` sustituye a la duración por defecto solo para este día.
    """
    s = env["fuerta.settings"].get_settings()
    groups = s["week"].get(str(date.fromisoformat(day).weekday())) or []
    monday = monday_of(day)
    week = env["fuerta.plan"].get_plans(monday.isoformat(), (monday + timedelta(6)).isoformat())
    used = {pid for d, p in week.items() if d != day for pid in p["postIds"]}
    return _auto_day(env, day, groups, s, used, minutes)


def _auto_day(env, day, groups, s, used, minutes=None):
    env["fuerta.day.status"].clear_status(day, day)  # generar a mano un día saltado/movido lo vuelve a activar
    res = generate(env, {"minutes": minutes or s["dailyMinutes"], "groups": groups, "materials": s["materials"] or None,
                    "warmup": s["warmup"], "cooldown": s["cooldown"], "exclude": list(used),
                    "seed": f"{day}-{random.random()}"})
    ids = [b["id"] for b in res["blocks"]]
    if ids:
        env["fuerta.plan"].save_plan(day, ids, " + ".join(groups) or "Libre", source="auto")
    return ids
