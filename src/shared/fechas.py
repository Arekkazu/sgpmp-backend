"""Fecha calendario de referencia para validar campos ``date`` del usuario.

Los campos ``date`` (fecha de ingreso, baja, cierre...) son la fecha que el
usuario elige en Colombia. Compararlos contra el día UTC deja pasar "mañana"
desde las 19:00 hora local (UTC ya va en el día siguiente) y convierte los
timestamps de la BD al día equivocado. Colombia no tiene horario de verano,
así que el desfase fijo -05:00 basta y no depende de tzdata.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

ZONA_COLOMBIA = timezone(timedelta(hours=-5))


def _ahora() -> datetime:
    return datetime.now(ZONA_COLOMBIA)


def hoy_colombia() -> date:
    return _ahora().date()


def fecha_colombia(valor: datetime | date) -> date:
    """Día calendario en Colombia de un timestamp con zona (un ``date`` pasa tal cual)."""
    if isinstance(valor, datetime) and valor.tzinfo is not None:
        return valor.astimezone(ZONA_COLOMBIA).date()
    return valor.date() if isinstance(valor, datetime) else valor
