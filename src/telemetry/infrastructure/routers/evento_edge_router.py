"""Router FastAPI para recepción de eventos Edge IoT (`/iot/eventos-edge`).

RF-56 — CU02 Dev scope:
  POST  /iot/eventos-edge  — Recibe evento clasificado por RF-55 (AIOT) y consolida
                             el paquete multivariable hacia M04.

Auth: igual que CU01 — sin JWT Bearer. La identidad se verifica con `access_key`
      en el body. El header opcional `X-Gateway-Id` se registra para trazabilidad.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.inferencia.recibir_evento_edge_use_case import RecibirEventoEdgeUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.repositories.evento_edge_repository import SqlAlchemyEventoEdgeRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.schema.evento_edge_schema import EventoEdgeResponse

router = APIRouter(prefix="/iot/eventos-edge", tags=["Telemetría IoT - Eventos Edge"])


@router.post(
    "",
    response_model=EventoEdgeResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Recibir evento Edge clasificado por RF-55 y consolidar paquete a M04 (RF-56)",
)
def recibir_evento_edge(
    dto: RecibirEventoEdgeDTO,
    db: Session = Depends(get_db),
    x_gateway_id: Optional[str] = Header(default=None, alias="X-Gateway-Id"),
) -> EventoEdgeResponse:
    use_case = RecibirEventoEdgeUseCase(
        db=db,
        evento_edge_repo=SqlAlchemyEventoEdgeRepository(db),
        paquete_repo=SqlAlchemyPaqueteInferenciaRepository(db),
        dispositivo_port=DispositivoM09Adapter(db),
        motor_inferencia_port=MotorInferenciaStubAdapter(),
    )
    resultado = use_case.execute(dto, gateway_id=x_gateway_id)
    return EventoEdgeResponse.model_validate(resultado.__dict__)
