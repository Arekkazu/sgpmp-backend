"""Router FastAPI para contexto adaptativo de interfaz (`/configuracion/interfaz/contexto`).

RF-25:
  A) GET /configuracion/interfaz/contexto — Obtener contexto del usuario autenticado.

RBAC: id_recurso=22 (contexto_interfaz). Todos los roles con permiso R.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.personalizacion.obtener_contexto_use_case import ObtenerContextoUseCase
from src.configuration.infrastructure.repositories.contexto_interfaz_repository import SqlAlchemyContextoInterfazRepository
from src.configuration.infrastructure.repositories.identidad_visual_repository import SqlAlchemyIdentidadVisualRepository
from src.configuration.infrastructure.schema.contexto_interfaz_schema import ContextoInterfazResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/interfaz", tags=["Configuración - Interfaz Adaptativa (RF-25)"])

_RECURSO = 22  # modulo1.recursos: 'contexto_interfaz'


@router.get(
    "/contexto",
    response_model=ContextoInterfazResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Obtener contexto adaptativo de interfaz del usuario (Flujo A)",
)
def obtener_contexto(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ContextoInterfazResponse:
    use_case = ObtenerContextoUseCase(
        contexto_repo=SqlAlchemyContextoInterfazRepository(db),
        identidad_repo=SqlAlchemyIdentidadVisualRepository(db),
    )
    contexto = use_case.execute(usuario_actual)
    return ContextoInterfazResponse.from_entity(contexto)
