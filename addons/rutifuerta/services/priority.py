"""Prioridad de las rutinas de un día: qué hacer primero si no da tiempo a todo.

Las duraciones son las nominales de FuertaFit y a veces el vídeo dura más, así que cada bloque lleva un número:
se hacen todas en el orden del plan, pero si vas justo se recorta empezando por la de número más alto.

Reglas (objetivo: perder grasa sin perder músculo):
- El calentamiento no se recorta nunca (prioridad 0, «siempre»).
- 1: la rutina fuerte del grupo principal del día (el que más minutos tiene).
- Luego una de cada grupo secundario, para que el día no pierda su segunda parte (Core, Cardio…).
- Después lo que sobre del grupo principal y del resto.
- La vuelta a la calma, al final.
Dentro de cada escalón manda la intensidad y, a igualdad, la duración.
"""
from .catalog import COOLDOWN_TYPE, WARMUP_TYPE

INTENSITY = {"high": 3, "medium": 2, "low": 1}


def rank(blocks):
    """Lista con la prioridad de cada bloque, en el mismo orden: 0 = siempre, 1 = la más importante…"""
    main = [i for i, b in enumerate(blocks) if b.get("trainingType") not in (WARMUP_TYPE, COOLDOWN_TYPE)]
    minutes = {}
    for i in main:
        minutes[blocks[i].get("group")] = minutes.get(blocks[i].get("group"), 0) + blocks[i]["durationMinutes"]
    # Grupos por minutos (a igualdad, el que aparece antes en el plan).
    groups = sorted(minutes, key=lambda g: -minutes[g])

    def strength(i):
        b = blocks[i]
        return (-INTENSITY.get(b.get("intensity"), 0), -b["durationMinutes"], i)

    order = []
    for g in groups:  # la mejor de cada grupo, empezando por el principal
        order.append(min((i for i in main if blocks[i].get("group") == g), key=strength))
    rest = [i for i in main if i not in order]
    order += sorted(rest, key=lambda i: (blocks[i].get("group") != (groups[0] if groups else None), strength(i)))
    order += [i for i, b in enumerate(blocks) if b.get("trainingType") == COOLDOWN_TYPE]

    out = [0] * len(blocks)
    for n, i in enumerate(order, 1):
        out[i] = n
    return out
