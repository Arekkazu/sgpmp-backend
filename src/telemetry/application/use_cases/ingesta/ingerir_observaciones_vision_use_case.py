"""Caso de uso: ingesta de observaciones de visión por área (RF-53/RF-56/RF-62 v2.0, RFC-011).

La cámara se identifica como en la ingesta escalar (device_id + serial como
access_key, sin JWT). Cada observación recibe su índice de calidad de visión y
``apto_para_ia``; es lo que la calibración VISION de RF-24 consume
(INC-M09-77-G137, #513).

El lote es atómico: una observación inválida rechaza el lote completo. Un
reenvío (misma cámara e instante) no es error: se cuenta como duplicado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError, BusinessRuleError, ValidationError
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import _MAX_DRIFT_FUTURO_SEG
from src.telemetry.domain.entities.observacion_vision import ObservacionVision
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.observacion_vision_repository import ObservacionVisionRepository
from src.telemetry.infrastructure.dto.ingerir_observaciones_vision_dto import IngerirObservacionesVisionDTO


@dataclass
class ResultadoIngestaVision:
    total: int
    duplicados: int
    observaciones: list[ObservacionVision]


def _utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


class IngerirObservacionesVisionUseCase:

    def __init__(
        self,
        db: Session,
        repo: ObservacionVisionRepository,
        dispositivo_port: DispositivoPort,
    ) -> None:
        self.db = db
        self.repo = repo
        self.dispositivo_port = dispositivo_port

    def execute(self, dto: IngerirObservacionesVisionDTO) -> ResultadoIngestaVision:
        camara = self.dispositivo_port.obtener_camara(dto.device_id, dto.access_key)
        if camara is None:
            raise AuthenticationError(
                code='ERROR_AUTENTICACION',
                message='Dispositivo no encontrado o credenciales inválidas.',
            )
        if not camara.es_activo:
            raise AuthenticationError(
                code='ERROR_AUTENTICACION',
                message='El dispositivo no está en estado ACTIVO.',
            )
        if not camara.es_camara:
            raise BusinessRuleError(
                code='DISPOSITIVO_NO_ES_CAMARA',
                message=f'El dispositivo {dto.device_id} no es una cámara de visión (RF-21).',
                field='device_id',
            )
        # RF-22 v1.2: la cámara se asocia al área por su id_infraestructura.
        if camara.id_infraestructura != dto.area_id:
            raise BusinessRuleError(
                code='AREA_NO_COINCIDE',
                message=f'La cámara {dto.device_id} no está asociada al área {dto.area_id} (RF-22).',
                field='area_id',
            )

        limite_futuro = datetime.now(timezone.utc) + timedelta(seconds=_MAX_DRIFT_FUTURO_SEG)
        for i, obs in enumerate(dto.observaciones):
            if _utc(obs.timestamp_captura) > limite_futuro:
                raise ValidationError(
                    code='ERROR_TIEMPO',
                    message='El timestamp_captura es posterior a la hora del servidor.',
                    field=f'observaciones[{i}].timestamp_captura',
                )

        fechas = [_utc(o.timestamp_captura) for o in dto.observaciones]
        vistas = self.repo.fechas_existentes(camara.id_dispositivo_iot, fechas)
        guardadas: list[ObservacionVision] = []
        try:
            for obs, fecha in zip(dto.observaciones, fechas):
                if fecha in vistas:
                    continue
                vistas.add(fecha)
                guardadas.append(self.repo.guardar(ObservacionVision.crear(
                    id_dispositivo_iot=camara.id_dispositivo_iot,
                    id_infraestructura=dto.area_id,
                    fecha_observacion=fecha,
                    cobertura_ventana=obs.cobertura_ventana,
                    cantidad_tracks=obs.n_tracks,
                    cantidad_tracks_perdidos=obs.n_tracks_perdidos,
                    fps_efectivo=obs.fps_efectivo,
                    fps_nominal=camara.fps_nominal,
                    estado_calibracion=obs.estado_calibracion,
                    vector=obs.vector,
                )))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ResultadoIngestaVision(
            total=len(dto.observaciones),
            duplicados=len(dto.observaciones) - len(guardadas),
            observaciones=guardadas,
        )
