"""Una solicitud de seguimiento enviada y aún pendiente, de un usuario de Odoo. No se habla nunca con Instagram:
el usuario cancela a mano en el perfil (que abre la web) y lo marca aquí."""
from odoo import api, fields, models

from ..services import lector

ESTADOS = [
    ("pendiente", "Pendiente"),
    ("abierta", "Abierta"),        # su perfil se ha abierto en un pack, falta confirmar
    ("hecha", "Cancelada"),        # el usuario dice que la ha cancelado
    ("resuelta", "Ya no sale"),    # no está en la última exportación completa (cancelada o aceptada)
]


class IgSolicitud(models.Model):
    _name = "ig.solicitud"
    _description = "Solicitud de seguimiento pendiente en Instagram"
    # Las más antiguas primero. Sin fecha, al final; el archivo va de la más nueva a la más antigua, por eso
    # «sequence desc» desempata (mismo minuto) y ordena las que no tienen fecha.
    _order = "requested_at, sequence desc, id"
    _rec_name = "username"

    user_id = fields.Many2one("res.users", "Usuario", required=True, default=lambda self: self.env.user,
                              ondelete="cascade", index=True)
    username = fields.Char("Cuenta", required=True)
    url = fields.Char("Perfil", compute="_compute_url")
    state = fields.Selection(ESTADOS, "Estado", default="pendiente", required=True, index=True)
    sequence = fields.Integer("Orden", help="Orden en el archivo importado.")
    requested_at = fields.Datetime("Solicitada")
    opened_at = fields.Datetime("Abierta el")
    done_at = fields.Datetime("Cancelada el")

    _uniq = models.Constraint("UNIQUE (user_id, username)", "Esa cuenta ya está en tu lista.")

    @api.depends("username")
    def _compute_url(self):
        for s in self:
            s.url = f"https://www.instagram.com/{s.username}/"

    def marcar(self, state):
        ahora = fields.Datetime.now()
        vals = {"state": state}
        if state == "abierta":
            vals["opened_at"] = ahora
        elif state == "hecha":
            vals["done_at"] = ahora
        elif state == "pendiente":
            vals.update(opened_at=False, done_at=False)
        self.write(vals)

    @api.model
    def importar(self, contenido, completa=True):
        """Añade las cuentas del archivo. Si es la lista completa, lo pendiente o abierto que ya no sale pasa a «Ya no
        sale»; lo cancelado o resuelto que vuelve a salir, a pendiente (la cancelación no se hizo)."""
        filas = lector.leer(contenido)
        mias = {s.username: s for s in self.search([("user_id", "=", self.env.uid)])}
        stats = {"leidas": len(filas), "nuevas": 0, "ya_estaban": 0, "vuelven": 0, "resueltas": 0}
        en_archivo = set()
        for i, (usuario, fecha) in enumerate(filas):
            en_archivo.add(usuario)
            s = mias.get(usuario)
            if not s:
                self.create({"username": usuario, "requested_at": fecha, "sequence": i})
                stats["nuevas"] += 1
                continue
            s.sequence = i
            if s.state in ("hecha", "resuelta"):
                s.marcar("pendiente")
                stats["vuelven"] += 1
            else:
                stats["ya_estaban"] += 1
        if completa and filas:
            fuera = [s for u, s in mias.items() if u not in en_archivo and s.state in ("pendiente", "abierta")]
            for s in fuera:
                s.state = "resuelta"
            stats["resueltas"] = len(fuera)
        return stats
