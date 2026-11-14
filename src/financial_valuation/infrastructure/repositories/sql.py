# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: ayudas de SQL de los repositorios del módulo financiero |
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
# | 2026-11-12 | Arekkazu | USAB-M05-M06 N-04 RF-92/93: alcance de titulares y períodos a las fincas de quien solo consulta |
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

# RF-85 FA-4: un cálculo consumido por una cosecha del 100 % (producto de consumo con proporción 1) ya no es
# valor del activo: su valor pasó a inventario y el activo queda en cero.
CONSUMIDO_POR_COSECHA = """EXISTS (SELECT 1 FROM modulo6.reconocimientos_productos_agricolas p
    WHERE p.id_calculo_valor_razonable = {calculo} AND p.tipo = 'PRODUCTO_DE_CONSUMO'
      AND p.proporcion_cosechada >= 1)"""


# N-04: quien no lee el cierre (el Productor, el Auditor) solo ve los titulares de sus propias fincas. Los
# períodos son legibles por cualquier usuario autenticado (RLS); `modulo9.fincas` ya está acotada por RLS a las
# fincas del usuario (el Administrador protegido las ve todas). Un período sin titular no es de nadie: no se ofrece.
def alcance_titular(columna: str) -> str:
    return (f"((SELECT modulo1.fn_tiene_permiso('cierre_periodo', 'R')) "
            f"OR {columna} IN (SELECT f.numero_id_tributaria FROM modulo9.fincas f))")


def alcance_periodo(columna: str) -> str:
    """El mismo alcance para lo que cuelga de un período (estados de resultados, informes de revelaciones).

    ``columna`` va calificada con el alias de la tabla externa: sin calificar se resolvería contra
    ``pa`` y la condición sería siempre verdadera."""
    return (f"EXISTS (SELECT 1 FROM modulo6.periodos_contables pa WHERE pa.id_periodo_contable = {columna} "
            f"AND {alcance_titular('pa.numero_id_tributaria')})")


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
