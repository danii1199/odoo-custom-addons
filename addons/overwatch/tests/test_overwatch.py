import json

from odoo.tests import HttpCase, TransactionCase, tagged

from ..services.wiki import parsear_tabla

TABLA = """{{CTH|h=Ana|i=Skins}}
|-
{{CTS|n=Common (Free)}}
{{CPB|h=Ana Skin|n=Classic|c=2}}
|-
{{CTS|n=‎ {{rl|e}}‎ {{Credits}} 250|linend=|c=2}}
{{CTS|n=‎ {{rl|l|Halloween Terror}} {{Halloween Icon}} {{Credits}} 750}}
{{CPB|h=Ana Skin|n=Merciful|c=2}}
{{CPB|h=Ana Skin|n=Ghoul|l=Ghoul Ana}}
|-
{{CPB|h=Ana Skin|n=Otra}}
|-
{{CTS|n=ㅤ{{rl|e|Battle Pass}}}}
{{CVB|h=Ana Emote|n=Tea Time}}
{{CVB|h=Ana Emote|n=Dance}}
|}"""


@tagged("post_install", "-at_install")
class TestWiki(TransactionCase):

    def test_parsear_tabla(self):
        items = {i["name"]: i for i in parsear_tabla(TABLA)}
        self.assertEqual(items["Classic"]["rarity"], "common")
        self.assertEqual(items["Classic"]["source"], "Gratis")
        self.assertEqual((items["Merciful"]["rarity"], items["Merciful"]["source"]), ("epic", "250 créditos"))
        self.assertEqual((items["Ghoul"]["rarity"], items["Ghoul"]["source"]), ("legendary", "Halloween Terror · 750 créditos"))
        self.assertEqual(items["Ghoul"]["file"], "File:Ana Skin Ghoul Ana.png")
        self.assertEqual(items["Otra"]["source"], "250 créditos")  # fila sin cabecera: la de su columna en la fila anterior
        self.assertEqual((items["Dance"]["kind"], items["Dance"]["file"]), ("video", "File:Ana Emote Dance.webm"))
        self.assertEqual(items["Dance"]["source"], "Battle Pass")


@tagged("post_install", "-at_install")
class TestOverwatchWeb(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ana = cls.env["ow.hero"].create({
            "key": "test-ana", "name": "Ana", "role": "support", "subrole": "tactician", "health": 250,
            "story_video_url": "https://youtu.be/yzFWIw7wV8Q",
            "ability_ids": [(0, 0, {"name": "Dardo sedante"})],
            "cosmetic_ids": [(0, 0, {"name": "Clásico", "type": "skin", "rarity": "common", "wiki_file": "x"})]})
        cls.rein = cls.env["ow.hero"].create({"key": "test-reinhardt", "name": "Reinhardt", "role": "tank"})
        cls.user = cls.env["res.users"].create({
            "name": "Jugador", "login": "jugador", "password": "jugador-1234",
            "group_ids": [(6, 0, [cls.env.ref("overwatch.group_ow_user").id])]})
        cls.sin = cls.env["res.users"].create({
            "name": "Sin acceso", "login": "sinacceso", "password": "sinacceso-1234",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])]})

    def test_youtube_id(self):
        self.assertEqual(self.ana.youtube_id, "yzFWIw7wV8Q")
        self.assertEqual(self.ana.subrole_name, "Táctico")

    def test_sin_grupo_solo_mirar(self):
        """Sin sesión o sin el grupo se ve todo, pero sin favoritos (decisión del usuario, 2026-11-03)."""
        for login in (None, "sinacceso"):
            if login:
                self.authenticate(login, f"{login}-1234")
            r = self.url_open("/overwatch")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Reinhardt", r.text)
            self.assertNotIn('data-action="fav"', r.text)
            r = self.url_open("/overwatch/heroe/test-ana")
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('data-action="fav"', r.text)
        r = self.url_open("/overwatch/api/favorito", data=json.dumps({"hero_id": self.ana.id, "fav": True}),
                          headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 403)

    def test_paginas_y_favoritos(self):
        self.authenticate("jugador", "jugador-1234")
        r = self.url_open("/overwatch")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Reinhardt", r.text)
        r = self.url_open("/overwatch/heroe/test-ana")
        self.assertEqual(r.status_code, 200)
        self.assertIn("yzFWIw7wV8Q", r.text)
        self.assertIn("Clásico", r.text)
        self.assertEqual(self.url_open("/overwatch/heroe/no-existe").status_code, 404)

        def fav(hero, value, ctype="application/json"):
            return self.url_open("/overwatch/api/favorito", data=json.dumps({"hero_id": hero.id, "fav": value}),
                                 headers={"Content-Type": ctype})
        self.assertEqual(fav(self.ana, True).json(), {"favorites": [self.ana.id]})
        self.assertEqual(sorted(fav(self.rein, True).json()["favorites"]), sorted([self.ana.id, self.rein.id]))
        self.assertEqual(fav(self.ana, False).json(), {"favorites": [self.rein.id]})
        self.assertEqual(fav(self.ana, True, "text/plain").status_code, 415)
        pref = self.env["ow.pref"].search([("user_id", "=", self.user.id)])
        self.assertEqual(pref.favorite_ids, self.rein)
        # Cada uno solo ve sus favoritos
        otro = self.user.copy({"login": "otro-jugador"})
        self.env["ow.pref"].with_user(otro).mine()
        self.assertEqual(self.env["ow.pref"].with_user(self.user).search([]), pref)


@tagged("post_install", "-at_install")
class TestCopia(TransactionCase):

    def test_exportar_y_cargar(self):
        import tempfile

        from ..services import copia
        hero = self.env["ow.hero"].create({
            "key": "test-mei", "name": "Mei", "role": "damage",
            "ability_ids": [(0, 0, {"name": "Muro de hielo"})],
            "chapter_ids": [(0, 0, {"title": "Ecopunto"})],
            "cosmetic_ids": [(0, 0, {"name": "Yeti", "type": "skin", "rarity": "legendary", "wiki_file": "y"})]})
        with tempfile.TemporaryDirectory() as tmp:
            copia.exportar(self.env, tmp)
            hero.cosmetic_ids.name = "Cambiado"
            hero.ability_ids.unlink()
            s = copia.cargar(self.env, tmp)
        self.assertEqual(s["cosmetics_new"], 0)
        self.assertEqual(hero.cosmetic_ids.name, "Yeti")
        self.assertEqual(hero.ability_ids.name, "Muro de hielo")
        self.assertEqual(hero.chapter_ids.title, "Ecopunto")
