"""Cosméticos de un héroe (aspectos, gestos, poses de victoria, presentaciones y grafitis), como la galería del juego.
Importados de la wiki de Overwatch: `media_url` apunta a su imagen o vídeo (la carga el navegador, no se descarga);
si subes `image`, se usa esa en su lugar."""
from odoo import api, fields, models

TYPES = [
    ("skin", "Aspectos"),
    ("emote", "Gestos"),
    ("victory_pose", "Poses de victoria"),
    ("highlight_intro", "Presentaciones de jugada destacada"),
    ("spray", "Grafitis"),
]
RARITIES = [("common", "Común"), ("rare", "Raro"), ("epic", "Épico"), ("legendary", "Legendario"), ("mythic", "Mítico")]


class OwCosmetic(models.Model):
    _name = "ow.cosmetic"
    _description = "Cosmético de un héroe"
    _order = "hero_id, type_order, sequence, id"

    hero_id = fields.Many2one("ow.hero", "Héroe", required=True, ondelete="cascade", index=True)
    type = fields.Selection(TYPES, "Tipo", required=True, default="skin")
    type_order = fields.Integer(compute="_compute_type_order", store=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Nombre", required=True)
    rarity = fields.Selection(RARITIES, "Rareza", default="common", required=True)
    rarity_order = fields.Integer(compute="_compute_rarity_order", store=True)
    source = fields.Char("Cómo se consigue", help="Evento, precio o reto (según la wiki).")
    media_kind = fields.Selection([("image", "Imagen"), ("video", "Vídeo")], "Formato", default="image", required=True)
    media_url = fields.Char("URL de la imagen o vídeo")
    image = fields.Image("Imagen propia", max_width=1024, max_height=1024,
                         help="Opcional: si la subes, se muestra en lugar de la de la wiki.")
    wiki_file = fields.Char("Archivo en la wiki", index=True,
                            help="Clave del importador (p. ej. «File:Ana Skin Classic.png»).")

    _uniq_wiki_file = models.Constraint("UNIQUE (hero_id, type, wiki_file)", "Ese cosmético ya existe.")

    @api.depends("type")
    def _compute_type_order(self):
        orden = {k: i for i, (k, _n) in enumerate(TYPES)}
        for c in self:
            c.type_order = orden.get(c.type, 9)

    @api.depends("rarity")
    def _compute_rarity_order(self):
        orden = {k: i for i, (k, _n) in enumerate(RARITIES)}
        for c in self:
            c.rarity_order = orden.get(c.rarity, 0)
