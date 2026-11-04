"""Números de las habilidades y ventajas desde la página de cada héroe en la wiki (solo su API).

Cada habilidad es una plantilla {{Ability_details | ability_name = … | cooldown = … | damage = … }}. Se guardan solo
los campos de CAMPOS, con la etiqueta en español y el valor limpio de marcado ({{tt|8 s|…}} → «8 s», enlaces, <br>,
referencias). Los textos de la wiki están en inglés: se traducen las unidades y expresiones más comunes; el resto queda
tal cual. Las habilidades marcadas como retiradas («removed» o «(old)» en el nombre) se saltan."""
import re

from . import wiki

# campo de la wiki → etiqueta (en este orden se enseñan)
CAMPOS = [
    ("cooldown", "Enfriamiento"), ("charges", "Cargas"), ("ult_req", "Carga de la definitiva"),
    ("damage", "Daño"), ("heal", "Curación"), ("overhealth", "Vida extra"), ("barrier_health", "Vida de la barrera"),
    ("duration", "Duración"), ("cast_time", "Tiempo de lanzamiento"), ("range", "Alcance"), ("radius", "Radio"),
    ("ammo", "Munición"), ("reload_time", "Recarga"), ("fire_rate", "Cadencia"), ("pellets", "Perdigones"),
    ("spread", "Dispersión"), ("damage_falloff_range", "Caída del daño"), ("pspeed", "Velocidad del proyectil"),
    ("mspeed", "Velocidad de movimiento"), ("mspeed_buff", "Aumento de velocidad"), ("mspeed_pen", "Ralentización"),
    ("damage_amp", "Aumento de daño"), ("damage_red", "Reducción de daño"), ("healing_mod", "Modificador de curación"),
    ("headshot", "Críticos"),
]
TRADUCCIONES = [
    (r"\bper second\b", "por segundo"), (r"\bper shot\b", "por disparo"), (r"\bper volley\b", "por ráfaga"),
    (r"\bper projectile\b", "por proyectil"), (r"\bper pellet\b", "por perdigón"), (r"\bper hit\b", "por golpe"),
    (r"\bper tick\b", "por tic"), (r"\bper bullet\b", "por bala"), (r"\bper enemy hit\b", "por enemigo alcanzado"),
    (r"\bshots/s\b", "disparos/s"), (r"\bvolleys/s\b", "ráfagas/s"), (r"\bpoints\b", "puntos"),
    (r"\brecovery\b", "de recuperación"), (r"\bself\b", "uno mismo"), (r"\ballies\b", "aliados"),
    (r"\benemies\b", "enemigos"), (r"\breceived\b", "recibida"), (r"\btaken\b", "recibido"), (r"\bdealt\b", "infligido"),
    (r"\bimpact\b", "impacto"), (r"\beffect\b", "efecto"), (r"\bexplosion\b", "explosión"), (r"\bover\b", "en"), (r"\bseconds?\b", "s"), (r"\bmeters?\b", "m"),
    (r"\bdegrees?\b", "°"), (r"\bhealth\b", "de vida"), (r"\bdamage\b", "de daño"), (r"\bhealing\b", "de curación"),
    (r"\bdirect hit\b", "impacto directo"), (r"\bsplash\b", "área"), (r"\bmax(imum)?\b", "máx."),
    (r"\bmin(imum)?\b", "mín."), (r"\bcharges?\b", "cargas"), (r"\band\b", "y"),
    (r"\bto\b", "a"), (r"\binstantly\b", "al instante"), (r"\bwhile\b", "mientras"),
]


def _tt(m):
    partes = [p.strip() for p in wiki._partir(m.group(1))]
    nombre, args = partes[0].lower(), [p for p in partes[1:] if "=" not in p]
    if nombre.startswith("#vardefineecho:") or nombre.startswith("#vardefine:"):
        return args[-1] if args else ""
    if nombre.startswith("#"):
        return ""
    return args[0] if args else ""


def limpiar(valor):
    """Valor legible de un campo de la wiki."""
    t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", valor or "", flags=re.S)
    for _ in range(4):  # plantillas anidadas, de dentro afuera
        nuevo = re.sub(r"\{\{((?:[^{}]|\{(?!\{)|\}(?!\}))*)\}\}", _tt, t)
        if nuevo == t:
            break
        t = nuevo
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"<br\s*/?>", " · ", t)
    t = re.sub(r"<[^>]+>|'{2,}", "", t)
    for patron, es in TRADUCCIONES:
        t = re.sub(patron, es, t, flags=re.I)
    t = re.sub(r"(\d)\s+(s|m|°)\b", r"\1 \2", t)
    t = t.replace("::", " ").replace(";;", " ")
    t = re.sub(r"[✓✔]", "Sí", t)
    t = re.sub(r"[✗✕✘]", "No", t)
    t = re.sub(r"\s+", " ", t).strip(" ·")
    return "" if t.lower() in ("none", "n/a", "-", "?") else t


def parsear(wikitext):
    """{nombre en inglés: [[etiqueta, valor], …]} de las habilidades y ventajas de la página."""
    res = {}
    for m in re.finditer(r"\{\{\s*Ability[_ ]details", wikitext):
        # el cuerpo de la plantilla, contando llaves (dentro hay otras plantillas)
        nivel, i = 0, m.start()
        while i < len(wikitext) - 1:
            par = wikitext[i:i + 2]
            if par == "{{":
                nivel += 1
                i += 2
                continue
            if par == "}}":
                nivel -= 1
                i += 2
                if nivel == 0:
                    break
                continue
            i += 1
        cuerpo = wikitext[m.end():i - 2]
        params = {}
        for p in wiki._partir(cuerpo):
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip().lower()] = v.strip()
        nombre = params.get("ability_name", "").strip()
        if not nombre or "removed" in params or re.search(r"\(old\)", nombre, re.I):
            continue
        datos = [[etiqueta, limpiar(params[campo])] for campo, etiqueta in CAMPOS if params.get(campo)]
        datos = [d for d in datos if d[1]]
        if nombre not in res or len(datos) > len(res[nombre]):
            res[nombre] = datos
    return res


def de_heroe(session, nombre_wiki):
    """Los números de las habilidades de un héroe ({} si la página no existe)."""
    data = wiki._api(session, action="parse", page=nombre_wiki, prop="wikitext", redirects=1)
    if "error" in data:
        return {}
    return parsear(data["parse"]["wikitext"])
