from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.repositories.configuracion_motor_ia_repository import ConfiguracionMotorIARepository
from src.prediction.infrastructure.models.configuracion_motor_ia_model import ConfiguracionMotorIAModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyConfiguracionMotorIARepository(ConfiguracionMotorIARepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def _a_entidad(self, orm: ConfiguracionMotorIAModel) -> ConfiguracionMotorIA:
        return ConfiguracionMotorIA(
            id_configuracion_motor=orm.id_configuracion_motor,
            tipo_modelo=orm.tipo_modelo,
            umbral_riesgo_alto=orm.umbral_riesgo_alto,
            umbral_alerta_critica=orm.umbral_alerta_critica,
            ventana_temporal_min=orm.ventana_temporal_min,
            id_version_modelo_activa=orm.id_version_modelo_activa,
            modo_ejecucion=orm.modo_ejecucion,
            config_version=orm.config_version,
            w_factor_sanitario=orm.w_factor_sanitario,
            w_factor_ambiental=orm.w_factor_ambiental,
            w_factor_densidad=orm.w_factor_densidad,
            temp_min_config=orm.temp_min_config,
            temp_max_config=orm.temp_max_config,
            hr_min_config=orm.hr_min_config,
            hr_max_config=orm.hr_max_config,
            densidad_maxima_config=orm.densidad_maxima_config,
            es_activa=orm.es_activa,
            id_usuario_responsable=orm.id_usuario_responsable,
            fecha_creacion=orm.fecha_creacion,
        )

    def obtener_por_tipo(self, tipo_modelo: str) -> Optional[ConfiguracionMotorIA]:
        orm = (
            self._db.query(ConfiguracionMotorIAModel)
            .filter(ConfiguracionMotorIAModel.tipo_modelo == tipo_modelo)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar(self) -> list[ConfiguracionMotorIA]:
        orms = (
            self._db.query(ConfiguracionMotorIAModel)
            .order_by(ConfiguracionMotorIAModel.tipo_modelo)
            .all()
        )
        return [self._a_entidad(orm) for orm in orms]

    def guardar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA:
        try:
            orm = ConfiguracionMotorIAModel(
                tipo_modelo=entidad.tipo_modelo,
                umbral_riesgo_alto=entidad.umbral_riesgo_alto,
                umbral_alerta_critica=entidad.umbral_alerta_critica,
                ventana_temporal_min=entidad.ventana_temporal_min,
                id_version_modelo_activa=entidad.id_version_modelo_activa,
                modo_ejecucion=entidad.modo_ejecucion,
                config_version=entidad.config_version,
                w_factor_sanitario=entidad.w_factor_sanitario,
                w_factor_ambiental=entidad.w_factor_ambiental,
                w_factor_densidad=entidad.w_factor_densidad,
                temp_min_config=entidad.temp_min_config,
                temp_max_config=entidad.temp_max_config,
                hr_min_config=entidad.hr_min_config,
                hr_max_config=entidad.hr_max_config,
                densidad_maxima_config=entidad.densidad_maxima_config,
                es_activa=entidad.es_activa,
                id_usuario_responsable=entidad.id_usuario_responsable,
            )
            self._db.add(orm)
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA:
        try:
            orm = self._db.get(ConfiguracionMotorIAModel, entidad.id_configuracion_motor)
            orm.umbral_riesgo_alto = entidad.umbral_riesgo_alto
            orm.umbral_alerta_critica = entidad.umbral_alerta_critica
            orm.ventana_temporal_min = entidad.ventana_temporal_min
            orm.id_version_modelo_activa = entidad.id_version_modelo_activa
            orm.modo_ejecucion = entidad.modo_ejecucion
            orm.config_version = entidad.config_version
            orm.w_factor_sanitario = entidad.w_factor_sanitario
            orm.w_factor_ambiental = entidad.w_factor_ambiental
            orm.w_factor_densidad = entidad.w_factor_densidad
            orm.temp_min_config = entidad.temp_min_config
            orm.temp_max_config = entidad.temp_max_config
            orm.hr_min_config = entidad.hr_min_config
            orm.hr_max_config = entidad.hr_max_config
            orm.densidad_maxima_config = entidad.densidad_maxima_config
            orm.id_usuario_responsable = entidad.id_usuario_responsable
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)
