"""Implementación SQLAlchemy del puerto ``ConfiguracionRemotaRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota
from src.configuration.domain.repositories.configuracion_remota_repository import ConfiguracionRemotaRepository
from src.configuration.infrastructure.models.configuracion_remota_model import ConfiguracionRemotaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyConfiguracionRemotaRepository(ConfiguracionRemotaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ConfiguracionRemotaModel) -> ConfiguracionRemota:
        return ConfiguracionRemota(
            id_configuracion_remota=orm.id_configuracion_remota,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            frecuencia_captura=orm.frecuencia_captura,
            intervalo_transmision=orm.intervalo_transmision,
            estado=orm.estado,
            id_usuario=orm.id_usuario,
            fecha_creacion=orm.fecha_creacion,
            fecha_aplicacion=orm.fecha_aplicacion,
        )

    def guardar(self, config: ConfiguracionRemota) -> ConfiguracionRemota:
        orm = ConfiguracionRemotaModel(
            id_dispositivo_iot=config.id_dispositivo_iot,
            frecuencia_captura=config.frecuencia_captura,
            intervalo_transmision=config.intervalo_transmision,
            estado=config.estado,
            id_usuario=config.id_usuario,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def obtener_pendiente(self, id_dispositivo_iot: int) -> Optional[ConfiguracionRemota]:
        orm = (
            self.db.query(ConfiguracionRemotaModel)
            .filter(
                ConfiguracionRemotaModel.id_dispositivo_iot == id_dispositivo_iot,
                ConfiguracionRemotaModel.estado == "PENDIENTE",
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[ConfiguracionRemota]:
        return [
            self._a_entidad(orm)
            for orm in (
                self.db.query(ConfiguracionRemotaModel)
                .filter(ConfiguracionRemotaModel.id_dispositivo_iot == id_dispositivo_iot)
                .order_by(ConfiguracionRemotaModel.fecha_creacion.desc())
                .all()
            )
        ]
