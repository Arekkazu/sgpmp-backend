"""Router FastAPI para configuración del motor de inferencia IA (`/prediccion/motor-ia`).

RF-65 CU-02: Configurar parámetros del motor de inferencia por especie.
  POST  /prediccion/motor-ia              — Crear o actualizar configuración (append-only vía auditoría)
  GET   /prediccion/motor-ia              — Listar todas las configuraciones activas
  GET   /prediccion/motor-ia/{tipo_modelo}— Obtener configuración por tipo de modelo

Autorización RBAC:
  recurso configuracion_motor_ia = id_recurso 41
  C=1 (Administrador, Veterinario), R=2 (Administrador, Veterinario, Ingeniero)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import ConfigurarMotorUseCase
from src.prediction.application.use_cases.motor_ia.consultar_motor_use_case import ConsultarMotorUseCase
from src.prediction.infrastructure.adapters.nodo_edge_stub_adapter import NodoEdgeStubAdapter
from src.prediction.infrastructure.adapters.version_modelo_adapter import VersionModeloAdapter
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.prediction.infrastructure.repositories.configuracion_motor_ia_repository import SqlAlchemyConfiguracionMotorIARepository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.schema.configuracion_motor_ia_schema import (
    ConfiguracionMotorIAListResponse,
    ConfiguracionMotorIAResponse,
)
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/motor-ia", tags=["Predicción M04 - Motor de Inferencia IA"])

_RECURSO = 41  # modulo1.recursos: 'configuracion_motor_ia'


@router.post(
    "",
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        200: {"model": ConfiguracionMotorIAResponse, "description": "Configuración actualizada"},
        201: {"model": ConfiguracionMotorIAResponse, "description": "Configuración creada"},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Configurar motor de inferencia IA por tipo de modelo (RF-65)",
)
def configurar_motor(
    dto: ConfigurarMotorDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> JSONResponse:
    use_case = ConfigurarMotorUseCase(
        db=db,
        repo=SqlAlchemyConfiguracionMotorIARepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        version_port=VersionModeloAdapter(db),
        nodo_edge_port=NodoEdgeStubAdapter(),
    )
    entidad, es_nueva = use_case.execute(dto, usuario_actual.id_usuario)
    status_code = 201 if es_nueva else 200
    return JSONResponse(
        content=ConfiguracionMotorIAResponse.from_entity(entidad).model_dump(mode="json"),
        status_code=status_code,
    )


@router.get(
    "",
    response_model=ConfiguracionMotorIAListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar configuraciones del motor de inferencia IA (RF-65)",
)
def listar_configuraciones(
    db: Session = Depends(get_db),
) -> ConfiguracionMotorIAListResponse:
    use_case = ConsultarMotorUseCase(repo=SqlAlchemyConfiguracionMotorIARepository(db))
    items = use_case.listar()
    return ConfiguracionMotorIAListResponse(
        total=len(items),
        items=[ConfiguracionMotorIAResponse.from_entity(e) for e in items],
    )


@router.get(
    "/{tipo_modelo}",
    response_model=ConfiguracionMotorIAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener configuración del motor por tipo de modelo (RF-65)",
)
def obtener_configuracion(
    tipo_modelo: str,
    db: Session = Depends(get_db),
) -> ConfiguracionMotorIAResponse:
    use_case = ConsultarMotorUseCase(repo=SqlAlchemyConfiguracionMotorIARepository(db))
    entidad = use_case.obtener_por_tipo(tipo_modelo)
    return ConfiguracionMotorIAResponse.from_entity(entidad)
