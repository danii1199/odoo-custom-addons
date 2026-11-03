"""Miembro de un grupo: un contacto (con o sin usuario). Si tiene usuario (interno o de portal), ve el grupo en /apachas:
al añadirlo o invitarlo se le da el grupo «Apachas: web» (_dar_acceso_web)."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class GastosMiembro(models.Model):
    _name = "gastos.miembro"
    _description = "Miembro de un grupo de gastos"
    _order = "grupo_id, name, id"

    grupo_id = fields.Many2one("gastos.grupo", "Grupo", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one("res.partner", "Contacto", required=True, ondelete="restrict")
    # Guardados para que los usuarios de portal los lean sin permiso sobre res.partner / res.users
    name = fields.Char("Nombre", related="partner_id.name", store=True, readonly=True)
    user_id = fields.Many2one("res.users", "Usuario", compute="_compute_user_id", store=True, index=True,
                              help="Usuario del contacto: con él entra en /apachas y ve este grupo.")
    email = fields.Char(related="partner_id.email", string="Correo", readonly=False)
    active = fields.Boolean(default=True, help="Archivado: ya no entra en los repartos nuevos, pero conserva su saldo.")
    currency_id = fields.Many2one(related="grupo_id.currency_id")
    saldo = fields.Monetary("Saldo", compute="_compute_saldo", compute_sudo=True,
                            help="Positivo: le deben; negativo: debe.")

    _uniq_partner = models.Constraint("UNIQUE (grupo_id, partner_id)", "Ese contacto ya está en el grupo.")

    @api.model_create_multi
    def create(self, vals_list):
        miembros = super().create(vals_list)
        miembros._dar_acceso_web()
        return miembros

    def write(self, vals):
        res = super().write(vals)
        if "partner_id" in vals:
            self._dar_acceso_web()
        return res

    def _dar_acceso_web(self):
        """Invitar o añadir a alguien con cuenta a un grupo le da permiso para la web /apachas (decisión del usuario)."""
        grupo_web = self.env.ref("apachas.group_gastos_web")
        usuarios = self.sudo().user_id.filtered(lambda u: grupo_web not in u.all_group_ids)
        if usuarios:
            usuarios.sudo().write({"group_ids": [(4, grupo_web.id)]})

    @api.depends("partner_id.user_ids")
    def _compute_user_id(self):
        for m in self:
            m.user_id = m.partner_id.with_context(active_test=False).user_ids[:1]

    @api.depends("grupo_id.gasto_ids.linea_ids.importe", "grupo_id.gasto_ids.pagador_id",
                 "grupo_id.liquidacion_ids.importe")
    def _compute_saldo(self):
        for grupo in self.grupo_id:
            saldos, f = grupo.saldos_centimos(), grupo._factor()
            for m in self.filtered(lambda x: x.grupo_id == grupo):
                m.saldo = saldos.get(m, 0) / f
        (self - self.filtered("grupo_id")).saldo = 0

    def action_invitar(self):
        """Da acceso de portal (o nada si ya tiene usuario) y Odoo le manda el correo de invitación para crear su
        contraseña. Con esa cuenta ve sus grupos en /apachas."""
        invitados = []
        for m in self:
            if m.user_id:
                continue
            if not m.partner_id.email:
                raise UserError(f"{m.name} no tiene correo: añádelo para poder invitarle.")
            wizard = self.env["portal.wizard"].sudo().with_context(
                active_model="res.partner", active_ids=m.partner_id.ids).create({})
            wizard.user_ids.filtered(lambda u: u.partner_id == m.partner_id).action_grant_access()
            m._dar_acceso_web()
            invitados.append(m.name)
        mensaje = f"Invitación enviada a {', '.join(invitados)}." if invitados else "Ya tenían cuenta."
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "message": mensaje, "next": {"type": "ir.actions.act_window_close"}}}
