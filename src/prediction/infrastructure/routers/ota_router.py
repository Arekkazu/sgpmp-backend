"""Router FastAPI para distribución OTA de modelos Edge (`/prediccion`).

RF-70 CU-06: Consulta del estado OTA y listado de despliegues por dispositivo.
  GET /prediccion/modelos/{id_version}/ota-status
  GET /prediccion/despliegues

Autorización RBAC:
  recurso ota_status = id_recurso 44
  R=2 (Administrador, Ingeniero)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.ota.consultar_ota_status_use_case import ConsultarOtaStatusUseCase
from src.prediction.application.use_cases.ota.listar_despliegues_use_case import ListarDesplieguesUseCase
from src.prediction.infrastructure.adapters.version_modelo_adapter import VersionModeloAdapter
from src.prediction.infrastructure.repositories.despliegue_ota_repository import SqlAlchemyDespliegueOtaRepository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.schema.despliegue_ota_schema import DespliegueOtaListResponse, DespliegueOtaResponse, OtaStatusResponse
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion", tags=["Predicción M04 - OTA"])

_RECURSO = 44


@router.get(
    "/modelos/{id_version}/ota-status",
    response_model=OtaStatusResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Consultar estado OTA de una versión de modelo (RF-70)",
)
def consultar_ota_status(
    id_version: int,
    id_dispositivo: Optional[int] = Query(None, description="Filtrar por ID de dispositivo IoT."),
    estado: Optional[str] = Query(None, description="Filtrar por estado: EXITOSO, FALLIDO, PENDIENTE, SIN_CAMBIOS, EN_PROCESO."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> OtaStatusResponse:
    use_case = ConsultarOtaStatusUseCase(
        db=db,
        repo=SqlAlchemyDespliegueOtaRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        version_port=VersionModeloAdapter(db),
    )
    id_version_resultado, despliegues = use_case.execute(
        id_version=id_version,
        id_dispositivo=id_dispositivo,
        estado=estado,
        id_usuario=usuario_actual.id_usuario,
    )
    return OtaStatusResponse(
        id_version_modelo=id_version_resultado,
        despliegues=[DespliegueOtaResponse.from_entity(d) for d in despliegues],
        total=len(despliegues),
    )


@router.get(
    "/despliegues",
    response_model=DespliegueOtaListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Listar despliegues OTA con filtros opcionales (RF-70)",
)
def listar_despliegues(
    id_version: Optional[int] = Query(None, description="Filtrar por ID de versión de modelo."),
    id_dispositivo: Optional[int] = Query(None, description="Filtrar por ID de dispositivo IoT."),
    estado: Optional[str] = Query(None, description="Filtrar por estado: EXITOSO, FALLIDO, PENDIENTE, SIN_CAMBIOS, EN_PROCESO."),
    limit: int = Query(20, ge=1, le=100, description="Registros por página (máx. 100)."),
    offset: int = Query(0, ge=0, description="Desplazamiento de la página."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DespliegueOtaListResponse:
    use_case = ListarDesplieguesUseCase(
        db=db,
        repo=SqlAlchemyDespliegueOtaRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        version_port=VersionModeloAdapter(db),
    )
    items, total = use_case.execute(
        id_version=id_version,
        id_dispositivo=id_dispositivo,
        estado=estado,
        limit=limit,
        offset=offset,
        id_usuario=usuario_actual.id_usuario,
    )
    return DespliegueOtaListResponse(
        total=total,
        items=[DespliegueOtaResponse.from_entity(d) for d in items],
    )
