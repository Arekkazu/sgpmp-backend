"""Router FastAPI para ingesta de telemetría IoT (`/iot/telemetria`).

RF-53 — CU01 Dev scope:
  POST  /iot/telemetria        — Ingesta individual (Flujo A TIEMPO_REAL + Flujo B EDGE_AGREGADO)
  POST  /iot/telemetria/batch  — Ingesta en lote    (Flujo C sincronización BUFFER_LOCAL, max 500)
  POST  /iot/telemetria/vision — Observaciones de visión por área (RF-53/56/62 v2.0, max 500)

Auth: los llama el broker MQTT, no el nodo (D3, AIOT-DEV-03). Exigen su token de servicio
      (`Authorization: Bearer`, `BROKER_SERVICE_TOKEN`); el `serial` del body es la identidad
      del nodo que el broker ya autenticó por MQTT, y `device_id` / `sensor_id` deben pertenecerle.
      El header opcional `X-Gateway-Id` se registra en la bitácora para trazabilidad de gateway LoRaWAN.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from src.shared.broker_auth import require_token_servicio_broker
from src.shared.database import get_db_sistema
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.ingesta.ingerir_observaciones_vision_use_case import (
    IngerirObservacionesVisionUseCase,
)
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import (
    IngerirTelemetriaUseCase,
    SincronizarBufferUseCase,
)
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.dto.ingerir_observaciones_vision_dto import IngerirObservacionesVisionDTO
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaBatchDTO, IngerirTelemetriaDTO
from src.telemetry.infrastructure.repositories.observacion_vision_repository import SqlAlchemyObservacionVisionRepository
from src.telemetry.infrastructure.schema.telemetria_schema import (
    IngestaBatchResponse,
    IngestaVisionResponse,
    ItemBatchResponse,
    ObservacionVisionResponse,
    TelemetriaResponse,
)

from src.telemetry.infrastructure.repositories.bitacora_ingest_repository import SqlAlchemyBitacoraIngestRepository
from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository

router = APIRouter(prefix="/iot/telemetria", tags=["Telemetría IoT - Ingesta"])


def _build_use_case(db: Session) -> IngerirTelemetriaUseCase:
    return IngerirTelemetriaUseCase(
        db=db,
        ingesta_port=SqlAlchemyIngestaTelemetriaRepository(db),
        bitacora_repo=SqlAlchemyBitacoraIngestRepository(db),
        dispositivo_port=DispositivoM09Adapter(db),
    )


@router.post(
    "",
    response_model=TelemetriaResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_token_servicio_broker)],
    summary="Ingerir lectura de sensor IoT (RF-53 Flujo A/B)",
)
def ingerir_telemetria(
    dto: IngerirTelemetriaDTO,
    db: Session = Depends(get_db_sistema),
    x_gateway_id: Optional[str] = Header(default=None, alias="X-Gateway-Id"),
) -> TelemetriaResponse:
    resultado = _build_use_case(db).execute(dto, gateway_id=x_gateway_id)
    return TelemetriaResponse(
        id_telemetria=resultado.id_telemetria,
        estado_calidad=resultado.estado_calidad,
        timestamp_procesamiento=resultado.timestamp_procesamiento,
        latencia_procesamiento_ms=resultado.latencia_procesamiento_ms,
    )


@router.post(
    "/batch",
    response_model=IngestaBatchResponse,
    status_code=200,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_token_servicio_broker)],
    summary="Sincronización de buffer IoT (RF-53 Flujo C — lote hasta 500 lecturas)",
)
def sincronizar_buffer(
    dto: IngerirTelemetriaBatchDTO,
    db: Session = Depends(get_db_sistema),
    x_gateway_id: Optional[str] = Header(default=None, alias="X-Gateway-Id"),
) -> IngestaBatchResponse:
    use_case = SincronizarBufferUseCase(
        ingerir_use_case_factory=lambda: _build_use_case(db),
        db=db,
    )
    resultado = use_case.execute(dto, gateway_id=x_gateway_id)
    return IngestaBatchResponse(
        total=resultado['total'],
        aceptados=resultado['aceptados'],
        rechazados=resultado['rechazados'],
        duplicados=resultado['duplicados'],
        detalle=[
            ItemBatchResponse(
                sensor_id=item.sensor_id,
                timestamp_captura=item.timestamp_captura,
                estado=item.estado,
                id_telemetria=item.id_telemetria,
                error=item.error,
            )
            for item in resultado['detalle']
        ],
    )


@router.post(
    "/vision",
    response_model=IngestaVisionResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_token_servicio_broker)],
    summary="Ingerir observaciones de visión de un área (RF-53/56/62 v2.0 — lote hasta 500)",
)
def ingerir_observaciones_vision(
    dto: IngerirObservacionesVisionDTO,
    db: Session = Depends(get_db_sistema),
) -> IngestaVisionResponse:
    resultado = IngerirObservacionesVisionUseCase(
        db=db,
        repo=SqlAlchemyObservacionVisionRepository(db),
        dispositivo_port=DispositivoM09Adapter(db),
    ).execute(dto)
    return IngestaVisionResponse(
        total=resultado.total,
        aceptadas=len(resultado.observaciones),
        duplicadas=resultado.duplicados,
        observaciones=[
            ObservacionVisionResponse(
                id_observacion_vision=o.id_observacion_vision,
                timestamp_captura=o.fecha_observacion,
                indice_calidad=o.indice_calidad,
                clasificacion_calidad=o.clasificacion_calidad.value,
                apto_para_ia=o.es_apto_para_ia,
            )
            for o in resultado.observaciones
        ],
    )
