"""Router FastAPI para propagar reglas compuestas al Gateway Edge (DEV-08, RF-55/RF-57).

  POST /iot/reglas-alertas/{id}/sincronizar-edge   — Enviar la regla a sus Gateway Edge
  GET  /iot/reglas-alertas/{id}/sincronizacion-edge — Estado vigente por Gateway Edge

Auth: JWT Bearer + RBAC recurso 65 (sincronizacion_reglas_edge): E para
propagar, R para consultar. Administrador e Ingeniero de Campo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.reglas.consultar_sincronizacion_regla_edge_use_case import (
    ConsultarSincronizacionReglaEdgeUseCase,
)
from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import SincronizarReglaEdgeUseCase
from src.telemetry.infrastructure.adapters.regla_compuesta_edge_mqtt_adapter import ReglaCompuestaEdgeMqttAdapter
from src.telemetry.infrastructure.repositories.regla_alerta_repository import SqlAlchemyReglaAlertaRepository
from src.telemetry.infrastructure.repositories.sincronizacion_regla_edge_repository import (
    SqlAlchemySincronizacionReglaEdgeRepository,
)
from src.telemetry.infrastructure.schema.sincronizacion_regla_edge_schema import SincronizacionReglaSchema

router = APIRouter(prefix="/iot/reglas-alertas", tags=["Telemetría IoT - Reglas en el Edge"])

ID_RECURSO_SINCRONIZACION_REGLAS_EDGE = 65


@router.post(
    "/{id_regla_alertas}/sincronizar-edge",
    response_model=SincronizacionReglaSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(ID_RECURSO_SINCRONIZACION_REGLAS_EDGE, 5))],
    summary="Propagar una regla compuesta a los Gateway Edge (RF-55/RF-57)",
)
def sincronizar_regla_edge(
    id_regla_alertas: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> SincronizacionReglaSchema:
    use_case = SincronizarReglaEdgeUseCase(
        db=db,
        regla_repo=SqlAlchemyReglaAlertaRepository(db),
        sincronizacion_repo=SqlAlchemySincronizacionReglaEdgeRepository(db),
        edge_port=ReglaCompuestaEdgeMqttAdapter(),
    )
    resultado = use_case.execute(id_regla_alertas, id_usuario=usuario_actual.id_usuario)
    return SincronizacionReglaSchema.model_validate(resultado)


@router.get(
    "/{id_regla_alertas}/sincronizacion-edge",
    response_model=SincronizacionReglaSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(ID_RECURSO_SINCRONIZACION_REGLAS_EDGE, 2))],
    summary="Estado de una regla compuesta en cada Gateway Edge (RF-55/RF-57)",
)
def consultar_sincronizacion_regla_edge(
    id_regla_alertas: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> SincronizacionReglaSchema:
    use_case = ConsultarSincronizacionReglaEdgeUseCase(
        regla_repo=SqlAlchemyReglaAlertaRepository(db),
        sincronizacion_repo=SqlAlchemySincronizacionReglaEdgeRepository(db),
    )
    return SincronizacionReglaSchema.model_validate(use_case.execute(id_regla_alertas))
