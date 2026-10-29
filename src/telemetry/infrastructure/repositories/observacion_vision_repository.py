# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: ingesta sin evaluar y evaluación de calidad aparte |
"""Implementación SQLAlchemy de ``ObservacionVisionRepository`` (RF-53/RF-62 v2.0)."""
from __future__ import annotations

import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.observacion_vision import EstadoCalibracionCamara, ObservacionVision
from src.telemetry.domain.entities.calidad_vision import ClaseCalidadVision
from src.telemetry.domain.repositories.observacion_vision_repository import ObservacionVisionRepository
from src.telemetry.infrastructure.models.observacion_vision_model import ObservacionVisionModel


class SqlAlchemyObservacionVisionRepository(ObservacionVisionRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ObservacionVisionModel) -> ObservacionVision:
        return ObservacionVision(
            id_observacion_vision=orm.id_observacion_vision,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            id_infraestructura=orm.id_infraestructura,
            fecha_observacion=orm.fecha_observacion,
            cobertura_ventana=orm.cobertura_ventana,
            cantidad_tracks=orm.cantidad_tracks,
            cantidad_tracks_perdidos=orm.cantidad_tracks_perdidos,
            fps_efectivo=orm.fps_efectivo,
            estado_calibracion=EstadoCalibracionCamara(orm.estado_calibracion),
            vector=orm.json_vector,
            fecha_inicio_ventana=orm.fecha_inicio_ventana,
            version_cascada=orm.version_cascada,
            n_individuos_observados=orm.n_individuos_observados,
            origen=orm.origen,
            indice_calidad_vision=orm.indice_calidad_vision,
            clasificacion_calidad=(
                ClaseCalidadVision(orm.clasificacion_calidad) if orm.clasificacion_calidad else None
            ),
            es_apto_para_ia=orm.es_apto_para_ia,
            es_confianza_baja=orm.es_confianza_baja,
            flags_detectados=orm.json_flags_detectados,
            fecha_evaluacion_calidad=orm.fecha_evaluacion_calidad,
        )

    def fechas_existentes(
        self, id_dispositivo_iot: int, fechas: list[datetime.datetime]
    ) -> set[datetime.datetime]:
        filas = (
            self.db.query(ObservacionVisionModel.fecha_observacion)
            .filter(
                ObservacionVisionModel.id_dispositivo_iot == id_dispositivo_iot,
                ObservacionVisionModel.fecha_observacion.in_(fechas),
            )
            .all()
        )
        return {f for (f,) in filas}

    def guardar(self, observacion: ObservacionVision) -> ObservacionVision | None:
        try:
            sentencia = insert(ObservacionVisionModel).values(
                id_dispositivo_iot=observacion.id_dispositivo_iot,
                id_infraestructura=observacion.id_infraestructura,
                fecha_observacion=observacion.fecha_observacion,
                cobertura_ventana=observacion.cobertura_ventana,
                cantidad_tracks=observacion.cantidad_tracks,
                cantidad_tracks_perdidos=observacion.cantidad_tracks_perdidos,
                fps_efectivo=observacion.fps_efectivo,
                estado_calibracion=observacion.estado_calibracion.value,
                json_vector=observacion.vector,
                fecha_inicio_ventana=observacion.fecha_inicio_ventana,
                version_cascada=observacion.version_cascada,
                n_individuos_observados=observacion.n_individuos_observados,
                # Sin origen en el sobre (contrato legado) aplica el DEFAULT 'TIEMPO_REAL'.
                **({'origen': observacion.origen} if observacion.origen else {}),
            )
            sentencia = sentencia.on_conflict_do_nothing(
                constraint='uq_observacion_vision_id_dispositivo_iot_fecha_observacion'
            ).returning(ObservacionVisionModel)
            orm = self.db.scalars(sentencia).first()
            return self._a_entidad(orm) if orm else None
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener(self, id_observacion_vision: int) -> ObservacionVision | None:
        orm = self.db.get(ObservacionVisionModel, id_observacion_vision, with_for_update=True)
        return self._a_entidad(orm) if orm else None

    def guardar_evaluacion(self, observacion: ObservacionVision) -> None:
        try:
            self.db.execute(
                update(ObservacionVisionModel)
                .where(ObservacionVisionModel.id_observacion_vision == observacion.id_observacion_vision)
                .values(
                    indice_calidad_vision=observacion.indice_calidad_vision,
                    clasificacion_calidad=observacion.clasificacion_calidad.value,
                    es_apto_para_ia=observacion.es_apto_para_ia,
                    es_confianza_baja=observacion.es_confianza_baja,
                    json_flags_detectados=observacion.flags_detectados,
                    fecha_evaluacion_calidad=observacion.fecha_evaluacion_calidad,
                )
            )
        except Exception as exc:
            raise_from_db_error(exc)
