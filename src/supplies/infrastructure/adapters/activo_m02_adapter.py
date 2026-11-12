# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-75/76: los mensajes nombran el activo por su identificador, no por su id |
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-358-G43 RF-81: existe() consulta como el usuario de servicio para no confundir 403 con 404 |
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
from src.shared.database import como_sistema
from src.supplies.domain.repositories.activo_consulta_port import (
    ESTADO_EN_TRATAMIENTO,
    ActivoConsulta,
    ActivoConsultaPort,
)

_SQL_EXISTE = text("SELECT 1 FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id_activo")

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
            identificador=activo.identificador,
        )

    def existe(self, id_activo: int) -> bool:
        """Existencia sin el filtro de fincas: la RLS de ``modulo2`` oculta los activos ajenos, así que
        se pregunta como el usuario de servicio. Solo se devuelve sí/no (RF-81 E2: 403, no 404)."""
        with como_sistema(self.db):
            return self.db.execute(_SQL_EXISTE, {"id_activo": id_activo}).first() is not None

    def listar_en_tratamiento(self) -> list[int]:
        filas = self.db.execute(_SQL_EN_TRATAMIENTO, {"id_estado": ESTADO_EN_TRATAMIENTO}).fetchall()
        return [f.id_activo_biologico for f in filas]
