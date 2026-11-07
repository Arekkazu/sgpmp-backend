# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: exponer el perfil histórico real de cada versión RF-65. |
from __future__ import annotations

from sqlalchemy.orm import Session

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.entities.historial_configuracion_motor import VersionConfiguracionMotor
from src.prediction.domain.repositories.historial_configuracion_motor_repository import (
    HistorialConfiguracionMotorRepository,
)
from src.prediction.infrastructure.models.configuracion_ia_log_model import ConfiguracionIaLogModel


class SqlAlchemyHistorialConfiguracionMotorRepository(HistorialConfiguracionMotorRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def listar_por_tipo(self, tipo_modelo: str) -> list[VersionConfiguracionMotor]:
        orms = (
            self._db.query(ConfiguracionIaLogModel)
            .filter(ConfiguracionIaLogModel.tipo_modelo == tipo_modelo)
            .order_by(ConfiguracionIaLogModel.config_version.desc(), ConfiguracionIaLogModel.id_log.desc())
            .all()
        )
        return [self._a_version(orm) for orm in orms]

    @staticmethod
    def _a_version(orm: ConfiguracionIaLogModel) -> VersionConfiguracionMotor:
        # La configuración usa el mismo formato que _snapshot() de la entidad,
        # así la versión vigente y las anteriores se comparan campo a campo.
        configuracion = ConfiguracionMotorIA(
            tipo_modelo=orm.tipo_modelo,
            umbral_riesgo_alto=orm.umbral_riesgo_alto,
            umbral_alerta_critica=orm.umbral_alerta_critica,
            ventana_temporal_min=orm.ventana_temporal_min,
            modo_ejecucion=orm.modo_ejecucion,
            perfil_calculo_contagio=orm.perfil_calculo_contagio,
            w_factor_sanitario=orm.w_factor_sanitario,
            w_factor_ambiental=orm.w_factor_ambiental,
            w_factor_densidad=orm.w_factor_densidad,
            id_usuario_responsable=orm.id_usuario_responsable,
            config_version=orm.config_version,
            es_activa=orm.es_activa,
            id_configuracion_motor=orm.id_configuracion_motor,
            id_version_modelo_activa=orm.id_version_modelo_activa,
            temp_min_config=orm.temp_min_config,
            temp_max_config=orm.temp_max_config,
            hr_min_config=orm.hr_min_config,
            hr_max_config=orm.hr_max_config,
            densidad_maxima_config=orm.densidad_maxima_config,
            fecha_creacion=orm.fecha_creacion_config,
            umbral_score_anomalia=orm.umbral_score_anomalia,
            versiones_activas_por_componente=orm.versiones_activas_por_componente,
        )
        return VersionConfiguracionMotor(
            config_version=orm.config_version,
            vigente=False,
            id_usuario_responsable=orm.id_usuario_responsable,
            configuracion=configuracion._snapshot(),
            fecha_creacion_config=orm.fecha_creacion_config,
            operacion=orm.operacion,
            vigente_hasta=orm.fecha_cambio,
            id_usuario_cambio=orm.id_usuario_cambio,
        )
