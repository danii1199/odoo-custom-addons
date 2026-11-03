"""Catálogo de rutinas de FuertaFit (común a todos los usuarios). Solo enlaza a los vídeos."""
from datetime import datetime

from odoo import api, fields, models

from ..services import catalog

CATALOG_UPDATED = "rutifuerta.catalog_updated"  # ir.config_parameter: última actualización del catálogo


class FuertaRoutine(models.Model):
    _name = "fuerta.routine"
    _description = "Rutina de FuertaFit"
    _order = "publish_date desc, fuerta_id desc"

    fuerta_id = fields.Integer("Id en FuertaFit", required=True, index=True, readonly=True)
    data = fields.Json("Datos de FuertaFit", required=True, readonly=True)
    # Columnas calculadas a partir de `data` para las vistas de Odoo (la web usa services.catalog).
    name = fields.Char("Título", compute="_compute_from_data", store=True)
    duration_minutes = fields.Integer("Minutos", compute="_compute_from_data", store=True)
    training_type = fields.Char("Tipo", compute="_compute_from_data", store=True)
    intensity = fields.Char("Intensidad", compute="_compute_from_data", store=True)
    group = fields.Char("Grupo muscular", compute="_compute_from_data", store=True)
    methodology = fields.Char("Metodología", compute="_compute_from_data", store=True)
    trainers = fields.Char("Entrenadores", compute="_compute_from_data", store=True)
    materials = fields.Char("Material", compute="_compute_from_data", store=True)
    publish_date = fields.Char("Publicada", compute="_compute_from_data", store=True)
    url = fields.Char("Vídeo", compute="_compute_from_data", store=True)
    preview_image = fields.Char("Imagen", compute="_compute_from_data", store=True)
    proposable = fields.Boolean("Se propone", compute="_compute_from_data", store=True,
                                help="Las infantiles, tests, embarazo/posparto y presentaciones no se proponen nunca.")

    _fuerta_id_uniq = models.Constraint("UNIQUE (fuerta_id)", "Esa rutina ya está en el catálogo.")

    @api.depends("data")
    def _compute_from_data(self):
        for rec in self:
            it = catalog.enrich(rec.data or {"title": ""})
            rec.name = it.get("title")
            rec.duration_minutes = it.get("durationMinutes") or 0
            rec.training_type = it.get("trainingType")
            rec.intensity = it.get("intensity")
            rec.group = it["group"]
            rec.methodology = it["methodology"]
            rec.trainers = ", ".join(it.get("trainers") or [])
            rec.materials = ", ".join(it["materials"])
            rec.publish_date = (it.get("publishDate") or "")[:10] or False
            rec.url = it.get("url")
            rec.preview_image = it.get("previewImage")
            rec.proposable = catalog.usable(it) and not it["skip"]

    @api.model
    def by_fuerta_ids(self, fuerta_ids):
        """{id de FuertaFit: id de registro} de las rutinas indicadas que existan."""
        recs = self.search_read([("fuerta_id", "in", [int(i) for i in fuerta_ids])], ["fuerta_id"])
        return {r["fuerta_id"]: r["id"] for r in recs}

    @api.model
    def catalog_ids(self):
        """Ids de FuertaFit ya guardados (incluidos los que se filtran al cargar)."""
        return sorted(r["fuerta_id"] for r in self.search_read([], ["fuerta_id"]))

    @api.model
    def import_items(self, items):
        """Añade o actualiza rutinas (lo usa el marcador; cualquier usuario puede traer rutinas nuevas).

        Todo en la transacción de la petición: o entran todas o ninguna.
        """
        model = self.sudo()
        clean = [c for c in (catalog.clean_item(it) for it in items) if c]
        known = model.by_fuerta_ids([c["id"] for c in clean])
        added = updated = 0
        new = []
        for c in clean:
            if c["id"] in known:
                model.browse(known[c["id"]]).data = c
                updated += 1
            else:
                new.append({"fuerta_id": c["id"], "data": c})
                known[c["id"]] = None  # por si llega repetida en el mismo lote
                added += 1
        model.create(new)
        self.env["ir.config_parameter"].sudo().set_str(
            CATALOG_UPDATED, datetime.now().astimezone().isoformat(timespec="minutes"))
        return {"added": added, "updated": updated, "total": len(catalog.get(self.env).items)}
