import json
from datetime import date

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


TEMPORADAS = """==List of Seasons==
===Season 1===
[[File:Season 1.png|300px|thumb|Season 1 Roadmap]]
(4 October 2022 - 6 December 2022)
*'''New Heroes'''
**[[Heroe Inventado]] ([[Damage]])
**[[Test Ana]] ([[Support]])
*'''New Battle Pass'''
**Mythic [[Skins|Skin]] ({{rl|m|Clásico}} [[Test Ana]])
*'''Event'''
**[[Halloween Terror|Halloween Terror Event]] 2022
=== Season 4: Heroes of Busan <span class="anchor" id="Season 1"></span>===
(February 18 - 22 April 2025)
* '''Theme and Story:''' [[Busan]] attacked
* '''New Battle Pass:'''
** Mythic Skin ({{rl|m|Void Dancer}} [[Widowmaker]], Midseason)
** Mythic Weapon Skin - {{rl|m|Eternal Crystal}} ([[Sojourn]])
** Battle Pass rework
=== Season 5: A Grim Doctrine <span class="anchor" id="Season 5"></span>===
(6 October 2026 - 8 December 2026)
* '''New {{Raritylink|m|text=Mythic}} Skins'''
** Mythic Skin ({{Raritylink|m|text=Dragon Shaoxia}} [[Wuyang]])
** Mythic Weapon Skin - {{Raritylink|m|text=Treblemaker}} ([[Lúcio]])
=== Season 6: TBA ===
(December 2026 - February 2027)
==References==
"""


@tagged("post_install", "-at_install")
class TestTemporadas(TransactionCase):

    def test_parsear_y_guardar(self):
        from datetime import date

        from ..services import seasons
        self.env["ow.season"].search([]).unlink()  # la base de pruebas puede tener ya las de la wiki
        ts = seasons.parsear_pagina(TEMPORADAS, "Overwatch 2", None)
        self.assertEqual([t["key"] for t in ts], ["ow2-s1", "ow2-s4", "ow2-s5", "ow2-s6"])
        s1, s4, s5, s6 = ts
        self.assertEqual([(r["kind"], r["name"], r["hero"]) for r in s5["rewards"]],
                         [("skin", "Dragon Shaoxia", "Wuyang"), ("weapon", "Treblemaker", "Lúcio")], "formato de 2026")
        self.assertEqual((s1["date_start"], s1["date_end"]), (date(2022, 10, 4), date(2022, 12, 6)))
        self.assertEqual(s1["image_file"], "File:Season 1.png")
        self.assertEqual(s1["heroes"], ["Heroe Inventado", "Test Ana"])
        self.assertEqual(s1["rewards"], [{"kind": "skin", "name": "Clásico", "hero": "Test Ana"}])
        self.assertEqual(s4["subtitle"], "Heroes of Busan")
        self.assertEqual((s4["date_start"], s4["date_end"]), (date(2025, 2, 18), date(2025, 4, 22)))  # año del final
        self.assertEqual([(r["kind"], r["name"]) for r in s4["rewards"]],
                         [("midseason", "Void Dancer"), ("weapon", "Eternal Crystal")])
        self.assertEqual(s4["theme"], "Busan attacked")
        self.assertEqual((s6["subtitle"], s6["date_start"], s6["dates_text"]),
                         ("", None, "diciembre de 2026 – febrero de 2027"))

        ana = self.env["ow.hero"].create({
            "key": "test-ana", "name": "Ana", "wiki_name": "Test Ana", "role": "support",
            "cosmetic_ids": [(0, 0, {"name": "Clasico", "type": "skin", "rarity": "mythic", "wiki_file": "z"})]})
        r = seasons.guardar(self.env, ts)
        self.assertEqual(r, {"new": 4, "updated": 0, "changes": 0}, "la primera carga no llena Novedades")
        t1 = self.env["ow.season"].search([("key", "=", "ow2-s1")])
        self.assertEqual(t1.new_hero_ids, ana)
        self.assertEqual(t1.new_heroes_text, "Heroe Inventado")  # sin héroe en el catálogo: queda como texto
        self.assertEqual(t1.reward_ids.cosmetic_id, ana.cosmetic_ids, "enlaza el aspecto aunque cambien las tildes")
        self.assertEqual(seasons.guardar(self.env, ts), {"new": 0, "updated": 4, "changes": 0})
        self.assertEqual(len(t1.reward_ids), 1, "las recompensas se rehacen, no se duplican")
        self.assertEqual(t1.state, "past")
        self.assertEqual(self.env["ow.season"].search([("key", "=", "ow2-s6")]).state, "upcoming")


@tagged("post_install", "-at_install")
class TestPasesWeb(HttpCase):

    def test_pagina_publica(self):
        hoy = date.today()
        self.env["ow.season"].search([]).unlink()
        self.env["ow.season"].create([
            {"key": "t-1", "sequence": 1, "number": 1, "arc": "Overwatch 2", "date_start": hoy.replace(year=hoy.year - 2),
             "date_end": hoy.replace(year=hoy.year - 1), "dates_text": "hace tiempo"},
            {"key": "t-2", "sequence": 2, "number": 2, "subtitle": "La de ahora", "arc": "Overwatch 2",
             "date_start": hoy.replace(year=hoy.year - 1), "dates_text": "ahora",
             "reward_ids": [(0, 0, {"name": "Mítico <de> prueba", "kind": "skin", "hero_text": "Nadie"})]},
        ])
        r = self.url_open("/overwatch/pases")  # sin sesión: la web es pública
        self.assertEqual(r.status_code, 200)
        actual = r.text.split("Pase actual", 1)[1].split("Pases anteriores", 1)
        self.assertIn("La de ahora", actual[0])
        self.assertIn("Mítico &lt;de&gt; prueba", actual[0])
        self.assertIn("Temporada 1", actual[1])
        self.assertIn('href="/overwatch/pases"', self.url_open("/overwatch").text)


HABILIDADES = """{{Ability_details
| ability_name = Scattergun
| official_description = Pump action shotgun.
| damage = 8 – 2.4 (per shot)<br />80 – 24 (per volley)
| fire_rate = {{tt|1.33 volleys/s|1 volley every 0.75 seconds}}
| reload_time = 1.5 seconds
| spread = None
| headshot = ✓
| ability_details = * Notas largas que no se guardan.
}}
{{Ability_details
| ability_name = Adrenaline Rush
| heal = {{#vardefineecho:rush healing percent|250}}% of wound damage dealt
}}
{{Ability_details
| ability_name = Resurrect (old)
| cooldown = 30 seconds
}}"""


@tagged("post_install", "-at_install")
class TestDetalles(TransactionCase):

    def test_parsear_habilidades(self):
        from ..services import detalles
        d = detalles.parsear(HABILIDADES)
        self.assertEqual(set(d), {"Scattergun", "Adrenaline Rush"}, "las retiradas «(old)» no cuentan")
        self.assertEqual(d["Scattergun"], [
            ["Daño", "8 – 2.4 (por disparo) · 80 – 24 (por ráfaga)"], ["Recarga", "1.5 s"],
            ["Cadencia", "1.33 ráfagas/s"], ["Críticos", "Sí"]])  # «None» se descarta
        self.assertEqual(d["Adrenaline Rush"], [["Curación", "250% of wound de daño infligido"]])

    def test_novedades_al_comparar(self):
        from ..services.importer import Importer
        hero = self.env["ow.hero"].create({"key": "test-jq", "name": "Junker Queen", "role": "tank", "health": 525})
        imp = Importer(self.env, cosmetics=False, details=False, batch="prueba")
        antes = {("ability", "Escopeta"): {"description": "Pum", "stats": [["Recarga", "1.5 s"]]},
                 ("ability", "Vieja"): {"description": "", "stats": False}}
        nuevas = [{"kind": "ability", "name": "Escopeta", "description": "Pum", "stats": [["Recarga", "2 s"]]},
                  {"kind": "ability", "name": "Nueva", "description": "Otra", "stats": False}]
        imp._comparar(hero, {"health": 400, "armor": 0, "shields": 0}, antes, nuevas)
        cambios = self.env["ow.change"].search([("batch", "=", "prueba")])
        self.assertEqual(sorted((c.what, c.old_value or "", c.new_value or "") for c in cambios), [
            ("Escopeta · Recarga", "1.5 s", "2 s"), ("Nueva: nueva", "", "Otra"), ("Vida", "400", "525"),
            ("Vieja: retirada", "", "")])
        # los números que llegan por primera vez no son novedad
        imp2 = Importer(self.env, cosmetics=False, details=False, batch="prueba2")
        imp2._comparar(hero, {"health": 525, "armor": 0, "shields": 0},
                       {("ability", "Escopeta"): {"description": "Pum", "stats": False}}, nuevas[:1])
        self.assertFalse(self.env["ow.change"].search([("batch", "=", "prueba2")]))

    def test_boton_solo_administradores(self):
        from odoo.exceptions import AccessError
        user = self.env["res.users"].create({"name": "Jugador", "login": "jugador-btn",
                                             "group_ids": [(6, 0, [self.env.ref("overwatch.group_ow_user").id])]})
        with self.assertRaises(AccessError):
            self.env["ow.hero"].with_user(user).action_check_updates()


TABLA_PASE = """== Season 7 ==
===Free===
* texto que no es tabla
===Tiers===
{| class="fandom-table"
! colspan="3" | Season 7 Battle Pass
|-
! Tier
! Free
! Premium
|-
|1
|
|
Unlock [[Kiriko]]

{{rl|l|EDM|skin|D.Va}}
|-
|2
|{{rl|r|Cybermari|icon}}
|{{Credits}} 250
|-
! colspan="3" | Prestige Tiers
|-
|85
| colspan="2" | {{rl|p|Nomad|title}}
|}
== Season 8 ==
sin tabla
"""


@tagged("post_install", "-at_install")
class TestPases(TransactionCase):

    def test_tabla_de_niveles(self):
        from ..services import pases
        secs = pases.parsear_pagina(TABLA_PASE)
        self.assertEqual([(n, len(items)) for n, _nombre, items in secs], [(7, 5)], "la temporada sin tabla no cuenta")
        items = [(i["tier"], i["track"], i["kind"], i["rarity"], i["name"], i["hero"]) for i in secs[0][2]]
        self.assertEqual(items, [
            (1, "premium", "other", False, "Desbloquea a Kiriko", ""),
            (1, "premium", "skin", "legendary", "EDM", "D.Va"),
            (2, "free", "icon", "rare", "Cybermari", ""),
            (2, "premium", "other", False, "250 créditos", ""),
            (85, "prestige", "title", False, "Nomad", ""),
        ])
        self.assertEqual(pases.candidatos("icon", "Cybermari", ""), ["File:PI Cybermari.png"])
        # pase por caminos (desde la Temporada 4 de 2026): una tabla por camino
        caminos = pases.parsear_tabla("""{|
! colspan="4" |Season 5: A Grim Doctrine Battle Pass (1)
|-
|1
|
|{{rl|l|Ghostly Belle|skin|Ashe}}
|}
{|
! colspan="4" |Season 5: A Grim Doctrine Battle Pass (2)
|-
|1
|{{rl|c|Your Loyalty|voice|Doctrine}}
|
|}
{|
! colspan="4" |Season 5: A Grim Doctrine Battle Pass (Mythic)
|-
|1
|
|{{Mythic Prisms}} 10
|-
! colspan="3" | Prestige Tiers
|-
|10
| colspan="2" | {{rl|r|Bewitched|title}}
|}""")
        self.assertEqual([(i["section"], i["tier"], i["track"], i["name"]) for i in caminos], [
            ("Camino inicial", 1, "premium", "Ghostly Belle"), ("Camino 1", 1, "free", "Your Loyalty"),
            ("Camino de prismas", 1, "premium", "10 prismas míticos"), ("Prestigio", 10, "prestige", "Bewitched")])
        self.assertIn("File:S76 Weapon Skin Deliverance.png", pases.candidatos("weapon", "Deliverance", "Soldier: 76"))

    def test_guardar_recompensas_y_paginas(self):
        from ..services import seasons
        self.env["ow.season"].search([]).unlink()
        self.env["ow.season.item"].search([]).unlink()
        ts = seasons.parsear_pagina(TEMPORADAS, "Overwatch 2", None)
        ana = self.env["ow.hero"].create({
            "key": "test-ana", "name": "Ana", "wiki_name": "Test Ana", "role": "support",
            "cosmetic_ids": [(0, 0, {"name": "Sky", "type": "spray", "rarity": "common", "wiki_file": "s"})]})
        items = {"ow2-s1": [{"tier": 3, "track": "free", "rarity": "common", "kind": "spray", "name": "Sky Test Ana",
                             "hero": "Test Ana"}]}
        seasons.guardar(self.env, ts, items=items)
        t1 = self.env["ow.season"].search([("key", "=", "ow2-s1")])
        self.assertEqual(t1.item_count, 1)
        self.assertEqual(t1.item_ids.cosmetic_id, ana.cosmetic_ids, "grafiti con el nombre del héroe añadido")
        # recompensas que llegan a un pase que no las tenía: novedad (si ya había recompensas cargadas)
        items["ow2-s4"] = [{"tier": 1, "track": "premium", "rarity": "epic", "kind": "icon", "name": "X", "hero": ""}]
        r = seasons.guardar(self.env, ts, batch="pases", items=items)
        self.assertEqual(r["changes"], 1)
        self.assertIn("recompensas publicadas", self.env["ow.change"].search([("batch", "=", "pases")]).what)


@tagged("post_install", "-at_install")
class TestPasesYNovedadesWeb(HttpCase):

    def test_detalle_y_novedades(self):
        self.env["ow.season"].search([("key", "=", "t-web")]).unlink()
        t = self.env["ow.season"].create({
            "key": "t-web", "sequence": 999, "number": 9, "subtitle": "Prueba web", "arc": "Overwatch 2",
            "item_ids": [(0, 0, {"tier": 1, "track": "free", "kind": "icon", "rarity": "rare", "name": "Icono <x>",
                                 "media_url": "https://example.org/icono.png"}),
                         (0, 0, {"tier": 2, "track": "free", "kind": "skin", "rarity": "epic", "name": "Clásico",
                                 "cosmetic_id": self.env["ow.cosmetic"].create({
                                     "name": "Clásico", "type": "skin", "rarity": "epic", "wiki_file": "w",
                                     "hero_id": self.env["ow.hero"].create({"key": "test-web", "name": "Web", "role": "tank"}).id}).id}),
                         (0, 0, {"tier": 1, "track": "premium", "kind": "voice", "name": "Frase"}),
                         (0, 0, {"tier": 85, "track": "prestige", "kind": "title", "name": "Titulazo"})]})
        r = self.url_open("/overwatch/pases/t-web")  # sin sesión
        self.assertEqual(r.status_code, 200)
        self.assertIn("Icono &lt;x&gt;", r.text)
        # cada recompensa es su caja: enlace a la galería si es un cosmético, botón de vista grande si solo hay imagen
        self.assertEqual(r.text.count('class="ow-pitem"'), 4)
        c = self.env["ow.cosmetic"].search([("wiki_file", "=", "w")])
        self.assertIn(f'<a class="ow-pitem" href="/overwatch/heroe/test-web#aspectos/{c.id}"', r.text)
        self.assertRegex(r.text, r'<button type="button" class="ow-pitem"[^>]*data-big="https://example.org/icono.png"')
        self.assertIn("Titulazo", r.text.split("Niveles de prestigio", 1)[1])
        self.assertEqual(self.url_open("/overwatch/pases/no-existe").status_code, 404)
        self.env["ow.change"].create({"batch": "web", "kind": "hero", "what": "Vida <b>", "old_value": "400",
                                      "new_value": "525", "season_id": t.id})
        r = self.url_open("/overwatch/novedades")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Vida &lt;b&gt;", r.text)
        self.assertIn("/overwatch/pases/t-web", r.text)


@tagged("post_install", "-at_install")
class TestEventos(HttpCase):

    def test_fechas_enlaces_y_estado(self):
        from datetime import timedelta

        from ..services import eventos
        r = eventos.rangos("ran from February 10 to March 31, 2026. Also March 10 to 23, 2026.\n"
                           "*2025: October 14 to November 4\n*2026: October 6 to November 3\n"
                           "from October 6–November 2", 2026)
        self.assertIn((date(2026, 2, 10), date(2026, 3, 31)), r)
        self.assertIn((date(2026, 3, 10), date(2026, 3, 23)), r, "mes del final implícito")
        self.assertIn((date(2025, 10, 14), date(2025, 11, 4)), r, "año de la lista «*2025:»")
        self.assertIn((date(2026, 10, 6), date(2026, 11, 2)), r, "con raya y sin año: el de la temporada")
        self.assertEqual(eventos.elegir(r, date(2026, 10, 6), date(2026, 12, 8)), (date(2026, 10, 6), date(2026, 11, 2)))
        self.assertIsNone(eventos.elegir(r, date(2027, 6, 1), date(2027, 8, 1)))
        cuerpo = """* '''Events:'''
** [[Anima Strike]]
** [[Summer Games]] 2026
* '''New Hero:'''
** [[Shion]] (Damage)
* '''[[Mystery Madness: Graveyard Games]] Limited-Time Event'''
* '''[[Overwatch x Shadow Monarch]]'''
* '''[[Stadium]] updates'''"""
        self.assertEqual(eventos.enlaces_eventos(cuerpo),
                         ["Anima Strike", "Summer Games", "Mystery Madness: Graveyard Games", "Overwatch x Shadow Monarch"])

        hoy = date.today()
        E = self.env["ow.event"]
        E.search([]).unlink()
        mk = lambda k, a, b, approx=False: E.create({"key": k, "name": k, "date_start": a, "date_end": b, "approx": approx})  # noqa: E731
        activo = mk("Activo <x>", hoy - timedelta(3), hoy + timedelta(3))
        proximo = mk("Próximo", hoy + timedelta(5), hoy + timedelta(20))
        pasado = mk("Pasado", hoy - timedelta(30), hoy - timedelta(2))
        dudoso = mk("Sin fechas", hoy - timedelta(10), hoy + timedelta(30), approx=True)
        self.assertEqual((activo.state, proximo.state, pasado.state, dudoso.state), ("active", "upcoming", "past", "unconfirmed"))
        self.assertEqual(E.search([("state", "=", "active")]), activo, "uno con fechas supuestas no se da por activo")
        self.assertEqual(E.search([("state", "in", ["upcoming", "unconfirmed"])]), proximo | dudoso)

        r = self.url_open("/overwatch/eventos")
        self.assertEqual(r.status_code, 200)
        texto = r.text
        self.assertLess(texto.index("Activo &lt;x&gt;"), texto.index("Por empezar"))
        self.assertIn("empieza en 5 días", texto)
        self.assertIn("quedan 3 días", texto)
        self.assertIn("sin fechas confirmadas", texto.lower())
        self.assertIn('class="ow-zoom"', texto)
        pases = self.url_open("/overwatch/pases").text
        self.assertIn("Activo &lt;x&gt;", pases.split("Eventos", 1)[1])
        self.assertNotIn("Pasado", pases.split("Pase actual")[0] if "Pase actual" in pases else pases)

    def test_overwatch_countdown(self):
        """Los de ahora y los próximos, con hora, de Overwatch Countdown (la cuenta atrás de la portada de la wiki)."""
        from datetime import datetime, timedelta

        from ..services import countdown, seasons
        ahora = datetime.utcnow().replace(microsecond=0)
        iso = lambda d: d.isoformat() + "+00:00"  # noqa: E731
        datos = [
            {"id": 323, "title": "Season 9", "tags": "[\"Season\"]", "date": iso(ahora - timedelta(9)), "end_date": iso(ahora + timedelta(30))},
            {"id": 334, "title": "Junkrat’s Loot Hunt & Double XP Weekend", "tags": "[\"Limited-Time Event\"]",
             "date": iso(ahora + timedelta(days=15, hours=5, minutes=30)), "end_date": iso(ahora + timedelta(19)),
             "description": "Junkrat’s Loot Hunt returns!\n\nSource: [Patch Notes](https://example.org/notas)"},
            {"id": 335, "title": "Excavation Initiative", "tags": "[\"Limited-Time Event\"]",
             "date": iso(ahora - timedelta(1)), "end_date": iso(ahora + timedelta(34))},
        ]
        lista = countdown.convertir(datos)
        self.assertEqual([e["countdown_id"] for e in lista], [334, 335], "la temporada no es un evento")
        self.assertEqual(lista[0]["source_url"], "https://example.org/notas")
        self.assertEqual(lista[0]["description"], "Junkrat’s Loot Hunt returns!")

        E, S = self.env["ow.event"], self.env["ow.season"]
        E.search([]).unlink()
        S.search([]).unlink()
        hoy = date.today()
        temp = S.create({"key": "t-9", "arc": "Prueba", "number": 9, "date_start": hoy - timedelta(9),
                         "date_end": hoy + timedelta(30)})
        # la wiki ya tenía la Excavation Initiative de esta temporada, con fechas supuestas
        seasons.guardar_eventos(self.env, [{"key": "t-9:Excavation Initiative", "name": "Excavation Initiative",
                                            "season_key": "t-9", "kind": "event", "date_start": temp.date_start,
                                            "date_end": temp.date_end, "approx": True, "image_url": "https://example.org/e.png",
                                            "wiki_page": "Excavation Initiative"}], "b", avisar=False)
        self.assertEqual(seasons.guardar_countdown(self.env, lista, "b", avisar=True), 1, "solo el de Junkrat es nuevo")
        exc = E.search([("countdown_id", "=", 335)])
        self.assertEqual((exc.key, exc.approx, exc.state, exc.image_url), ("t-9:Excavation Initiative", False, "active",
                                                                         "https://example.org/e.png"))
        # otra pasada de la wiki no le pisa las fechas
        seasons.guardar_eventos(self.env, [{"key": "t-9:Excavation Initiative", "name": "Excavation Initiative",
                                            "season_key": "t-9", "kind": "event", "date_start": temp.date_start,
                                            "date_end": temp.date_end, "approx": True, "image_url": "",
                                            "wiki_page": "Excavation Initiative"}], "b", avisar=False)
        self.assertFalse(exc.approx)
        self.assertEqual(exc.image_url, "https://example.org/e.png")
        junk = E.search([("countdown_id", "=", 334)])
        self.assertEqual((junk.state, junk.season_id, junk.key), ("upcoming", temp, "owc:334"))
        self.assertTrue(self.env["ow.change"].search([("kind", "=", "event_new"), ("what", "=", junk.name)]))

        r = self.url_open("/overwatch/eventos").text
        self.assertIn("Junkrat’s Loot Hunt &amp; Double XP Weekend", r)
        self.assertRegex(r, r'data-countdown="[0-9T:-]+Z" data-mode="start"')
        self.assertIn("empieza en 15 d 5 h", r)
        self.assertIn('href="https://example.org/notas"', r)
        self.assertLess(r.index("Excavation Initiative"), r.index("Por empezar"))
        self.assertIn("Overwatch Countdown", r)
