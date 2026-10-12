"""Observaciones de visión de M03 para la calibración VISION de RF-24 (RF-53/RF-62 v2.0).

Lee ``modulo3.observaciones_vision`` (POST /iot/telemetria/vision), donde M03 ya
dejó el índice de calidad y ``apto_para_ia`` de cada observación.
"""
from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from src.configuration.domain.entities.observacion_vision import ObservacionVision
from src.configuration.domain.repositories.observacion_vision_port import ObservacionVisionPort
from src.telemetry.infrastructure.models.observacion_vision_model import ObservacionVisionModel


class ObservacionVisionM03Adapter(ObservacionVisionPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar(
        self,
        ids_dispositivos: list[int],
        inicio: datetime.datetime,
        fin: datetime.datetime,
    ) -> list[ObservacionVision]:
        filas = (
            self.db.query(ObservacionVisionModel)
            .filter(
                ObservacionVisionModel.id_dispositivo_iot.in_(ids_dispositivos),
                ObservacionVisionModel.fecha_observacion.between(inicio, fin),
            )
            .order_by(ObservacionVisionModel.fecha_observacion)
            .all()
        )
        return [
            ObservacionVision(
                id_dispositivo_iot=f.id_dispositivo_iot,
                fecha_observacion=f.fecha_observacion,
                es_apto_para_ia=f.es_apto_para_ia,
                cobertura_ventana=float(f.cobertura_ventana),
                n_tracks=f.cantidad_tracks,
                componentes=f.json_vector,
            )
            for f in filas
        ]
