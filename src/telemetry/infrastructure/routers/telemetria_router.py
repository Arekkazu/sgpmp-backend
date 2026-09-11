"""Router FastAPI para ingesta de telemetría IoT (`/iot/telemetria`).

RF-53 — CU01 Dev scope:
  POST  /iot/telemetria        — Ingesta individual (Flujo A TIEMPO_REAL + Flujo B EDGE_AGREGADO)
  POST  /iot/telemetria/batch  — Ingesta en lote    (Flujo C sincronización BUFFER_LOCAL, max 500)

Auth: los dispositivos IoT no usan JWT Bearer. La identidad se verifica dentro del use case
      mediante `access_key` (serial del dispositivo en M09) y `device_id` / `sensor_id` en el body.
      El header opcional `X-Gateway-Id` se registra en la bitácora para trazabilidad de gateway LoRaWAN.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import (
    IngerirTelemetriaUseCase,
    SincronizarBufferUseCase,
)
from src.telemetry.infrastructure.adapters.calibracion_m09_adapter import CalibracionM09Adapter
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.adapters.variable_catalogo_m09_adapter import VariableCatalogoM09Adapter
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaBatchDTO, IngerirTelemetriaDTO
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import VincularLecturaActivoUseCase
from src.telemetry.infrastructure.adapters.activo_biologico_stub_adapter import ActivoBiologicoStubAdapter
from src.telemetry.infrastructure.adapters.parametros_calidad_stub_adapter import ParametrosCalidadStubAdapter
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.bitacora_ingest_repository import SqlAlchemyBitacoraIngestRepository
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import SqlAlchemyVinculacionLecturaRepository
from src.telemetry.infrastructure.schema.telemetria_schema import IngestaBatchResponse, ItemBatchResponse, TelemetriaResponse

router = APIRouter(prefix="/iot/telemetria", tags=["Telemetría IoT - Ingesta"])


def _build_use_case(db: Session) -> IngerirTelemetriaUseCase:
    telemetria_repo = SqlAlchemyTelemetriaRepository(db)
    return IngerirTelemetriaUseCase(
        db=db,
        repo=telemetria_repo,
        bitacora_repo=SqlAlchemyBitacoraIngestRepository(db),
        dispositivo_port=DispositivoM09Adapter(db),
        variable_port=VariableCatalogoM09Adapter(db),
        calibracion_port=CalibracionM09Adapter(db),
        vincular_use_case=VincularLecturaActivoUseCase(
            db=db,
            vinculacion_repo=SqlAlchemyVinculacionLecturaRepository(db),
            activo_port=ActivoBiologicoStubAdapter(),
        ),
        evaluar_calidad_use_case=EvaluarCalidadTelemetriaUseCase(
            db=db,
            telemetria_repo=telemetria_repo,
            calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
            parametros_port=ParametrosCalidadStubAdapter(),
            auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
        ),
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
    },
    summary="Ingerir lectura de sensor IoT (RF-53 Flujo A/B)",
)
def ingerir_telemetria(
    dto: IngerirTelemetriaDTO,
    db: Session = Depends(get_db),
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
        422: {"model": ErrorResponse},
    },
    summary="Sincronización de buffer IoT (RF-53 Flujo C — lote hasta 500 lecturas)",
)
def sincronizar_buffer(
    dto: IngerirTelemetriaBatchDTO,
    db: Session = Depends(get_db),
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
