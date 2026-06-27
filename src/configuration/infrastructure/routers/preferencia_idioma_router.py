"""Router FastAPI para preferencia de idioma (`/configuracion/personalizacion/idioma`).

RF-29:
  A) GET   /configuracion/personalizacion/idioma         — Idioma resuelto del usuario.
  B) PATCH /configuracion/personalizacion/idioma         — Guardar preferencia personal.
  C) GET   /configuracion/personalizacion/idioma/global  — Idioma global (Admin).
  D) PATCH /configuracion/personalizacion/idioma/global  — Actualizar idioma global (Admin).

RBAC: id_recurso=26 (preferencia_idioma), id_recurso=27 (configuracion_ui_global).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.personalizacion.guardar_idioma_global_use_case import GuardarIdiomaGlobalUseCase
from src.configuration.application.use_cases.personalizacion.guardar_idioma_personal_use_case import GuardarIdiomaPersonalUseCase
from src.configuration.application.use_cases.personalizacion.obtener_idioma_resuelto_use_case import ObtenerIdiomaResueltoUseCase
from src.configuration.infrastructure.dto.guardar_idioma_dto import GuardarIdiomaDTO
from src.configuration.infrastructure.repositories.preferencia_idioma_repository import SqlAlchemyPreferenciaIdiomaRepository
from src.configuration.infrastructure.schema.preferencia_idioma_schema import IdiomaResueltoResponse, PreferenciaIdiomaResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/configuracion/personalizacion/idioma",
    tags=["Configuración - Preferencia de Idioma (RF-29)"],
)

_RECURSO_IDIOMA = 26      # modulo1.recursos: 'preferencia_idioma'
_RECURSO_GLOBAL = 27      # modulo1.recursos: 'configuracion_ui_global'


@router.get(
    "",
    response_model=IdiomaResueltoResponse,
    dependencies=[Depends(require_permission(_RECURSO_IDIOMA, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Obtener idioma resuelto del usuario (Flujo A)",
)
def obtener_idioma(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> IdiomaResueltoResponse:
    use_case = ObtenerIdiomaResueltoUseCase(idioma_repo=SqlAlchemyPreferenciaIdiomaRepository(db))
    resultado = use_case.execute(usuario_actual)
    return IdiomaResueltoResponse(**resultado)


@router.patch(
    "",
    response_model=PreferenciaIdiomaResponse,
    dependencies=[Depends(require_permission(_RECURSO_IDIOMA, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Guardar preferencia de idioma personal (Flujo B)",
)
def guardar_idioma_personal(
    dto: GuardarIdiomaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PreferenciaIdiomaResponse:
    use_case = GuardarIdiomaPersonalUseCase(db=db, idioma_repo=SqlAlchemyPreferenciaIdiomaRepository(db))
    entidad = use_case.execute(dto, usuario_actual)
    return PreferenciaIdiomaResponse.from_entity(entidad)


@router.get(
    "/global",
    response_model=Optional[PreferenciaIdiomaResponse],
    dependencies=[Depends(require_permission(_RECURSO_GLOBAL, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Obtener idioma global del sistema (Flujo C — Admin)",
)
def obtener_idioma_global(
    db: Session = Depends(get_db),
) -> Optional[PreferenciaIdiomaResponse]:
    repo = SqlAlchemyPreferenciaIdiomaRepository(db)
    entidad = repo.obtener_global()
    if entidad is None:
        return None
    return PreferenciaIdiomaResponse.from_entity(entidad)


@router.patch(
    "/global",
    response_model=PreferenciaIdiomaResponse,
    dependencies=[Depends(require_permission(_RECURSO_GLOBAL, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Actualizar idioma global del sistema (Flujo D — Admin)",
)
def guardar_idioma_global(
    dto: GuardarIdiomaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PreferenciaIdiomaResponse:
    use_case = GuardarIdiomaGlobalUseCase(db=db, idioma_repo=SqlAlchemyPreferenciaIdiomaRepository(db))
    entidad = use_case.execute(dto, usuario_actual)
    return PreferenciaIdiomaResponse.from_entity(entidad)
