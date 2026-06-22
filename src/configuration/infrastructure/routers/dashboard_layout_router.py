"""Router FastAPI para layout del dashboard (`/configuracion/personalizacion/dashboard`).

RF-28:
  A) GET  /configuracion/personalizacion/dashboard          — Layout actual (o default del rol).
  B) PATCH /configuracion/personalizacion/dashboard         — Guardar layout personalizado.
  C) POST  /configuracion/personalizacion/dashboard/restaurar — Restaurar layout predeterminado.

RBAC: id_recurso=25 (dashboard_layout).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.personalizacion.guardar_dashboard_use_case import GuardarDashboardUseCase
from src.configuration.application.use_cases.personalizacion.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.configuration.application.use_cases.personalizacion.restaurar_dashboard_use_case import RestaurarDashboardUseCase
from src.configuration.infrastructure.dto.guardar_dashboard_dto import GuardarDashboardDTO
from src.configuration.infrastructure.repositories.dashboard_layout_repository import SqlAlchemyDashboardLayoutRepository
from src.configuration.infrastructure.schema.dashboard_layout_schema import DashboardLayoutResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/configuracion/personalizacion/dashboard",
    tags=["Configuración - Dashboard Layout (RF-28)"],
)

_RECURSO = 25  # modulo1.recursos: 'dashboard_layout'


@router.get(
    "",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Obtener layout del dashboard (Flujo A)",
)
def obtener_dashboard(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardLayoutResponse:
    use_case = ObtenerDashboardUseCase(dashboard_repo=SqlAlchemyDashboardLayoutRepository(db))
    entidad = use_case.execute(usuario_actual)
    return DashboardLayoutResponse.from_entity(entidad)


@router.patch(
    "",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Guardar configuración del dashboard (Flujo B)",
)
def guardar_dashboard(
    dto: GuardarDashboardDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardLayoutResponse:
    use_case = GuardarDashboardUseCase(db=db, dashboard_repo=SqlAlchemyDashboardLayoutRepository(db))
    entidad = use_case.execute(dto, usuario_actual)
    return DashboardLayoutResponse.from_entity(entidad)


@router.post(
    "/restaurar",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Restaurar layout predeterminado del rol (Flujo C)",
)
def restaurar_dashboard(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardLayoutResponse:
    use_case = RestaurarDashboardUseCase(db=db, dashboard_repo=SqlAlchemyDashboardLayoutRepository(db))
    entidad = use_case.execute(usuario_actual)
    return DashboardLayoutResponse.from_entity(entidad)
