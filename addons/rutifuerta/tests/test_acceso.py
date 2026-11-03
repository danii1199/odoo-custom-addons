"""Rutifuerta solo existe para quien tiene el grupo: para el resto, todo da 404 (ni pide login)."""
from odoo.tests import HttpCase, new_test_user, tagged

RUTAS = ["/rutifuerta", "/rutifuerta/sync", "/rutifuerta/web/js/main.js", "/rutifuerta/web/icon.png",
         "/rutifuerta/api/meta"]


@tagged("post_install", "-at_install")
class TestAcceso(HttpCase):

    def _codigos(self):
        return {r: self.url_open(r, allow_redirects=False).status_code for r in RUTAS}

    def test_sin_sesion_no_existe(self):
        self.assertEqual(set(self._codigos().values()), {404})
        self.assertEqual(self.url_open("/rutifuerta/api/catalog/import", data="{}", allow_redirects=False,
                                       headers={"Content-Type": "application/json"}).status_code, 404)

    def test_otro_usuario_no_existe(self):
        new_test_user(self.env, login="sin_fuerta", groups="base.group_user", password="sin_fuerta_1234")
        self.authenticate("sin_fuerta", "sin_fuerta_1234")
        self.assertEqual(set(self._codigos().values()), {404})

    def test_con_permiso(self):
        new_test_user(self.env, login="con_fuerta", groups="base.group_user,rutifuerta.group_fuerta_user",
                      password="con_fuerta_1234")
        self.authenticate("con_fuerta", "con_fuerta_1234")
        self.assertEqual(set(self._codigos().values()), {200})

    def test_no_sale_de_web(self):
        new_test_user(self.env, login="con_fuerta2", groups="base.group_user,rutifuerta.group_fuerta_user",
                      password="con_fuerta_1234")
        self.authenticate("con_fuerta2", "con_fuerta_1234")
        # Con %2e%2e Odoo da 500 al pintar su 404 (también en rutas inventadas): lo que importa es que no lo sirva
        for r in ("/rutifuerta/web/../__manifest__.py", "/rutifuerta/web/%2e%2e/__manifest__.py"):
            res = self.url_open(r, allow_redirects=False)
            self.assertNotEqual(res.status_code, 200, r)
            self.assertNotIn(b"depends", res.content, r)

    def test_misma_404_que_una_ruta_inventada(self):
        inventada = self.url_open("/no-existe-esto", allow_redirects=False)
        for r in RUTAS:
            res = self.url_open(r, allow_redirects=False)
            self.assertIn(b"<title>Page Not Found", res.content, r)
            self.assertEqual(res.headers.get("Content-Type"), inventada.headers.get("Content-Type"), r)
