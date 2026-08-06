"""Adaptador de consulta del activo biológico (RF-33 / RF-36) contra ``modulo2``.

Reutiliza ``SqlAlchemyActivoBiologicoRepository`` de biological_assets y proyecta
la entidad a la vista de solo lectura ``ActivoConsulta`` que necesita el módulo
de suministros. Mantiene el bajo acoplamiento: el dominio de suministros solo
conoce su puerto ``ActivoConsultaPort``.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.supplies.domain.repositories.activo_consulta_port import (
    ESTADO_EN_TRATAMIENTO,
    ActivoConsulta,
    ActivoConsultaPort,
)

_SQL_EN_TRATAMIENTO = text(
    "SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE id_estado = :id_estado"
)


class ActivoM02Adapter(ActivoConsultaPort):
    """Consulta ``modulo2.activos_biologicos`` para el módulo de suministros."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = SqlAlchemyActivoBiologicoRepository(db)

    def obtener(self, id_activo: int) -> Optional[ActivoConsulta]:
        activo = self._repo.obtener_por_id(id_activo)
        if activo is None:
            return None
        cantidad_actual = (
            activo.detalle_poblacional.cantidad_actual if activo.detalle_poblacional else None
        )
        return ActivoConsulta(
            id_activo_biologico=activo.id_activo_biologico,
            tipo=activo.tipo,
            id_estado=activo.id_estado,
            nombre_estado=activo.nombre_estado,
            cantidad_actual=cantidad_actual,
            fecha_inicio_ciclo=activo.fecha_inicio_ciclo,
        )

    def listar_en_tratamiento(self) -> list[int]:
        filas = self.db.execute(_SQL_EN_TRATAMIENTO, {"id_estado": ESTADO_EN_TRATAMIENTO}).fetchall()
        return [f.id_activo_biologico for f in filas]
