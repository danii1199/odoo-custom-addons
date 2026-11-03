from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # URLs de las entradas del menú del sitio que el usuario ha ocultado para sí (separadas por espacios).
    # Se cambia desde la portada («Personalizar menú», /inicio/menu); solo afecta a su sesión.
    ini_menu_oculto = fields.Char("Menú del sitio: entradas ocultas", default="")

    def ini_menu_ocultos(self):
        return set((self.sudo().ini_menu_oculto or "").split())
