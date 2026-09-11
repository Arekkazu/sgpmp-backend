"""Router FastAPI para identidad visual institucional (`/configuracion/identidad-visual`).

RF-26:
  A) GET   /configuracion/identidad-visual/{id_finca} — Consultar identidad visual activa.
  B) POST  /configuracion/identidad-visual            — Crear (multipart/form-data).
  C) PATCH /configuracion/identidad-visual/{id_finca} — Actualizar; 412 si versión diverge.

RBAC: id_recurso=23 (identidad_visual). Solo Administrador.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.personalizacion.actualizar_identidad_visual_use_case import ActualizarIdentidadVisualUseCase
from src.configuration.application.use_cases.personalizacion.guardar_identidad_visual_use_case import GuardarIdentidadVisualUseCase
from src.configuration.application.use_cases.personalizacion.obtener_identidad_visual_use_case import ObtenerIdentidadVisualUseCase
from src.configuration.infrastructure.dto.actualizar_identidad_visual_dto import ActualizarIdentidadVisualDTO
from src.configuration.infrastructure.dto.guardar_identidad_visual_dto import GuardarIdentidadVisualDTO
from src.configuration.infrastructure.repositories.auditoria_identidad_visual_repository import SqlAlchemyAuditoriaIdentidadVisualRepository
from src.configuration.infrastructure.repositories.identidad_visual_repository import SqlAlchemyIdentidadVisualRepository
from src.configuration.infrastructure.schema.identidad_visual_schema import IdentidadVisualResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/identidad-visual", tags=["Configuración - Identidad Visual (RF-26)"])

_RECURSO = 23  # modulo1.recursos: 'identidad_visual'


@router.get(
    "/{id_finca}",
    response_model=Optional[IdentidadVisualResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar identidad visual activa de una finca (Flujo A)",
)
def obtener_identidad_visual(
    id_finca: int,
    db: Session = Depends(get_db),
) -> Optional[IdentidadVisualResponse]:
    use_case = ObtenerIdentidadVisualUseCase(
        identidad_repo=SqlAlchemyIdentidadVisualRepository(db),
    )
    entidad = use_case.execute(id_finca)
    if entidad is None:
        return None
    return IdentidadVisualResponse.from_entity(entidad)


@router.post(
    "",
    response_model=IdentidadVisualResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Crear identidad visual para una finca (Flujo B)",
)
async def crear_identidad_visual(
    id_finca: int = Form(...),
    primary_color: str = Form(..., pattern=r'^#[0-9A-Fa-f]{6}$'),
    secondary_color: str = Form(..., pattern=r'^#[0-9A-Fa-f]{6}$'),
    org_display_name: str = Form(..., min_length=1, max_length=50),
    logo: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> IdentidadVisualResponse:
    dto = GuardarIdentidadVisualDTO(
        id_finca=id_finca,
        primary_color=primary_color,
        secondary_color=secondary_color,
        org_display_name=org_display_name,
    )
    logo_bytes = await logo.read() if logo else None
    logo_content_type = logo.content_type if logo else None

    use_case = GuardarIdentidadVisualUseCase(
        db=db,
        identidad_repo=SqlAlchemyIdentidadVisualRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaIdentidadVisualRepository(db),
    )
    entidad = use_case.execute(dto, logo_bytes, logo_content_type, usuario_actual)
    return IdentidadVisualResponse.from_entity(entidad)


@router.patch(
    "/{id_finca}",
    response_model=IdentidadVisualResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
    },
    summary="Actualizar identidad visual de una finca (Flujo C)",
)
async def actualizar_identidad_visual(
    id_finca: int,
    primary_color: str = Form(..., pattern=r'^#[0-9A-Fa-f]{6}$'),
    secondary_color: str = Form(..., pattern=r'^#[0-9A-Fa-f]{6}$'),
    org_display_name: str = Form(..., min_length=1, max_length=50),
    version: int = Form(...),
    logo: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> IdentidadVisualResponse:
    dto = ActualizarIdentidadVisualDTO(
        primary_color=primary_color,
        secondary_color=secondary_color,
        org_display_name=org_display_name,
        version=version,
    )
    logo_bytes = await logo.read() if logo else None
    logo_content_type = logo.content_type if logo else None

    use_case = ActualizarIdentidadVisualUseCase(
        db=db,
        identidad_repo=SqlAlchemyIdentidadVisualRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaIdentidadVisualRepository(db),
    )
    entidad = use_case.execute(id_finca, dto, logo_bytes, logo_content_type, usuario_actual)
    return IdentidadVisualResponse.from_entity(entidad)
