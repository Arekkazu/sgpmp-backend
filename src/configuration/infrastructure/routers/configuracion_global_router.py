"""Router FastAPI para parámetros operativos del sistema (`/configuracion/parametros`).

RF-18 — CU04:
  A) POST  /configuracion/parametros         — Crear (Admin; 409 si ya existe activo)
  B) GET   /configuracion/parametros         — Consultar configuración activa (Admin)
  C) PATCH /configuracion/parametros/{id}   — Actualizar (Admin; 412 concurrencia)

RBAC: id_recurso=21 (configuraciones_globales). Solo Administrador.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion.actualizar_configuracion_use_case import ActualizarConfiguracionUseCase
from src.configuration.application.use_cases.configuracion.consultar_configuracion_use_case import ConsultarConfiguracionUseCase
from src.configuration.application.use_cases.configuracion.crear_configuracion_use_case import CrearConfiguracionUseCase
from src.configuration.infrastructure.adapters.iot_stub_adapter import IotStubAdapter
from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO
from src.configuration.infrastructure.dto.crear_configuracion_dto import CrearConfiguracionDTO
from src.configuration.infrastructure.repositories.auditoria_config_repository import SqlAlchemyAuditoriaConfigRepository
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.configuration.infrastructure.schema.configuracion_global_schema import ConfiguracionGlobalResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/parametros", tags=["Configuración - Parámetros Operativos"])

_RECURSO = 21  # modulo1.recursos: 'configuraciones_globales'


@router.post(
    "",
    response_model=ConfiguracionGlobalResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Crear configuración operativa (Flujo A)",
)
def crear_configuracion(
    dto: CrearConfiguracionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConfiguracionGlobalResponse:
    use_case = CrearConfiguracionUseCase(
        db=db,
        config_repo=SqlAlchemyConfiguracionGlobalRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaConfigRepository(db),
        iot_port=IotStubAdapter(),
    )
    config = use_case.execute(dto, usuario_actual)
    return ConfiguracionGlobalResponse.from_entity(config)


@router.get(
    "",
    response_model=Optional[ConfiguracionGlobalResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar configuración operativa activa (Flujo B)",
)
def consultar_configuracion(
    db: Session = Depends(get_db),
) -> Optional[ConfiguracionGlobalResponse]:
    use_case = ConsultarConfiguracionUseCase(
        config_repo=SqlAlchemyConfiguracionGlobalRepository(db),
    )
    config = use_case.execute()
    if config is None:
        return None
    return ConfiguracionGlobalResponse.from_entity(config)


@router.patch(
    "/{id_configuracion_global}",
    response_model=ConfiguracionGlobalResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
    },
    summary="Actualizar configuración operativa (Flujo C)",
)
def actualizar_configuracion(
    id_configuracion_global: int,
    dto: ActualizarConfiguracionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConfiguracionGlobalResponse:
    use_case = ActualizarConfiguracionUseCase(
        db=db,
        config_repo=SqlAlchemyConfiguracionGlobalRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaConfigRepository(db),
        iot_port=IotStubAdapter(),
    )
    config = use_case.execute(id_configuracion_global, dto, usuario_actual)
    return ConfiguracionGlobalResponse.from_entity(config)
