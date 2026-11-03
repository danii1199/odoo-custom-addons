"""Importar rutinas al catálogo desde el backend: el mismo JSON que manda el marcador de la web
(lista de rutinas, o {"items": [...]}), pegado o en un archivo."""
import json

from odoo import fields, models
from odoo.exceptions import UserError


class FuertaRoutineImport(models.TransientModel):
    _name = "fuerta.routine.import"
    _description = "Importar rutinas"

    file = fields.Binary("Archivo JSON")
    filename = fields.Char()
    payload = fields.Text("O pega aquí el JSON")

    def action_import(self):
        self.ensure_one()
        raw = self.file.decode("utf-8") if self.file else (self.payload or "")  # Odoo 20: BinaryValue, ya sin base64
        try:
            data = json.loads(raw)
        except ValueError as e:
            raise UserError(f"JSON no válido: {e}") from e
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            raise UserError("Se esperaba una lista de rutinas (o {\"items\": [...]}).")
        res = self.env["fuerta.routine"].import_items(items)
        msg = f"{res['added']} nuevas, {res['updated']} actualizadas. El catálogo tiene {res['total']} rutinas usables."
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Catálogo actualizado", "message": msg, "type": "success",
                           "next": {"type": "ir.actions.act_window_close"}}}
