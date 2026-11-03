"""Héroes de Overwatch con sus habilidades (y ventajas) y su historia por capítulos.

Los datos vienen de OverFast API (overfast-api.tekrop.fr, que lee la web oficial) en español; `key` es su clave
(«ana», «soldier-76»). El retrato se descarga (lo usa la pantalla de selección); fondos, iconos de habilidades,
vídeos e imágenes de la historia se enlazan a la CDN oficial. Si subes una imagen a mano, manda sobre el enlace."""
import re

from odoo import api, fields, models

ROLES = [("tank", "Tanque"), ("damage", "Daño"), ("support", "Apoyo")]
SUBROLES = {
    "bruiser": "Luchador", "initiator": "Iniciador", "stalwart": "Incondicional",
    "flanker": "Flanqueador", "recon": "Reconocimiento", "sharpshooter": "Tirador", "specialist": "Especialista",
    "medic": "Médico", "survivor": "Superviviente", "tactician": "Táctico",
}


class OwHero(models.Model):
    _name = "ow.hero"
    _description = "Héroe de Overwatch"
    _order = "role_order, name"

    key = fields.Char("Clave", required=True, index=True, help="Clave en OverFast API (p. ej. «soldier-76»).")
    name = fields.Char("Nombre", required=True)
    wiki_name = fields.Char("Nombre en la wiki", help="Si no coincide con el nombre (para importar los cosméticos).")
    active = fields.Boolean(default=True)
    role = fields.Selection(ROLES, "Rol", required=True)
    role_order = fields.Integer(compute="_compute_role_order", store=True)
    subrole = fields.Char("Subrol (clave)")
    subrole_name = fields.Char("Subrol", compute="_compute_subrole_name")
    description = fields.Text("Descripción")
    location = fields.Char("Ubicación")
    birthday = fields.Char("Cumpleaños")
    age = fields.Integer("Edad")
    health = fields.Integer("Salud")
    armor = fields.Integer("Armadura")
    shields = fields.Integer("Escudos")

    portrait = fields.Image("Retrato", max_width=512, max_height=512)
    portrait_url = fields.Char("URL del retrato")
    background_url = fields.Char("URL del fondo")

    story_summary = fields.Text("Resumen de la historia")
    story_video_url = fields.Char("Vídeo de origen", help="Enlace de YouTube con la historia de origen del héroe.")
    youtube_id = fields.Char(compute="_compute_youtube_id")
    chapter_ids = fields.One2many("ow.hero.chapter", "hero_id", "Capítulos de la historia")
    ability_ids = fields.One2many("ow.hero.ability", "hero_id", "Habilidades y ventajas")
    cosmetic_ids = fields.One2many("ow.cosmetic", "hero_id", "Cosméticos")
    cosmetic_count = fields.Integer("Nº de cosméticos", compute="_compute_cosmetic_count")

    _uniq_key = models.Constraint("UNIQUE (key)", "Ya hay un héroe con esa clave.")

    @api.depends("role")
    def _compute_role_order(self):
        orden = {k: i for i, (k, _n) in enumerate(ROLES)}
        for h in self:
            h.role_order = orden.get(h.role, 9)

    @api.depends("subrole")
    def _compute_subrole_name(self):
        for h in self:
            h.subrole_name = SUBROLES.get(h.subrole or "", (h.subrole or "").capitalize())

    @api.depends("story_video_url")
    def _compute_youtube_id(self):
        for h in self:
            m = re.search(r"(?:youtu\.be/|v=|embed/|shorts/)([\w-]{11})", h.story_video_url or "")
            h.youtube_id = m and m.group(1)

    def _compute_cosmetic_count(self):
        datos = dict(self.env["ow.cosmetic"]._read_group([("hero_id", "in", self.ids)], ["hero_id"], ["__count"]))
        for h in self:
            h.cosmetic_count = datos.get(h, 0)

    def action_open_web(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": f"/overwatch/heroe/{self.key}", "target": "self"}


class OwHeroChapter(models.Model):
    _name = "ow.hero.chapter"
    _description = "Capítulo de la historia de un héroe"
    _order = "hero_id, sequence, id"

    hero_id = fields.Many2one("ow.hero", "Héroe", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    title = fields.Char("Título", required=True)
    content = fields.Text("Texto")
    picture_url = fields.Char("URL de la imagen")


class OwHeroAbility(models.Model):
    _name = "ow.hero.ability"
    _description = "Habilidad o ventaja de un héroe"
    _order = "hero_id, kind_order, sequence, id"

    hero_id = fields.Many2one("ow.hero", "Héroe", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([("ability", "Habilidad"), ("perk_minor", "Ventaja menor"), ("perk_major", "Ventaja mayor")],
                            "Tipo", default="ability", required=True)
    kind_order = fields.Integer(compute="_compute_kind_order", store=True)
    name = fields.Char("Nombre", required=True)
    description = fields.Text("Descripción")
    icon_url = fields.Char("URL del icono")
    video_url = fields.Char("Vídeo (mp4)")
    video_webm_url = fields.Char("Vídeo (webm)")
    thumbnail_url = fields.Char("Miniatura del vídeo")

    @api.depends("kind")
    def _compute_kind_order(self):
        orden = {"ability": 0, "perk_minor": 1, "perk_major": 2}
        for a in self:
            a.kind_order = orden.get(a.kind, 9)
