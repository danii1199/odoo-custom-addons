"""Casilla «Web de Apachas» en el formulario del usuario.

En Odoo 20 el bloque de permisos del formulario se oculta a los usuarios de portal (salvo en modo desarrollador),
así que el grupo «Apachas: web» no se podía ver ni quitar a mano. Esta casilla lo muestra para todos.
"""
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    apachas_web = fields.Boolean(
        "Web de Apachas", compute="_compute_apachas_web", inverse="_inverse_apachas_web",
        help="Entra en /apachas y ve los grupos de gastos de los que es miembro. Se marca sola al añadirle o invitarle "
             "a un grupo; desmárcala para quitarle el acceso. Con «Apachas: Usuario» o «Administrador» va incluida.")
    apachas_interno = fields.Boolean(compute="_compute_apachas_web")

    @api.depends("group_ids")
    def _compute_apachas_web(self):
        web, interno = self.env.ref("apachas.group_gastos_web"), self.env.ref("apachas.group_gastos_user")
        for user in self:
            grupos = user.all_group_ids
            user.apachas_web = web in grupos
            user.apachas_interno = interno in grupos

    def _inverse_apachas_web(self):
        web = self.env.ref("apachas.group_gastos_web")
        for user in self:
            if user.apachas_web != (web in user.all_group_ids):
                user.group_ids = [(4 if user.apachas_web else 3, web.id)]
