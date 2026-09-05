"""Router FastAPI para el catálogo de especies productivas (`/configuracion/especies`).

Expone los cinco flujos de RF-15 (CU01):
  A) POST   /configuracion/especies              — Registrar especie (Admin)
  B) PATCH  /configuracion/especies/{id}         — Editar especie (Admin + Ingeniero de Campo)
  C) PATCH  /configuracion/especies/{id}/desactivar — Desactivar (Admin)
  D) PATCH  /configuracion/especies/{id}/reactivar  — Reactivar (Admin)
  E) GET    /configuracion/especies              — Consultar catálogo (autenticado)

Autorización delegada al RBAC centralizado (`src/shared/rbac.py`):
  recurso especies = id_recurso 8
  C=1, R=2, U=3, D=4
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.especies.consultar_catalogo_use_case import ConsultarCatalogoUseCase
from src.configuration.application.use_cases.especies.desactivar_especie_use_case import DesactivarEspecieUseCase
from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.application.use_cases.especies.reactivar_especie_use_case import ReactivarEspecieUseCase
from src.configuration.application.use_cases.especies.registrar_especie_use_case import RegistrarEspecieUseCase
from src.configuration.infrastructure.adapters.proceso_critico_stub import StubProcesoCriticoAdapter
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.dto.registrar_especie_dto import RegistrarEspecieDTO
from src.configuration.infrastructure.repositories.auditoria_especie_repository import SqlAlchemyAuditoriaEspecieRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.schema.especie_schema import CatalogoEspeciesResponse, EspecieResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/especies", tags=["Configuración - Especies"])

_RECURSO = 8  # modulo1.recursos: 'especies'


@router.post(
    "",
    response_model=EspecieResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Registrar especie (Flujo A)",
)
def registrar_especie(
    dto: RegistrarEspecieDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EspecieResponse:
    use_case = RegistrarEspecieUseCase(
        db=db,
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaEspecieRepository(db),
    )
    especie = use_case.execute(dto, usuario_actual)
    return EspecieResponse.model_validate(especie)


@router.get(
    "",
    response_model=CatalogoEspeciesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar catálogo de especies (Flujo E)",
)
def consultar_catalogo(
    solo_activas: bool = Query(False, description="Si es true, solo devuelve especies activas."),
    db: Session = Depends(get_db),
) -> CatalogoEspeciesResponse:
    use_case = ConsultarCatalogoUseCase(
        especies_repo=SqlAlchemyEspecieRepository(db),
    )
    especies = use_case.execute(solo_activas=solo_activas)
    items = [EspecieResponse.model_validate(e) for e in especies]
    return CatalogoEspeciesResponse(total=len(items), items=items)


@router.patch(
    "/{id_especie}",
    response_model=EspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Editar especie (Flujo B)",
)
def editar_especie(
    id_especie: int,
    dto: EditarEspecieDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EspecieResponse:
    use_case = EditarEspecieUseCase(
        db=db,
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaEspecieRepository(db),
    )
    especie = use_case.execute(id_especie, dto, usuario_actual)
    return EspecieResponse.model_validate(especie)


@router.patch(
    "/{id_especie}/desactivar",
    response_model=EspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
    },
    summary="Desactivar especie (Flujo C)",
)
def desactivar_especie(
    id_especie: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EspecieResponse:
    use_case = DesactivarEspecieUseCase(
        db=db,
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaEspecieRepository(db),
        proceso_critico_port=StubProcesoCriticoAdapter(),
    )
    especie = use_case.execute(id_especie, usuario_actual)
    return EspecieResponse.model_validate(especie)


@router.patch(
    "/{id_especie}/reactivar",
    response_model=EspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Reactivar especie (Flujo D)",
)
def reactivar_especie(
    id_especie: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EspecieResponse:
    use_case = ReactivarEspecieUseCase(
        db=db,
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaEspecieRepository(db),
    )
    especie = use_case.execute(id_especie, usuario_actual)
    return EspecieResponse.model_validate(especie)
