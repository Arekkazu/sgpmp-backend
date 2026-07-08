from __future__ import annotations

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.infrastructure.models.regla_alerta_model import ReglaAlertaModel

# Mapa tipo_variable → tipo_sensor (enum de la tabla reglas_alertas)
_VARIABLE_A_TIPO_SENSOR: dict[str, str] = {
    "TEMPERATURA_AMBIENTAL": "TEMPERATURA",
    "TEMPERATURA_CORPORAL": "TEMPERATURA",
    "TEMP_CORPORAL": "TEMPERATURA",
    "HUMEDAD_RELATIVA": "HUMEDAD",
    "OXIGENO_DISUELTO": "OXIGENO",
    "PH_AGUA": "PH",
    "NH3": "AMONIACO",
    "CO2": "AMONIACO",
    "TDS": "SALINIDAD",
    "CONDUCTIVIDAD_ELECTRICA": "SALINIDAD",
    "ACTIVIDAD_MOVIMIENTO": "LUMINOSIDAD",
    "ACTIVIDAD": "LUMINOSIDAD",
    "FRECUENCIA_CARDIACA": "TEMPERATURA",
    "FRECUENCIA_RESPIRATORIA": "AMONIACO",
}


class SqlAlchemyReglaAlertaRepository(ReglaAlertaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_reglas_activas_por_variable(self, tipo_variable: str) -> list[ReglaAlerta]:
        tipo_sensor = _VARIABLE_A_TIPO_SENSOR.get(tipo_variable.upper())
        if tipo_sensor is None:
            return []
        orms = (
            self.db.query(ReglaAlertaModel)
            .filter(
                ReglaAlertaModel.tipo_sensor == tipo_sensor,
                ReglaAlertaModel.es_activa.is_(True),
                ReglaAlertaModel.es_regla_compuesta.is_(False),
            )
            .all()
        )
        return [self._a_entidad(o) for o in orms]

    def obtener_reglas_compuestas_activas(self) -> list[ReglaAlerta]:
        orms = (
            self.db.query(ReglaAlertaModel)
            .filter(
                ReglaAlertaModel.es_activa.is_(True),
                ReglaAlertaModel.es_regla_compuesta.is_(True),
            )
            .all()
        )
        return [self._a_entidad(o) for o in orms]

    @staticmethod
    def _a_entidad(orm: ReglaAlertaModel) -> ReglaAlerta:
        return ReglaAlerta(
            id_regla_alertas=orm.id_regla_alertas,
            nombre=orm.nombre,
            descripcion=orm.descripcion,
            tipo_sensor=orm.tipo_sensor,
            es_regla_compuesta=orm.es_regla_compuesta,
            umbral_min=orm.umbral_min,
            umbral_max=orm.umbral_max,
            categoria_variable=orm.categoria_variable,
            ventana_confirmacion_min=orm.ventana_confirmacion_min,
            lectura_confirmacion_max=orm.lectura_confirmacion_max,
            umbrales_severidad=dict(orm.umbrales_severdiad) if orm.umbrales_severdiad else None,
            id_finca=orm.id_finca,
            id_especie=orm.id_especie,
            es_activa=orm.es_activa,
            tiene_ejecutar_edge=orm.tiene_ejecutar_edge,
            id_usuario=orm.id_usuario,
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
            version_regla=orm.version_regla,
            mensaje=orm.mensaje,
        )
