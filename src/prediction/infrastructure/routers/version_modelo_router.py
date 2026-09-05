"""Router FastAPI para ciclo de vida de versiones de modelos IA (`/prediccion/modelos`).

RF-69 CU-05: Validar y versionar modelos de IA.
  POST  /prediccion/modelos                     — Registro interno desde RF-71 (multipart/form-data)
  GET   /prediccion/modelos                     — Listar versiones (filtros: tipo_modelo, estado)
  GET   /prediccion/modelos/{id_version}        — Obtener versión por id
  PATCH /prediccion/modelos/{id_version}/notas  — Registrar notas de validación clínica
  POST  /prediccion/modelos/{id_version}/activar — Activar versión APROBADA (atómico)

Autorización RBAC:
  recurso version_modelo = id_recurso 43
  R=2 (Admin, Vet), U=3 (Admin, Vet), E=5 (Admin, Vet)
  El endpoint POST (registro) no usa RBAC; está protegido por X-RF71-Internal-Key.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.versiones_modelo.activar_version_modelo_use_case import ActivarVersionModeloUseCase
from src.prediction.application.use_cases.versiones_modelo.consultar_versiones_use_case import ConsultarVersionesUseCase
from src.prediction.application.use_cases.versiones_modelo.registrar_notas_version_use_case import RegistrarNotasVersionUseCase
from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import RegistrarVersionModeloUseCase
from src.prediction.infrastructure.adapters.variable_i3p1_m09_adapter import VariableI3P1M09Adapter
from src.prediction.infrastructure.dto.registrar_notas_version_dto import RegistrarNotasVersionDTO
from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.version_modelo_repository import SqlAlchemyVersionModeloRepository
from src.prediction.infrastructure.schema.version_modelo_schema import VersionModeloListResponse, VersionModeloResponse
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/modelos", tags=["Predicción M04 - Versiones de Modelos IA"])

_RECURSO = 43  # modulo1.recursos: 'version_modelo'


@router.post(
    "",
    response_model=VersionModeloResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Registrar nueva versión de modelo IA desde RF-71 (RF-69 — solo interno)",
)
async def registrar_version_modelo(
    x_rf71_internal_key: Optional[str] = Header(None, alias="X-RF71-Internal-Key"),
    db: Session = Depends(get_db),
    dto: RegistrarVersionModeloDTO = Depends(),
) -> VersionModeloResponse:
    use_case = RegistrarVersionModeloUseCase(
        db=db,
        repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        variable_port=VariableI3P1M09Adapter(db),
    )
    entidad = use_case.execute(dto, internal_key=x_rf71_internal_key)
    return VersionModeloResponse.from_entity(entidad)


@router.get(
    "",
    response_model=VersionModeloListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar versiones de modelos IA (RF-69)",
)
def listar_versiones(
    tipo_modelo: Optional[str] = Query(None, description="Filtrar por tipo de modelo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado (APROBADO, ACTIVO, etc.)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VersionModeloListResponse:
    use_case = ConsultarVersionesUseCase(
        repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        db=db,
    )
    items, total = use_case.listar(
        tipo_modelo=tipo_modelo,
        estado=estado,
        limit=limit,
        offset=offset,
        id_usuario=usuario_actual.id_usuario,
    )
    return VersionModeloListResponse(
        total=total,
        items=[VersionModeloResponse.from_entity(e) for e in items],
    )


@router.get(
    "/{id_version}",
    response_model=VersionModeloResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener versión de modelo IA por id (RF-69)",
)
def obtener_version(
    id_version: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VersionModeloResponse:
    use_case = ConsultarVersionesUseCase(
        repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        db=db,
    )
    entidad = use_case.obtener_por_id(id_version, id_usuario=usuario_actual.id_usuario)
    return VersionModeloResponse.from_entity(entidad)


@router.patch(
    "/{id_version}/notas",
    response_model=VersionModeloResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar notas de validación clínica sobre una versión (RF-69 Fase 4)",
)
def registrar_notas(
    id_version: int,
    dto: RegistrarNotasVersionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VersionModeloResponse:
    use_case = RegistrarNotasVersionUseCase(
        db=db,
        repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    entidad = use_case.execute(id_version, dto, id_usuario=usuario_actual.id_usuario)
    return VersionModeloResponse.from_entity(entidad)


@router.post(
    "/{id_version}/activar",
    response_model=VersionModeloResponse,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Activar versión APROBADA de modelo IA (RF-69 Fase 5 — atómico)",
)
def activar_version(
    id_version: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VersionModeloResponse:
    use_case = ActivarVersionModeloUseCase(
        db=db,
        repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    entidad = use_case.execute(id_version, id_usuario=usuario_actual.id_usuario)
    return VersionModeloResponse.from_entity(entidad)
