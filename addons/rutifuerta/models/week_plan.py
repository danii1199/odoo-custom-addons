"""Semanas tipo («Mis semanas»): las recomendadas (comunes, data/week_recommended.xml) y las que guarda cada usuario.
Usar una copia sus grupos y sus minutos a los ajustes, que es lo que usan «Generar…» y el plan automático."""
from odoo import api, fields, models
from odoo.exceptions import UserError

DAY_SHORT = ["L", "M", "X", "J", "V", "S", "D"]


def clean_week(week):
    """{"0".."6": [grupos]} con todas las claves y solo listas de texto."""
    week = week or {}
    return {str(i): [str(g) for g in (week.get(str(i)) or [])] for i in range(7)}


class FuertaWeekPlan(models.Model):
    _name = "fuerta.week.plan"
    _description = "Semana tipo guardada"
    _order = "days_count, minutes, recommended desc, sequence, id"

    name = fields.Char("Nombre", required=True)
    # Vacío en las recomendadas (comunes, de solo lectura); las demás son de su usuario.
    user_id = fields.Many2one("res.users", "Usuario", index=True, ondelete="cascade", copy=False,
                              default=lambda self: self.env.user)
    recommended = fields.Boolean("Recomendada", readonly=True, copy=False,
                                 help="Diseñada según las pautas de ACSM/NSCA. No se edita: guárdala como nueva para cambiarla.")
    description = fields.Text("Por qué así")
    minutes = fields.Integer("Minutos por sesión", default=45, required=True)
    sequence = fields.Integer("Orden", default=10)
    week = fields.Json("Semana", default=lambda self: clean_week({}))  # fuente de verdad (con el orden de grupos)
    # El «mundo» de la semana: cuántos días se entrena (3 días, 4 días, 5 días…). Se agrupan por él.
    days_count = fields.Integer("Días de entreno", compute="_compute_days_count", store=True)
    summary = fields.Char("Resumen", compute="_compute_fields")
    # Los mismos días como etiquetas, para editarlos desde el backend (se leen y escriben en `week`).
    day_0 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_0_rel", string="Lunes",
                             compute="_compute_fields", inverse="_inverse_days")
    day_1 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_1_rel", string="Martes",
                             compute="_compute_fields", inverse="_inverse_days")
    day_2 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_2_rel", string="Miércoles",
                             compute="_compute_fields", inverse="_inverse_days")
    day_3 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_3_rel", string="Jueves",
                             compute="_compute_fields", inverse="_inverse_days")
    day_4 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_4_rel", string="Viernes",
                             compute="_compute_fields", inverse="_inverse_days")
    day_5 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_5_rel", string="Sábado",
                             compute="_compute_fields", inverse="_inverse_days")
    day_6 = fields.Many2many("fuerta.group", "fuerta_week_plan_day_6_rel", string="Domingo",
                             compute="_compute_fields", inverse="_inverse_days")

    _name_per_user = models.Constraint("UNIQUE (user_id, name)", "Ya tienes una semana con ese nombre.")

    @api.depends("week")
    def _compute_days_count(self):
        for rec in self:
            rec.days_count = sum(1 for groups in clean_week(rec.week).values() if groups)

    @api.depends("week")
    def _compute_fields(self):
        groups = self.env["fuerta.group"].search([])
        for rec in self:
            week = clean_week(rec.week)
            rec.summary = " · ".join(f"{DAY_SHORT[i]} {' + '.join(week[str(i)])}"
                                     for i in range(7) if week[str(i)]) or "Todo descanso"
            for i in range(7):
                rec[f"day_{i}"] = [g.id for n in week[str(i)] for g in groups if g.name == n]

    def copy_data(self, default=None):
        """Duplicar (también una recomendada) da una semana propia y editable."""
        vals_list = super().copy_data(default)
        if "name" not in (default or {}):
            for rec, vals in zip(self, vals_list):
                vals["name"] = f"{rec.name} (mía)"
        return vals_list

    def _inverse_days(self):
        for rec in self:
            rec.week = {str(i): rec[f"day_{i}"].mapped("name") for i in range(7)}

    # ---------- para la web (y el backend) ----------
    @api.model
    def get_weeks(self):
        """Las recomendadas y las del usuario, ordenadas por días y minutos (las recomendadas primero)."""
        return [{"id": w.id, "name": w.name, "week": clean_week(w.week), "days": w.days_count, "minutes": w.minutes,
                 "recommended": w.recommended, "description": w.description or ""}
                for w in self.search(["|", ("user_id", "=", self.env.uid), ("recommended", "=", True)]).sorted(
                    lambda w: (w.days_count, w.minutes, not w.recommended, w.sequence, w.id))]

    @api.model
    def save_week(self, name, week, minutes, week_id=None):
        """Crea o actualiza (con `week_id`, solo las propias) una semana guardada. Devuelve su id."""
        name = (name or "").strip()
        if not name:
            raise UserError("Ponle un nombre a la semana.")
        vals = {"name": name, "week": clean_week(week), "minutes": max(5, int(minutes))}
        if self.search_count([("user_id", "=", self.env.uid), ("name", "=", name), ("id", "!=", int(week_id or 0))]):
            raise UserError(f"Ya tienes una semana llamada «{name}».")
        if week_id:
            rec = self.search([("id", "=", int(week_id)), ("user_id", "=", self.env.uid)])
            if not rec:
                raise UserError("Esa semana ya no existe.")
            rec.write(vals)
            return rec.id
        last = self.search([("user_id", "=", self.env.uid)], order="sequence desc", limit=1)
        return self.create({**vals, "sequence": last.sequence + 1}).id

    @api.model
    def delete_week(self, week_id):
        self.search([("id", "=", int(week_id)), ("user_id", "=", self.env.uid)]).unlink()

    def action_use(self):
        """Backend: la convierte en la semana tipo de los ajustes (la que usan «Generar…» y el plan automático)."""
        self.ensure_one()
        self.env["fuerta.settings"].save_settings({"week": clean_week(self.week), "dailyMinutes": self.minutes})
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"message": f"«{self.name}» es ahora tu semana tipo ({self.minutes} min por sesión).",
                           "type": "success"}}
