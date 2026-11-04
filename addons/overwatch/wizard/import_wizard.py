from odoo import fields, models

from ..services import copia, seasons
from ..services.importer import Importer


class OwImportWizard(models.TransientModel):
    _name = "ow.import.wizard"
    _description = "Actualizar el catálogo de Overwatch"

    source = fields.Selection([("internet", "Internet (OverFast API y la wiki)"), ("local", "Copia local del módulo (sin internet)")],
                              "Origen", default="internet", required=True,
                              help="La copia local es la exportada en addons/overwatch/datos/ (scripts/exportar_catalogo.py).")
    cosmetics = fields.Boolean("Cosméticos de la wiki", default=True,
                               help="Aspectos, gestos, poses, presentaciones y grafitis (tarda un par de minutos).")
    seasons = fields.Boolean("Pases de batalla", default=True,
                             help="Todas las temporadas con su pase (fechas, míticos, héroes nuevos), de la wiki.")
    reload_images = fields.Boolean("Volver a descargar los retratos")
    hero_keys = fields.Char("Solo estos héroes", help="Claves separadas por comas (p. ej. «ana, soldier-76»). Vacío: todos.")
    result = fields.Text("Resultado", readonly=True)
    state = fields.Selection([("draft", "Inicio"), ("done", "Hecho")], default="draft")

    def action_import(self):
        self.ensure_one()
        if self.source == "local":
            s = copia.cargar(self.env)
            self.write({"state": "done", "result":
                        f"Copia local: {s['heroes_new']} héroes nuevos, {s['heroes_updated']} actualizados "
                        f"({s['portraits']} retratos); cosméticos: {s['cosmetics_new']} nuevos, "
                        f"{s['cosmetics_updated']} actualizados; pases de batalla: {s['seasons']}"})
            return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                    "view_mode": "form", "target": "new"}
        keys = [k.strip() for k in (self.hero_keys or "").split(",") if k.strip()]
        imp = Importer(self.env, reload_images=self.reload_images, cosmetics=self.cosmetics, heroes=keys)
        s = imp.run()
        lineas = [
            f"Héroes: {s['heroes_new']} nuevos, {s['heroes_updated']} actualizados ({s['portraits']} retratos descargados)",
            f"Cosméticos: {s['cosmetics_new']} nuevos, {s['cosmetics_updated']} actualizados, "
            f"{s['cosmetics_no_media']} sin imagen en la wiki",
        ]
        if self.seasons and not keys:
            try:
                with self.env.cr.savepoint():
                    t = seasons.importar(self.env, batch=imp.batch)
                lineas.append(f"Pases de batalla: {t['new']} nuevos, {t['updated']} actualizados")
            except Exception as e:  # que un cambio en la wiki no tire lo demás
                s["errors"].append(f"pases de batalla: {e}")
        n = self.env["ow.change"].search_count([("batch", "=", imp.batch)])
        lineas.append(f"Novedades: {n}" + (" (en Overwatch → Novedades)" if n else ""))
        if s["errors"]:
            lineas += ["", "Errores:"] + s["errors"]
        self.write({"result": "\n".join(lineas), "state": "done"})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "target": "new"}
