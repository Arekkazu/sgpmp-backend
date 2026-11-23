# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: repositorio SQLAlchemy de aristas de transmisión |
# | 2026-11-02 | Arekkazu | RF-110: editar vía, dirección, intensidad y barrera de una arista |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Bajo RLS: solo ve las aristas cuya área de origen es del usuario (o el usuario de servicio)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.domain.repositories.arista_transmision_repository import AristaTransmisionRepository
from src.configuration.infrastructure.models.arista_transmision_model import AristaTransmisionModel
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error

_CAMPOS = ("id_infraestructura_origen", "id_infraestructura_destino", "via", "direccion", "intensidad",
           "factor_barrera", "origen_dato", "descripcion", "es_activo", "id_usuario")


class SqlAlchemyAristaTransmisionRepository(AristaTransmisionRepository):
    """Implementación SQLAlchemy de ``AristaTransmisionRepository``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, arista: AristaTransmision) -> AristaTransmision:
        """409 si ya hay una arista activa con el mismo origen, destino y vía."""
        try:
            orm = AristaTransmisionModel(**{c: getattr(arista, c) for c in _CAMPOS})
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_id(self, id_arista: int) -> Optional[AristaTransmision]:
        """Devuelve la arista, o ``None``."""
        orm = self.db.get(AristaTransmisionModel, id_arista)
        return self._a_entidad(orm) if orm else None

    def actualizar(self, arista: AristaTransmision) -> AristaTransmision:
        """Actualiza los datos editables validándolos."""
        try:
            orm = self.db.get(AristaTransmisionModel, arista.id_arista_transmision)
            orm.via = arista.via
            orm.direccion = arista.direccion
            orm.intensidad = arista.intensidad
            orm.factor_barrera = arista.factor_barrera
            orm.descripcion = arista.descripcion
            orm.es_activo = arista.es_activo
            orm.fecha_actualizacion = arista.fecha_actualizacion
            self.db.flush()
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_activas_por_finca(self, id_finca: int) -> list[AristaTransmision]:
        """Lista las aristas activas de la finca."""
        filas = self.db.execute(
            select(AristaTransmisionModel)
            .join(InfraestructuraModel,
                  InfraestructuraModel.id_infraestructura == AristaTransmisionModel.id_infraestructura_origen)
            .where(InfraestructuraModel.id_finca == id_finca, AristaTransmisionModel.es_activo.is_(True))
            .order_by(AristaTransmisionModel.id_arista_transmision)
        ).scalars().all()
        return [self._a_entidad(f) for f in filas]

    @staticmethod
    def _a_entidad(orm: AristaTransmisionModel) -> AristaTransmision:
        return AristaTransmision(
            **{c: getattr(orm, c) for c in _CAMPOS},
            id_arista_transmision=orm.id_arista_transmision,
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
        )
