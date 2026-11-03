"""Gastos pasa a pedir el grupo «Gastos compartidos: web": quien ya era miembro con cuenta lo conserva (una vez)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["gastos.miembro"].with_context(active_test=False).search([("user_id", "!=", False)])._dar_acceso_web()
