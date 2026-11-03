"""Rutinas marcadas como hechas (de cada usuario)."""
from datetime import timedelta

from odoo import api, fields, models

from ..services.dates import today


class FuertaHistory(models.Model):
    _name = "fuerta.history"
    _description = "Rutina hecha"
    _order = "done_on desc, id desc"

    user_id = fields.Many2one("res.users", "Usuario", required=True, index=True, ondelete="cascade",
                              default=lambda self: self.env.user)
    routine_id = fields.Many2one("fuerta.routine", "Rutina", required=True, ondelete="cascade")
    fuerta_id = fields.Integer(related="routine_id.fuerta_id", store=True, string="Id en FuertaFit")
    done_on = fields.Date("Hecha el", required=True, index=True)

    # Una misma rutina solo cuenta una vez por día.
    _once_per_day = models.Constraint("UNIQUE (user_id, routine_id, done_on)", "Esa rutina ya está marcada ese día.")

    def _rows(self, domain):
        recs = self.search([("user_id", "=", self.env.uid), *domain])
        return [(r.fuerta_id, r.done_on.isoformat()) for r in recs]

    @api.model
    def recent(self, days):
        """[(id de FuertaFit, día)] de los últimos `days` días, lo más reciente primero."""
        return self._rows([("done_on", ">=", today(self.env) - timedelta(days=days))])

    @api.model
    def between(self, start, end):
        return self._rows([("done_on", ">=", start), ("done_on", "<=", end)])

    @api.model
    def mark_done(self, post_ids, day=None):
        day = day or today(self.env).isoformat()
        routines = self.env["fuerta.routine"].by_fuerta_ids(post_ids)
        have = {r.routine_id.id for r in self.search([("user_id", "=", self.env.uid), ("done_on", "=", day),
                                                       ("routine_id", "in", list(routines.values()))])}
        self.create([{"routine_id": rid, "done_on": day} for rid in set(routines.values()) - have])

    @api.model
    def unmark_done(self, post_ids, day=None):
        day = day or today(self.env).isoformat()
        self.search([("user_id", "=", self.env.uid), ("done_on", "=", day),
                     ("fuerta_id", "in", [int(p) for p in post_ids])]).unlink()
