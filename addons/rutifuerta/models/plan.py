"""Rutinas planificadas por día (calendario de cada usuario). Una línea por bloque, en orden."""
from datetime import timedelta

from odoo import api, fields, models

from ..services import catalog, planner
from ..services.dates import today


class FuertaPlan(models.Model):
    _name = "fuerta.plan"
    _description = "Rutina planificada"
    _order = "day, sequence, id"

    user_id = fields.Many2one("res.users", "Usuario", required=True, index=True, ondelete="cascade",
                              default=lambda self: self.env.user)
    day = fields.Date("Día", required=True, index=True)
    sequence = fields.Integer("Orden", default=0)
    routine_id = fields.Many2one("fuerta.routine", "Rutina", required=True, ondelete="cascade")
    fuerta_id = fields.Integer(related="routine_id.fuerta_id", store=True, string="Id en FuertaFit")
    duration_minutes = fields.Integer(related="routine_id.duration_minutes", string="Minutos")
    note = fields.Char("Nota")
    source = fields.Selection([("manual", "A mano"), ("auto", "Automática"), ("bot", "Entrenador")],
                              "Origen", default="manual")
    url = fields.Char(related="routine_id.url", string="Vídeo")
    done = fields.Boolean("Hecha", compute="_compute_done")

    def _compute_done(self):
        history = self.env["fuerta.history"].search([("user_id", "in", self.user_id.ids),
                                                    ("done_on", "in", self.mapped("day"))])
        done = {(h.user_id.id, h.routine_id.id, h.done_on) for h in history}
        for rec in self:
            rec.done = (rec.user_id.id, rec.routine_id.id, rec.day) in done

    # ---------- acciones del backend (lo mismo que los botones de la web) ----------
    def action_mark_done(self):
        for rec in self:
            self.env["fuerta.history"].mark_done([rec.fuerta_id], rec.day.isoformat())

    def action_unmark_done(self):
        for rec in self:
            self.env["fuerta.history"].unmark_done([rec.fuerta_id], rec.day.isoformat())

    def action_plan_this_week(self):
        return self._plan_week_notify(today(self.env))

    def action_plan_next_week(self):
        return self._plan_week_notify(today(self.env) + timedelta(days=7))

    def _plan_week_notify(self, day):
        created = planner.plan_week(self.env, day.isoformat())
        msg = (f"Planificados: {', '.join(sorted(created))}" if created
               else "No había días libres que rellenar (o la semana tipo no tiene grupos).")
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"message": msg, "type": "success" if created else "warning",
                           "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}

    def _mine(self, start, end):
        return self.search([("user_id", "=", self.env.uid), ("day", ">=", start), ("day", "<=", end)])

    @api.model
    def get_plans(self, start, end):
        """{día: {"note": str, "source": str, "postIds": [...]}} entre dos fechas (incluidas)."""
        plans = {}
        for line in self._mine(start, end):
            p = plans.setdefault(line.day.isoformat(), {"note": line.note, "source": line.source, "postIds": []})
            p["postIds"].append(line.fuerta_id)
        return plans

    @api.model
    def save_plan(self, day, post_ids, note=None, source="manual"):
        by_id = catalog.get(self.env).by_id
        ids = [int(pid) for pid in post_ids if int(pid) in by_id]
        routines = self.env["fuerta.routine"].by_fuerta_ids(ids)
        self._mine(day, day).unlink()
        self.create([{"day": day, "sequence": i, "routine_id": routines[pid], "note": note,
                      "source": source if source in ("manual", "auto", "bot") else "manual"}
                     for i, pid in enumerate(ids)])
        return ids

    @api.model
    def delete_plan(self, day):
        self.delete_range(day, day)

    @api.model
    def delete_range(self, start, end):
        self._mine(start, end).unlink()
