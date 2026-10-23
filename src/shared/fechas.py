# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Regla única de fechas: se guarda y viaja en UTC; el día se ve en la zona del usuario.

- **Instantes** (``datetime``): todo lo que entra se normaliza a UTC con
  ``FechaHoraUtc``. Un valor con zona se convierte; uno sin zona se toma como
  UTC, la hora norma. Las columnas son ``timestamptz`` y la sesión de Postgres
  está en UTC, así que es lo mismo que ya hacía la BD, pero explícito.
- **Días calendario** (``date``: fecha de ingreso, baja, cierre...): "hoy" y
  "¿es futura?" dependen de dónde está el usuario. El frontend envía su zona
  IANA en ``X-Zona-Horaria`` (sale de ``Intl`` en el navegador) y el middleware
  la deja aquí por request. Sin cabecera, o con una zona inválida, el día es
  el de UTC: quien no comparte su zona ve la hora norma.

Las tareas en segundo plano no tienen usuario detrás y trabajan en UTC.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import date, datetime, timezone, tzinfo
from typing import Annotated, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator

CABECERA_ZONA = "x-zona-horaria"

_zona: ContextVar[tzinfo] = ContextVar("zona_usuario", default=timezone.utc)


def a_utc(valor: datetime) -> datetime:
    """El mismo instante en UTC; un valor sin zona ya se considera UTC."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


FechaHoraUtc = Annotated[datetime, AfterValidator(a_utc)]
"""``datetime`` de entrada (DTO, Query, Form) normalizado a UTC."""


def zona_desde_nombre(nombre: Optional[str]) -> tzinfo:
    """Zona IANA (``America/Bogota``); UTC si falta o no existe."""
    if not nombre:
        return timezone.utc
    try:
        return ZoneInfo(nombre.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def establecer_zona_usuario(nombre: Optional[str]) -> Token:
    """Fija la zona del request en curso. Lo llama el middleware."""
    return _zona.set(zona_desde_nombre(nombre))


def zona_usuario() -> tzinfo:
    return _zona.get()


def _ahora() -> datetime:
    return datetime.now(zona_usuario())


def hoy_usuario() -> date:
    """Día calendario actual en la zona del usuario."""
    return _ahora().date()


def fecha_usuario(valor: datetime | date) -> date:
    """Día calendario, en la zona del usuario, de un instante (un ``date`` pasa tal cual)."""
    if isinstance(valor, datetime):
        return a_utc(valor).astimezone(zona_usuario()).date()
    return valor
