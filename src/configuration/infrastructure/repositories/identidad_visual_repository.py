"""Implementación SQLAlchemy del puerto ``IdentidadVisualRepository`` (RF-26)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.identidad_visual import IdentidadVisual
from src.configuration.domain.repositories.identidad_visual_repository import IdentidadVisualRepository
from src.configuration.domain.value_objects.color_hex import ColorHex
from src.configuration.domain.value_objects.nombre_organizacion import NombreOrganizacion
from src.configuration.infrastructure.models.identidad_visual_model import IdentidadVisualModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyIdentidadVisualRepository(IdentidadVisualRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: IdentidadVisualModel) -> IdentidadVisual:
        return IdentidadVisual(
            id_identidad_visual=orm.id_identidad_visual,
            id_finca=orm.id_finca,
            id_usuario=orm.id_usuario,
            logo_path=orm.logo_path,
            primary_color=ColorHex(orm.primary_color) if orm.primary_color else None,
            secondary_color=ColorHex(orm.secondary_color) if orm.secondary_color else None,
            org_display_name=NombreOrganizacion(orm.org_display_name) if orm.org_display_name else None,
            version=orm.version,
            fecha_creacion=orm.fecha_creacion,
        )

    def obtener_por_finca(self, id_finca: int) -> Optional[IdentidadVisual]:
        # Usa la misma lógica que vw_rf26_identidad_visual_activa: última versión por finca
        orm = (
            self.db.query(IdentidadVisualModel)
            .filter(IdentidadVisualModel.id_finca == id_finca)
            .order_by(
                IdentidadVisualModel.version.desc().nullslast(),
                IdentidadVisualModel.fecha_creacion.desc().nullslast(),
                IdentidadVisualModel.id_identidad_visual.desc(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        orm = IdentidadVisualModel(
            id_finca=entidad.id_finca,
            id_usuario=entidad.id_usuario,
            logo_path=entidad.logo_path,
            primary_color=str(entidad.primary_color) if entidad.primary_color else None,
            secondary_color=str(entidad.secondary_color) if entidad.secondary_color else None,
            org_display_name=str(entidad.org_display_name) if entidad.org_display_name else None,
            version=entidad.version,
            fecha_creacion=entidad.fecha_creacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def actualizar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        orm = self.db.get(IdentidadVisualModel, entidad.id_identidad_visual)
        orm.id_usuario = entidad.id_usuario
        orm.logo_path = entidad.logo_path
        orm.primary_color = str(entidad.primary_color) if entidad.primary_color else None
        orm.secondary_color = str(entidad.secondary_color) if entidad.secondary_color else None
        orm.org_display_name = str(entidad.org_display_name) if entidad.org_display_name else None
        orm.version = entidad.version
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)
