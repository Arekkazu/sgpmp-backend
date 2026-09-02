"""Router FastAPI para layout del dashboard (`/configuracion/personalizacion/dashboard`).

RF-28:
  A) GET   /configuracion/personalizacion/dashboard            — Layout actual (o default del rol).
  B) PATCH /configuracion/personalizacion/dashboard            — Guardar layout personalizado.
  C) POST  /configuracion/personalizacion/dashboard/restaurar  — Restaurar layout predeterminado.
  D) GET   /configuracion/personalizacion/dashboard/widgets    — Catálogo disponible para el rol.
  E) GET   /configuracion/personalizacion/dashboard/datos      — Datos de los widgets visibles.

RBAC: id_recurso=25 (dashboard_layout). El catálogo aplica además el permiso de
lectura del recurso propio de cada widget, así que dos roles distintos ven listas
distintas con el mismo permiso sobre el dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.personalizacion.guardar_dashboard_use_case import GuardarDashboardUseCase
from src.configuration.application.use_cases.personalizacion.obtener_catalogo_widgets_use_case import ObtenerCatalogoWidgetsUseCase
from src.configuration.application.use_cases.personalizacion.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.configuration.application.use_cases.personalizacion.obtener_datos_dashboard_use_case import ObtenerDatosDashboardUseCase
from src.configuration.application.use_cases.personalizacion.restaurar_dashboard_use_case import RestaurarDashboardUseCase
from src.configuration.infrastructure.dto.guardar_dashboard_dto import GuardarDashboardDTO
from src.configuration.infrastructure.repositories.dashboard_layout_repository import SqlAlchemyDashboardLayoutRepository
from src.configuration.infrastructure.repositories.widget_datos_repository import SqlAlchemyWidgetDatosRepository
from src.configuration.infrastructure.repositories.widget_repository import SqlAlchemyWidgetRepository
from src.configuration.infrastructure.schema.dashboard_layout_schema import (
    DashboardLayoutResponse,
    WidgetCatalogoResponse,
    WidgetDatosResponse,
)
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
    repo = SqlAlchemyDashboardLayoutRepository(db)
    entidad = ObtenerDashboardUseCase(dashboard_repo=repo).execute(usuario_actual)
    return DashboardLayoutResponse.from_entity(
        entidad,
        version_perfil=repo.version_perfil(usuario_actual.id_usuario),
    )


@router.get(
    "/widgets",
    response_model=list[WidgetCatalogoResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Catálogo de widgets disponibles para el rol",
)
def obtener_catalogo_widgets(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[WidgetCatalogoResponse]:
    use_case = ObtenerCatalogoWidgetsUseCase(widget_repo=SqlAlchemyWidgetRepository(db))
    return [WidgetCatalogoResponse.model_validate(w) for w in use_case.execute(usuario_actual)]


@router.get(
    "/datos",
    response_model=list[WidgetDatosResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Datos de los widgets visibles del dashboard",
)
def obtener_datos_dashboard(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[WidgetDatosResponse]:
    use_case = ObtenerDatosDashboardUseCase(
        dashboard_repo=SqlAlchemyDashboardLayoutRepository(db),
        widget_repo=SqlAlchemyWidgetRepository(db),
        datos_repo=SqlAlchemyWidgetDatosRepository(db),
    )
    return [WidgetDatosResponse.model_validate(w) for w in use_case.execute(usuario_actual)]


@router.patch(
    "",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Guardar configuración del dashboard (Flujo B)",
)
def guardar_dashboard(
    dto: GuardarDashboardDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardLayoutResponse:
    repo = SqlAlchemyDashboardLayoutRepository(db)
    use_case = GuardarDashboardUseCase(
        db=db,
        dashboard_repo=repo,
        widget_repo=SqlAlchemyWidgetRepository(db),
    )
    entidad = use_case.execute(dto, usuario_actual)
    return DashboardLayoutResponse.from_entity(
        entidad,
        version_perfil=repo.version_perfil(usuario_actual.id_usuario),
    )


@router.post(
    "/restaurar",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Restaurar layout predeterminado del rol (Flujo C)",
)
def restaurar_dashboard(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardLayoutResponse:
    repo = SqlAlchemyDashboardLayoutRepository(db)
    entidad = RestaurarDashboardUseCase(db=db, dashboard_repo=repo).execute(usuario_actual)
    return DashboardLayoutResponse.from_entity(
        entidad,
        version_perfil=repo.version_perfil(usuario_actual.id_usuario),
    )
