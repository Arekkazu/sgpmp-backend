"""Implementación SQLAlchemy del puerto ``ConfiguracionGlobalRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal
from src.configuration.domain.repositories.configuracion_global_repository import ConfiguracionGlobalRepository
from src.configuration.domain.value_objects.frecuencia_muestreo import FrecuenciaMuestreo
from src.configuration.domain.value_objects.heartbeat import Heartbeat
from src.configuration.infrastructure.models.configuracion_global_model import ConfiguracionGlobalModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyConfiguracionGlobalRepository(ConfiguracionGlobalRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ConfiguracionGlobalModel) -> ConfiguracionGlobal:
        return ConfiguracionGlobal(
            id_configuracion_global=orm.id_configuracion_global,
            frecuencia_muestreo=FrecuenciaMuestreo(orm.frecuencia_muestreo),
            heartbeat=Heartbeat(orm.heartbeat),
            fecha_actualizacion=orm.fecha_actualizacion,
            id_usuario=orm.id_usuario,
            es_activo=orm.es_activo,
        )

    def obtener_activo(self) -> Optional[ConfiguracionGlobal]:
        orm = (
            self.db.query(ConfiguracionGlobalModel)
            .filter(ConfiguracionGlobalModel.es_activo.is_(True))
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def obtener_por_id(self, id_configuracion_global: int) -> Optional[ConfiguracionGlobal]:
        orm = self.db.get(ConfiguracionGlobalModel, id_configuracion_global)
        return self._a_entidad(orm) if orm else None

    def guardar(self, config: ConfiguracionGlobal) -> ConfiguracionGlobal:
        orm = ConfiguracionGlobalModel(
            frecuencia_muestreo=config.frecuencia_muestreo.valor,
            heartbeat=config.heartbeat.valor,
            fecha_actualizacion=config.fecha_actualizacion,
            id_usuario=config.id_usuario,
            es_activo=config.es_activo,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def actualizar(self, config: ConfiguracionGlobal) -> ConfiguracionGlobal:
        orm = self.db.get(ConfiguracionGlobalModel, config.id_configuracion_global)
        orm.frecuencia_muestreo = config.frecuencia_muestreo.valor
        orm.heartbeat = config.heartbeat.valor
        orm.fecha_actualizacion = config.fecha_actualizacion
        orm.id_usuario = config.id_usuario
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)
