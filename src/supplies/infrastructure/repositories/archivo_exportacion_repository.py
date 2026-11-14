# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: archivos exportados          |
"""Implementación SQLAlchemy de :class:`ArchivoExportacionRepository`."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.archivo_exportacion import ArchivoExportacion
from src.supplies.domain.repositories.archivo_exportacion_repository import ArchivoExportacionRepository
from src.supplies.infrastructure.models.archivo_exportacion_suministro_model import (
    ArchivoExportacionSuministroModel,
)


class SqlAlchemyArchivoExportacionRepository(ArchivoExportacionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ArchivoExportacionSuministroModel) -> ArchivoExportacion:
        return ArchivoExportacion(
            id_archivo=orm.id_archivo_exportacion_suministro,
            origen=orm.origen,
            formato=orm.formato,
            nombre_archivo=orm.nombre_archivo,
            contenido=orm.contenido,
            total_registros=orm.total_registros,
            id_usuario=orm.id_usuario,
            fecha_generacion=orm.fecha_generacion,
            fecha_expiracion=orm.fecha_expiracion,
            id_referencia=orm.id_referencia,
            fecha_eliminacion=orm.fecha_eliminacion,
        )

    def guardar(self, archivo: ArchivoExportacion) -> ArchivoExportacion:
        orm = ArchivoExportacionSuministroModel(
            origen=archivo.origen,
            id_referencia=archivo.id_referencia,
            formato=archivo.formato,
            nombre_archivo=archivo.nombre_archivo,
            tipo_contenido=archivo.tipo_contenido,
            contenido=archivo.contenido,
            tamano_bytes=archivo.tamano_bytes,
            total_registros=archivo.total_registros,
            id_usuario=archivo.id_usuario,
            fecha_generacion=archivo.fecha_generacion,
            fecha_expiracion=archivo.fecha_expiracion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def obtener(self, id_archivo: UUID) -> Optional[ArchivoExportacion]:
        orm = self.db.get(ArchivoExportacionSuministroModel, id_archivo)
        return self._a_entidad(orm) if orm else None

    def obtener_por_referencia(self, origen: str, id_referencia: int) -> Optional[ArchivoExportacion]:
        orm = (
            self.db.query(ArchivoExportacionSuministroModel)
            .filter(
                ArchivoExportacionSuministroModel.origen == origen,
                ArchivoExportacionSuministroModel.id_referencia == id_referencia,
            )
            .order_by(ArchivoExportacionSuministroModel.fecha_generacion.desc())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def purgar_vencidos(self, ahora: datetime) -> list[ArchivoExportacion]:
        vencidos = (
            self.db.query(ArchivoExportacionSuministroModel)
            .filter(
                ArchivoExportacionSuministroModel.fecha_eliminacion.is_(None),
                ArchivoExportacionSuministroModel.fecha_expiracion <= ahora,
            )
            .all()
        )
        for orm in vencidos:
            orm.contenido = None
            orm.fecha_eliminacion = ahora
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        return [self._a_entidad(o) for o in vencidos]
