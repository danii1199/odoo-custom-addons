"""Gasto de un grupo: quién lo pagó y cómo se reparte entre los miembros (una línea por miembro que participa).

Reparto (campo `valor` de cada línea):
- igual: a partes iguales entre las líneas (valor sin uso)
- partes: proporcional al valor (2 = paga el doble que 1)
- porcentaje: valor en %, las líneas suman 100
- importes: valor = importe exacto, las líneas suman el total
Se calcula en céntimos: lo que sobra al redondear va, céntimo a céntimo, a las primeras líneas."""
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

CATEGORIAS = [
    ("comida", "🍽️ Comida y bebida"),
    ("super", "🛒 Supermercado"),
    ("transporte", "🚗 Transporte"),
    ("alojamiento", "🏨 Alojamiento"),
    ("ocio", "🎉 Ocio"),
    ("casa", "🏠 Casa y facturas"),
    ("regalos", "🎁 Regalos"),
    ("otros", "📦 Otros"),
]
REPARTOS = [
    ("igual", "A partes iguales"),
    ("partes", "Por partes"),
    ("porcentaje", "Por porcentaje"),
    ("importes", "Importes exactos"),
]


def repartir(total_c, reparto, valores):
    """Céntimos de cada línea. `valores`: lista con el valor de cada línea (en `importes`, ya en céntimos)."""
    n = len(valores)
    if not n:
        return []
    if reparto == "importes":
        return list(valores)
    pesos = [1] * n if reparto == "igual" else [max(v, 0) for v in valores]
    suma = sum(pesos)
    if not suma:
        return [0] * n
    partes = [int(total_c * p // suma) for p in pesos]
    resto = total_c - sum(partes)
    for i in range(int(resto)):
        partes[i % n] += 1
    return partes


class GastosGasto(models.Model):
    _name = "gastos.gasto"
    _description = "Gasto compartido"
    _order = "fecha desc, id desc"

    name = fields.Char("Concepto", required=True)
    grupo_id = fields.Many2one("gastos.grupo", "Grupo", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="grupo_id.currency_id", store=True)
    fecha = fields.Date("Fecha", required=True, default=fields.Date.context_today)
    importe = fields.Monetary("Importe", required=True)
    pagador_id = fields.Many2one("gastos.miembro", "Pagado por", required=True, ondelete="restrict",
                                 domain="[('grupo_id', '=', grupo_id)]")
    categoria = fields.Selection(CATEGORIAS, "Categoría", default="otros", required=True)
    reparto = fields.Selection(REPARTOS, "Reparto", default="igual", required=True)
    linea_ids = fields.One2many("gastos.gasto.linea", "gasto_id", "Reparto entre", copy=True)
    nota = fields.Text("Nota")
    ticket = fields.Image("Ticket", max_width=1600, max_height=1600)

    @api.onchange("grupo_id")
    def _onchange_grupo_id(self):
        """Por defecto, entre todos los miembros activos; paga el usuario actual si es miembro."""
        if not self.grupo_id:
            return
        miembros = self.grupo_id.member_ids
        self.linea_ids = [(5, 0, 0)] + [(0, 0, {"miembro_id": m.id, "valor": 1}) for m in miembros]
        yo = miembros.filtered(lambda m: m.user_id == self.env.user)
        if yo and not self.pagador_id:
            self.pagador_id = yo[:1]

    @api.constrains("importe", "reparto", "pagador_id", "linea_ids", "grupo_id")
    def _check_reparto(self):
        for g in self:
            if g.importe <= 0:
                raise ValidationError("El importe tiene que ser mayor que cero.")
            if not g.linea_ids:
                raise ValidationError("Elige al menos un miembro entre quienes se reparte el gasto.")
            if g.pagador_id.grupo_id != g.grupo_id or any(l.miembro_id.grupo_id != g.grupo_id for l in g.linea_ids):
                raise ValidationError("Quien paga y quienes participan tienen que ser del grupo.")
            if len(g.linea_ids.miembro_id) != len(g.linea_ids):
                raise ValidationError("Un miembro está repetido en el reparto.")
            valores = g.linea_ids.mapped("valor")
            if g.reparto in ("partes", "porcentaje", "importes") and any(v < 0 for v in valores):
                raise ValidationError("Los valores del reparto no pueden ser negativos.")
            if g.reparto == "partes" and not sum(valores):
                raise ValidationError("Las partes no pueden sumar cero.")
            if g.reparto == "porcentaje" and abs(sum(valores) - 100) > 0.01:
                raise ValidationError(f"Los porcentajes suman {sum(valores):g} %, tienen que sumar 100 %.")
            if g.reparto == "importes" and g.currency_id.compare_amounts(sum(valores), g.importe):
                raise ValidationError(
                    f"Los importes suman {g.grupo_id._fmt(sum(valores))} y el gasto es de {g.grupo_id._fmt(g.importe)}.")

    # ------------------------------------------------------------------ avisos

    def _autor(self):
        return self.grupo_id.member_ids.filtered(lambda m: m.user_id == self.env.user)[:1]

    def _datos_webhook(self):
        return {"gasto": {"id": self.id, "concepto": self.name, "importe": self.importe, "fecha": self.fecha,
                          "pagado_por": self.pagador_id.name, "categoria": dict(CATEGORIAS)[self.categoria],
                          "reparto": [{"miembro": l.miembro_id.name, "importe": l.importe} for l in self.linea_ids],
                          "apuntado_por": self.env.user.name}}

    @api.model_create_multi
    def create(self, vals_list):
        gastos = super().create(vals_list)
        if self.env.context.get("gastos_importando"):
            return gastos  # importación de Splitwise: sin avisos por gasto (deja una sola nota al final)
        for g in gastos:
            g.grupo_id.sudo().message_post(body=Markup("Gasto <b>%s</b>: %s, pagado por %s (apuntado por %s).") % (
                g.name, g.grupo_id._fmt(g.importe), g.pagador_id.name, self.env.user.name))
            g.grupo_id._avisar("gasto_creado", f"nuevo gasto «{g.name}»", "apachas.correo_gasto",
                               g._autor(), g._datos_webhook(), gasto=g, accion="nuevo")
        return gastos

    # Cambios que se avisan (no, por ejemplo, la nota o el ticket)
    CAMPOS_AVISO = {"name", "importe", "fecha", "pagador_id", "reparto", "linea_ids"}

    def write(self, vals):
        res = super().write(vals)
        if self.CAMPOS_AVISO & set(vals):
            for g in self:
                g.grupo_id.sudo().message_post(body=Markup("Gasto modificado por %s: <b>%s</b>, %s, pagado por %s.") % (
                    self.env.user.name, g.name, g.grupo_id._fmt(g.importe), g.pagador_id.name))
                g.grupo_id._avisar("gasto_editado", f"gasto modificado «{g.name}»", "apachas.correo_gasto",
                                   g._autor(), g._datos_webhook(), gasto=g, accion="editado")
        return res

    def unlink(self):
        for g in self:
            g.grupo_id.sudo().message_post(body=Markup("Gasto borrado por %s: <b>%s</b> (%s).") % (
                self.env.user.name, g.name, g.grupo_id._fmt(g.importe)))
            g.grupo_id._webhook("gasto_borrado", gasto={"id": g.id, "concepto": g.name, "importe": g.importe})
        return super().unlink()


class GastosGastoLinea(models.Model):
    _name = "gastos.gasto.linea"
    _description = "Parte de un gasto"
    _order = "gasto_id, id"

    gasto_id = fields.Many2one("gastos.gasto", "Gasto", required=True, ondelete="cascade", index=True)
    grupo_id = fields.Many2one(related="gasto_id.grupo_id", store=True)
    miembro_id = fields.Many2one("gastos.miembro", "Miembro", required=True, ondelete="restrict",
                                 domain="[('grupo_id', '=', grupo_id)]")
    valor = fields.Float("Valor", default=1, digits=(16, 2),
                         help="Partes, porcentaje o importe según el tipo de reparto (en «a partes iguales» no se usa).")
    currency_id = fields.Many2one(related="gasto_id.currency_id")
    importe = fields.Monetary("Le toca", compute="_compute_importe", store=True)

    @api.depends("valor", "gasto_id.importe", "gasto_id.reparto", "gasto_id.linea_ids")
    def _compute_importe(self):
        for gasto in self.gasto_id:
            lineas = gasto.linea_ids
            f = 100  # euros: céntimos
            valores = lineas.mapped("valor")
            if gasto.reparto == "importes":
                valores = [round(v * f) for v in valores]
            for linea, c in zip(lineas, repartir(round(gasto.importe * f), gasto.reparto, valores)):
                linea.importe = c / f
        (self - self.filtered("gasto_id")).importe = 0
