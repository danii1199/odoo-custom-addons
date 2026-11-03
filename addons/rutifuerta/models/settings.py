"""Ajustes de cada usuario (un registro por usuario con un JSON) y plan automático (ir.cron)."""
import logging

from odoo import api, fields, models

from ..services import planner
from .routine import CATALOG_UPDATED

_logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "autoPlan": False,       # rellenar sola cada semana en el calendario
    # Semana tipo según las guías de la OMS y el ACSM: cada grupo muscular 2 veces por semana con ≥48 h entre
    # sesiones del mismo grupo, cardio 2 días, core 2 días y fin de semana de descanso.
    # 45 min = calentamiento (5-10) + ~25-30 de trabajo + vuelta a la calma/estiramientos (5-10).
    "dailyMinutes": 45,
    # Grupos de cada día de la semana (0 = lunes). Lista vacía = descanso. El primero es el principal del día.
    "week": {"0": ["Pierna y glúteo", "Core"], "1": ["Torso"], "2": ["Cardio"],
             "3": ["Pierna y glúteo", "Core"], "4": ["Torso", "Cardio"], "5": [], "6": []},
    "materials": [],         # material disponible; vacío = cualquiera
    "warmup": True,
    "cooldown": True,
    "preferences": "",       # texto libre para el entrenador con IA (solo si hay API key)
}


class FuertaSettings(models.Model):
    _name = "fuerta.settings"
    _description = "Ajustes de Rutifuerta"
    _rec_name = "user_id"

    user_id = fields.Many2one("res.users", "Usuario", required=True, index=True, ondelete="cascade",
                              default=lambda self: self.env.user)
    values = fields.Json("Ajustes", default=dict)
    # Los mismos ajustes como campos, para editarlos desde el backend (se leen y escriben en `values`).
    auto_plan = fields.Boolean("Rellenar el calendario automáticamente", compute="_compute_auto_plan",
                               inverse="_inverse_fields", store=True)  # guardado: el cron busca por él
    daily_minutes = fields.Integer("Minutos por sesión", compute="_compute_fields", inverse="_inverse_fields")
    warmup = fields.Boolean("Empezar con calentamiento", compute="_compute_fields", inverse="_inverse_fields")
    cooldown = fields.Boolean("Terminar con estiramiento / yoga", compute="_compute_fields", inverse="_inverse_fields")
    materials = fields.Char("Material que tengo", compute="_compute_fields", inverse="_inverse_fields",
                            help="Separado por comas, tal y como aparece en el catálogo. Vacío = cualquiera.")
    preferences = fields.Text("Lo que el entrenador debe saber de ti", compute="_compute_fields",
                              inverse="_inverse_fields")
    week_0 = fields.Many2many("fuerta.group", "fuerta_settings_week_0_rel", string="Lunes",
                              compute="_compute_fields", inverse="_inverse_fields")
    week_1 = fields.Many2many("fuerta.group", "fuerta_settings_week_1_rel", string="Martes",
                              compute="_compute_fields", inverse="_inverse_fields")
    week_2 = fields.Many2many("fuerta.group", "fuerta_settings_week_2_rel", string="Miércoles",
                              compute="_compute_fields", inverse="_inverse_fields")
    week_3 = fields.Many2many("fuerta.group", "fuerta_settings_week_3_rel", string="Jueves",
                              compute="_compute_fields", inverse="_inverse_fields")
    week_4 = fields.Many2many("fuerta.group", "fuerta_settings_week_4_rel", string="Viernes",
                              compute="_compute_fields", inverse="_inverse_fields")
    week_5 = fields.Many2many("fuerta.group", "fuerta_settings_week_5_rel", string="Sábado",
                              compute="_compute_fields", inverse="_inverse_fields")
    week_6 = fields.Many2many("fuerta.group", "fuerta_settings_week_6_rel", string="Domingo",
                              compute="_compute_fields", inverse="_inverse_fields")

    _one_per_user = models.Constraint("UNIQUE (user_id)", "Ese usuario ya tiene ajustes.")

    @api.depends("values")
    def _compute_auto_plan(self):
        for rec in self:
            rec.auto_plan = bool((rec.values or {}).get("autoPlan"))

    @api.depends("values")
    def _compute_fields(self):
        groups = self.env["fuerta.group"].search([])
        for rec in self:
            v = {**DEFAULT_SETTINGS, **(rec.values or {})}
            rec.daily_minutes = v["dailyMinutes"]
            rec.warmup, rec.cooldown = bool(v["warmup"]), bool(v["cooldown"])
            rec.materials = ", ".join(v["materials"] or [])
            rec.preferences = v["preferences"] or False
            for i in range(7):
                names = v["week"].get(str(i)) or []
                # en el orden guardado: el primero es el grupo principal del día
                rec[f"week_{i}"] = [g.id for n in names for g in groups if g.name == n]

    def _inverse_fields(self):
        for rec in self:
            rec.values = {**(rec.values or {}),
                          "autoPlan": rec.auto_plan,
                          "dailyMinutes": rec.daily_minutes or DEFAULT_SETTINGS["dailyMinutes"],
                          "warmup": rec.warmup, "cooldown": rec.cooldown,
                          "materials": [m.strip() for m in (rec.materials or "").split(",") if m.strip()],
                          "preferences": rec.preferences or "",
                          "week": {str(i): rec[f"week_{i}"].mapped("name") for i in range(7)}}

    @api.model
    def action_my_settings(self):
        """Abre (y crea si hace falta) los ajustes del usuario actual en el backend."""
        rec = self._mine() or self.create({})
        return {"type": "ir.actions.act_window", "name": "Mis ajustes", "res_model": self._name,
                "res_id": rec.id, "view_mode": "form", "target": "current"}

    def _mine(self):
        return self.search([("user_id", "=", self.env.uid)], limit=1)

    @api.model
    def get_settings(self):
        saved = self._mine().values or {}
        out = {k: saved.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
        # La fecha del catálogo es común a todos (la pone la importación).
        out["catalogUpdated"] = self.env["ir.config_parameter"].sudo().get_str(CATALOG_UPDATED) or None
        return out

    @api.model
    def save_settings(self, values):
        rec = self._mine() or self.create({})
        rec.values = {**(rec.values or {}), **{k: v for k, v in values.items() if k in DEFAULT_SETTINGS}}
        return self.get_settings()

    @api.model
    def _cron_auto_plan(self):
        """Cada 30 min: a quien tenga el plan automático, rellenarle los días vacíos de la semana."""
        for rec in self.sudo().search([("auto_plan", "=", True), ("user_id.active", "=", True)]):
            if not rec.user_id.has_group("rutifuerta.group_fuerta_user"):
                continue  # ya no tiene acceso al módulo
            env = self.env(user=rec.user_id.id, su=False)
            try:
                with self.env.cr.savepoint():  # que el fallo de un usuario no afecte a los demás
                    created = planner.plan_week(env)
                if created:
                    _logger.info("[auto] %s: planificados %s", rec.user_id.login, ", ".join(created))
            except Exception:
                _logger.exception("[auto] Error planificando para %s", rec.user_id.login)


class FuertaGroup(models.Model):
    """Grupos musculares / enfoques del catálogo (fijos, los de services.catalog.GROUPS), para elegirlos con
    etiquetas en la semana tipo del backend."""
    _name = "fuerta.group"
    _description = "Grupo muscular"
    _order = "sequence"

    name = fields.Char("Grupo", required=True, readonly=True)
    sequence = fields.Integer(readonly=True)

    _name_uniq = models.Constraint("UNIQUE (name)", "Ese grupo ya existe.")
