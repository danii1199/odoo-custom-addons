"""Migra los datos de la web antigua (base de datos `rutinas`) a Odoo. Solo LEE `rutinas`; no la modifica.

Se ejecuta dentro del contenedor con el shell de Odoo, desde la raíz del repo:

    sg docker -c "docker exec -i -e MIGRAR_LOGIN=admin odoo odoo shell -d rutifuerta --no-http" \
        < addons/rutifuerta/scripts/migrar_rutinas.py

- Catálogo: se añade/actualiza (común a todos los usuarios).
- Historial, plan, estados de día y ajustes: se asignan al usuario MIGRAR_LOGIN (por defecto `admin`).
  Si ese usuario ya tiene datos de calendario/historial, no se toca nada (para no duplicar).
"""
import json
import os

import psycopg2

from odoo.addons.rutifuerta.models.routine import CATALOG_UPDATED
from odoo.addons.rutifuerta.models.settings import DEFAULT_SETTINGS

env = env  # noqa: F821  (lo inyecta `odoo shell`)
login = os.environ.get("MIGRAR_LOGIN", "admin")
user = env["res.users"].search([("login", "=", login)])
if not user:
    raise SystemExit(f"No existe el usuario {login!r} en Odoo")
uenv = env(user=user.id, su=False)

old = psycopg2.connect(os.environ["RUTINAS_DATABASE_URL"])
old.set_session(readonly=True)
cur = old.cursor()


def rows(sql):
    cur.execute(sql)
    return cur.fetchall()


# ---- catálogo (común) ----
items = [r[0] for r in rows("SELECT data FROM catalog ORDER BY id")]
res = env["fuerta.routine"].import_items(items)
print(f"Catálogo: {res['added']} nuevas, {res['updated']} actualizadas, {res['total']} usables")

# ---- datos del usuario ----
mine = [("user_id", "=", user.id)]
if any(env[m].search_count(mine) for m in ("fuerta.history", "fuerta.plan", "fuerta.day.status")):
    print(f"{login} ya tiene historial/plan/estados en Odoo: no los migro otra vez.")
else:
    routines = env["fuerta.routine"].by_fuerta_ids([r[0] for r in rows("SELECT id FROM catalog")])
    lost = set()

    hist = []
    for pid, day in rows("SELECT post_id, done_on FROM history ORDER BY done_on"):
        if pid in routines:
            hist.append({"user_id": user.id, "routine_id": routines[pid], "done_on": day})
        else:
            lost.add(pid)
    env["fuerta.history"].create(hist)

    plan = []
    for day, pos, pid, note, source in rows("SELECT day, position, post_id, note, source FROM plan ORDER BY day, position"):
        if pid in routines:
            plan.append({"user_id": user.id, "day": day, "sequence": pos, "routine_id": routines[pid], "note": note,
                         "source": source if source in ("manual", "auto", "bot") else "manual"})
        else:
            lost.add(pid)
    env["fuerta.plan"].create(plan)

    status = [{"user_id": user.id, "day": d, "status": st, "note": note}
              for d, st, note in rows("SELECT day, status, note FROM day_status ORDER BY day")]
    env["fuerta.day.status"].create(status)
    print(f"{login}: {len(hist)} hechas, {len(plan)} rutinas planificadas, {len(status)} días especiales")
    if lost:
        print(f"Ojo: {len(lost)} rutinas del historial/plan ya no están en el catálogo y no se migran: {sorted(lost)}")

# ---- ajustes ----
saved = {k: json.loads(v) for k, v in rows("SELECT key, value FROM settings")}
uenv["fuerta.settings"].save_settings({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
if saved.get("catalogUpdated"):  # conservar la fecha real de la última actualización, no la de la migración
    env["ir.config_parameter"].sudo().set_str(CATALOG_UPDATED, saved["catalogUpdated"])
print(f"Ajustes de {login}: {sorted(k for k in saved if k in DEFAULT_SETTINGS)}")

env.cr.commit()
print("Migración terminada.")
