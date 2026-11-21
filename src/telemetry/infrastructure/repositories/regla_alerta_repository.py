# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: crear, actualizar y listar reglas de alerta |
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
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

_NOMBRE_DUPLICADO = "Ya existe una regla de alerta con ese nombre."
# La tabla tiene dos UNIQUE sobre nombre.
_CONFLICTOS = {"uq_regla_nombre": _NOMBRE_DUPLICADO, "uq_reglas_alerta_combre": _NOMBRE_DUPLICADO}


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

    def obtener_por_id(self, id_regla_alertas: int, *, bloquear: bool = False) -> Optional[ReglaAlerta]:
        orm = self.db.get(ReglaAlertaModel, id_regla_alertas, with_for_update=bloquear)
        return self._a_entidad(orm) if orm is not None else None

    def listar(
        self,
        *,
        tipo_sensor: Optional[str] = None,
        es_activa: Optional[bool] = None,
        es_regla_compuesta: Optional[bool] = None,
    ) -> list[ReglaAlerta]:
        consulta = self.db.query(ReglaAlertaModel)
        if tipo_sensor is not None:
            consulta = consulta.filter(ReglaAlertaModel.tipo_sensor == tipo_sensor)
        if es_activa is not None:
            consulta = consulta.filter(ReglaAlertaModel.es_activa.is_(es_activa))
        if es_regla_compuesta is not None:
            consulta = consulta.filter(ReglaAlertaModel.es_regla_compuesta.is_(es_regla_compuesta))
        return [self._a_entidad(o) for o in consulta.order_by(ReglaAlertaModel.id_regla_alertas).all()]

    def crear(self, regla: ReglaAlerta) -> ReglaAlerta:
        try:
            # id, fecha_creacion, fecha_actualizacion y version_regla: defaults de la BD.
            orm = ReglaAlertaModel(**self._columnas(regla))
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc, _CONFLICTOS)

    def actualizar(self, regla: ReglaAlerta) -> ReglaAlerta:
        try:
            orm = self.db.get(ReglaAlertaModel, regla.id_regla_alertas)
            for columna, valor in self._columnas(regla).items():
                setattr(orm, columna, valor)
            self.db.flush()
            # El trigger reescribe version_regla y fecha_actualizacion.
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc, _CONFLICTOS)

    @staticmethod
    def _columnas(regla: ReglaAlerta) -> dict:
        return dict(
            nombre=regla.nombre,
            descripcion=regla.descripcion,
            tipo_sensor=regla.tipo_sensor,
            es_regla_compuesta=regla.es_regla_compuesta,
            umbral_min=regla.umbral_min,
            umbral_max=regla.umbral_max,
            categoria_variable=regla.categoria_variable,
            ventana_confirmacion_min=regla.ventana_confirmacion_min,
            lectura_confirmacion_max=regla.lectura_confirmacion_max,
            umbrales_severdiad=regla.umbrales_severidad,
            id_finca=regla.id_finca,
            id_especie=regla.id_especie,
            es_activa=regla.es_activa,
            tiene_ejecutar_edge=regla.tiene_ejecutar_edge,
            id_usuario=regla.id_usuario,
            mensaje=regla.mensaje,
        )

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
