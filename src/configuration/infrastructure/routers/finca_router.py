"""Router FastAPI para la gestión de fincas (`/configuracion/fincas`).

RF-19 — CU04:
  A) POST  /configuracion/fincas          — Registrar (Admin)
  B) GET   /configuracion/fincas          — Listar (Admin=todas, Prod=las suyas)
  C) GET   /configuracion/fincas/{id}    — Detalle
  D) PATCH /configuracion/fincas/{id}    — Editar (Admin; 412 concurrencia)
  E) PATCH /configuracion/fincas/{id}/desactivar — Desactivar (Admin; FA-04)

RBAC: id_recurso=9 (fincas).
  Admin: C=1, R=2, U=3, D=4
  Productor/Vet/Ing: R=2
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.fincas.consultar_fincas_use_case import ConsultarFincasUseCase
from src.configuration.application.use_cases.fincas.desactivar_finca_use_case import DesactivarFincaUseCase
from src.configuration.application.use_cases.fincas.editar_finca_use_case import EditarFincaUseCase
from src.configuration.application.use_cases.fincas.registrar_finca_use_case import RegistrarFincaUseCase
from src.configuration.infrastructure.adapters.finca_stub_adapter import FincaStubAdapter
from src.configuration.infrastructure.dto.editar_finca_dto import EditarFincaDTO
from src.configuration.infrastructure.dto.registrar_finca_dto import RegistrarFincaDTO
from src.configuration.infrastructure.repositories.auditoria_finca_repository import SqlAlchemyAuditoriaFincaRepository
from src.configuration.infrastructure.repositories.finca_repository import SqlAlchemyFincaRepository
from src.configuration.infrastructure.schema.finca_schema import FincaResponse, ListaFincasResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/fincas", tags=["Configuración - Fincas"])

_RECURSO = 9   # modulo1.recursos: 'fincas'
_ROL_ADMIN = 1
_ROL_PROD = 2


@router.post(
    "",
    response_model=FincaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Registrar finca (Flujo A)",
)
def registrar_finca(
    dto: RegistrarFincaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> FincaResponse:
    use_case = RegistrarFincaUseCase(
        db=db,
        finca_repo=SqlAlchemyFincaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaFincaRepository(db),
    )
    finca = use_case.execute(dto, usuario_actual)
    return FincaResponse.from_entity(finca)


@router.get(
    "",
    response_model=ListaFincasResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar fincas (Flujo B)",
)
def listar_fincas(
    solo_activas: bool = Query(False, description="Si true, solo fincas activas."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaFincasResponse:
    id_filtro: Optional[int] = (
        usuario_actual.id_usuario if usuario_actual.id_rol == _ROL_PROD else None
    )
    use_case = ConsultarFincasUseCase(finca_repo=SqlAlchemyFincaRepository(db))
    fincas = use_case.listar(id_usuario_filtro=id_filtro, solo_activas=solo_activas)
    items = [FincaResponse.from_entity(f) for f in fincas]
    return ListaFincasResponse(total=len(items), items=items)


@router.get(
    "/{id_finca}",
    response_model=FincaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Detalle de finca (Flujo C)",
)
def obtener_finca(
    id_finca: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> FincaResponse:
    id_filtro: Optional[int] = (
        usuario_actual.id_usuario if usuario_actual.id_rol == _ROL_PROD else None
    )
    use_case = ConsultarFincasUseCase(finca_repo=SqlAlchemyFincaRepository(db))
    finca = use_case.obtener(id_finca, id_usuario_filtro=id_filtro)
    return FincaResponse.from_entity(finca)


@router.patch(
    "/{id_finca}",
    response_model=FincaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
    },
    summary="Editar finca (Flujo D)",
)
def editar_finca(
    id_finca: int,
    dto: EditarFincaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> FincaResponse:
    use_case = EditarFincaUseCase(
        db=db,
        finca_repo=SqlAlchemyFincaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaFincaRepository(db),
    )
    finca = use_case.execute(id_finca, dto, usuario_actual)
    return FincaResponse.from_entity(finca)


@router.patch(
    "/{id_finca}/desactivar",
    response_model=FincaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar finca (Flujo E)",
)
def desactivar_finca(
    id_finca: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> FincaResponse:
    use_case = DesactivarFincaUseCase(
        db=db,
        finca_repo=SqlAlchemyFincaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaFincaRepository(db),
        dependency_port=FincaStubAdapter(),
    )
    finca = use_case.execute(id_finca, usuario_actual)
    return FincaResponse.from_entity(finca)
