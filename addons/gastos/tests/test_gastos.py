from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.gasto import repartir
from ..models.grupo import simplificar_deudas


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
        self.assertTrue(user.has_group("gastos.group_gastos_web"), "invitar da el permiso de la web")
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
        # Sin permiso «Gastos compartidos: web» no hay nada que ver
        self.authenticate("dora", "dora-dora-1")
        self.assertEqual(self.url_open("/gastos").status_code, 404)
        # Al añadirla como miembro se le da el permiso
        grupo = self.env["gastos.grupo"].create({"name": "Piso", "member_ids": [
            (0, 0, {"partner_id": partner.id}), (0, 0, {"partner_id": otro.id})]})
        self.assertTrue(dora.has_group("gastos.group_gastos_web"))
        ajeno = self.env["gastos.grupo"].create({"name": "Ajeno", "member_ids": [(0, 0, {"partner_id": otro.id})]})
        r = self.url_open("/gastos")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Piso", r.text)
        self.assertNotIn("Ajeno", r.text)
        self.assertEqual(self.url_open(f"/gastos/{grupo.id}").status_code, 200)
        self.assertEqual(self.url_open(f"/gastos/{ajeno.id}").status_code, 404)
        yo, eva = grupo.member_ids.sorted(lambda m: m.name != "Dora")
        r = self.url_open(f"/gastos/{grupo.id}/nuevo", data={
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
                                                            self.env.ref("gastos.group_gastos_web").id])]})
        self.authenticate("fran", "fran-fran-1")

    def _post(self, url, **data):
        return self.url_open(url, data={"csrf_token": self.csrf_token(), **data})

    def test_gestion_completa(self):
        # Crear grupo: entra como primer miembro
        r = self._post("/gastos/nuevo-grupo", name="Cumple de Gael", description="Regalo")
        self.assertEqual(r.status_code, 200)
        grupo = self.env["gastos.grupo"].search([("name", "=", "Cumple de Gael")])
        self.assertEqual(grupo.member_ids.partner_id, self.partner)
        self.assertEqual(grupo.currency_id, self.env.ref("base.EUR"))
        # Ajustes
        self._post(f"/gastos/{grupo.id}/ajustes", name="Cumple de Gael 🎂", description="", notificar_gastos="1")
        self.assertEqual(grupo.name, "Cumple de Gael 🎂")
        self.assertTrue(grupo.notificar_gastos)
        self.assertFalse(grupo.resumen_semanal)
        # Añadir miembros (uno sin correo, otro con correo e invitación)
        self._post(f"/gastos/{grupo.id}/miembros/nuevo", name="Gael")
        self._post(f"/gastos/{grupo.id}/miembros/nuevo", name="Iris", email="iris@example.com", invitar="1")
        miembros = {m.name: m for m in grupo.member_ids}
        self.assertEqual(set(miembros), {"Fran", "Gael", "Iris"})
        self.assertTrue(miembros["Iris"].user_id, "Iris debería tener cuenta de portal tras la invitación")
        # Gasto y edición
        fran, gael, iris = miembros["Fran"], miembros["Gael"], miembros["Iris"]
        self._post(f"/gastos/{grupo.id}/nuevo", name="Regalo", importe="30", pagador_id=fran.id, reparto="igual",
                   **{f"m_{m.id}": "1" for m in (fran, gael, iris)})
        gasto = grupo.gasto_ids
        self.assertEqual(gasto.importe, 30)
        r = self.url_open(f"/gastos/{grupo.id}/gasto/{gasto.id}")
        self.assertIn("Editar gasto", r.text)
        self._post(f"/gastos/{grupo.id}/gasto/{gasto.id}", name="Regalo y tarta", importe="45", pagador_id=fran.id,
                   reparto="partes", **{f"v_{fran.id}": "1", f"v_{gael.id}": "2"})
        self.assertEqual((gasto.name, gasto.importe, gasto.reparto), ("Regalo y tarta", 45, "partes"))
        self.assertEqual(sorted(gasto.linea_ids.mapped("importe")), [15, 30])
        self.assertEqual(gael.saldo, -30)
        # Quitar: Iris no tiene movimientos; Gael sí (solo se puede archivar)
        self._post(f"/gastos/{grupo.id}/miembros/{iris.id}/quitar")
        self.assertFalse(iris.exists())
        r = self._post(f"/gastos/{grupo.id}/miembros/{gael.id}/quitar")
        self.assertTrue(gael.exists())
        self.assertIn("archívalo", r.text)
        self._post(f"/gastos/{grupo.id}/miembros/{gael.id}/archivar")
        self.assertFalse(gael.active)
        self.assertEqual(gael.saldo, -30, "archivar conserva el saldo")
        # No puede sacarse a sí mismo
        self._post(f"/gastos/{grupo.id}/miembros/{fran.id}/archivar")
        self.assertTrue(fran.active)
        # Archivar el grupo
        self._post(f"/gastos/{grupo.id}/archivar")
        self.assertFalse(grupo.active)
        self.assertIn("Grupos archivados", self.url_open("/gastos").text)

    def test_grupo_ajeno(self):
        otro = self.env["res.partner"].create({"name": "Hugo"})
        ajeno = self.env["gastos.grupo"].create({"name": "Ajeno", "member_ids": [(0, 0, {"partner_id": otro.id})]})
        self.assertEqual(self.url_open(f"/gastos/{ajeno.id}/ajustes").status_code, 404)
        self.assertEqual(self._post(f"/gastos/{ajeno.id}/miembros/nuevo", name="Intruso").status_code, 404)
        self.assertEqual(self._post(f"/gastos/{ajeno.id}/archivar").status_code, 404)
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
        self.assertTrue(admin.has_group("gastos.group_gastos_manager"))
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
