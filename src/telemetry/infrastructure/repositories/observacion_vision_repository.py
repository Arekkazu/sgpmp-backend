"""Implementación SQLAlchemy de ``ObservacionVisionRepository`` (RF-53/RF-62 v2.0)."""
from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.observacion_vision import EstadoCalibracionCamara, ObservacionVision
from src.telemetry.domain.entities.telemetria_calidad import ClasificacionCalidad
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
            indice_calidad=orm.indice_calidad,
            clasificacion_calidad=ClasificacionCalidad(orm.clasificacion_calidad),
            es_apto_para_ia=orm.es_apto_para_ia,
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

    def guardar(self, observacion: ObservacionVision) -> ObservacionVision:
        try:
            orm = ObservacionVisionModel(
                id_dispositivo_iot=observacion.id_dispositivo_iot,
                id_infraestructura=observacion.id_infraestructura,
                fecha_observacion=observacion.fecha_observacion,
                cobertura_ventana=observacion.cobertura_ventana,
                cantidad_tracks=observacion.cantidad_tracks,
                cantidad_tracks_perdidos=observacion.cantidad_tracks_perdidos,
                fps_efectivo=observacion.fps_efectivo,
                estado_calibracion=observacion.estado_calibracion.value,
                json_vector=observacion.vector,
                indice_calidad=observacion.indice_calidad,
                clasificacion_calidad=observacion.clasificacion_calidad.value,
                es_apto_para_ia=observacion.es_apto_para_ia,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)
