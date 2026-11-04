"""Temporadas de Overwatch con su pase de batalla (desde Overwatch 2, octubre de 2022: antes no había pases).

Importadas de la wiki (páginas «Season/2022-2026» y «Season/<año>»: services/seasons.py): fechas, imagen de la hoja
de ruta (enlazada, como los cosméticos), héroes nuevos y las recompensas míticas del pase, enlazadas al aspecto del
catálogo cuando existe (para enseñar su imagen). `key` = «ow2-s12», «2026-s5»… El pase actual es el de la última
temporada que ya ha empezado."""
from odoo import api, fields, models


ARCS = [("ow2", "Overwatch 2"), ("reign_of_talon", "Reign of Talon")]
ITEM_KINDS = [("skin", "Aspecto"), ("emote", "Gesto"), ("victory_pose", "Pose de victoria"),
              ("highlight_intro", "Presentación"), ("spray", "Grafiti"), ("icon", "Icono de jugador"),
              ("card", "Tarjeta de nombre"), ("charm", "Amuleto de arma"), ("souvenir", "Recuerdo"),
              ("voice", "Frase"), ("title", "Título"), ("other", "Otro")]
TRACKS = [("free", "Gratis"), ("premium", "Prémium"), ("prestige", "Prestigio")]
RARITIES = [("common", "Común"), ("rare", "Raro"), ("epic", "Épico"), ("legendary", "Legendario"), ("mythic", "Mítico")]
REWARD_KINDS = [("skin", "Aspecto mítico"), ("midseason", "Aspecto mítico de mitad de temporada"),
                ("weapon", "Arma mítica")]


class OwSeason(models.Model):
    _name = "ow.season"
    _inherit = ["ow.update.mixin"]
    _description = "Temporada de Overwatch (pase de batalla)"
    _order = "sequence desc, id desc"

    key = fields.Char("Clave", required=True, index=True, help="«ow2-s12», «2026-s5»… (la pone el importador).")
    sequence = fields.Integer("Orden", help="Orden cronológico (1 = la primera temporada con pase).")
    arc = fields.Char("Etapa", help="«Overwatch 2» (2022-2026) o el arco del año («Reign of Talon»…).")
    year = fields.Integer("Año del arco", help="Vacío en las de Overwatch 2.")
    number = fields.Integer("Temporada", required=True)
    subtitle = fields.Char("Nombre", help="«Into the Tiger's Den», «A Grim Doctrine»… (las primeras no tienen).")
    name = fields.Char("Título", compute="_compute_name", store=True)
    date_start = fields.Date("Empieza")
    date_end = fields.Date("Termina")
    dates_text = fields.Char("Fechas (texto)", help="Lo que dice la wiki, por si alguna fecha no es exacta "
                                                    "(«diciembre de 2026»).")
    theme = fields.Char("Tema")
    image_url = fields.Char("Imagen (hoja de ruta)")
    image = fields.Image("Imagen propia", max_width=1024, max_height=1024,
                         help="Opcional: si la subes, se muestra en lugar de la de la wiki.")
    new_hero_ids = fields.Many2many("ow.hero", string="Héroes nuevos")
    new_heroes_text = fields.Char("Héroes nuevos (texto)", help="Los que aún no están en el catálogo.")
    reward_ids = fields.One2many("ow.season.reward", "season_id", "Recompensas míticas del pase")
    hack_ids = fields.One2many("ow.season.hack", "season_id", "Tier Hack",
                               help="Aspectos legendarios por los que se puede cambiar uno del pase (desde 2026 T4).")
    item_ids = fields.One2many("ow.season.item", "season_id", "Todas las recompensas")
    event_ids = fields.One2many("ow.event", "season_id", "Eventos")
    item_count = fields.Integer("Nº de recompensas", compute="_compute_item_count")
    wiki_page = fields.Char("Página de la wiki")
    state = fields.Selection([("past", "Anterior"), ("current", "Actual"), ("upcoming", "Próxima")], "Estado",
                             compute="_compute_state")

    _uniq_key = models.Constraint("UNIQUE (key)", "Ya hay una temporada con esa clave.")

    def _compute_item_count(self):
        datos = {t.id: n for t, n in self.env["ow.season.item"]._read_group(
            [("season_id", "in", self.ids)], ["season_id"], ["__count"])}
        for s in self:
            s.item_count = datos.get(s.id, 0)

    @api.depends("arc", "year", "number", "subtitle")
    def _compute_name(self):
        for s in self:
            base = f"Temporada {s.number}" + (f": {s.subtitle}" if s.subtitle else "")
            s.name = f"{s.arc} {s.year or ''} · {base}".replace("  ", " ") if s.year else base

    def _compute_state(self):
        actual = self.current()
        today = fields.Date.context_today(self)
        for s in self:
            if s == actual:
                s.state = "current"
            elif s.date_start and s.date_start <= today:
                s.state = "past"
            else:
                s.state = "upcoming"

    @api.model
    def current(self):
        """La temporada en curso: la última que ya ha empezado (y no ha terminado, si se sabe cuándo acaba)."""
        today = fields.Date.context_today(self)
        s = self.search([("date_start", "<=", today)], order="date_start desc, sequence desc", limit=1)
        return s if s and (not s.date_end or today < s.date_end) else self.browse()


class OwEvent(models.Model):
    """Evento de tiempo limitado o colaboración: de la wiki (services/eventos.py, historial e imágenes) y de
    Overwatch Countdown (services/countdown.py: los de ahora y los próximos, con hora exacta)."""
    _name = "ow.event"
    _description = "Evento de Overwatch"
    _order = "date_start desc, id desc"

    key = fields.Char("Clave", required=True, index=True,
                      help="«<temporada>:<página de la wiki>» o «owc:<id>» si solo está en Overwatch Countdown.")
    name = fields.Char("Nombre", required=True)
    season_id = fields.Many2one("ow.season", "Temporada", ondelete="cascade", index=True)
    kind = fields.Selection([("event", "Evento"), ("collab", "Colaboración")], "Tipo", default="event", required=True)
    date_start = fields.Date("Empieza")
    date_end = fields.Date("Termina")
    approx = fields.Boolean("Fechas aproximadas", help="La wiki no da sus fechas: son las de su temporada.")
    image_url = fields.Char("Imagen")
    image = fields.Image("Imagen propia", max_width=1024, max_height=1024)
    wiki_page = fields.Char("Página de la wiki")
    countdown_id = fields.Integer("Id en Overwatch Countdown", index=True,
                                  help="Con él, las fechas son las de Overwatch Countdown (con hora) y la wiki no las toca.")
    start_at = fields.Datetime("Empieza (hora)")
    end_at = fields.Datetime("Termina (hora)")
    description = fields.Text("Descripción")
    source_url = fields.Char("Fuente", help="Notas del parche o noticia de Blizzard que cita Overwatch Countdown.")
    tags = fields.Char("Etiquetas", help="De Overwatch Countdown: Limited-Time Event, Twitch Drops, Competitive Drives…")
    state = fields.Selection([("active", "Activo"), ("upcoming", "Por empezar"), ("unconfirmed", "Sin fechas confirmadas"),
                              ("past", "Terminado")], "Estado", compute="_compute_state", search="_search_state",
                             help="«Sin fechas confirmadas»: la wiki no da sus fechas y su temporada sigue en curso "
                                  "(no se da por activo: podría haber terminado ya).")

    _uniq_key = models.Constraint("UNIQUE (key)", "Ese evento ya existe.")

    def _compute_state(self):
        hoy = fields.Date.context_today(self)
        ahora = fields.Datetime.now()
        for e in self:
            if e.start_at or e.end_at:  # hora exacta (Overwatch Countdown)
                e.state = ("upcoming" if e.start_at and e.start_at > ahora
                           else "past" if e.end_at and e.end_at < ahora else "active")
            elif e.date_start and e.date_start > hoy:
                e.state = "upcoming"
            elif e.date_end and e.date_end < hoy:
                e.state = "past"
            else:
                e.state = "unconfirmed" if e.approx else "active"

    def _search_state(self, operator, value):
        """Buscar por estado («=» o «in»): se traduce a fechas respecto a hoy (el día en que empieza o acaba uno
        con hora puede dar los dos estados: el controlador lo afina con `state`)."""
        if operator not in ("=", "in"):
            return NotImplemented
        hoy = fields.Date.context_today(self)
        dominios = {
            "upcoming": [("date_start", ">", hoy)],
            "past": [("date_end", "<", hoy)],
            "active": ["&", "&", ("approx", "=", False), "|", ("date_start", "=", False), ("date_start", "<=", hoy),
                       "|", ("date_end", "=", False), ("date_end", ">=", hoy)],
            "unconfirmed": ["&", "&", ("approx", "=", True), "|", ("date_start", "=", False), ("date_start", "<=", hoy),
                            "|", ("date_end", "=", False), ("date_end", ">=", hoy)],
        }
        valores = [value] if isinstance(value, str) else list(value)
        dominio = ["|"] * (len(valores) - 1)
        for v in valores:
            dominio += dominios[v]
        return dominio


class OwSeasonReward(models.Model):
    _name = "ow.season.reward"
    _description = "Recompensa mítica de un pase de batalla"
    _order = "season_id, sequence, id"

    season_id = fields.Many2one("ow.season", "Temporada", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(REWARD_KINDS, "Tipo", required=True, default="skin")
    name = fields.Char("Nombre", required=True)
    hero_id = fields.Many2one("ow.hero", "Héroe", ondelete="set null")
    hero_text = fields.Char("Héroe (texto)", help="Como viene en la wiki, por si no está en el catálogo.")
    cosmetic_id = fields.Many2one("ow.cosmetic", "Aspecto del catálogo", ondelete="set null",
                                  help="El aspecto de la galería del héroe con ese nombre (para su imagen).")
    media_url = fields.Char("Imagen", help="De la wiki, si no está en la galería (p. ej. las armas míticas).")


class OwSeasonItem(models.Model):
    """Una recompensa de un nivel del pase (gratis, prémium o de prestigio), de la tabla de niveles de la wiki."""
    _name = "ow.season.item"
    _description = "Recompensa de un nivel del pase de batalla"
    _order = "season_id, sequence, id"

    season_id = fields.Many2one("ow.season", "Temporada", required=True, ondelete="cascade", index=True)
    tier = fields.Integer("Nivel", required=True)
    section = fields.Char("Camino", help="En los pases por caminos (desde la Temporada 4 de 2026): «Camino inicial», "
                                         "«Camino 1»…, «Camino mítico», «Prestigio». Vacío en los de 80 niveles.")
    track = fields.Selection(TRACKS, "Pista", required=True, default="free")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(ITEM_KINDS, "Tipo", required=True, default="other")
    rarity = fields.Selection(RARITIES, "Rareza")
    name = fields.Char("Nombre", required=True)
    hero_id = fields.Many2one("ow.hero", "Héroe", ondelete="set null")
    hero_text = fields.Char("Héroe (texto)")
    cosmetic_id = fields.Many2one("ow.cosmetic", "Cosmético del catálogo", ondelete="set null")
    media_url = fields.Char("Imagen", help="De la wiki (si no está en la galería del héroe).")


class OwSeasonHack(models.Model):
    """Tier Hack: un aspecto legendario por el que se puede cambiar uno del pase (services/hack.py)."""
    _name = "ow.season.hack"
    _description = "Aspecto del Tier Hack de un pase"
    _order = "season_id, sequence, id"

    season_id = fields.Many2one("ow.season", "Temporada", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Aspecto", required=True)
    hero_id = fields.Many2one("ow.hero", "Héroe", ondelete="set null")
    hero_text = fields.Char("Héroe (texto)", help="Como viene en la wiki, por si no está en el catálogo.")
    cosmetic_id = fields.Many2one("ow.cosmetic", "Aspecto del catálogo", ondelete="set null")
    media_url = fields.Char("Imagen", help="De la wiki, si el aspecto no está en la galería del héroe.")
