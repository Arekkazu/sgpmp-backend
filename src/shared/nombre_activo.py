# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75/76/80/82: nombre visible del activo en un solo lugar |
"""Cómo se nombra un activo biológico en lo que ve el usuario (Suministros y Finanzas).

Por su identificador. Un lote o un animal registrado sin identificador se nombra
«Lote 1632» o «Animal 1632»: nunca ``null`` ni ``#1632`` (reporte de usabilidad T-01).
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def nombre_activo_sql(alias: str = "a") -> str:
    """Expresión SQL con el nombre visible del activo ``{alias}`` de ``modulo2.activos_biologicos``."""
    return (f"COALESCE(NULLIF(btrim({alias}.identificador), ''), "
            f"CASE WHEN {alias}.tipo::text = 'POBLACIONAL' THEN 'Lote ' ELSE 'Animal ' END "
            f"|| {alias}.id_activo_biologico)")


_SQL = text(
    f"SELECT a.id_activo_biologico, {nombre_activo_sql()} AS nombre "
    "FROM modulo2.activos_biologicos a WHERE a.id_activo_biologico IN :ids"
).bindparams(bindparam("ids", expanding=True))


def nombres_activos(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    """``{id_activo_biologico: nombre visible}`` de los activos dados que el usuario puede ver (RLS)."""
    unicos = sorted({i for i in ids if i is not None})
    if not unicos:
        return {}
    return {f.id_activo_biologico: f.nombre for f in db.execute(_SQL, {"ids": unicos})}
