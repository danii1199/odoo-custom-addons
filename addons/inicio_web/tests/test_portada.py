from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPortada(HttpCase):

    def setUp(self):
        super().setUp()
        self.user = self.env["res.users"].create({
            "name": "Lola Prueba", "login": "lola", "password": "lola-lola-1",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])]})
        website = self.env.ref("base.default_website")
        self.menu = self.env["website.menu"].create({
            "name": "Rincón de prueba", "url": "/rincon-prueba", "parent_id": website.menu_id.id, "website_id": website.id})

    def test_portada_publica(self):
        r = self.url_open("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ini-app", r.text)
        self.assertIn("rincón privado", r.text)
        self.assertNotIn("Personalizar menú", r.text)

    def test_ocultar_entrada_del_menu(self):
        self.authenticate("lola", "lola-lola-1")
        r = self.url_open("/")
        self.assertIn("Personalizar menú", r.text)
        self.assertIn('href="/rincon-prueba"', r.text)
        # Guarda sin marcar «Rincón de prueba»: desaparece del menú solo para ella
        r = self.url_open("/inicio/menu", data={"csrf_token": self.csrf_token(), "visible": []})
        self.assertEqual(r.status_code, 200)
        self.assertIn("/rincon-prueba", self.user.ini_menu_oculto)
        self.assertNotIn('href="/rincon-prueba"', self.url_open("/").text)
        self.assertTrue(self.menu.with_user(self.env.ref("base.user_admin")).is_visible)
        # Y vuelve al marcarla
        self.url_open("/inicio/menu", data={"csrf_token": self.csrf_token(), "visible": ["/rincon-prueba"]})
        self.assertNotIn("/rincon-prueba", self.user.ini_menu_oculto or "")
        self.assertIn('href="/rincon-prueba"', self.url_open("/").text)

    def test_portal_desde_el_perfil(self):
        """Un usuario de portal lo cambia desde «Personalizar menú» del desplegable del perfil (/mi-menu)."""
        self.env["res.users"].create({"name": "Pepa", "login": "pepa", "password": "pepa-pepa-1",
                                      "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.authenticate("pepa", "pepa-pepa-1")
        r = self.url_open("/mi-menu")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/mi-menu"', r.text)  # el enlace del desplegable
        self.assertIn('value="/rincon-prueba"', r.text)
        r = self.url_open("/inicio/menu", data={"csrf_token": self.csrf_token(), "volver": "mi-menu"})
        self.assertTrue(r.url.endswith("/mi-menu?guardado=1"))
        self.assertIn("Guardado", r.text)
        self.assertNotIn('href="/rincon-prueba"', r.text)
