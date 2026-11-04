"""Novedades del catálogo: lo que ha cambiado en cada «Buscar actualizaciones» (vida de un héroe, números de una
habilidad, héroes y pases nuevos…). Las escribe el importador (services/importer.py y services/seasons.py) comparando
lo que había con lo que llega; `batch` agrupa las de una misma búsqueda."""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

KINDS = [("hero_new", "Héroe nuevo"), ("hero", "Héroe"), ("ability", "Habilidad"), ("season_new", "Pase nuevo"),
         ("season", "Pase"), ("event_new", "Evento nuevo")]


def buscar_actualizaciones(env):
    """Botón «Buscar actualizaciones»: héroes y sus habilidades (OverFast + números de la wiki) y pases de batalla.
    Sin cosméticos, para que tarde poco (esos, con «Actualizar catálogo»). Abre las novedades que haya encontrado."""
    from ..services import seasons
    from ..services.importer import Importer
    env["ow.change"].check_access("create")
    imp = Importer(env, cosmetics=False)
    stats = imp.run()
    errores = list(stats["errors"])
    try:
        with env.cr.savepoint():
            seasons.importar(env, batch=imp.batch)
    except Exception as e:  # que un cambio en la wiki no tire lo demás
        errores.append(f"pases de batalla: {e}")
    n = env["ow.change"].search_count([("batch", "=", imp.batch)])
    aviso = (f"{n} novedades." if n else "Todo estaba al día: no hay novedades.") + \
        (f" {stats['heroes_new']} héroes nuevos." if stats["heroes_new"] else "") + \
        (f" Errores: {'; '.join(errores)}" if errores else "")
    siguiente = {"type": "ir.actions.act_window", "name": "Novedades", "res_model": "ow.change",
                 "view_mode": "list,form", "domain": [("batch", "=", imp.batch)]} if n else \
        {"type": "ir.actions.client", "tag": "soft_reload"}
    return {"type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": "Buscar actualizaciones", "message": aviso, "sticky": bool(errores),
                       "type": "warning" if errores else "success", "next": siguiente}}


class OwChangeButton(models.AbstractModel):
    """El botón está en las listas de héroes, pases y novedades: los tres modelos heredan este método."""
    _name = "ow.update.mixin"
    _description = "Botón «Buscar actualizaciones»"

    @api.model
    def action_check_updates(self):
        return buscar_actualizaciones(self.env)

    @api.model
    def _cron_check_updates(self):
        """Búsqueda diaria (data/ir_cron.xml): lo mismo que el botón y, además, los cosméticos nuevos (tarda unos
        minutos; en una tarea programada no importa). Hace commit por héroe para no perderlo todo si algo falla."""
        from ..services import seasons
        from ..services.importer import Importer
        imp = Importer(self.env(context=dict(self.env.context, ow_commit=True)), cosmetics=True)
        stats = imp.run()
        try:
            with self.env.cr.savepoint():
                seasons.importar(self.env, batch=imp.batch)
        except Exception as e:  # que un cambio en la wiki no tire lo demás
            stats["errors"].append(f"pases de batalla: {e}")
        if stats["errors"]:
            _logger.warning("Overwatch: búsqueda diaria con errores: %s", "; ".join(stats["errors"]))
        _logger.info("Overwatch: búsqueda diaria: %s novedades, %s cosméticos nuevos",
                     self.env["ow.change"].search_count([("batch", "=", imp.batch)]), stats["cosmetics_new"])


class OwChange(models.Model):
    _name = "ow.change"
    _inherit = ["ow.update.mixin"]
    _description = "Novedad del catálogo de Overwatch"
    _order = "create_date desc, id"
    _rec_name = "what"

    batch = fields.Char("Búsqueda", index=True, help="Fecha y hora de la búsqueda que lo detectó.")
    kind = fields.Selection(KINDS, "Tipo", required=True)
    hero_id = fields.Many2one("ow.hero", "Héroe", ondelete="cascade", index=True)
    season_id = fields.Many2one("ow.season", "Pase", ondelete="cascade")
    what = fields.Char("Qué", required=True)
    old_value = fields.Char("Antes")
    new_value = fields.Char("Ahora")

