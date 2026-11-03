"""Fechas en la zona horaria del usuario (Odoo trabaja en UTC por dentro, así que date.today() no sirve)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Europe/Madrid"
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def today(env):
    try:
        tz = ZoneInfo(env.user.tz or DEFAULT_TZ)
    except Exception:  # zona desconocida en el perfil
        tz = ZoneInfo(DEFAULT_TZ)
    return datetime.now(tz).date()


def days_between(start, end):
    d, last = date.fromisoformat(start), date.fromisoformat(end)
    while d <= last:
        yield d.isoformat()
        d += timedelta(1)
