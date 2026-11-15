import json
from datetime import datetime

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from ..services import lector

HTML = """<html><body><div class="_a6-g"><div class="_a6-p"><div><div>
<a target="_blank" href="https://www.instagram.com/Cuenta.Uno">Cuenta.Uno</a></div><div>Nov 10, 2026 3:41 pm</div></div></div></div>
<div><a target="_blank" href="https://www.instagram.com/_u/cuenta_dos">cuenta_dos</a></div>
<div><a href="https://www.instagram.com/cuenta.uno">repetida</a><a href="https://www.instagram.com/accounts/login">x</a></div>
<div><a href="https://help.instagram.com/123">ayuda</a> &amp; texto</div></body></html>"""

# Forma real de la exportación (2026-11-15), con datos inventados: tabla por cuenta, «URL» de la biografía que puede
# ser otro perfil de Instagram, cuentas sin «Nombre» y la fecha debajo.
def _cuenta(usuario, fecha, nombre=None, url=None):
    filas = "".join(f'<tr><td class="_a6_q">{k}</td><td class="_2piu _a6_r">{v}</td></tr>'
                    for k, v in (("URL", url), ("Nombre", nombre), ("Nombre de usuario", usuario)) if v)
    return (f'<div class="pam _3-95 _2ph- _a6-g uiBoxWhite noborder"><div class="_3-95 _a6-p"><div class="pam _a6-g">'
            f'<div class="_a6-p"><table style="table-layout: fixed;">{filas}</table></div></div></div>'
            f'<div class="_3-94 _a6-o">{fecha}</div></div>')


HTML_REAL = ('<html><head><title>Solicitudes de seguimiento pendientes</title></head><body><header><h1>Solicitudes</h1>'
             '<aside>Generado por <time datetime="2026-11-15T12:55Z">x</time></aside></header><main>'
             + _cuenta("prueba_uno", "nov. 15, 2026 4:05 am", "P R U E B A")
             + _cuenta("prueba.dos", "sept. 30, 2026 7:37 pm", "Dos &lt;3", url="https://instagram.com/otra.cuenta?utm_medium=copy_link")
             + _cuenta("__prueba_tres", "feb. 27, 2026 12:00 am")
             + _cuenta("prueba_cuatro", "fecha rara", url="https://www.tiktok.com/&#064;alguien")
             + "</main></body></html>")

JSON_EXPORT = {"relationships_follow_requests_sent": [
    {"title": "", "media_list_data": [], "string_list_data": [
        {"href": "https://www.instagram.com/json_uno", "value": "json_uno", "timestamp": 1762800000}]},
    {"title": "json_dos", "string_list_data": [{"href": "https://www.instagram.com/_u/json_dos", "timestamp": 1762800100}]},
]}


@tagged("post_install", "-at_install")
class TestLector(TransactionCase):

    def test_html(self):
        self.assertEqual([u for u, _f in lector.leer(HTML)], ["cuenta.uno", "cuenta_dos"])

    def test_html_real(self):
        filas = lector.leer(HTML_REAL)
        self.assertEqual([u for u, _f in filas], ["prueba_uno", "prueba.dos", "__prueba_tres", "prueba_cuatro"],
                         "solo la fila «Nombre de usuario», no la URL de la biografía")
        self.assertEqual([f for _u, f in filas], [datetime(2026, 11, 15, 4, 5), datetime(2026, 9, 30, 19, 37),
                                                   datetime(2026, 2, 27, 0, 0), None])

    def test_json(self):
        filas = lector.leer(json.dumps(JSON_EXPORT))
        self.assertEqual([u for u, _f in filas], ["json_uno", "json_dos"])
        self.assertEqual(filas[0][1], datetime(2025, 11, 10, 18, 40))

    def test_texto(self):
        texto = "@uno\n\nhttps://www.instagram.com/dos/\ntres, 12 nov\nno valido!!\n"
        self.assertEqual([u for u, _f in lector.leer(texto)], ["uno", "dos", "tres"])
        self.assertEqual(lector.leer(""), [])


@tagged("post_install", "-at_install")
class TestImportar(TransactionCase):

    def test_mas_antiguas_primero(self):
        Sol = self.env["ig.solicitud"]
        Sol.importar(HTML_REAL)
        orden = Sol.search([("user_id", "=", self.env.uid)]).mapped("username")
        self.assertEqual(orden, ["__prueba_tres", "prueba.dos", "prueba_uno", "prueba_cuatro"], "sin fecha, al final")

    def test_importar_y_reimportar(self):
        Sol = self.env["ig.solicitud"]
        self.assertEqual(Sol.importar("a\nb\nc\nd")["nuevas"], 4)
        por = {s.username: s for s in Sol.search([("user_id", "=", self.env.uid)])}
        por["a"].marcar("hecha")
        por["b"].marcar("abierta")
        por["c"].marcar("hecha")
        # Exportación nueva: «a» sigue pendiente (la cancelación no se hizo); «b» y «d» ya no salen; «e» es nueva
        stats = Sol.importar("a\nc\ne")
        self.assertEqual((stats["nuevas"], stats["vuelven"], stats["resueltas"]), (1, 2, 2))
        self.assertEqual({k: v.state for k, v in por.items()}, {"a": "pendiente", "b": "resuelta", "c": "pendiente", "d": "resuelta"})
        self.assertFalse(por["a"].done_at)
        # Sin «lista completa», lo que falta no se toca
        self.assertEqual(Sol.importar("zz", completa=False)["resueltas"], 0)
        self.assertEqual(por["a"].state, "pendiente")
        self.assertEqual(por["a"].url, "https://www.instagram.com/a/")


@tagged("post_install", "-at_install")
class TestWeb(HttpCase):

    def test_solo_con_el_grupo(self):
        for login in (None, "ig_otro"):
            if login:
                user = new_test_user(self.env, login=login, groups="base.group_user")
                self.authenticate(login, login)
            for url in ("/solicitudes-ig", "/solicitudes-ig/api/estado", "/solicitudes-ig/web/app.js"):
                self.assertEqual(self.url_open(url).status_code, 404, (login, url))

    def test_flujo(self):
        dani = new_test_user(self.env, login="ig_dani", groups="base.group_user,solicitudes_ig.group_ig_user")
        otro = new_test_user(self.env, login="ig_otro2", groups="base.group_user,solicitudes_ig.group_ig_user")
        self.env["ig.solicitud"].with_user(otro).create({"username": "de_otro"})
        self.authenticate("ig_dani", "ig_dani")
        pagina = self.url_open("/solicitudes-ig")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn("Abrir siguientes 10", pagina.text)
        self.assertIn('<a class="btn btn-outline-light" id="igOpenOne" target="_blank"', pagina.text,
                      "«Abrir la siguiente» es un enlace: Ctrl+clic la abre detrás")
        self.assertEqual(self.url_open("/solicitudes-ig/web/app.js").status_code, 200)

        def post(accion, body, ctype="application/json"):
            return self.url_open(f"/solicitudes-ig/api/{accion}", data=json.dumps(body), headers={"Content-Type": ctype})
        r = post("importar", {"contenido": HTML, "completa": True})
        self.assertEqual(r.json()["stats"]["nuevas"], 2)
        items = r.json()["items"]
        self.assertEqual([i["username"] for i in items], ["cuenta_dos", "cuenta.uno"],
                         "las de otro no salen; sin fechas, al revés que el archivo (que empieza por la más nueva)")
        r = post("marcar", {"ids": [i["id"] for i in items], "state": "hecha"})
        self.assertEqual({i["state"] for i in r.json()["items"]}, {"hecha"})
        self.assertEqual(r.json()["hoy"], 2)
        ajena = self.env["ig.solicitud"].with_user(otro).search([])
        post("marcar", {"ids": [ajena.id], "state": "hecha"})
        self.assertEqual(ajena.state, "pendiente", "no se tocan las de otro usuario")
        self.assertEqual(post("marcar", {"ids": [1], "state": "borrar"}).status_code, 400)
        self.assertEqual(post("marcar", {"ids": [1], "state": "hecha"}, "text/plain").status_code, 415)
        self.assertEqual(self.env.ref("solicitudes_ig.group_ig_user").user_ids & self.env.ref("base.user_admin"),
                         self.env.ref("base.user_admin"), "al instalar, solo Dani")
