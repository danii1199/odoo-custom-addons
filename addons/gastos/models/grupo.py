"""Grupo o evento de gastos compartidos (un viaje, el piso, una cena…).

Saldo de un miembro = lo que ha pagado − lo que le toca de los gastos + lo que ha pagado a otros − lo que ha recibido.
Positivo: le deben dinero; negativo: debe. Las deudas simplificadas son el mínimo de pagos para dejarlo todo a cero.
Los avisos van por correo (mail.mail, uno por miembro con su saldo) y, si el grupo tiene webhook, también a n8n.
Todo va en euros (decisión del usuario): currency_id existe porque lo piden los campos Monetary, pero siempre es EUR."""
import json
import logging
from functools import partial

import requests
from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


def simplificar_deudas(saldos):
    """{clave: saldo en céntimos (int)} → [(deudor, acreedor, céntimos)] con el mínimo de pagos (voraz: el que más
    debe paga al que más le deben). La suma de saldos debe ser 0."""
    deudores = sorted(([k, -v] for k, v in saldos.items() if v < 0), key=lambda x: -x[1])
    acreedores = sorted(([k, v] for k, v in saldos.items() if v > 0), key=lambda x: -x[1])
    pagos = []
    i = j = 0
    while i < len(deudores) and j < len(acreedores):
        cantidad = min(deudores[i][1], acreedores[j][1])
        if cantidad:
            pagos.append((deudores[i][0], acreedores[j][0], cantidad))
        deudores[i][1] -= cantidad
        acreedores[j][1] -= cantidad
        if not deudores[i][1]:
            i += 1
        if not acreedores[j][1]:
            j += 1
    return pagos


class GastosGrupo(models.Model):
    _name = "gastos.grupo"
    _description = "Grupo de gastos compartidos"
    _inherit = ["mail.thread", "portal.mixin"]
    _order = "active desc, write_date desc, id desc"

    name = fields.Char("Nombre", required=True, tracking=True)
    image = fields.Image("Imagen", max_width=1024, max_height=1024, help="Foto del grupo (la del viaje, el piso…).")
    image_128 = fields.Image("Miniatura", related="image", max_width=128, max_height=128, store=True)
    description = fields.Text("Descripción")
    active = fields.Boolean(default=True, help="Archiva el grupo cuando ya esté todo saldado.")
    currency_id = fields.Many2one("res.currency", "Moneda", required=True, readonly=True,
                                  default=lambda self: self.env.ref("base.EUR"))
    member_ids = fields.One2many("gastos.miembro", "grupo_id", "Miembros")
    gasto_ids = fields.One2many("gastos.gasto", "grupo_id", "Gastos")
    liquidacion_ids = fields.One2many("gastos.liquidacion", "grupo_id", "Pagos")
    total_gastado = fields.Monetary("Total gastado", compute="_compute_total_gastado")
    gasto_count = fields.Integer("Nº de gastos", compute="_compute_total_gastado")
    deudas_html = fields.Html("Quién debe a quién", compute="_compute_deudas_html", sanitize=False)
    mi_saldo = fields.Monetary("Mi saldo", compute="_compute_mi_saldo",
                               help="Tu saldo en el grupo: positivo, te deben; negativo, debes.")

    # Avisos
    notificar_gastos = fields.Boolean("Avisar de cada gasto y pago", default=True,
                                      help="Manda un correo a los demás miembros con cada gasto o pago nuevo.")
    resumen_semanal = fields.Boolean("Resumen semanal", default=True,
                                     help="Cada lunes, a quien tenga saldo pendiente, un correo con lo que debe o le deben.")
    webhook_url = fields.Char(
        "Webhook (n8n)", groups="gastos.group_gastos_manager",
        help="Si lo rellenas, cada gasto, pago, recordatorio y resumen se manda también como JSON (POST) a esta URL, "
             "por ejemplo un Webhook de n8n que lo reenvíe a Telegram.")

    @api.model
    def _forzar_euros(self):
        """Al instalar o actualizar: EUR activo y todos los grupos (y sus gastos y pagos) en euros."""
        eur = self.env.ref("base.EUR")
        eur.active = True
        grupos = self.with_context(active_test=False).search([("currency_id", "!=", eur.id)])
        grupos.currency_id = eur

    @api.depends("gasto_ids.importe")
    def _compute_total_gastado(self):
        for grupo in self:
            grupo.total_gastado = sum(grupo.gasto_ids.mapped("importe"))
            grupo.gasto_count = len(grupo.gasto_ids)

    @api.depends_context("uid")
    @api.depends("member_ids.saldo")
    def _compute_mi_saldo(self):
        for grupo in self:
            yo = grupo.member_ids.filtered(lambda m: m.user_id == self.env.user)
            grupo.mi_saldo = yo[:1].saldo

    def _compute_access_url(self):
        super()._compute_access_url()
        for grupo in self:
            grupo.access_url = f"/gastos/{grupo.id}"

    # ------------------------------------------------------------------ saldos

    def _factor(self):
        return 100  # euros: dos decimales

    def saldos_centimos(self):
        """{miembro: saldo en céntimos} de todos los miembros (también los archivados que tengan movimientos)."""
        self.ensure_one()
        miembros = self.with_context(active_test=False).member_ids
        f = self._factor()
        saldos = dict.fromkeys(miembros, 0)
        for gasto in self.gasto_ids:
            saldos[gasto.pagador_id] = saldos.get(gasto.pagador_id, 0) + round(gasto.importe * f)
            for linea in gasto.linea_ids:
                saldos[linea.miembro_id] = saldos.get(linea.miembro_id, 0) - round(linea.importe * f)
        for pago in self.liquidacion_ids:
            c = round(pago.importe * f)
            saldos[pago.pagador_id] = saldos.get(pago.pagador_id, 0) + c
            saldos[pago.receptor_id] = saldos.get(pago.receptor_id, 0) - c
        return saldos

    def deudas(self):
        """[(deudor, acreedor, importe)] simplificadas, de mayor a menor."""
        self.ensure_one()
        f = self._factor()
        return [(d, a, c / f) for d, a, c in simplificar_deudas(self.saldos_centimos())]

    def _fmt(self, importe):
        """Importe en euros al estilo español (1.234,50 €)."""
        texto = f"{abs(importe):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"-{texto} €" if importe < 0 else f"{texto} €"

    @api.depends("gasto_ids.linea_ids.importe", "gasto_ids.pagador_id", "liquidacion_ids.importe")
    def _compute_deudas_html(self):
        for grupo in self:
            if not grupo.id:
                grupo.deudas_html = False
                continue
            filas = [
                Markup("<li><strong>%s</strong> debe <strong>%s</strong> a <strong>%s</strong></li>")
                % (d.name, grupo._fmt(importe), a.name)
                for d, a, importe in grupo.deudas()
            ]
            grupo.deudas_html = (Markup("<ul class='mb-0'>%s</ul>") % Markup("").join(filas)) if filas else \
                Markup("<p class='text-muted mb-0'>Todo saldado 🎉</p>")

    # ------------------------------------------------------------------ avisos

    def _correo(self, miembros, asunto, plantilla, **valores):
        """Un correo por miembro (con su saldo y lo que le toca pagar o cobrar) a los que tengan email."""
        self.ensure_one()
        grupo = self.sudo()
        deudas = grupo.deudas()
        saldos = grupo.saldos_centimos()
        f = grupo._factor()
        base = grupo.get_base_url()
        correos = self.env["mail.mail"].sudo()
        for miembro in miembros.sudo():
            email = miembro.partner_id.email
            if not email:
                continue
            body = self.env["ir.qweb"]._render(plantilla, {
                "grupo": grupo, "miembro": miembro, "saldo": saldos.get(miembro, 0) / f,
                "debo": [(a, i) for d, a, i in deudas if d == miembro],
                "me_deben": [(d, i) for d, a, i in deudas if a == miembro],
                "fmt": grupo._fmt, "url": f"{base}/gastos/{grupo.id}", **valores,
            })
            correos |= correos.create({
                "subject": f"{grupo.name}: {asunto}",
                "body_html": body,
                "recipient_ids": [(4, miembro.partner_id.id)],
                "email_from": self.env.company.email_formatted or self.env.user.email_formatted,
                "auto_delete": True,  # sin model/res_id: el historial ya lleva la nota del movimiento
            })
        return correos

    def _webhook(self, evento, **datos):
        """POST JSON al webhook del grupo después del commit (si falla la transacción, no se manda nada)."""
        self.ensure_one()
        url = self.sudo().webhook_url
        if not url:
            return
        grupo = self.sudo()
        payload = {
            "evento": evento,
            "grupo": {"id": grupo.id, "nombre": grupo.name, "moneda": "EUR",
                      "url": f"{grupo.get_base_url()}/gastos/{grupo.id}"},
            "saldos": [{"miembro": m.name, "email": m.partner_id.email or None, "saldo": s / grupo._factor()}
                       for m, s in grupo.saldos_centimos().items() if m.active or s],
            "deudas": [{"de": d.name, "a": a.name, "importe": i} for d, a, i in grupo.deudas()],
            **datos,
        }
        self.env.cr.postcommit.add(partial(_enviar_webhook, url, payload))

    def _avisar(self, evento, asunto, plantilla, autor, datos, **valores):
        """Aviso de un movimiento: correo a los demás miembros (si el grupo lo tiene activado) y webhook.
        `autor`: miembro que lo ha apuntado (no se le avisa); `datos`: lo que va al webhook."""
        self.ensure_one()
        if self.notificar_gastos:
            self._correo(self.member_ids - autor, asunto, plantilla, autor=autor, **valores)
        self._webhook(evento, **datos)

    def action_recordar_pagos(self):
        """Recordatorio ahora mismo a quien debe dinero."""
        for grupo in self:
            deudores = self.env["gastos.miembro"].browse({d.id for d, a, i in grupo.deudas()})
            grupo._correo(deudores, "recordatorio de pagos pendientes", "gastos.correo_recordatorio")
            grupo._webhook("recordatorio", deudores=deudores.mapped("name"))
            grupo.message_post(body=Markup("Recordatorio de pagos enviado a: %s") % (", ".join(deudores.mapped("name")) or "nadie"))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "message": "Recordatorio enviado a quien debe dinero."}}

    def action_abrir_web(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": f"/gastos/{self.id}", "target": "self"}

    @api.model
    def _cron_resumen_semanal(self):
        for grupo in self.search([("resumen_semanal", "=", True)]):
            saldos = grupo.saldos_centimos()
            pendientes = grupo.member_ids.filtered(lambda m: saldos.get(m))
            if not pendientes:
                continue
            grupo._correo(pendientes, "resumen semanal", "gastos.correo_resumen")
            grupo._webhook("resumen_semanal")


def _enviar_webhook(url, payload):
    try:
        requests.post(url, data=json.dumps(payload, default=str), timeout=5,
                      headers={"Content-Type": "application/json", "User-Agent": "Odoo gastos"})
    except requests.RequestException as e:
        _logger.warning("Webhook de gastos (%s) ha fallado: %s", url, e)
