import base64

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.gasto import repartir
from ..models.grupo import simplificar_deudas
from ..models.splitwise import leer_csv, movimientos


@tagged("post_install", "-at_install")
class TestGastos(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.ana, cls.bea, cls.carlos = (Partner.create({"name": n, "email": f"{n.lower()}@example.com"})
                                         for n in ("Ana", "Bea", "Carlos"))
        cls.grupo = cls.env["gastos.grupo"].create({
            "name": "Viaje", "member_ids": [(0, 0, {"partner_id": p.id}) for p in (cls.ana, cls.bea, cls.carlos)]})
        cls.m = {m.name: m for m in cls.grupo.member_ids}

    def _gasto(self, importe, pagador, reparto="igual", valores=None, **kw):
        valores = valores or {n: 1 for n in self.m}
        return self.env["gastos.gasto"].create({
            "grupo_id": self.grupo.id, "name": "x", "importe": importe, "pagador_id": self.m[pagador].id,
            "reparto": reparto,
            "linea_ids": [(0, 0, {"miembro_id": self.m[n].id, "valor": v}) for n, v in valores.items()], **kw})

    def test_euros(self):
        self.assertEqual(self.grupo.currency_id, self.env.ref("base.EUR"))
        self.assertEqual(self.grupo._fmt(1234.5), "1.234,50 €")
        self.assertEqual(self.grupo._fmt(-3), "-3,00 €")
        usd = self.env.ref("base.USD")
        self.grupo.currency_id = usd
        self.env["gastos.grupo"]._forzar_euros()
        self.assertEqual(self.grupo.currency_id, self.env.ref("base.EUR"))

    def test_repartir(self):
        self.assertEqual(repartir(1000, "igual", [1, 1, 1]), [334, 333, 333])
        self.assertEqual(repartir(900, "partes", [2, 1]), [600, 300])
        self.assertEqual(repartir(1000, "porcentaje", [50, 25, 25]), [500, 250, 250])
        self.assertEqual(sum(repartir(1001, "porcentaje", [33.33, 33.33, 33.34])), 1001)

    def test_simplificar(self):
        pagos = simplificar_deudas({"a": 3000, "b": -1000, "c": -2000})
        self.assertEqual(sorted(pagos), [("b", "a", 1000), ("c", "a", 2000)])
        self.assertEqual(simplificar_deudas({"a": 0, "b": 0}), [])

    def test_saldos_y_deudas(self):
        self._gasto(30, "Ana")                                    # cada uno 10
        self._gasto(60, "Bea", "partes", {"Bea": 1, "Carlos": 2})  # Bea 20, Carlos 40
        self.assertEqual(self.m["Ana"].saldo, 20)
        self.assertEqual(self.m["Bea"].saldo, 30)
        self.assertEqual(self.m["Carlos"].saldo, -50)
        deudas = {(d.name, a.name): i for d, a, i in self.grupo.deudas()}
        self.assertEqual(deudas, {("Carlos", "Bea"): 30, ("Carlos", "Ana"): 20})
        self.env["gastos.liquidacion"].create({"grupo_id": self.grupo.id, "pagador_id": self.m["Carlos"].id,
                                                "receptor_id": self.m["Bea"].id, "importe": 30})
        self.assertEqual(self.m["Carlos"].saldo, -20)
        self.assertEqual(self.m["Bea"].saldo, 0)

    def test_redondeo_suma_total(self):
        g = self._gasto(10, "Ana")
        self.assertAlmostEqual(sum(g.linea_ids.mapped("importe")), 10)
        self.assertEqual(sorted(g.linea_ids.mapped("importe")), [3.33, 3.33, 3.34])

    def test_validaciones(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._gasto(10, "Ana", "porcentaje", {"Ana": 50, "Bea": 40})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._gasto(10, "Ana", "importes", {"Ana": 5, "Bea": 4})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._gasto(0, "Ana")
        otro = self.env["gastos.grupo"].create({"name": "Otro", "member_ids": [(0, 0, {"partner_id": self.ana.id})]})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["gastos.liquidacion"].create({"grupo_id": self.grupo.id, "pagador_id": otro.member_ids.id,
                                                    "receptor_id": self.m["Bea"].id, "importe": 5})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["gastos.liquidacion"].create({"grupo_id": self.grupo.id, "pagador_id": self.m["Bea"].id,
                                                    "receptor_id": self.m["Bea"].id, "importe": 5})

    def test_correos(self):
        Mail = self.env["mail.mail"]
        antes = Mail.search_count([])
        self._gasto(30, "Ana")
        # El administrador no es miembro: avisa a los tres (todos tienen correo)
        self.assertEqual(Mail.search_count([]) - antes, 3)
        self.grupo.notificar_gastos = False
        antes = Mail.search_count([])
        self._gasto(30, "Ana")
        self.assertEqual(Mail.search_count([]), antes)
        self.grupo.action_recordar_pagos()
        self.assertEqual(Mail.search_count([]) - antes, 2)  # Bea y Carlos deben

    def test_portal_solo_sus_grupos(self):
        self.m["Ana"].action_invitar()
        user = self.ana.user_ids
        self.assertTrue(user and user._is_portal())
        self.assertEqual(self.m["Ana"].user_id, user)
        self.assertTrue(user.has_group("apachas.group_gastos_web"), "invitar da el permiso de la web")
        # La casilla «Web de Apachas» del formulario del usuario lo refleja, lo quita y lo devuelve
        self.assertTrue(user.apachas_web)
        self.assertFalse(user.apachas_interno)
        user.apachas_web = False
        self.assertFalse(user.has_group("apachas.group_gastos_web"))
        self.assertTrue(user._is_portal(), "quitar la web no le cambia el tipo de usuario")
        user.apachas_web = True
        self.assertTrue(user.has_group("apachas.group_gastos_web"))
        ajeno = self.env["gastos.grupo"].create({"name": "Ajeno", "member_ids": [(0, 0, {"partner_id": self.bea.id})]})
        Grupo = self.env["gastos.grupo"].with_user(user)
        self.assertEqual(Grupo.search([]), self.grupo)
        with self.assertRaises(AccessError):
            ajeno.with_user(user).check_access("read")
        # Puede apuntar un gasto en su grupo, y solo borrar lo suyo
        g = self.env["gastos.gasto"].with_user(user).create({
            "grupo_id": self.grupo.id, "name": "Pan", "importe": 3, "pagador_id": self.m["Ana"].id,
            "linea_ids": [(0, 0, {"miembro_id": self.m["Ana"].id}), (0, 0, {"miembro_id": self.m["Bea"].id})]})
        self.assertEqual(self.m["Ana"].saldo, 1.5)
        # Como en el backend: cualquier miembro edita y borra los gastos de su grupo
        otro = self._gasto(9, "Bea")
        otro.with_user(user).write({"name": "Cambiado por Ana"})
        otro.with_user(user).unlink()
        g.unlink()
        # …pero no los de un grupo ajeno, ni el grupo ajeno
        ajeno_gasto = self.env["gastos.gasto"].create({
            "grupo_id": ajeno.id, "name": "y", "importe": 2, "pagador_id": ajeno.member_ids.id,
            "linea_ids": [(0, 0, {"miembro_id": ajeno.member_ids.id})]})
        with self.assertRaises(AccessError):
            ajeno_gasto.with_user(user).unlink()
        with self.assertRaises(AccessError):
            ajeno.with_user(user).write({"name": "Mío"})
        self.grupo.with_user(user).write({"name": "Viaje (editado)"})
        with self.assertRaises(AccessError):
            self.env["gastos.gasto"].with_user(user).create({
                "grupo_id": ajeno.id, "name": "x", "importe": 1, "pagador_id": ajeno.member_ids.id,
                "linea_ids": [(0, 0, {"miembro_id": ajeno.member_ids.id})]})


@tagged("post_install", "-at_install")
class TestGastosWeb(HttpCase):

    def test_web_portal(self):
        partner = self.env["res.partner"].create({"name": "Dora", "email": "dora@example.com"})
        otro = self.env["res.partner"].create({"name": "Eva"})
        dora = self.env["res.users"].create({"name": "Dora", "login": "dora", "password": "dora-dora-1",
                                             "partner_id": partner.id, "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])]})
        # Sin permiso «Apachas: web» no hay nada que ver
        self.authenticate("dora", "dora-dora-1")
        self.assertEqual(self.url_open("/apachas").status_code, 404)
        # Al añadirla como miembro se le da el permiso
        grupo = self.env["gastos.grupo"].create({"name": "Piso", "member_ids": [
            (0, 0, {"partner_id": partner.id}), (0, 0, {"partner_id": otro.id})]})
        self.assertTrue(dora.has_group("apachas.group_gastos_web"))
        ajeno = self.env["gastos.grupo"].create({"name": "Ajeno", "member_ids": [(0, 0, {"partner_id": otro.id})]})
        r = self.url_open("/apachas")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Piso", r.text)
        self.assertNotIn("Ajeno", r.text)
        self.assertEqual(self.url_open(f"/apachas/{grupo.id}").status_code, 200)
        self.assertEqual(self.url_open(f"/apachas/{ajeno.id}").status_code, 404)
        yo, eva = grupo.member_ids.sorted(lambda m: m.name != "Dora")
        r = self.url_open(f"/apachas/{grupo.id}/nuevo", data={
            "csrf_token": self.csrf_token(), "name": "Luz", "importe": "50,40", "pagador_id": yo.id,
            "reparto": "igual", f"m_{yo.id}": "1", f"m_{eva.id}": "1", "categoria": "casa"})
        self.assertEqual(r.status_code, 200)
        gasto = grupo.gasto_ids
        self.assertEqual((gasto.name, gasto.importe, gasto.create_uid.login), ("Luz", 50.4, "dora"))
        self.assertEqual(eva.saldo, -25.2)


@tagged("post_install", "-at_install")
class TestGastosWebGestion(HttpCase):
    """Desde la web, un miembro de portal gestiona su grupo como desde el backend."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Fran", "email": "fran@example.com"})
        self.env["res.users"].create({"name": "Fran", "login": "fran", "password": "fran-fran-1",
                                      "partner_id": self.partner.id,
                                      "group_ids": [(6, 0, [self.env.ref("base.group_portal").id,
                                                            self.env.ref("apachas.group_gastos_web").id])]})
        self.authenticate("fran", "fran-fran-1")

    def _post(self, url, **data):
        return self.url_open(url, data={"csrf_token": self.csrf_token(), **data})

    def test_gestion_completa(self):
        # Crear grupo: entra como primer miembro
        r = self._post("/apachas/nuevo-grupo", name="Cumple de Gael", description="Regalo")
        self.assertEqual(r.status_code, 200)
        grupo = self.env["gastos.grupo"].search([("name", "=", "Cumple de Gael")])
        self.assertEqual(grupo.member_ids.partner_id, self.partner)
        self.assertEqual(grupo.currency_id, self.env.ref("base.EUR"))
        # Ajustes
        self._post(f"/apachas/{grupo.id}/ajustes", name="Cumple de Gael 🎂", description="", notificar_gastos="1")
        self.assertEqual(grupo.name, "Cumple de Gael 🎂")
        self.assertTrue(grupo.notificar_gastos)
        self.assertFalse(grupo.resumen_semanal)
        # Añadir miembros (uno sin correo, otro con correo e invitación)
        self._post(f"/apachas/{grupo.id}/miembros/nuevo", name="Gael")
        self._post(f"/apachas/{grupo.id}/miembros/nuevo", name="Iris", email="iris@example.com", invitar="1")
        miembros = {m.name: m for m in grupo.member_ids}
        self.assertEqual(set(miembros), {"Fran", "Gael", "Iris"})
        self.assertTrue(miembros["Iris"].user_id, "Iris debería tener cuenta de portal tras la invitación")
        # Gasto y edición
        fran, gael, iris = miembros["Fran"], miembros["Gael"], miembros["Iris"]
        self._post(f"/apachas/{grupo.id}/nuevo", name="Regalo", importe="30", pagador_id=fran.id, reparto="igual",
                   **{f"m_{m.id}": "1" for m in (fran, gael, iris)})
        gasto = grupo.gasto_ids
        self.assertEqual(gasto.importe, 30)
        r = self.url_open(f"/apachas/{grupo.id}/gasto/{gasto.id}")
        self.assertIn("Editar gasto", r.text)
        self._post(f"/apachas/{grupo.id}/gasto/{gasto.id}", name="Regalo y tarta", importe="45", pagador_id=fran.id,
                   reparto="partes", **{f"v_{fran.id}": "1", f"v_{gael.id}": "2"})
        self.assertEqual((gasto.name, gasto.importe, gasto.reparto), ("Regalo y tarta", 45, "partes"))
        self.assertEqual(sorted(gasto.linea_ids.mapped("importe")), [15, 30])
        self.assertEqual(gael.saldo, -30)
        # Quitar: Iris no tiene movimientos; Gael sí (solo se puede archivar)
        self._post(f"/apachas/{grupo.id}/miembros/{iris.id}/quitar")
        self.assertFalse(iris.exists())
        r = self._post(f"/apachas/{grupo.id}/miembros/{gael.id}/quitar")
        self.assertTrue(gael.exists())
        self.assertIn("archívalo", r.text)
        self._post(f"/apachas/{grupo.id}/miembros/{gael.id}/archivar")
        self.assertFalse(gael.active)
        self.assertEqual(gael.saldo, -30, "archivar conserva el saldo")
        # No puede sacarse a sí mismo
        self._post(f"/apachas/{grupo.id}/miembros/{fran.id}/archivar")
        self.assertTrue(fran.active)
        # Archivar el grupo
        self._post(f"/apachas/{grupo.id}/archivar")
        self.assertFalse(grupo.active)
        self.assertIn("Grupos archivados", self.url_open("/apachas").text)

    def test_mensajes_no_vienen_de_la_url(self):
        """Un enlace con ?error=… no puede meter texto en la página (phishing); los avisos reales van por la sesión."""
        grupo = self.env["gastos.grupo"].create({"name": "Casa", "member_ids": [(0, 0, {"partner_id": self.partner.id})]})
        r = self.url_open(f"/apachas/{grupo.id}?error=Haz+un+Bizum+a+este+numero&aviso=Cuenta+bloqueada")
        self.assertNotIn("Bizum a este", r.text)
        self.assertNotIn("Cuenta bloqueada", r.text)
        r = self._post(f"/apachas/{grupo.id}/ajustes", name="Casa nueva")
        self.assertIn("Cambios guardados", r.text)
        self.assertNotIn("Cambios guardados", self.url_open(f"/apachas/{grupo.id}/ajustes").text)  # solo una vez

    def test_pago_rellena_lo_que_debo(self):
        hugo = self.env["res.partner"].create({"name": "Hugo"})
        grupo = self.env["gastos.grupo"].create({"name": "Cena", "member_ids": [
            (0, 0, {"partner_id": self.partner.id}), (0, 0, {"partner_id": hugo.id})]})
        m = {x.name: x for x in grupo.member_ids}
        self.env["gastos.gasto"].create({"grupo_id": grupo.id, "name": "Pizza", "importe": 30,
                                         "pagador_id": m["Hugo"].id,
                                         "linea_ids": [(0, 0, {"miembro_id": x.id}) for x in m.values()]})
        r = self.url_open(f"/apachas/{grupo.id}")
        self.assertIn('data-debo="15,00"', r.text)
        self.assertIn("le debes 15,00 €", r.text)

    def test_splitwise_web(self):
        grupo = self.env["gastos.grupo"].create({"name": "Casa", "member_ids": [(0, 0, {"partner_id": self.partner.id})]})
        r = self.url_open(f"/apachas/{grupo.id}/exportar-splitwise")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertTrue(r.text.startswith("Date,Description,Category,Cost,Currency,Fran"))
        csv_texto = "Date,Description,Category,Cost,Currency,Fran,Gil\n2026-10-01,Pizza,Dining out,20.00,EUR,10.00,-10.00\n"
        r = self.url_open(f"/apachas/{grupo.id}/importar-splitwise", data={"csrf_token": self.csrf_token()},
                          files={"archivo": ("export.csv", csv_texto.encode(), "text/csv")})
        self.assertEqual(r.status_code, 200)
        self.assertIn("¿Quién es quién?", r.text)
        fran = grupo.member_ids
        r = self._post(f"/apachas/{grupo.id}/importar-splitwise/confirmar",
                       csv=base64.b64encode(csv_texto.encode()).decode(), p_0=str(fran.id), n_0="No se usa",
                       p_1="", n_1="Gil Pérez")
        self.assertIn("Importados", r.text)
        self.assertEqual(sorted(grupo.member_ids.mapped("name")), ["Fran", "Gil Pérez"])
        self.assertEqual(fran.saldo, 10)

    def test_grupo_ajeno(self):
        otro = self.env["res.partner"].create({"name": "Hugo"})
        ajeno = self.env["gastos.grupo"].create({"name": "Ajeno", "member_ids": [(0, 0, {"partner_id": otro.id})]})
        self.assertEqual(self.url_open(f"/apachas/{ajeno.id}/ajustes").status_code, 404)
        self.assertEqual(self._post(f"/apachas/{ajeno.id}/miembros/nuevo", name="Intruso").status_code, 404)
        self.assertEqual(self._post(f"/apachas/{ajeno.id}/archivar").status_code, 404)
        self.assertTrue(ajeno.active)
        self.assertEqual(ajeno.member_ids.partner_id, otro)


@tagged("post_install", "-at_install")
class TestPagosEditables(TransactionCase):
    """Solo quien apuntó un pago lo edita, y cada edición queda en el historial."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal = cls.env.ref("base.group_portal")
        cls.users = {}
        miembros = []
        for nombre in ("Olga", "Pau"):
            p = cls.env["res.partner"].create({"name": nombre, "email": f"{nombre.lower()}@example.com"})
            cls.users[nombre] = cls.env["res.users"].create({
                "name": nombre, "login": nombre.lower(), "partner_id": p.id, "group_ids": [(6, 0, [portal.id])]})
            miembros.append((0, 0, {"partner_id": p.id}))
        cls.grupo = cls.env["gastos.grupo"].create({"name": "Piso", "member_ids": miembros})
        cls.m = {m.name: m for m in cls.grupo.member_ids}
        cls.pago = cls.env["gastos.liquidacion"].with_user(cls.users["Olga"]).create({
            "grupo_id": cls.grupo.id, "pagador_id": cls.m["Olga"].id, "receptor_id": cls.m["Pau"].id, "importe": 50})

    def test_autor_edita_y_queda_historial(self):
        pago = self.pago.with_user(self.users["Olga"])
        self.assertTrue(pago.puedo_editar)
        pago.write({"importe": 60, "nota": "Bizum"})
        self.assertEqual(len(pago.historial_ids), 1)
        h = pago.historial_ids
        self.assertEqual(h.user_name, "Olga")
        self.assertIn("Importe: 50,00 € → 60,00 €", h.cambios)
        self.assertIn("Nota: — → Bizum", h.cambios)
        self.assertEqual(self.m["Pau"].saldo, -60)
        # Guardar sin cambios no ensucia el historial
        pago.write({"importe": 60})
        self.assertEqual(len(pago.historial_ids), 1)
        # El otro miembro ve el historial
        self.assertEqual(self.pago.with_user(self.users["Pau"]).historial_ids.cambios, h.cambios)

    def test_solo_el_autor(self):
        with self.assertRaises(AccessError):
            self.pago.with_user(self.users["Pau"]).write({"importe": 1})
        self.assertFalse(self.pago.with_user(self.users["Pau"]).puedo_editar)
        # Tampoco el administrador del módulo (Dani); solo el superusuario técnico (sudo) se lo salta
        admin = self.env.ref("base.user_admin")
        self.assertTrue(admin.has_group("apachas.group_gastos_manager"))
        with self.assertRaises(AccessError):
            self.pago.with_user(admin).write({"importe": 1})
        self.assertEqual(self.pago.importe, 50)
        self.assertFalse(self.pago.historial_ids)
        # Borrar sí puede cualquier miembro
        self.pago.with_user(self.users["Pau"]).unlink()

    def test_nadie_paga_por_otro(self):
        Pago = self.env["gastos.liquidacion"]
        # Pau no puede apuntar que Olga le ha pagado
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            Pago.with_user(self.users["Pau"]).create({
                "grupo_id": self.grupo.id, "pagador_id": self.m["Olga"].id, "receptor_id": self.m["Pau"].id,
                "importe": 5})
        # Ni el administrador del módulo apunta pagos de otros
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            Pago.with_user(self.env.ref("base.user_admin")).create({
                "grupo_id": self.grupo.id, "pagador_id": self.m["Olga"].id, "receptor_id": self.m["Pau"].id,
                "importe": 5})
        # Olga no puede cambiar su pago para que pague Pau
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.pago.with_user(self.users["Olga"]).write({"pagador_id": self.m["Pau"].id,
                                                           "receptor_id": self.m["Olga"].id})
        self.assertEqual(self.pago.pagador_id, self.m["Olga"])
        # Lo suyo sí
        Pago.with_user(self.users["Pau"]).create({
            "grupo_id": self.grupo.id, "pagador_id": self.m["Pau"].id, "receptor_id": self.m["Olga"].id, "importe": 5})


# CSV como lo exporta Splitwise: una cena que paga Ana, un hotel que pagan Ana y Bea a medias pero solo es de Ana,
# Bea y Carlos, un pago de Carlos a Ana, una línea en dólares (error) y la fila final de saldos
CSV_SPLITWISE = """Date,Description,Category,Cost,Currency,Ana,Bea,Carlos
2026-10-01,Cena,Dining out,30.00,EUR,20.00,-10.00,-10.00
2026-10-02,Hotel,Hotel,90.00,EUR,15.00,15.00,-30.00
2026-10-03,Carlos paid Ana,Payment,25.00,EUR,-25.00,0.00,25.00
2026-10-04,Souvenir,General,10.00,USD,5.00,-5.00,0.00

,Total balance,,,EUR,10.00,5.00,-15.00
"""


@tagged("post_install", "-at_install")
class TestSplitwise(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Grupo = cls.env["gastos.grupo"]

    def _grupo(self, *nombres):
        return self.Grupo.create({"name": "Splitwise", "member_ids": [
            (0, 0, {"partner_id": self.env["res.partner"].create({"name": n}).id}) for n in nombres]})

    @staticmethod
    def _saldos(grupo):
        return {m.name: c for m, c in grupo.saldos_centimos().items() if c}

    def test_leer_csv(self):
        datos = leer_csv(CSV_SPLITWISE)
        self.assertEqual(datos["personas"], ["Ana", "Bea", "Carlos"])
        self.assertEqual([f["concepto"] for f in datos["filas"]], ["Cena", "Hotel", "Carlos paid Ana"])
        self.assertEqual(len(datos["errores"]), 1)
        self.assertIn("USD", datos["errores"][0])
        cena, hotel, pago = datos["filas"]
        self.assertEqual((cena["categoria"], cena["importe"], cena["pago"]), ("comida", 3000, False))
        self.assertTrue(pago["pago"])
        [(tipo, pagador, total, reparto, partes, nota)] = movimientos(cena)
        self.assertEqual((tipo, pagador, total, reparto), ("gasto", "Ana", 3000, "igual"))
        self.assertEqual(sorted(partes), [("Ana", 1000), ("Bea", 1000), ("Carlos", 1000)])
        self.assertEqual(movimientos(pago), [("pago", "Carlos", "Ana", 2500)])
        # Dos pagadores: un gasto por cada uno, con lo que le deben
        partes = movimientos(hotel)
        self.assertEqual(sorted((m[1], m[2]) for m in partes), [("Ana", 1500), ("Bea", 1500)])
        with self.assertRaises(UserError):
            leer_csv("Nombre,Apellidos\nAna,López\n")

    def test_importar(self):
        grupo = self._grupo("ana")  # se empareja sin mirar mayúsculas; Bea y Carlos se crean
        info = grupo.analizar_splitwise(CSV_SPLITWISE)
        self.assertEqual((info["gastos"], info["pagos"], info["repetidas"]), (2, 1, 0))
        self.assertEqual(info["propuesta"]["Ana"], grupo.member_ids)
        mensajes = len(grupo.message_ids)
        correos = self.env["mail.mail"].search_count([])
        # Carlos se crea con otro nombre; Bea, con el del CSV
        self.assertEqual(grupo.importar_splitwise(CSV_SPLITWISE, {}, {"Carlos": "Carlos M."}), (3, 1))  # hotel: 2
        self.assertEqual(self._saldos(grupo), {"ana": 1000, "Bea": 500, "Carlos M.": -1500})  # = Total balance
        self.assertEqual(len(grupo.member_ids), 3)
        self.assertEqual(len(grupo.message_ids), mensajes + 1)  # una sola nota
        self.assertEqual(self.env["mail.mail"].search_count([]), correos)  # ningún correo
        pago = grupo.liquidacion_ids
        self.assertEqual((pago.pagador_id.name, pago.receptor_id.name, pago.importe), ("Carlos M.", "ana", 25))
        # Volver a importar el mismo archivo no repite nada
        self.assertEqual(grupo.analizar_splitwise(CSV_SPLITWISE)["repetidas"], 3)
        self.assertEqual(grupo.importar_splitwise(CSV_SPLITWISE, {}), (0, 0))

    def test_ida_y_vuelta(self):
        """Exportar un grupo e importarlo en otro deja los mismos saldos."""
        origen = self._grupo("Ana", "Bea", "Carlos")
        m = {x.name: x for x in origen.member_ids}
        Gasto = self.env["gastos.gasto"]
        Gasto.create({"grupo_id": origen.id, "name": "Luz, agua", "importe": 100, "pagador_id": m["Ana"].id,
                      "categoria": "casa", "linea_ids": [(0, 0, {"miembro_id": x.id}) for x in m.values()]})
        Gasto.create({"grupo_id": origen.id, "name": "Taxi", "importe": 12.5, "pagador_id": m["Bea"].id,
                      "categoria": "transporte", "reparto": "importes", "linea_ids": [
                          (0, 0, {"miembro_id": m["Bea"].id, "valor": 2.5}),
                          (0, 0, {"miembro_id": m["Carlos"].id, "valor": 10})]})
        self.env["gastos.liquidacion"].sudo().create({"grupo_id": origen.id, "pagador_id": m["Carlos"].id,
                                                      "receptor_id": m["Ana"].id, "importe": 20})
        csv_texto = origen.exportar_splitwise()
        self.assertTrue(csv_texto.startswith("Date,Description,Category,Cost,Currency,Ana,Bea,Carlos\n"))
        self.assertIn('"Luz, agua",Utilities,100.00,EUR', csv_texto)
        self.assertIn("Carlos paid Ana,Payment,20.00", csv_texto)
        destino = self._grupo("Ana", "Bea", "Carlos")
        destino.importar_splitwise(csv_texto, {})
        self.assertEqual(self._saldos(destino), self._saldos(origen))
        luz = destino.gasto_ids.filtered(lambda g: g.name == "Luz, agua")
        self.assertEqual((luz.reparto, luz.categoria), ("igual", "casa"))
        self.assertEqual(destino.gasto_ids.filtered(lambda g: g.name == "Taxi").categoria, "transporte")
