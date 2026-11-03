"""Preferencias de cada usuario en la pantalla de selección: sus héroes favoritos."""
from odoo import api, fields, models


class OwPref(models.Model):
    _name = "ow.pref"
    _description = "Héroes favoritos de un usuario"

    user_id = fields.Many2one("res.users", "Usuario", required=True, ondelete="cascade",
                              default=lambda self: self.env.user, index=True)
    favorite_ids = fields.Many2many("ow.hero", string="Favoritos")

    _uniq_user = models.Constraint("UNIQUE (user_id)", "Cada usuario tiene una sola lista de favoritos.")

    @api.model
    def mine(self):
        """La del usuario actual (se crea la primera vez)."""
        pref = self.search([("user_id", "=", self.env.uid)], limit=1)
        return pref or self.create({"user_id": self.env.uid})
