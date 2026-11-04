"""Reclasifica el catálogo: los Cardio-Fuerza y demás vídeos de fuerza que hablan de «cardio» ya no son del grupo
Cardio (catalog._group). Recalcula las columnas guardadas de `fuerta.routine` (la web lee el JSON y se entera sola)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    recs = env["fuerta.routine"].with_context(active_test=False).search([])
    env.add_to_compute(recs._fields["group"], recs)
    recs.flush_recordset()
