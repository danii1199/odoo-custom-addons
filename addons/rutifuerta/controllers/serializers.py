"""Presentación de los datos del modelo como JSON para el navegador."""


def routine(it):
    """Rutina sin la descripción larga, para mandar al navegador."""
    return {k: v for k, v in it.items() if k != "description"}


def history_entry(by_id, pid, day):
    return {"postId": pid, "doneOn": day, **(routine(by_id[pid]) if pid in by_id else {})}


def calendar(by_id, plans, status, history):
    """Días del calendario: {día: {note, source, blocks, done, status, statusNote, extra}}.

    `by_id` del catálogo, `plans` de fuerta.plan.get_plans, `status` de fuerta.day.status.get_status y
    `history` [(post_id, día)] de fuerta.history.between.
    """
    done = {}
    for pid, day in history:
        done.setdefault(day, []).append(pid)
    out = {}
    for day in sorted(set(plans) | set(done) | set(status)):
        p = plans.get(day, {})
        out[day] = {
            "note": p.get("note"),
            "source": p.get("source"),
            "blocks": [routine(by_id[i]) for i in p.get("postIds", []) if i in by_id],
            "done": done.get(day, []),
            "status": status.get(day, {}).get("status"),
            "statusNote": status.get(day, {}).get("note"),
            # Hechas ese día que no estaban en el plan (p. ej. desde "Hoy" o el catálogo).
            "extra": [routine(by_id[i]) for i in done.get(day, [])
                      if i in by_id and i not in p.get("postIds", [])],
        }
    return out
