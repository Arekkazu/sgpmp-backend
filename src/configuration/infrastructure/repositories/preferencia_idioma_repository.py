# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy del puerto ``PreferenciaIdiomaRepository`` (RF-29)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.preferencia_idioma import PreferenciaIdioma
from src.configuration.domain.repositories.preferencia_idioma_repository import PreferenciaIdiomaRepository
from src.configuration.infrastructure.models.preferencia_idioma_model import PreferenciaIdiomaModel
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import NotFoundError


class SqlAlchemyPreferenciaIdiomaRepository(PreferenciaIdiomaRepository):
    """Implementación SQLAlchemy de ``PreferenciaIdiomaRepository``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: PreferenciaIdiomaModel) -> PreferenciaIdioma:
        return PreferenciaIdioma(
            id_preferencia_idioma=orm.id_preferencia_idioma,
            id_usuario=orm.id_usuario,
            locale_code=orm.locale_code,
            es_por_defecto=orm.es_por_defecto,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_usuario(self, id_usuario: int) -> Optional[PreferenciaIdioma]:
        """Obtiene la preferencia de idioma personal del usuario, o ``None`` si no
        tiene.
        """
        orm = (
            self.db.query(PreferenciaIdiomaModel)
            .filter(
                PreferenciaIdiomaModel.id_usuario == id_usuario,
                PreferenciaIdiomaModel.es_por_defecto.is_(False),
            )
            .order_by(
                PreferenciaIdiomaModel.fecha_actualizacion.desc().nullslast(),
                PreferenciaIdiomaModel.id_preferencia_idioma.desc(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def obtener_global(self) -> Optional[PreferenciaIdioma]:
        """Obtiene la preferencia de idioma global del sistema, o ``None`` si no está
        definido.
        """
        orm = (
            self.db.query(PreferenciaIdiomaModel)
            .filter(PreferenciaIdiomaModel.es_por_defecto.is_(True))
            .order_by(
                PreferenciaIdiomaModel.fecha_actualizacion.desc().nullslast(),
                PreferenciaIdiomaModel.id_preferencia_idioma.desc(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def version_perfil(self, id_usuario: int) -> Optional[int]:
        """Versión actual del perfil del usuario, para la comprobación de concurrencia."""
        return (
            self.db.query(Usuarios.version)
            .filter(Usuarios.id_usuario == id_usuario)
            .scalar()
        )

    def guardar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        """Inserta la preferencia de idioma y devuelve la entidad con su id asignado."""
        orm = PreferenciaIdiomaModel(
            id_usuario=entidad.id_usuario,
            locale_code=entidad.locale_code,
            es_por_defecto=entidad.es_por_defecto,
            fecha_actualizacion=entidad.fecha_actualizacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def actualizar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        """Persiste los cambios de la preferencia de idioma y devuelve la entidad
        actualizada.
        """
        orm = self.db.get(PreferenciaIdiomaModel, entidad.id_preferencia_idioma)
        if orm is None:
            raise NotFoundError(
                code="PREFERENCIA_IDIOMA_NO_ENCONTRADA",
                message="La preferencia de idioma que intenta actualizar ya no existe.",
                field="id_preferencia_idioma",
            )
        orm.locale_code = entidad.locale_code
        orm.fecha_actualizacion = entidad.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)
