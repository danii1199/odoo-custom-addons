"""Menú del sitio a gusto de cada usuario: página /mi-menu (enlazada desde el desplegable del perfil, para internos y
portal) y el formulario de la portada; los dos guardan en /inicio/menu."""
from odoo import http
from odoo.http import request


class InicioWeb(http.Controller):

    @http.route("/mi-menu", type="http", auth="user", methods=["GET"], website=True)
    def mi_menu(self, **kw):
        return request.render("inicio_web.mi_menu", {
            "entradas": request.env.website.inicio_menu(), "guardado": kw.get("guardado")})

    @http.route("/inicio/menu", type="http", auth="user", methods=["POST"], website=True)
    def guardar_menu(self, **post):
        # Solo URLs de entradas que el usuario puede ver (las de primer nivel del menú del sitio, salvo la portada)
        posibles = {m["url"] for m in request.env.website.inicio_menu()}
        visibles = set(request.httprequest.form.getlist("visible"))
        ocultos = sorted(posibles - visibles)
        request.env.user.sudo().ini_menu_oculto = " ".join(ocultos)
        if post.get("volver") == "mi-menu":
            return request.redirect("/mi-menu?guardado=1")
        return request.redirect("/")
