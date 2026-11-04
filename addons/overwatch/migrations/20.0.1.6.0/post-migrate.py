"""La búsqueda de actualizaciones pasa de semanal a diaria (decisión del usuario, 2026-11-04).

La tarea es noupdate (para no pisar cambios hechos a mano): por eso se cambia aquí y no en data/ir_cron.xml.
Próxima: mañana a las 4:00 UTC (5:00 en Madrid en invierno)."""
from datetime import datetime, time, timedelta

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref("overwatch.cron_check_updates", raise_if_not_found=False)
    if cron:
        manana = datetime.combine(datetime.utcnow().date() + timedelta(days=1), time(4, 0))
        cron.write({"name": "Overwatch: buscar actualizaciones (diaria)", "interval_number": 1,
                    "interval_type": "days", "nextcall": manana})
