"""Entrenador con Claude (latente: solo se activa con ANTHROPIC_API_KEY).

Conversa, consulta el catálogo/historial y planifica días en el calendario con herramientas."""
import os
import re
from datetime import date, timedelta

from . import catalog
from .dates import WEEKDAYS, today as user_today
from .generator import generate

try:
    import anthropic
except ImportError:  # sin el SDK (p. ej. fuera de Docker) el bot queda desactivado
    anthropic = None

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
MAX_STEPS = 12

SYSTEM = """Eres el entrenador personal de la persona que usa esta web. Trabajas SOLO con las rutinas en vídeo \
de su catálogo de FuertaFit, que consultas con las herramientas; nunca inventes rutinas ni ids.

Cómo trabajas:
- Antes de proponer, mira el historial reciente y lo que ya hay planificado para no repetir rutinas y alternar \
zonas (no dos días seguidos de la misma zona intensa, mete días suaves o de cuerpo-mente tras varios días duros).
- Ajusta la suma de duraciones al tiempo que te den (±5 min). Si piden calentamiento o estiramientos, inclúyelos \
dentro de ese tiempo.
- Respeta el material que tenga y sus preferencias.
- Cuando te pidan planificar uno o varios días, guárdalos con guardar_plan (un día por llamada) y después \
resume en pocas líneas qué has puesto cada día y por qué.
- Si solo preguntan o piden ideas, contesta sin guardar nada.
- Responde en español, cercano y breve. Para cada rutina que menciones indica título y minutos."""

TOOLS = [
    {
        "name": "buscar_rutinas",
        "description": "Busca rutinas del catálogo con filtros. Devuelve como mucho `limite` resultados "
                       "(id, título, minutos, tipo, zona, intensidad, material, resumen) y el total que encajan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Palabras en título/resumen, p. ej. 'glúteos', 'yoga', 'hiit'."},
                "tipos": {"type": "array", "items": {"type": "string", "enum": [
                    "Fuerza", "Cardiovascular", "Mixto", "Cuerpo-Mente", "Calentamiento"]}},
                "intensidades": {"type": "array", "items": {"type": "string", "enum": ["low", "medium", "high"]}},
                "materiales": {"type": "array", "items": {"type": "string"},
                               "description": "Material disponible; vale la rutina si usa alguno de ellos "
                                              "(p. ej. 'No Material', 'Mancuernas', 'Material Casero', 'Gomas')."},
                "min_minutos": {"type": "integer"},
                "max_minutos": {"type": "integer"},
                "zona": {"type": "string", "description": "Metodología/zona, p. ej. 'Pierna', 'Torso', 'Fullbody'."},
                "limite": {"type": "integer", "description": "Máx. resultados (por defecto 20, tope 40)."},
            },
        },
    },
    {
        "name": "proponer_combinacion",
        "description": "Genera al azar una combinación de rutinas que suma el tiempo pedido, evitando las "
                       "hechas en los últimos 14 días. Útil como punto de partida; puedes ajustarla después.",
        "input_schema": {
            "type": "object",
            "properties": {
                "minutos": {"type": "integer"},
                "tipos": {"type": "array", "items": {"type": "string"}},
                "intensidades": {"type": "array", "items": {"type": "string", "enum": ["low", "medium", "high"]}},
                "materiales": {"type": "array", "items": {"type": "string"}},
                "calentamiento": {"type": "boolean"},
                "estiramiento": {"type": "boolean"},
            },
            "required": ["minutos"],
        },
    },
    {
        "name": "ver_historial",
        "description": "Rutinas marcadas como hechas en los últimos `dias` días, de la más reciente a la más antigua.",
        "input_schema": {
            "type": "object",
            "properties": {"dias": {"type": "integer", "description": "Por defecto 14."}},
        },
    },
    {
        "name": "ver_calendario",
        "description": "Rutinas planificadas entre dos fechas (YYYY-MM-DD, incluidas).",
        "input_schema": {
            "type": "object",
            "properties": {"desde": {"type": "string"}, "hasta": {"type": "string"}},
            "required": ["desde", "hasta"],
        },
    },
    {
        "name": "guardar_plan",
        "description": "Guarda (sustituyendo lo que hubiera) las rutinas planificadas para un día, en orden.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fecha": {"type": "string", "description": "YYYY-MM-DD"},
                "ids": {"type": "array", "items": {"type": "integer"}},
                "nota": {"type": "string", "description": "Una frase: enfoque del día o por qué."},
            },
            "required": ["fecha", "ids"],
        },
    },
    {
        "name": "borrar_plan",
        "description": "Elimina lo planificado para un día.",
        "input_schema": {
            "type": "object",
            "properties": {"fecha": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["fecha"],
        },
    },
]


def available():
    has_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    return bool(anthropic and has_key)


def _line(it):
    parts = [f"#{it['id']}", it["title"], f"{it['durationMinutes']} min", it.get("trainingType"),
             it.get("methodology"), it.get("intensity"), "material: " + ", ".join(it["materials"]),
             it.get("summary")]
    return " | ".join(str(p) for p in parts if p)


def _date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise ValueError(f"Fecha no válida: {value!r}. Usa YYYY-MM-DD.")
    date.fromisoformat(value)
    return value


def _run_tool(env, name, args, changed):
    cat, plans = catalog.get(env), env["fuerta.plan"]
    if name == "buscar_rutinas":
        res = catalog.search(cat, q=args.get("texto"), types=args.get("tipos"), intensities=args.get("intensidades"),
                          materials=args.get("materiales"), min_minutes=args.get("min_minutos"),
                          max_minutes=args.get("max_minutos"), methodology=args.get("zona"),
                          limit=min(int(args.get("limite") or 20), 40))
        lines = [_line(it) for it in res["items"]]
        return f"{res['total']} rutinas encajan; mostrando {len(lines)}:\n" + "\n".join(lines)

    if name == "proponer_combinacion":
        res = generate(env, {"minutes": args["minutos"], "types": args.get("tipos"),
                             "intensities": args.get("intensidades"), "materials": args.get("materiales"),
                             "warmup": args.get("calentamiento", False), "cooldown": args.get("estiramiento", False)})
        lines = [_line(it) for it in res["blocks"]]
        return f"Total {res['total']} min:\n" + ("\n".join(lines) or "No hay rutinas que encajen.")

    if name == "ver_historial":
        days = int(args.get("dias") or 14)
        rows = env["fuerta.history"].recent(days)
        if not rows:
            return f"No hay nada marcado como hecho en los últimos {days} días."
        return "\n".join(f"{d}: " + (_line(cat.by_id[pid]) if pid in cat.by_id else f"#{pid}") for pid, d in rows)

    if name == "ver_calendario":
        found = plans.get_plans(_date(args["desde"]), _date(args["hasta"]))
        if not found:
            return "No hay nada planificado en esas fechas."
        out = []
        for day, p in found.items():
            out.append(f"{day}{' — ' + p['note'] if p['note'] else ''}")
            out += ["  " + _line(cat.by_id[pid]) for pid in p["postIds"] if pid in cat.by_id]
        return "\n".join(out)

    if name == "guardar_plan":
        day = _date(args["fecha"])
        unknown = [i for i in args["ids"] if int(i) not in cat.by_id]
        if unknown:
            raise ValueError(f"Estos ids no existen en el catálogo: {unknown}. Búscalos con buscar_rutinas.")
        ids = plans.save_plan(day, args["ids"], args.get("nota"), source="bot")
        changed.add(day)
        total = sum(cat.by_id[i]["durationMinutes"] for i in ids)
        return f"Guardado {day}: {len(ids)} rutinas, {total} min."

    if name == "borrar_plan":
        day = _date(args["fecha"])
        plans.delete_plan(day)
        changed.add(day)
        return f"Borrado el plan del {day}."

    raise ValueError(f"Herramienta desconocida: {name}")


def _context(env):
    today = user_today(env)
    settings = env["fuerta.settings"].get_settings()
    week = ", ".join(f"{WEEKDAYS[(today + timedelta(d)).weekday()]} {today + timedelta(d)}" for d in range(7))
    ctx = f"[Contexto] Hoy es {WEEKDAYS[today.weekday()]} {today.isoformat()}. Próximos días: {week}."
    if settings["preferences"]:
        ctx += f"\nPreferencias guardadas: {settings['preferences']}"
    return ctx


def chat(env, history, message):
    """history: [{"role": "user"|"assistant", "content": str}, ...] de turnos anteriores (solo texto).

    Devuelve {"reply": str, "changedDays": [..]}.
    """
    if not available():
        return {"reply": "El entrenador no está activo: falta la API key de Anthropic (ANTHROPIC_API_KEY en .env).",
                "changedDays": [], "error": True}

    client = anthropic.Anthropic()
    messages = [{"role": m["role"], "content": m["content"]} for m in history[-20:] if m.get("content")]
    messages.append({"role": "user", "content": f"{_context(env)}\n\n{message}"})
    changed = set()

    try:
        for _ in range(MAX_STEPS):
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS,
                messages=messages,
                # Si el modelo rechazara la petición, la API la reintenta sola con el modelo de respaldo.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if response.stop_reason == "refusal":
                return {"reply": "No he podido responder a eso. Prueba a reformularlo.",
                        "changedDays": sorted(changed), "error": True}
            if response.stop_reason != "tool_use":
                text = "\n".join(b.text for b in response.content if b.type == "text").strip()
                if response.stop_reason == "max_tokens":
                    text += "\n\n(Respuesta cortada por longitud.)"
                return {"reply": text or "Hecho.", "changedDays": sorted(changed)}

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    content, is_error = _run_tool(env, block.name, block.input, changed), False
                except (ValueError, KeyError, TypeError) as e:
                    content, is_error = f"Error: {e}", True
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": content, "is_error": is_error})
            messages.append({"role": "user", "content": results})

        return {"reply": "Me he quedado a medias (demasiados pasos). Pídemelo de nuevo más concreto.",
                "changedDays": sorted(changed), "error": True}
    except anthropic.AuthenticationError:
        msg = "La API key de Anthropic no es válida."
    except anthropic.RateLimitError:
        msg = "Límite de uso de la API alcanzado; prueba en un rato."
    except anthropic.APIStatusError as e:
        msg = f"Error de la API de Anthropic ({e.status_code}): {e.message}"
    except anthropic.APIConnectionError:
        msg = "No hay conexión con la API de Anthropic."
    return {"reply": msg, "changedDays": sorted(changed), "error": True}

