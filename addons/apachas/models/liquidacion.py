"""Pago entre dos miembros para saldar deudas («Saldar» en Splitwise).

Nadie paga por otro: quien paga (pagador_id) es siempre el miembro del usuario que lo apunta o lo edita (decisión
del usuario). Solo quien apuntó un pago puede editarlo, desde la web o el backend y sea cual sea su grupo;
cada edición queda en su historial (gastos.liquidacion.historial: quién, cuándo y qué cambió). Borrar lo puede
cualquier miembro, como los gastos."""
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

CAMPOS_HISTORIAL = ["fecha", "pagador_id", "receptor_id", "importe", "nota"]


class GastosLiquidacion(models.Model):
    _name = "gastos.liquidacion"
    _description = "Pago entre miembros"
    _order = "fecha desc, id desc"

    grupo_id = fields.Many2one("gastos.grupo", "Grupo", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="grupo_id.currency_id", store=True)
    fecha = fields.Date("Fecha", required=True, default=fields.Date.context_today)
    pagador_id = fields.Many2one("gastos.miembro", "Paga", required=True, ondelete="restrict",
                                 domain="[('grupo_id', '=', grupo_id), ('user_id', '=', uid)]",
                                 help="Siempre tú: nadie puede apuntar un pago en nombre de otro.")
    receptor_id = fields.Many2one("gastos.miembro", "Recibe", required=True, ondelete="restrict",
                                  domain="[('grupo_id', '=', grupo_id)]")
    importe = fields.Monetary("Importe", required=True)
    nota = fields.Char("Nota", help="Bizum, efectivo, transferencia…")
    autor_name = fields.Char("Apuntado por", compute="_compute_autor_name", compute_sudo=True)
    puedo_editar = fields.Boolean(compute="_compute_puedo_editar")
    historial_ids = fields.One2many("gastos.liquidacion.historial", "liquidacion_id", "Historial de cambios")

    @api.depends("pagador_id", "receptor_id", "importe")
    def _compute_display_name(self):
        for p in self:
            p.display_name = f"{p.pagador_id.name} → {p.receptor_id.name}: {p.grupo_id._fmt(p.importe)}"

    @api.depends("create_uid")
    def _compute_autor_name(self):
        for p in self:
            p.autor_name = p.create_uid.name

    @api.depends_context("uid")
    @api.depends("create_uid")
    def _compute_puedo_editar(self):
        for p in self:
            p.puedo_editar = not p.id or p.create_uid == self.env.user

    @api.onchange("grupo_id")
    def _onchange_grupo_id(self):
        self.pagador_id = self.grupo_id.member_ids.filtered(lambda m: m.user_id == self.env.user)[:1]

    def _check_pagas_tu(self):
        """Quien paga tiene que ser el propio usuario (el superusuario técnico, sudo, se lo salta)."""
        if self.env.su:
            return
        for p in self:
            if p.pagador_id.user_id != self.env.user:
                raise ValidationError(
                    f"Solo puedes apuntar pagos que haces tú: {p.pagador_id.name} tiene que apuntar el suyo.")

    @api.constrains("pagador_id", "receptor_id", "importe", "grupo_id")
    def _check_pago(self):
        for p in self:
            if p.importe <= 0:
                raise ValidationError("El importe tiene que ser mayor que cero.")
            if p.pagador_id == p.receptor_id:
                raise ValidationError("Quien paga y quien recibe no pueden ser la misma persona.")
            if p.pagador_id.grupo_id != p.grupo_id or p.receptor_id.grupo_id != p.grupo_id:
                raise ValidationError("Los dos tienen que ser del grupo.")

    def _datos_webhook(self):
        return {"pago": {"id": self.id, "paga": self.pagador_id.name, "recibe": self.receptor_id.name,
                         "importe": self.importe, "fecha": self.fecha, "nota": self.nota or None}}

    @api.model_create_multi
    def create(self, vals_list):
        pagos = super().create(vals_list)
        pagos._check_pagas_tu()
        if self.env.context.get("gastos_importando"):
            return pagos  # importación de Splitwise: sin avisos por pago
        for p in pagos:
            g = p.grupo_id
            g.sudo().message_post(body=Markup("Pago: %s (apuntado por %s).") % (p.display_name, self.env.user.name))
            autor = g.member_ids.filtered(lambda m: m.user_id == self.env.user)[:1]
            g._avisar("pago_registrado", f"{p.pagador_id.name} ha pagado a {p.receptor_id.name}",
                      "apachas.correo_pago", autor, p._datos_webhook(), pago=p, accion="nuevo")
        return pagos

    def _texto(self, campo):
        valor = self[campo]
        if campo == "importe":
            return self.grupo_id._fmt(valor)
        if campo == "fecha":
            return valor.strftime("%d/%m/%Y") if valor else "—"
        if campo in ("pagador_id", "receptor_id"):
            return valor.name or "—"
        return valor or "—"

    def write(self, vals):
        if not self.env.su:
            ajenos = self.filtered(lambda p: p.create_uid != self.env.user)
            if ajenos:
                raise AccessError(f"Solo quien apuntó el pago puede editarlo ({ajenos[0].autor_name}).")
        campos = [c for c in CAMPOS_HISTORIAL if c in vals]
        antes = {p.id: {c: p._texto(c) for c in campos} for p in self}
        res = super().write(vals)
        if "pagador_id" in vals:
            self._check_pagas_tu()
        for p in self:
            cambios = [(self._fields[c].string, antes[p.id][c], p._texto(c)) for c in campos
                       if antes[p.id][c] != p._texto(c)]
            if not cambios:
                continue
            texto = "; ".join(f"{nombre}: {a} → {b}" for nombre, a, b in cambios)
            self.env["gastos.liquidacion.historial"].sudo().create({
                "liquidacion_id": p.id, "user_id": self.env.uid, "cambios": texto})
            g = p.grupo_id
            g.sudo().message_post(body=Markup("Pago modificado por %s (%s): %s.") % (
                self.env.user.name, p.display_name, texto))
            autor = g.member_ids.filtered(lambda m: m.user_id == self.env.user)[:1]
            g._avisar("pago_editado", f"pago modificado ({p.pagador_id.name} → {p.receptor_id.name})",
                      "apachas.correo_pago", autor, {**p._datos_webhook(), "cambios": texto}, pago=p,
                      accion="editado", cambios=texto)
        return res


class GastosLiquidacionHistorial(models.Model):
    _name = "gastos.liquidacion.historial"
    _description = "Cambio en un pago"
    _order = "create_date desc, id desc"

    liquidacion_id = fields.Many2one("gastos.liquidacion", "Pago", required=True, ondelete="cascade", index=True)
    grupo_id = fields.Many2one(related="liquidacion_id.grupo_id", store=True)
    user_id = fields.Many2one("res.users", "Quién", required=True)
    user_name = fields.Char("Quién", related="user_id.name", store=True)  # el portal no lee res.users
    cambios = fields.Text("Cambios", required=True)
