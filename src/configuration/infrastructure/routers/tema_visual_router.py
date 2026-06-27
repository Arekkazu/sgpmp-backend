"""Router FastAPI para tema visual (`/configuracion/personalizacion/tema`).

RF-27:
  A) GET   /configuracion/personalizacion/tema         — Tema resuelto del usuario.
  B) PATCH /configuracion/personalizacion/tema         — Guardar preferencia personal.
  C) GET   /configuracion/personalizacion/tema/global  — Tema global (Admin).
  D) PATCH /configuracion/personalizacion/tema/global  — Actualizar tema global (Admin).

RBAC: id_recurso=24 (tema_visual), id_recurso=27 (configuracion_ui_global).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.personalizacion.guardar_tema_global_use_case import GuardarTemaGlobalUseCase
from src.configuration.application.use_cases.personalizacion.guardar_tema_personal_use_case import GuardarTemaPersonalUseCase
from src.configuration.application.use_cases.personalizacion.obtener_tema_resuelto_use_case import ObtenerTemaResueltoUseCase
from src.configuration.infrastructure.dto.guardar_tema_dto import GuardarTemaDTO
from src.configuration.infrastructure.repositories.tema_visual_repository import SqlAlchemyTemaVisualRepository
from src.configuration.infrastructure.schema.tema_visual_schema import TemaResueltoResponse, TemaVisualResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/personalizacion/tema", tags=["Configuración - Tema Visual (RF-27)"])

_RECURSO_TEMA = 24        # modulo1.recursos: 'tema_visual'
_RECURSO_GLOBAL = 27      # modulo1.recursos: 'configuracion_ui_global'


@router.get(
    "",
    response_model=TemaResueltoResponse,
    dependencies=[Depends(require_permission(_RECURSO_TEMA, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Obtener tema visual resuelto del usuario (Flujo A)",
)
def obtener_tema(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TemaResueltoResponse:
    use_case = ObtenerTemaResueltoUseCase(tema_repo=SqlAlchemyTemaVisualRepository(db))
    resultado = use_case.execute(usuario_actual)
    return TemaResueltoResponse(**resultado)


@router.patch(
    "",
    response_model=TemaVisualResponse,
    dependencies=[Depends(require_permission(_RECURSO_TEMA, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Guardar preferencia de tema personal (Flujo B)",
)
def guardar_tema_personal(
    dto: GuardarTemaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TemaVisualResponse:
    use_case = GuardarTemaPersonalUseCase(db=db, tema_repo=SqlAlchemyTemaVisualRepository(db))
    entidad = use_case.execute(dto, usuario_actual)
    return TemaVisualResponse.from_entity(entidad)


@router.get(
    "/global",
    response_model=Optional[TemaVisualResponse],
    dependencies=[Depends(require_permission(_RECURSO_GLOBAL, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Obtener tema visual global (Flujo C — Admin)",
)
def obtener_tema_global(
    db: Session = Depends(get_db),
) -> Optional[TemaVisualResponse]:
    repo = SqlAlchemyTemaVisualRepository(db)
    entidad = repo.obtener_global()
    if entidad is None:
        return None
    return TemaVisualResponse.from_entity(entidad)


@router.patch(
    "/global",
    response_model=TemaVisualResponse,
    dependencies=[Depends(require_permission(_RECURSO_GLOBAL, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Actualizar tema visual global del sistema (Flujo D — Admin)",
)
def guardar_tema_global(
    dto: GuardarTemaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TemaVisualResponse:
    use_case = GuardarTemaGlobalUseCase(db=db, tema_repo=SqlAlchemyTemaVisualRepository(db))
    entidad = use_case.execute(dto, usuario_actual)
    return TemaVisualResponse.from_entity(entidad)
