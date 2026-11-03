"""Marcar unos días como fuera (vacaciones, viaje…), igual que «Vacaciones y ausencias» del calendario de la web."""
from odoo import fields, models
from odoo.exceptions import UserError

from ..services import calendar


class FuertaAwayWizard(models.TransientModel):
    _name = "fuerta.away.wizard"
    _description = "Marcar ausencia"

    date_from = fields.Date("Desde", required=True, default=fields.Date.context_today)
    date_to = fields.Date("Hasta", required=True, default=fields.Date.context_today)
    note = fields.Char("Motivo")
    remove_plans = fields.Boolean("Quitar las rutinas de esos días", default=True,
                                  help="Si no se quitan, se quedan en el calendario marcadas como «no estoy».")

    def action_apply(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError("La fecha final es anterior a la inicial.")
        calendar.set_away(self.env, self.date_from.isoformat(), self.date_to.isoformat(), self.note,
                          self.remove_plans)
        return {"type": "ir.actions.client", "tag": "soft_reload"}
