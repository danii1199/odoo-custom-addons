"""Estados especiales de un día: 'skipped' (saltado), 'moved' (su rutina se movió), 'away' (vacaciones/fuera)."""
from odoo import api, fields, models

from ..services.dates import days_between


class FuertaDayStatus(models.Model):
    _name = "fuerta.day.status"
    _description = "Estado de un día"
    _order = "day"

    user_id = fields.Many2one("res.users", "Usuario", required=True, index=True, ondelete="cascade",
                              default=lambda self: self.env.user)
    day = fields.Date("Día", required=True, index=True)
    status = fields.Selection([("skipped", "Saltado"), ("moved", "Movido"), ("away", "Fuera")], "Estado",
                              required=True)
    note = fields.Char("Nota")

    _one_per_day = models.Constraint("UNIQUE (user_id, day)", "Ese día ya tiene un estado.")

    def _mine(self, start, end, extra=()):
        return self.search([("user_id", "=", self.env.uid), ("day", ">=", start), ("day", "<=", end), *extra])

    @api.model
    def get_status(self, start, end):
        return {r.day.isoformat(): {"status": r.status, "note": r.note} for r in self._mine(start, end)}

    @api.model
    def set_status(self, start, end, status, note=None):
        existing = {r.day.isoformat(): r for r in self._mine(start, end)}
        new = []
        for d in days_between(start, end):
            if d in existing:
                existing[d].write({"status": status, "note": note})
            else:
                new.append({"day": d, "status": status, "note": note})
        self.create(new)

    @api.model
    def clear_status(self, start, end):
        self._mine(start, end).unlink()

    @api.model
    def clear_away(self, start, end):
        self._mine(start, end, [("status", "=", "away")]).unlink()

    @api.model
    def away_days(self, since):
        """[(día, motivo)] marcados como fuera desde `since`, en orden."""
        recs = self.search([("user_id", "=", self.env.uid), ("status", "=", "away"), ("day", ">=", since)])
        return [(r.day.isoformat(), r.note) for r in recs]
