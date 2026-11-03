"""Cada usuario con sesión puede ocultarse entradas del menú del sitio (res.users.ini_menu_oculto). Solo esconde:
los permisos de cada módulo (group_ids del menú y de las rutas) siguen mandando."""
from odoo import api, models


class WebsiteMenu(models.Model):
    _inherit = "website.menu"

    @api.depends_context("uid")
    def _compute_visible(self):
        super()._compute_visible()
        user = self.env.user
        if user._is_public():
            return
        ocultos = user.ini_menu_ocultos()
        if ocultos:
            for menu in self.filtered(lambda m: m.is_visible and m.url in ocultos):
                menu.is_visible = False
