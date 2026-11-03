"""Datos de la portada (website.inicio_datos(), lo llama la plantilla inicio_web.portada).

No depende de los otros módulos: cada tarjeta mira si su modelo existe y si el usuario tiene el grupo. Las consultas
van con sudo pero siempre filtradas al usuario actual (sus entrenos, sus grupos de gastos, sus favoritos) o sobre
catálogos que ya son públicos para él."""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from odoo import models

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
FRASES = [
    "Hoy es buen día para no dejar nada a medias.",
    "Primero el café, luego el mundo.",
    "Un entreno corto vale más que uno que no se hace.",
    "Las cuentas claras y el chocolate espeso.",
    "Si el aleatorio te da tanque, es el destino.",
    "Tres generadores más y nos vamos a casa.",
    "Nadie se arrepiente de haber estirado.",
    "Lo que se apunta, no se olvida.",
    "Hay días de pico y días de valle; los dos cuentan.",
    "La mejor build es la que te hace reír.",
    "Despacio, pero sin pausa.",
    "Este rincón es tuyo: ponlo a tu gusto.",
    "Hoy toca ganar, o por lo menos pasarlo bien.",
    "Pequeños pasos, grandes rachas.",
]


def saludo(hora):
    if 6 <= hora < 13:
        return "Buenos días"
    if 13 <= hora < 21:
        return "Buenas tardes"
    return "Buenas noches"


def euros(valor):
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{texto} €"


class Website(models.Model):
    _inherit = "website"

    def inicio_menu(self):
        """Entradas de primer nivel del menú del sitio que el usuario puede ver (sin la portada), con si se las ha
        ocultado. Las que no puede ver por permisos no salen (el acceso de website.menu ya filtra por grupos)."""
        user = self.env.user
        ocultos = user.ini_menu_ocultos()
        entradas = []
        for menu in self.menu_id.child_id:
            if not menu.url or menu.url == "/":
                continue
            oculto = menu.url in ocultos
            if menu.is_visible or oculto:
                entradas.append({"url": menu.url, "nombre": menu.name, "oculto": oculto})
        return entradas

    def inicio_datos(self):
        env = self.env
        user = env.user
        publico = user._is_public()
        ahora = datetime.now(ZoneInfo(user.tz or "Europe/Madrid"))
        hoy = ahora.date()
        dia = random.Random(hoy.toordinal())  # lo mismo durante todo el día
        tarjetas = []

        if "fuerta.history" in env and not publico and user.has_group("rutifuerta.group_fuerta_user"):
            lunes = hoy - timedelta(days=hoy.weekday())
            hechos = set(env["fuerta.history"].sudo().search(
                [("user_id", "=", user.id), ("done_on", ">=", lunes), ("done_on", "<=", hoy)]).mapped("done_on"))
            semana = [{"letra": "LMXJVSD"[i], "hecho": (lunes + timedelta(days=i)) in hechos,
                       "hoy": i == hoy.weekday()} for i in range(7)]
            n = len(hechos)
            tarjetas.append({
                "clave": "fuerta", "titulo": "Rutifuerta", "url": "/rutifuerta", "marca": "RF",
                "dato": "Hoy ya has entrenado" if hoy in hechos else (
                    f"{n} {'día' if n == 1 else 'días'} esta semana" if n else "La semana está por estrenar"),
                "semana": semana,
            })

        if "dbd.killer" in env:
            sup = env["dbd.survivor"].sudo().search_count([])
            ase = env["dbd.killer"].sudo().search_count([])
            perks = env["dbd.perk"].sudo().search_count([])
            tarjetas.append({
                "clave": "dbd", "titulo": "Dead by Daylight", "url": "/dbd", "marca": "DbD",
                "dato": f"{sup} supervivientes · {ase} asesinos · {perks} perks",
                "extra": "Una build aleatoria por si no sabes qué jugar", "extra_url": "/dbd/aleatoria",
            })

        if "ow.hero" in env:  # la web de Overwatch es pública; favoritos solo con su grupo
            heroes = env["ow.hero"].sudo().search([])
            favs = env["ow.hero"]
            if not publico and user.has_group("overwatch.group_ow_user"):
                favs = env["ow.pref"].sudo().search([("user_id", "=", user.id)], limit=1).favorite_ids
            bolsa = favs or heroes
            heroe = dia.choice(bolsa) if bolsa else None
            tarjetas.append({
                "clave": "ow", "titulo": "Overwatch", "url": "/overwatch", "marca": "OW",
                "dato": f"{len(heroes)} héroes" + (f" · {len(favs)} favoritos" if favs else ""),
                "fondo": heroe.background_url if heroe else "",
                "extra": f"Héroe del día: {heroe.name}" if heroe else "",
                "extra_url": f"/overwatch/heroe/{heroe.key}" if heroe else "",
            })

        if "gastos.miembro" in env and not publico and user.has_group("apachas.group_gastos_web"):
            miembros = env["gastos.miembro"].sudo().search(
                [("user_id", "=", user.id), ("grupo_id.active", "=", True)])
            saldo = round(sum(miembros.mapped("saldo")), 2)
            grupos = len(miembros.grupo_id)
            if not grupos:
                dato, tono = "Aún no estás en ningún grupo", ""
            elif saldo > 0:
                dato, tono = f"Te deben {euros(saldo)}", "verde"
            elif saldo < 0:
                dato, tono = f"Debes {euros(saldo)}", "rojo"
            else:
                dato, tono = "Todo en paz, nadie debe nada", ""
            tarjetas.append({
                "clave": "gastos", "titulo": "Apachas", "url": "/apachas", "marca": "€",
                "dato": dato, "tono": tono,
                "extra": f"{grupos} {'grupo' if grupos == 1 else 'grupos'}" if grupos else "",
            })

        if not publico and user._is_internal():
            tarjetas.append({"clave": "odoo", "titulo": "Backend", "url": "/odoo", "marca": "⌘",
                             "dato": "Ajustes, catálogos y todo lo demás"})

        # Lo que el usuario se ha ocultado del menú tampoco sale como tarjeta
        ocultos = set() if publico else user.ini_menu_ocultos()
        tarjetas = [t for t in tarjetas if t["url"] not in ocultos]

        return {
            "publico": publico,
            "nombre": "" if publico else (user.name or "").split(" ")[0],
            "saludo": saludo(ahora.hour),
            "hora": ahora.strftime("%H:%M"),
            "fecha": f"{DIAS[hoy.weekday()].capitalize()}, {hoy.day} de {MESES[hoy.month - 1]}",
            "frase": dia.choice(FRASES),
            "tarjetas": tarjetas,
            "menu": [] if publico else self.inicio_menu(),
        }
