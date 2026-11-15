"""Preferencias de cada usuario en la pantalla de selección: sus héroes favoritos y sus mains (hasta 3 por rol)."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .hero import ROLES

MAX_MAINS = 3


class OwPref(models.Model):
    _name = "ow.pref"
    _description = "Héroes favoritos de un usuario"

    user_id = fields.Many2one("res.users", "Usuario", required=True, ondelete="cascade",
                              default=lambda self: self.env.user, index=True)
    favorite_ids = fields.Many2many("ow.hero", string="Favoritos")
    # Tabla propia: dos Many2many al mismo modelo no pueden compartir la de por defecto
    main_ids = fields.Many2many("ow.hero", "ow_pref_main_rel", "pref_id", "hero_id", string="Mains",
                                help=f"Hasta {MAX_MAINS} por rol; salen encima de cada rol en la selección.")

    _uniq_user = models.Constraint("UNIQUE (user_id)", "Cada usuario tiene una sola lista de favoritos.")

    @api.model
    def mine(self):
        """La del usuario actual (se crea la primera vez)."""
        pref = self.search([("user_id", "=", self.env.uid)], limit=1)
        return pref or self.create({"user_id": self.env.uid})

    @api.constrains("main_ids")
    def _check_mains(self):
        nombres = dict(ROLES)
        for pref in self:
            for role, nombre in nombres.items():
                if len(pref.main_ids.filtered(lambda h: h.role == role)) > MAX_MAINS:
                    raise ValidationError(f"Como mucho {MAX_MAINS} mains de {nombre.lower()}.")
