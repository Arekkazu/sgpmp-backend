# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-45 RF-56: E7 token inválido en bitácora, 429 por dispositivo (E6) y bitácora de rechazos |
# | 2026-10-21 | Leandro | DEV-49 RF-57: inyecta bitacora para indisponibilidad IA  |
# | 2026-10-27 | destroyerban | INC-M03-120-G63 RF-56: usa el cliente HTTPS hacia M04 cuando está configurado |
"""Router FastAPI para recepción de eventos Edge IoT (`/iot/eventos-edge`).

RF-56 — CU02 Dev scope:
  POST  /iot/eventos-edge  — Recibe evento clasificado por RF-55 (AIOT) y consolida
                             el paquete multivariable hacia M04.

Auth: igual que CU01 — token de servicio del broker (`Authorization: Bearer`); el `serial`
      del body es la identidad del nodo. El header opcional `X-Gateway-Id` se registra para trazabilidad.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from src.shared.broker_auth import require_token_servicio_broker
from src.shared.database import get_db_sistema, sesion_sistema
from src.shared.errors import AuthenticationError
from src.telemetry.application.use_cases.inferencia.registrar_rechazo_evento_edge import registrar_intento_no_autorizado
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.inferencia.recibir_evento_edge_use_case import RecibirEventoEdgeUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.adapters.motor_inferencia_http_adapter import motor_inferencia_http_desde_entorno
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.repositories.evento_edge_repository import SqlAlchemyEventoEdgeRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.schema.evento_edge_schema import EventoEdgeResponse

router = APIRouter(prefix="/iot/eventos-edge", tags=["Telemetría IoT - Eventos Edge"])


def _token_broker_auditado(request: Request, authorization: Optional[str] = Header(default=None)) -> None:
    """RF-56 E7: el token inválido del broker también deja su intento en la bitácora."""
    try:
        require_token_servicio_broker(authorization)
    except AuthenticationError as exc:
        db = sesion_sistema()
        try:
            registrar_intento_no_autorizado(db, SqlAlchemyBitacoraAuditoriaIotRepository(db), codigo=exc.code,
                                            direccion_ip=request.client.host if request.client else None)
        finally:
            db.close()
        raise


@router.post(
    "",
    response_model=EventoEdgeResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(_token_broker_auditado)],
    summary="Recibir evento Edge clasificado por RF-55 y consolidar paquete a M04 (RF-56)",
)
def recibir_evento_edge(
    dto: RecibirEventoEdgeDTO,
    db: Session = Depends(get_db_sistema),
    x_gateway_id: Optional[str] = Header(default=None, alias="X-Gateway-Id"),
) -> EventoEdgeResponse:
    use_case = RecibirEventoEdgeUseCase(
        db=db,
        evento_edge_repo=SqlAlchemyEventoEdgeRepository(db),
        paquete_repo=SqlAlchemyPaqueteInferenciaRepository(db),
        dispositivo_port=DispositivoM09Adapter(db),
        # G63: cliente HTTPS (TLS >= 1.3) si IOT_INFERENCIA_M04_URL está configurada; si no, el stub.
        motor_inferencia_port=motor_inferencia_http_desde_entorno() or MotorInferenciaStubAdapter(),
        parametros_alertas_port=ParametrosAlertasMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db)),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    resultado = use_case.execute(dto, gateway_id=x_gateway_id)
    return EventoEdgeResponse.model_validate(resultado.__dict__)
