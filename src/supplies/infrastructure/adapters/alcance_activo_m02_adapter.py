# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-75/76/80: filtro por finca del usuario |
"""Adaptador de alcance de activos por rol contra ``modulo2`` (RF-81 / CU-04).

Aísla la deuda de que no existe un modelo real de "unidad productiva asignada
a un usuario" (ver ``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md``). El use
case y el router no saben nada de roles; solo llaman a ``AlcanceActivoPort``.

Regla de alcance (RF-25): cada usuario queda restringido a los activos
ubicados en sus fincas (``activos_biologicos.id_infraestructura`` →
``infraestructuras.id_finca``), salvo el Administrador, que es global
(``AlcanceFincaAdapter``).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort

_SQL_ACTIVOS_POR_FINCA = text(
    """
    SELECT ab.id_activo_biologico
    FROM modulo2.activos_biologicos ab
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    WHERE i.id_finca = ANY(:ids_fincas)
    """
)


class AlcanceActivoM02Adapter(AlcanceActivoPort):
    """Resuelve el alcance de activos del usuario a partir de su alcance de fincas."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_ids_activos_permitidos(
        self, id_usuario: int, id_rol: int, id_finca: Optional[int] = None
    ) -> Optional[list[int]]:
        alcance_finca = AlcanceFincaAdapter(self.db)
        ids_fincas = None if alcance_finca.es_global(id_rol) else alcance_finca.listar_ids_fincas_permitidas(
            id_usuario, id_rol)
        if id_finca is not None:  # el filtro se combina con el alcance: una finca ajena no devuelve nada
            ids_fincas = [id_finca] if ids_fincas is None or id_finca in ids_fincas else []
        if ids_fincas is None:
            return None
        filas = self.db.execute(_SQL_ACTIVOS_POR_FINCA, {"ids_fincas": ids_fincas}).fetchall()
        return [f.id_activo_biologico for f in filas]
