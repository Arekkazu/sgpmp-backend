# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: ayudas de SQL de los repositorios del módulo financiero |
"""Ayudas de SQL compartidas por los repositorios de M06.

Los repositorios de M06 usan SQL explícito: casi todas sus lecturas cruzan M02, M09 y M05, y las
escrituras pasan por los triggers de ``modulo6`` (inmutabilidad, período cerrado). Toda escritura
traduce el error de BD antes de salir de la capa (``raise_from_db_error``)."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error


def a_json(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    return json.dumps(valor, default=lambda v: str(v) if isinstance(v, Decimal) else str(v), ensure_ascii=False)


def filas(db: Session, sql: str, params: Optional[dict] = None) -> list[dict]:
    return [dict(f._mapping) for f in db.execute(text(sql), params or {})]


def fila(db: Session, sql: str, params: Optional[dict] = None) -> Optional[dict]:
    resultado = db.execute(text(sql), params or {}).first()
    return dict(resultado._mapping) if resultado is not None else None


def escribir(db: Session, sql: str, params: Optional[dict] = None, conflictos: Optional[dict] = None) -> Optional[Any]:
    """Ejecuta una escritura (con ``RETURNING`` devuelve el primer valor) y traduce los errores."""
    try:
        resultado = db.execute(text(sql), params or {})
        db.flush()
        return resultado.scalar() if resultado.returns_rows else resultado.rowcount
    except Exception as exc:
        raise_from_db_error(exc, conflictos)
