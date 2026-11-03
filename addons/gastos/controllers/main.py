"""Web /gastos para los miembros (usuarios de portal o internos): todo lo que se hace en el backend, desde el móvil.
Grupos (crear, ajustes, imagen, archivar), miembros (añadir, invitar, archivar, quitar), gastos (apuntar, editar,
borrar), pagos (saldar, borrar) y exportar/importar el CSV de Splitwise.

Solo con el grupo gastos.group_gastos_web (si no, 404 en todas las rutas: `_acceso`). Lo que ve y edita cada uno
lo limitan los dominios de security/ir.access.csv (solo sus grupos), sin sudo. Excepciones
con sudo, siempre después de comprobar que el usuario puede editar el grupo (`_gestionable`): crear el grupo con su
primer miembro, y crear/cambiar miembros (los de portal no pueden crear contactos ni miembros)."""
import base64
from pathlib import Path
from urllib.parse import quote

from odoo import fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.tools import email_normalize

from ..models.gasto import CATEGORIAS, REPARTOS
from ..models.splitwise import MAX_CSV

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "src"
VERSION = str(int(max(p.stat().st_mtime for p in STATIC_DIR.rglob("*") if p.is_file())))
MAX_IMAGEN = 10 * 1024 * 1024


def _num(texto):
    """'12,50' o '1.234,5' → 12.5 / 1234.5 (también acepta el punto decimal)."""
    texto = (texto or "").strip().replace(" ", "").replace("€", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto) if texto else 0.0


def _coma(n):
    """12.5 → '12,5' para rellenar los campos del formulario."""
    return f"{n:g}".replace(".", ",")


def _msg(e):
    return str(e.args[0] if getattr(e, "args", None) else e)


class GastosWeb(http.Controller):

    def _render(self, template, **values):
        return request.render(template, {"v": VERSION, "categorias": dict(CATEGORIAS), **values})

    def _acceso(self):
        if not request.env.user.has_group("gastos.group_gastos_web"):
            raise request.not_found()

    def _grupo(self, grupo_id, archivados=False):
        self._acceso()
        grupo = request.env["gastos.grupo"].with_context(active_test=not archivados).browse(grupo_id)
        try:
            grupo.check_access("read")
            grupo.name  # noqa: B018 (lanza MissingError si no existe)
        except (AccessError, MissingError):
            raise request.not_found()
        return grupo

    def _gestionable(self, grupo_id):
        """El grupo, si el usuario puede editarlo (miembro, creador o administrador); si no, 404."""
        grupo = self._grupo(grupo_id, archivados=True)
        try:
            grupo.check_access("write")
        except AccessError:
            raise request.not_found()
        return grupo

    def _yo(self, grupo):
        return grupo.member_ids.filtered(lambda m: m.user_id == request.env.user)[:1]

    def _puede_crear_grupos(self):
        user = request.env.user
        return user.has_group("gastos.group_gastos_web")

    def _volver(self, url, aviso=None, error=None):
        if error:
            return request.redirect(f"{url}?error={quote(error)}")
        return request.redirect(f"{url}?aviso={quote(aviso)}" if aviso else url)

    # ------------------------------------------------------------------ grupos

    @http.route("/gastos", type="http", auth="user", website=True)
    def grupos(self, **kw):
        self._acceso()
        Grupo = request.env["gastos.grupo"].with_context(active_test=False)
        mios = Grupo.search([("member_ids.user_id", "=", request.env.user.id)])
        return self._render("gastos.web_grupos", grupos=mios.filtered("active"),
                            archivados=mios.filtered(lambda g: not g.active),
                            puede_crear=self._puede_crear_grupos(), aviso=kw.get("aviso"))

    @http.route("/gastos/<int:grupo_id>", type="http", auth="user", website=True)
    def grupo(self, grupo_id, **kw):
        grupo = self._grupo(grupo_id, archivados=True)
        saldos, f = grupo.saldos_centimos(), grupo._factor()
        movimientos = sorted(
            [("gasto", g) for g in grupo.gasto_ids] + [("pago", p) for p in grupo.liquidacion_ids],
            key=lambda x: (x[1].fecha, x[1].create_date), reverse=True)
        return self._render(
            "gastos.web_grupo", grupo=grupo, yo=self._yo(grupo), fmt=grupo._fmt,
            saldos=sorted(((m, s / f) for m, s in saldos.items() if m.active or s), key=lambda x: -x[1]),
            deudas=grupo.deudas(), movimientos=movimientos[:200], aviso=kw.get("aviso"), error=kw.get("error"))

    @http.route("/gastos/nuevo-grupo", type="http", auth="user", website=True, methods=["GET", "POST"])
    def nuevo_grupo(self, **post):
        if not self._puede_crear_grupos():
            raise request.not_found()
        if request.httprequest.method == "GET":
            return self._render("gastos.web_grupo_nuevo", form={}, error=None)
        nombre = (post.get("name") or "").strip()
        if not nombre:
            return self._render("gastos.web_grupo_nuevo", form=post, error="Ponle un nombre al grupo.")
        vals = {"name": nombre, "description": post.get("description") or False,
                "member_ids": [(0, 0, {"partner_id": request.env.user.partner_id.id})]}
        try:
            imagen = self._imagen(post)
        except UserError as e:
            return self._render("gastos.web_grupo_nuevo", form=post, error=_msg(e))
        if imagen:
            vals["image"] = imagen
        # sudo: los de portal no pueden crear miembros; el creador entra como primer miembro
        grupo = request.env["gastos.grupo"].sudo().create(vals)
        return self._volver(f"/gastos/{grupo.id}/ajustes", "Grupo creado: añade a los demás miembros")

    def _imagen(self, post):
        """Imagen subida en el formulario (base64) o None."""
        archivo = request.httprequest.files.get("image")
        if not archivo or not archivo.filename:
            return None
        datos = archivo.read()
        if len(datos) > MAX_IMAGEN:
            raise UserError("La imagen es demasiado grande (máximo 10 MB).")
        if not (archivo.mimetype or "").startswith("image/"):
            raise UserError("El archivo no es una imagen.")
        return base64.b64encode(datos).decode()

    @http.route("/gastos/<int:grupo_id>/ajustes", type="http", auth="user", website=True, methods=["GET"])
    def ajustes(self, grupo_id, **kw):
        grupo = self._gestionable(grupo_id)
        miembros = grupo.with_context(active_test=False).member_ids
        saldos = grupo.saldos_centimos()
        return self._render("gastos.web_ajustes", grupo=grupo, yo=self._yo(grupo), miembros=miembros,
                            con_movimientos={m.id for m in miembros if self._tiene_movimientos(m)},
                            fmt=grupo._fmt, saldos={m.id: saldos.get(m, 0) / 100 for m in miembros},
                            aviso=kw.get("aviso"), error=kw.get("error"))

    @staticmethod
    def _tiene_movimientos(miembro):
        g = miembro.grupo_id
        return bool(g.gasto_ids.filtered(lambda x: x.pagador_id == miembro or miembro in x.linea_ids.miembro_id)
                    or g.liquidacion_ids.filtered(lambda p: miembro in (p.pagador_id | p.receptor_id)))

    @http.route("/gastos/<int:grupo_id>/ajustes", type="http", auth="user", website=True, methods=["POST"])
    def guardar_ajustes(self, grupo_id, **post):
        grupo = self._gestionable(grupo_id)
        url = f"/gastos/{grupo.id}/ajustes"
        nombre = (post.get("name") or "").strip()
        if not nombre:
            return self._volver(url, error="El grupo tiene que tener nombre.")
        vals = {"name": nombre, "description": post.get("description") or False,
                "notificar_gastos": bool(post.get("notificar_gastos")),
                "resumen_semanal": bool(post.get("resumen_semanal"))}
        try:
            imagen = self._imagen(post)
            if imagen:
                vals["image"] = imagen
            elif post.get("quitar_imagen"):
                vals["image"] = False
            grupo.write(vals)
        except (UserError, ValidationError, AccessError) as e:
            request.env.cr.rollback()
            return self._volver(url, error=_msg(e))
        return self._volver(url, "Cambios guardados")

    @http.route("/gastos/<int:grupo_id>/archivar", type="http", auth="user", website=True, methods=["POST"])
    def archivar(self, grupo_id, **post):
        grupo = self._gestionable(grupo_id)
        grupo.active = not grupo.active
        return self._volver(f"/gastos/{grupo.id}", "Grupo archivado" if not grupo.active else "Grupo reactivado")

    # ------------------------------------------------------------------ miembros

    @http.route("/gastos/<int:grupo_id>/miembros/nuevo", type="http", auth="user", website=True, methods=["POST"])
    def nuevo_miembro(self, grupo_id, **post):
        grupo = self._gestionable(grupo_id)
        url = f"/gastos/{grupo.id}/ajustes"
        nombre = (post.get("name") or "").strip()
        email = email_normalize(post.get("email") or "") or False
        if not nombre:
            return self._volver(url, error="Escribe el nombre del nuevo miembro.")
        if post.get("email") and not email:
            return self._volver(url, error="Ese correo no es válido.")
        g = grupo.sudo()
        Partner = request.env["res.partner"].sudo()
        # Si ya hay alguien con cuenta y ese correo, es esa persona (así ve el grupo al momento); si no, contacto nuevo
        partner = email and Partner.search([("email_normalized", "=", email), ("user_ids", "!=", False)], limit=1)
        if partner and partner in g.with_context(active_test=False).member_ids.partner_id:
            return self._volver(url, error=f"{partner.name} ya está en el grupo.")
        try:
            partner = partner or Partner.create({"name": nombre, "email": email})
            miembro = request.env["gastos.miembro"].sudo().create({"grupo_id": g.id, "partner_id": partner.id})
            if post.get("invitar") and email and not miembro.user_id:
                miembro.action_invitar()
        except (UserError, ValidationError) as e:
            request.env.cr.rollback()
            return self._volver(url, error=_msg(e))
        g.message_post(body=f"{request.env.user.name} ha añadido a {miembro.name} al grupo.")
        aviso = f"{miembro.name} añadido" + (" e invitado" if post.get("invitar") and email and miembro.user_id else "")
        return self._volver(url, aviso)

    @http.route("/gastos/<int:grupo_id>/miembros/<int:miembro_id>/<string:accion>", type="http", auth="user",
                website=True, methods=["POST"])
    def miembro(self, grupo_id, miembro_id, accion, **post):
        grupo = self._gestionable(grupo_id)
        url = f"/gastos/{grupo.id}/ajustes"
        miembro = request.env["gastos.miembro"].sudo().with_context(active_test=False).browse(miembro_id).exists()
        if not miembro or miembro.grupo_id != grupo.sudo():
            raise request.not_found()
        if accion in ("archivar", "quitar") and miembro.user_id == request.env.user:
            return self._volver(url, error="No puedes sacarte a ti mismo del grupo (perderías el acceso).")
        try:
            if accion == "invitar":
                if not miembro.email:
                    raise UserError(f"{miembro.name} no tiene correo.")
                miembro.action_invitar()
                aviso = f"Invitación enviada a {miembro.name}"
            elif accion == "correo":
                email = email_normalize(post.get("email") or "")
                if not email:
                    raise UserError("Ese correo no es válido.")
                if miembro.user_id:
                    raise UserError(f"{miembro.name} ya tiene cuenta: su correo lo cambia él en su perfil.")
                miembro.partner_id.email = email
                aviso = f"Correo de {miembro.name} guardado"
            elif accion == "archivar":
                miembro.active = False
                aviso = f"{miembro.name} archivado: ya no entra en los repartos nuevos"
            elif accion == "activar":
                miembro.active = True
                aviso = f"{miembro.name} vuelve a estar activo"
            elif accion == "quitar":
                if self._tiene_movimientos(miembro):
                    raise UserError(f"{miembro.name} tiene gastos o pagos en el grupo: archívalo en vez de quitarlo.")
                nombre = miembro.name
                miembro.unlink()
                aviso = f"{nombre} ya no está en el grupo"
            else:
                raise request.not_found()
        except (UserError, ValidationError) as e:
            request.env.cr.rollback()
            return self._volver(url, error=_msg(e))
        return self._volver(url, aviso)

    # ------------------------------------------------------------------ gastos

    @http.route("/gastos/<int:grupo_id>/nuevo", type="http", auth="user", website=True, methods=["GET"])
    def nuevo(self, grupo_id, **kw):
        grupo = self._grupo(grupo_id)
        return self._form(grupo, {})

    def _form(self, grupo, form, error=None, gasto=None):
        return self._render("gastos.web_nuevo", grupo=grupo, yo=self._yo(grupo), form=form, error=error,
                            gasto=gasto, repartos=REPARTOS, hoy=fields.Date.context_today(grupo))

    def _vals_gasto(self, grupo, post):
        reparto = post.get("reparto") if post.get("reparto") in dict(REPARTOS) else "igual"
        lineas = []
        for m in grupo.member_ids:
            if reparto == "igual":
                if post.get(f"m_{m.id}"):
                    lineas.append((0, 0, {"miembro_id": m.id, "valor": 1}))
            else:
                valor = _num(post.get(f"v_{m.id}"))
                if valor:
                    lineas.append((0, 0, {"miembro_id": m.id, "valor": valor}))
        return {
            "name": (post.get("name") or "").strip() or "Gasto",
            "importe": _num(post.get("importe")),
            "fecha": post.get("fecha") or fields.Date.context_today(grupo),
            "pagador_id": int(post.get("pagador_id") or 0),
            "categoria": post.get("categoria") if post.get("categoria") in dict(CATEGORIAS) else "otros",
            "reparto": reparto,
            "nota": post.get("nota") or False,
            "linea_ids": lineas,
        }

    @http.route("/gastos/<int:grupo_id>/nuevo", type="http", auth="user", website=True, methods=["POST"])
    def guardar(self, grupo_id, **post):
        grupo = self._grupo(grupo_id)
        try:
            gasto = request.env["gastos.gasto"].create({"grupo_id": grupo.id, **self._vals_gasto(grupo, post)})
            gasto.flush_recordset()  # que salten aquí las restricciones
        except (ValidationError, AccessError, ValueError) as e:
            request.env.cr.rollback()
            return self._form(grupo, post, error=_msg(e))
        return self._volver(f"/gastos/{grupo.id}", "Gasto guardado")

    def _gasto(self, grupo, gasto_id):
        gasto = request.env["gastos.gasto"].browse(gasto_id).exists()
        if not gasto or gasto.grupo_id != grupo:
            raise request.not_found()
        return gasto

    @http.route("/gastos/<int:grupo_id>/gasto/<int:gasto_id>", type="http", auth="user", website=True,
                methods=["GET"])
    def editar(self, grupo_id, gasto_id, **kw):
        grupo = self._grupo(grupo_id)
        gasto = self._gasto(grupo, gasto_id)
        form = {"name": gasto.name, "importe": _coma(gasto.importe), "fecha": str(gasto.fecha),
                "pagador_id": str(gasto.pagador_id.id), "categoria": gasto.categoria, "reparto": gasto.reparto,
                "nota": gasto.nota or ""}
        for linea in gasto.linea_ids:
            form[f"m_{linea.miembro_id.id}"] = "1"
            form[f"v_{linea.miembro_id.id}"] = _coma(linea.valor)
        return self._form(grupo, form, gasto=gasto)

    @http.route("/gastos/<int:grupo_id>/gasto/<int:gasto_id>", type="http", auth="user", website=True,
                methods=["POST"])
    def guardar_edicion(self, grupo_id, gasto_id, **post):
        grupo = self._grupo(grupo_id)
        gasto = self._gasto(grupo, gasto_id)
        try:
            vals = self._vals_gasto(grupo, post)
            vals["linea_ids"] = [(5, 0, 0)] + vals["linea_ids"]
            gasto.write(vals)
            gasto.flush_recordset()
        except (ValidationError, AccessError, ValueError) as e:
            request.env.cr.rollback()
            return self._form(grupo, post, error=_msg(e), gasto=gasto)
        return self._volver(f"/gastos/{grupo.id}", "Gasto modificado")

    # ------------------------------------------------------------------ saldar y borrar

    @http.route("/gastos/<int:grupo_id>/saldar", type="http", auth="user", website=True, methods=["POST"])
    def saldar(self, grupo_id, **post):
        """Apuntar un pago: quien paga es siempre el usuario (nadie paga por otro)."""
        grupo = self._grupo(grupo_id)
        yo = self._yo(grupo)
        if not yo:
            return self._volver(f"/gastos/{grupo.id}", error="Solo los miembros del grupo pueden apuntar pagos.")
        try:
            pago = request.env["gastos.liquidacion"].create({
                "grupo_id": grupo.id,
                "pagador_id": yo.id,
                "receptor_id": int(post.get("receptor_id") or 0),
                "importe": _num(post.get("importe")),
                "nota": post.get("nota") or False,
            })
            pago.flush_recordset()
        except (ValidationError, AccessError, ValueError) as e:
            request.env.cr.rollback()
            return self._volver(f"/gastos/{grupo.id}", error=_msg(e))
        return self._volver(f"/gastos/{grupo.id}", "Pago apuntado")

    def _pago(self, grupo, pago_id):
        pago = request.env["gastos.liquidacion"].browse(pago_id).exists()
        if not pago or pago.grupo_id != grupo:
            raise request.not_found()
        return pago

    @http.route("/gastos/<int:grupo_id>/pago/<int:pago_id>", type="http", auth="user", website=True,
                methods=["GET", "POST"])
    def pago(self, grupo_id, pago_id, **post):
        """Editar un pago: solo quien lo apuntó (el modelo lo vuelve a comprobar). Cada cambio queda en su historial."""
        grupo = self._grupo(grupo_id, archivados=True)
        pago = self._pago(grupo, pago_id)
        error = None
        if request.httprequest.method == "POST":
            try:
                pago.write({  # quien paga no cambia: es quien lo apuntó
                    "receptor_id": int(post.get("receptor_id") or 0),
                    "importe": _num(post.get("importe")),
                    "fecha": post.get("fecha") or pago.fecha,
                    "nota": post.get("nota") or False,
                })
                pago.flush_recordset()
                return self._volver(f"/gastos/{grupo.id}", "Pago modificado")
            except (ValidationError, AccessError, ValueError) as e:
                request.env.cr.rollback()
                error = _msg(e)
        return self._render("gastos.web_pago", grupo=grupo, pago=pago, fmt=grupo._fmt, form=post, error=error)

    @http.route("/gastos/<int:grupo_id>/borrar/<string:tipo>/<int:rec_id>", type="http", auth="user",
                website=True, methods=["POST"])
    def borrar(self, grupo_id, tipo, rec_id, **post):
        grupo = self._grupo(grupo_id)
        modelo = {"gasto": "gastos.gasto", "pago": "gastos.liquidacion"}.get(tipo)
        if not modelo:
            raise request.not_found()
        rec = request.env[modelo].browse(rec_id)
        try:
            if rec.grupo_id != grupo:
                raise AccessError("No es de este grupo")
            rec.unlink()
        except (AccessError, MissingError):
            request.env.cr.rollback()
            return self._volver(f"/gastos/{grupo.id}", error="No se ha podido borrar.")
        return self._volver(f"/gastos/{grupo.id}", "Borrado")

    # ------------------------------------------------------------------ Splitwise

    @http.route("/gastos/<int:grupo_id>/exportar-splitwise", type="http", auth="user", website=True, methods=["GET"])
    def exportar_splitwise(self, grupo_id, **kw):
        grupo = self._grupo(grupo_id, archivados=True)
        nombre = grupo.nombre_exportacion()
        return request.make_response(grupo.exportar_splitwise().encode("utf-8"), headers=[
            ("Content-Type", "text/csv; charset=utf-8"),
            ("Content-Disposition", f"attachment; filename=\"{nombre}\"; filename*=UTF-8''{quote(nombre)}"),
        ])

    @staticmethod
    def _leer_csv_subido():
        archivo = request.httprequest.files.get("archivo")
        if not archivo or not archivo.filename:
            raise UserError("Elige el CSV que exportaste de Splitwise.")
        datos = archivo.read(MAX_CSV + 1)
        if len(datos) > MAX_CSV:
            raise UserError("El archivo es demasiado grande (máximo 5 MB).")
        try:
            return datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            return datos.decode("latin-1")

    @http.route("/gastos/<int:grupo_id>/importar-splitwise", type="http", auth="user", website=True, methods=["POST"])
    def importar_splitwise(self, grupo_id, **post):
        """Paso 1: leer el CSV y enseñar qué se va a importar y a qué miembro corresponde cada persona."""
        grupo = self._gestionable(grupo_id)
        try:
            texto = self._leer_csv_subido()
            info = grupo.analizar_splitwise(texto)
        except UserError as e:
            return self._volver(f"/gastos/{grupo.id}/ajustes", error=_msg(e))
        return self._render("gastos.web_importar", grupo=grupo, info=info,
                            miembros=grupo.with_context(active_test=False).member_ids,
                            csv=base64.b64encode(texto.encode()).decode())

    @http.route("/gastos/<int:grupo_id>/importar-splitwise/confirmar", type="http", auth="user", website=True,
                methods=["POST"])
    def confirmar_splitwise(self, grupo_id, **post):
        """Paso 2: importar con el emparejamiento elegido (p_<n> = id del miembro o vacío para crear uno nuevo)."""
        grupo = self._gestionable(grupo_id)
        url = f"/gastos/{grupo.id}"
        try:
            texto = base64.b64decode(post.get("csv") or "").decode()
            personas = grupo.analizar_splitwise(texto)["personas"]
            Miembro = request.env["gastos.miembro"].sudo().with_context(active_test=False)
            mapeo = {n: Miembro.browse(int(post.get(f"p_{i}") or 0)).exists() for i, n in enumerate(personas)}
            n_gastos, n_pagos = grupo.importar_splitwise(texto, mapeo)
        except (UserError, ValidationError, AccessError, ValueError) as e:
            request.env.cr.rollback()
            return self._volver(f"{url}/ajustes", error=f"No se ha podido importar: {_msg(e)}")
        if not n_gastos and not n_pagos:
            return self._volver(url, "No había nada nuevo que importar")
        return self._volver(url, f"Importados de Splitwise {n_gastos} gastos y {n_pagos} pagos")
