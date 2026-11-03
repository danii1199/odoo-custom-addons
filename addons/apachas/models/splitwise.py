"""Exportar e importar un grupo en el CSV de Splitwise («Exportar como hoja de cálculo» en un grupo de Splitwise).

Formato: `Date,Description,Category,Cost,Currency` y una columna por persona con el efecto de cada movimiento en
su saldo (lo que pagó − lo que le toca; la fila suma 0). Los pagos llevan la categoría «Payment» (quien paga sale en
positivo). Al final, tras una línea vacía, una fila «Total balance» que se ignora al importar.

Al importar se reconstruye cada fila: con un solo pagador, un gasto pagado por él con importes exactos (o a partes
iguales si lo es); con varios pagadores (Splitwise lo permite, aquí no), un gasto por pagador con las partes que le
deben, de modo que los saldos quedan idénticos. Los pagos se importan tal cual aunque los hiciera otro: es historial,
la regla «nadie paga por otro» es para los pagos nuevos. Cada fila deja su huella (`splitwise_ref`) y volver a
importar el mismo archivo se salta lo ya importado. Durante la importación no se manda ningún aviso por movimiento
(contexto `gastos_importando`): solo una nota en el grupo."""
import csv
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime

from markupsafe import Markup

from odoo import fields, models
from odoo.exceptions import UserError

from .gasto import repartir
from .grupo import simplificar_deudas

MAX_CSV = 5 * 1024 * 1024
CATEGORIA_PAGO = "Payment"

# Columnas fijas (en inglés, como exporta Splitwise; también en español por si acaso)
COLUMNAS = {
    "fecha": {"date", "fecha"},
    "concepto": {"description", "descripcion", "concepto"},
    "categoria": {"category", "categoria"},
    "importe": {"cost", "coste", "costo", "importe"},
    "moneda": {"currency", "moneda", "divisa"},
}
TOTAL = {"total balance", "saldo total", "balance total", "total"}
PAGO = {"payment", "pago"}

# Nuestra categoría → la de Splitwise al exportar
A_SPLITWISE = {"comida": "Dining out", "super": "Groceries", "transporte": "Transportation", "alojamiento": "Hotel",
               "ocio": "Entertainment", "casa": "Utilities", "regalos": "Gifts", "otros": "General"}
# Palabras de las categorías de Splitwise (inglés y español) → nuestra categoría al importar
DE_SPLITWISE = [
    ("super", ("grocer", "supermerc", "compra")),
    ("comida", ("dining", "food", "drink", "liquor", "restaur", "comida", "bebida", "cena", "comer")),
    ("alojamiento", ("hotel", "lodging", "alojam", "hostal")),
    ("transporte", ("transport", "car", "gas/fuel", "fuel", "parking", "taxi", "bus", "train", "plane", "bicycle",
                    "gasolina", "coche", "aparcam", "tren", "avion", "vuelo")),
    ("ocio", ("entertain", "game", "movie", "music", "sport", "ocio", "cine", "juego", "deporte", "musica")),
    ("casa", ("rent", "mortgage", "electric", "utilit", "water", "heat", "tv/phone", "internet", "household",
              "cleaning", "furniture", "maintenance", "home", "alquiler", "luz", "agua", "casa", "hogar", "limpieza")),
    ("regalos", ("gift", "regalo")),
]


def _clave(texto):
    """Minúsculas y sin tildes, para comparar cabeceras y nombres."""
    texto = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _centimos(texto):
    """'12.50', '-6,25', '1,234.50' o '1.234,50' → céntimos (int). Vacío = 0."""
    texto = (texto or "").strip().replace(" ", "").replace("€", "")
    if not texto:
        return 0
    if "," in texto and "." in texto:  # el último separador es el decimal
        miles = "," if texto.rfind(".") > texto.rfind(",") else "."
        texto = texto.replace(miles, "")
    texto = texto.replace(",", ".")
    try:
        return round(float(texto) * 100)
    except ValueError:
        raise ValueError(f"«{texto}» no es un importe")


def _fecha(texto):
    texto = (texto or "").strip()
    for formato, largo in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10), ("%m/%d/%Y", 10)):
        try:
            return datetime.strptime(texto[:largo], formato).date()
        except ValueError:
            continue
    raise ValueError(f"«{texto}» no es una fecha")


def _categoria(texto):
    clave = _clave(texto)
    for nuestra, palabras in DE_SPLITWISE:
        if any(p in clave for p in palabras):
            return nuestra
    return "otros"


def _euros(c):
    return f"{c / 100:.2f}"


def leer_csv(texto):
    """CSV de Splitwise → {"personas": [nombres], "filas": [...], "errores": [...]}.
    Cada fila: {"num", "fecha", "concepto", "categoria", "importe" (céntimos), "pago" (bool),
    "netos" ({nombre: céntimos}), "ref"}. Lanza UserError si el archivo no tiene el formato."""
    texto = texto.lstrip("﻿")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    lector = csv.reader(io.StringIO(texto), dialecto)
    cabecera = next(lector, None) or []
    indices = {}
    for i, col in enumerate(cabecera):
        for campo, nombres in COLUMNAS.items():
            if _clave(col) in nombres and campo not in indices:
                indices[campo] = i
    if not {"fecha", "concepto", "importe"} <= set(indices):
        raise UserError("No parece un CSV de Splitwise: faltan las columnas Date, Description y Cost. "
                        "En Splitwise, entra en el grupo y usa «Exportar como hoja de cálculo».")
    fijas = set(indices.values())
    personas = [(i, col.strip()) for i, col in enumerate(cabecera) if i not in fijas and col.strip()]
    if len(personas) < 2:
        raise UserError("El CSV no trae columnas de personas (hacen falta al menos dos).")

    filas, errores = [], []
    for num, fila in enumerate(lector, start=2):
        valor = lambda campo: fila[indices[campo]].strip() if campo in indices and indices[campo] < len(fila) else ""
        if not any(c.strip() for c in fila):
            continue
        concepto = valor("concepto")
        if _clave(concepto) in TOTAL or not valor("fecha"):
            continue
        try:
            moneda = valor("moneda").upper()
            if moneda and moneda != "EUR":
                raise ValueError(f"está en {moneda} y aquí todo va en euros")
            netos = {n: _centimos(fila[i] if i < len(fila) else "") for i, n in personas}
            descuadre = sum(netos.values())
            if abs(descuadre) > len(personas):
                raise ValueError(f"los importes de las personas no cuadran ({_euros(descuadre)})")
            if descuadre:  # redondeo de Splitwise: el céntimo suelto, al de mayor saldo
                mayor = max(netos, key=lambda n: abs(netos[n]))
                netos[mayor] -= descuadre
            if not any(netos.values()):
                continue  # no cambia ningún saldo (p. ej. un gasto que solo es de quien lo pagó)
            importe = abs(_centimos(valor("importe")))
            pago = _clave(valor("categoria")) in PAGO
            filas.append({
                "num": num, "fecha": _fecha(valor("fecha")), "concepto": concepto or "Gasto",
                "categoria": _categoria(valor("categoria")), "importe": importe, "pago": pago, "netos": netos,
                "ref": hashlib.sha1("|".join([valor("fecha")[:10], concepto, str(importe)] + [
                    f"{n}:{c}" for n, c in sorted(netos.items())]).encode()).hexdigest()[:20],
            })
        except ValueError as e:
            errores.append(f"Línea {num} («{concepto}»): {e}.")
    return {"personas": [n for i, n in personas], "filas": filas, "errores": errores}


def movimientos(fila):
    """Fila leída → lista de movimientos a crear, con nombres de persona:
    ("pago", paga, recibe, céntimos) o ("gasto", pagador, importe, reparto, [(persona, céntimos)], nota)."""
    netos = fila["netos"]
    if fila["pago"]:
        # Quien paga sale en positivo y quien recibe en negativo
        return [("pago", acreedor, deudor, c) for deudor, acreedor, c in simplificar_deudas(netos)]
    pagadores = [n for n, c in netos.items() if c > 0]
    if len(pagadores) == 1:
        pagador = pagadores[0]
        partes = {n: -c for n, c in netos.items() if c < 0}
        propia = fila["importe"] - netos[pagador]
        if propia >= 0 and fila["importe"]:
            if propia:
                partes[pagador] = propia
            return [("gasto", pagador, fila["importe"], *_reparto(fila["importe"], partes), "")]
    # Varios pagadores (o un importe que no cuadra): un gasto por acreedor con lo que le deben
    por_pagador = {}
    for deudor, acreedor, c in simplificar_deudas(netos):
        por_pagador.setdefault(acreedor, {})[deudor] = c
    nota = (f"Importado de Splitwise: lo pagaron varios ({', '.join(pagadores)}); "
            "se ha repartido para que los saldos queden igual.") if len(pagadores) > 1 else ""
    return [("gasto", p, sum(partes.values()), "importes", list(partes.items()), nota)
            for p, partes in por_pagador.items()]


def _reparto(total, partes):
    """(reparto, [(persona, céntimos)]): «igual» si sale igual que repartirlo a partes iguales; si no, «importes»."""
    orden = sorted(partes.items(), key=lambda x: -x[1])
    if [c for n, c in orden] == repartir(total, "igual", [1] * len(orden)):
        return "igual", orden
    return "importes", list(partes.items())


class GastosGrupoSplitwise(models.Model):
    _inherit = "gastos.grupo"

    def exportar_splitwise(self):
        """CSV del grupo en el formato de Splitwise (texto)."""
        self.ensure_one()
        miembros = self.with_context(active_test=False).member_ids
        saldos = self.saldos_centimos()
        personas = [m for m in miembros if m.active or saldos.get(m)]
        filas = []
        for g in self.gasto_ids:
            netos = dict.fromkeys(personas, 0)
            netos[g.pagador_id] = netos.get(g.pagador_id, 0) + round(g.importe * 100)
            for linea in g.linea_ids:
                netos[linea.miembro_id] = netos.get(linea.miembro_id, 0) - round(linea.importe * 100)
            filas.append((g.fecha, g.id, g.name, A_SPLITWISE.get(g.categoria, "General"), g.importe, netos))
        for p in self.liquidacion_ids:
            c = round(p.importe * 100)
            netos = dict.fromkeys(personas, 0)
            netos[p.pagador_id] = netos.get(p.pagador_id, 0) + c
            netos[p.receptor_id] = netos.get(p.receptor_id, 0) - c
            filas.append((p.fecha, p.id, f"{p.pagador_id.name} paid {p.receptor_id.name}", CATEGORIA_PAGO,
                          p.importe, netos))
        salida = io.StringIO()
        w = csv.writer(salida, lineterminator="\n")
        w.writerow(["Date", "Description", "Category", "Cost", "Currency"] + [m.name for m in personas])
        for fecha, _id, concepto, categoria, importe, netos in sorted(filas, key=lambda f: (f[0], f[1])):
            w.writerow([fecha.isoformat(), concepto, categoria, f"{importe:.2f}", "EUR"]
                       + [_euros(netos.get(m, 0)) for m in personas])
        w.writerow([])
        w.writerow(["", "Total balance", "", "", "EUR"] + [_euros(saldos.get(m, 0)) for m in personas])
        return salida.getvalue()

    def action_exportar_splitwise(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": f"/apachas/{self.id}/exportar-splitwise", "target": "self"}

    def action_importar_splitwise(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "gastos.importar.splitwise", "view_mode": "form",
                "target": "new", "name": "Importar de Splitwise", "context": {"default_grupo_id": self.id}}

    def nombre_exportacion(self):
        self.ensure_one()
        nombre = re.sub(r"[^\w-]+", "-", _clave(self.name)).strip("-") or "grupo"
        return f"{nombre}_{date.today().isoformat()}_export.csv"

    def analizar_splitwise(self, texto):
        """Resumen antes de importar: personas del CSV con el miembro que se les propone, cuántos gastos y pagos son
        nuevos, cuántos ya estaban y los errores."""
        self.ensure_one()
        datos = leer_csv(texto)
        hechas = self._refs_splitwise()
        nuevas = [f for f in datos["filas"] if f["ref"] not in hechas]
        miembros = self.with_context(active_test=False).member_ids
        por_nombre = {_clave(m.name): m for m in miembros}
        return {
            **datos,
            "nuevas": nuevas,
            "gastos": sum(1 for f in nuevas if not f["pago"]),
            "pagos": sum(1 for f in nuevas if f["pago"]),
            "repetidas": len(datos["filas"]) - len(nuevas),
            "propuesta": {n: por_nombre.get(_clave(n), self.env["gastos.miembro"]) for n in datos["personas"]},
        }

    def _refs_splitwise(self):
        return set(self.gasto_ids.mapped("splitwise_ref")) | set(self.liquidacion_ids.mapped("splitwise_ref"))

    def importar_splitwise(self, texto, mapeo, nombres=None):
        """Importa las filas nuevas del CSV. `mapeo`: {nombre en el CSV: miembro del grupo o vacío = crear uno nuevo}.
        `nombres`: {nombre en el CSV: nombre que tendrá el miembro nuevo} (por defecto, el del CSV). Devuelve (gastos creados, pagos creados). Quien llama ya ha comprobado que puede editar el
        grupo: los miembros nuevos y los pagos se crean con sudo."""
        self.ensure_one()
        datos = self.analizar_splitwise(texto)
        if not datos["nuevas"]:
            return 0, 0
        g = self.sudo()
        Miembro = self.env["gastos.miembro"].sudo()
        quien = {}
        for nombre in datos["personas"]:
            miembro = mapeo.get(nombre)
            if miembro and miembro.grupo_id != g:
                raise UserError(f"{miembro.name} no es de este grupo.")
            if not miembro:
                nuevo = ((nombres or {}).get(nombre) or "").strip() or nombre
                usadas = g.with_context(active_test=False).member_ids
                miembro = usadas.filtered(lambda m: _clave(m.name) == _clave(nuevo))[:1] or Miembro.create({
                    "grupo_id": g.id, "partner_id": self.env["res.partner"].sudo().create({"name": nuevo}).id})
            quien[nombre] = miembro
        if len(set(quien.values())) < len(quien):
            raise UserError("Dos personas del CSV no pueden ser el mismo miembro.")

        ctx = {"gastos_importando": True}
        Gasto = self.env["gastos.gasto"].sudo().with_context(**ctx)
        Pago = self.env["gastos.liquidacion"].sudo().with_context(**ctx)
        n_gastos = n_pagos = 0
        for fila in datos["nuevas"]:
            for mov in movimientos(fila):
                if mov[0] == "pago":
                    _tipo, paga, recibe, c = mov
                    Pago.create({"grupo_id": g.id, "fecha": fila["fecha"], "pagador_id": quien[paga].id,
                                 "receptor_id": quien[recibe].id, "importe": c / 100,
                                 "nota": fila["concepto"][:200], "splitwise_ref": fila["ref"]})
                    n_pagos += 1
                else:
                    _tipo, pagador, total, reparto, partes, nota = mov
                    Gasto.create({
                        "grupo_id": g.id, "name": fila["concepto"], "fecha": fila["fecha"], "importe": total / 100,
                        "pagador_id": quien[pagador].id, "categoria": fila["categoria"], "reparto": reparto,
                        "nota": nota or False, "splitwise_ref": fila["ref"],
                        "linea_ids": [(0, 0, {"miembro_id": quien[n].id,
                                              "valor": 1 if reparto == "igual" else c / 100}) for n, c in partes]})
                    n_gastos += 1
        g.message_post(body=Markup("%s ha importado de Splitwise %s gastos y %s pagos.") % (
            self.env.user.name, n_gastos, n_pagos))
        return n_gastos, n_pagos


class GastosGastoSplitwise(models.Model):
    _inherit = "gastos.gasto"

    splitwise_ref = fields.Char("Huella de Splitwise", index=True, copy=False, readonly=True,
                                help="Fila del CSV de Splitwise de la que viene (para no importarla dos veces).")


class GastosLiquidacionSplitwise(models.Model):
    _inherit = "gastos.liquidacion"

    splitwise_ref = fields.Char("Huella de Splitwise", index=True, copy=False, readonly=True)


class GastosImportarSplitwise(models.TransientModel):
    """Asistente del backend: subir el CSV, revisar a quién corresponde cada persona e importar."""
    _name = "gastos.importar.splitwise"
    _description = "Importar de Splitwise"

    grupo_id = fields.Many2one("gastos.grupo", "Grupo", required=True, ondelete="cascade")
    archivo = fields.Binary("CSV de Splitwise", required=True)
    nombre_archivo = fields.Char()
    paso = fields.Selection([("subir", "Subir"), ("revisar", "Revisar")], default="subir")
    resumen = fields.Text(readonly=True)
    linea_ids = fields.One2many("gastos.importar.splitwise.linea", "asistente_id", "Personas")

    def _texto(self):
        if not self.archivo:
            raise UserError("Sube el CSV que exportaste de Splitwise.")
        if self.archivo.size > MAX_CSV:
            raise UserError("El archivo es demasiado grande (máximo 5 MB).")
        datos = self.archivo.content  # Odoo 20: BinaryValue (contenido ya sin base64)
        try:
            return datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            return datos.decode("latin-1")

    def _reabrir(self):
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form",
                "target": "new", "name": "Importar de Splitwise"}

    def action_analizar(self):
        self.ensure_one()
        self.grupo_id.check_access("write")
        info = self.grupo_id.analizar_splitwise(self._texto())
        partes = [f"{info['gastos']} gastos y {info['pagos']} pagos nuevos."]
        if info["repetidas"]:
            partes.append(f"{info['repetidas']} ya estaban importados y se saltan.")
        partes += info["errores"]
        self.write({"paso": "revisar", "resumen": "\n".join(partes), "linea_ids": [(5, 0, 0)] + [
            (0, 0, {"nombre": n, "nombre_nuevo": n, "miembro_id": m.id}) for n, m in info["propuesta"].items()]})
        return self._reabrir()

    def action_importar(self):
        self.ensure_one()
        self.grupo_id.check_access("write")
        mapeo = {l.nombre: l.miembro_id for l in self.linea_ids}
        nombres = {l.nombre: l.nombre_nuevo for l in self.linea_ids}
        n_gastos, n_pagos = self.grupo_id.importar_splitwise(self._texto(), mapeo, nombres)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "message": f"Importados {n_gastos} gastos y {n_pagos} pagos.",
                           "next": {"type": "ir.actions.act_window_close"}}}


class GastosImportarSplitwiseLinea(models.TransientModel):
    _name = "gastos.importar.splitwise.linea"
    _description = "Persona del CSV de Splitwise"

    asistente_id = fields.Many2one("gastos.importar.splitwise", required=True, ondelete="cascade")
    grupo_id = fields.Many2one(related="asistente_id.grupo_id")
    nombre = fields.Char("En Splitwise", readonly=True)
    nombre_nuevo = fields.Char("Nombre al crearlo", help="Nombre del miembro nuevo (solo si no eliges uno del grupo).")
    miembro_id = fields.Many2one("gastos.miembro", "Miembro del grupo", domain="[('grupo_id', '=', grupo_id)]",
                                 context={"active_test": False},
                                 help="Vacío: se crea un miembro nuevo con ese nombre.")
