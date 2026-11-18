# | Fecha      | Nombre   | Que se hizo                                         |
# |------------|----------|-----------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: datos y opciones de cada widget          |
"""Router FastAPI del dashboard por widgets (`/dashboard`, RF-103).

  GET /dashboard/widgets/{clave}?id_finca=           — Datos de un widget con las opciones guardadas.
  GET /dashboard/widgets/{clave}/opciones?id_finca=  — Valores elegibles de sus opciones.

RBAC: lectura de ``dashboard_layout`` (25) y, en el caso de uso, lectura del recurso del widget.
El layout, el catálogo y el guardado de opciones siguen en `/configuracion/personalizacion/dashboard`.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from src.configuration.infrastructure.repositories.dashboard_layout_repository import SqlAlchemyDashboardLayoutRepository
from src.configuration.infrastructure.repositories.widget_repository import SqlAlchemyWidgetRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.reporting.application.use_cases.dashboard.obtener_datos_widget_use_case import ObtenerDatosWidgetUseCase
from src.reporting.application.use_cases.dashboard.obtener_opciones_widget_use_case import ObtenerOpcionesWidgetUseCase
from src.reporting.infrastructure.repositories.datos_widget_repository import SqlAlchemyDatosWidgetRepository
from src.reporting.infrastructure.schema.dashboard_schema import DatosWidgetResponse, ValorOpcionResponse
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard por widgets (RF-103)"])

_RECURSO = 25  # modulo1.recursos: 'dashboard_layout'
_CLAVE = Path(pattern=r"^[a-z0-9_]{1,40}$", description="Clave del widget en el catálogo")
_FINCA = Query(default=None, gt=0, description="Finca activa; los widgets contables la aceptan opcional")
_ERRORES: dict[int | str, dict[str, Any]] = {400: {"model": ErrorResponse}, 401: {"model": ErrorResponse},
            403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


def _datos_widget(db: Session) -> ObtenerDatosWidgetUseCase:
    return ObtenerDatosWidgetUseCase(
        widget_repo=SqlAlchemyWidgetRepository(db),
        dashboard_repo=SqlAlchemyDashboardLayoutRepository(db),
        datos_repo=SqlAlchemyDatosWidgetRepository(db),
        alcance=AlcanceFincaAdapter(db),
    )


@router.get(
    "/widgets/{clave}",
    response_model=DatosWidgetResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses=_ERRORES,
    summary="Datos de un widget para la finca activa (RF-103)",
)
def obtener_datos_widget(
    clave: str = _CLAVE,
    id_finca: Optional[int] = _FINCA,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DatosWidgetResponse:
    """Datos de un widget con las opciones que el usuario guardó en su dashboard.

    **Acceso:** `dashboard_layout` · Leer, y leer el recurso del widget (403 si no).

    Finca ajena → 403. Sin finca en un widget que la necesita → 400. Si la consulta falla, responde
    200 con `estado=ERROR` para que el resto del dashboard siga cargando.
    """
    resultado = _datos_widget(db).execute(clave, id_finca, usuario_actual)
    return DatosWidgetResponse.model_validate(resultado)


@router.get(
    "/widgets/{clave}/opciones",
    response_model=dict[str, list[ValorOpcionResponse]],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses=_ERRORES,
    summary="Valores elegibles de las opciones de un widget (RF-103)",
)
def obtener_opciones_widget(
    clave: str = _CLAVE,
    id_finca: Optional[int] = _FINCA,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> dict[str, list[ValorOpcionResponse]]:
    """Áreas, especies y sensores de la finca activa, y los valores de las opciones de lista.

    **Acceso:** `dashboard_layout` · Leer, y leer el recurso del widget.
    """
    opciones = ObtenerOpcionesWidgetUseCase(_datos_widget(db)).execute(clave, id_finca, usuario_actual)
    return {nombre: [ValorOpcionResponse(**v) for v in valores] for nombre, valores in opciones.items()}
