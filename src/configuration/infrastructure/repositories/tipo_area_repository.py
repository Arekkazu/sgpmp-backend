"""Implementación SQLAlchemy del puerto :class:`TipoAreaRepository` (RF-20)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.configuration.domain.entities.tipo_area import TipoArea
from src.configuration.domain.repositories.tipo_area_repository import TipoAreaRepository
from src.configuration.infrastructure.models.tipo_area_model import TipoAreaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyTipoAreaRepository(TipoAreaRepository):
    """Adaptador SQLAlchemy que mapea entre ``modulo9.tipos_area`` y la entidad."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: TipoAreaModel) -> TipoArea:
        return TipoArea(
            id_tipo_area=orm.id_tipo_area,
            nombre=orm.nombre,
            es_activo=orm.es_activo,
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_id(self, id_tipo_area: int) -> Optional[TipoArea]:
        orm = self.db.get(TipoAreaModel, id_tipo_area)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre(self, nombre: str) -> Optional[TipoArea]:
        orm = (
            self.db.query(TipoAreaModel)
            .filter(func.lower(TipoAreaModel.nombre) == nombre.strip().lower())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, tipo_area: TipoArea) -> TipoArea:
        orm = TipoAreaModel(
            nombre=tipo_area.nombre,
            es_activo=tipo_area.es_activo,
            fecha_creacion=tipo_area.fecha_creacion or datetime.now(timezone.utc),
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_tipo_area_nombre": (
                    f"El tipo de área '{tipo_area.nombre}' ya se encuentra registrado en el catálogo."
                ),
            })
        return self._a_entidad(orm)

    def actualizar(self, tipo_area: TipoArea) -> TipoArea:
        orm = self.db.get(TipoAreaModel, tipo_area.id_tipo_area)
        orm.nombre = tipo_area.nombre
        orm.es_activo = tipo_area.es_activo
        orm.fecha_actualizacion = tipo_area.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_tipo_area_nombre": (
                    f"El nombre '{tipo_area.nombre}' ya pertenece a otro tipo de área del catálogo."
                ),
            })
        return self._a_entidad(orm)

    def listar(self, *, solo_activos: bool = False) -> list[TipoArea]:
        query = self.db.query(TipoAreaModel)
        if solo_activos:
            query = query.filter(TipoAreaModel.es_activo.is_(True))
        return [
            self._a_entidad(orm)
            for orm in query.order_by(TipoAreaModel.nombre).all()
        ]
