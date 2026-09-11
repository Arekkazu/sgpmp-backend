"""Router FastAPI para etapas del ciclo productivo (`/configuracion/ciclos`).

Expone los cuatro flujos de RF-16 CU02 para etapas:
  A) POST   /configuracion/ciclos              — Registrar etapa
  B) PATCH  /configuracion/ciclos/{id}         — Editar etapa
  C) PATCH  /configuracion/ciclos/{id}/desactivar — Desactivar etapa
  D) GET    /configuracion/ciclos              — Consultar etapas por especie

Autorización RBAC:
  recurso ciclos_biologicos = id_recurso 17
  C=1, R=2, U=3, D=4
  Roles autorizados: Administrador (1) y Veterinario (3).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.ciclos.consultar_ciclos_use_case import ConsultarCiclosUseCase
from src.configuration.application.use_cases.ciclos.desactivar_ciclo_use_case import DesactivarCicloUseCase
from src.configuration.application.use_cases.ciclos.editar_ciclo_use_case import EditarCicloUseCase
from src.configuration.application.use_cases.ciclos.registrar_ciclo_use_case import RegistrarCicloUseCase
from src.configuration.infrastructure.dto.editar_ciclo_dto import EditarCicloDTO
from src.configuration.infrastructure.dto.registrar_ciclo_dto import RegistrarCicloDTO
from src.configuration.infrastructure.repositories.auditoria_ciclo_repository import SqlAlchemyAuditoriaCicloRepository
from src.configuration.infrastructure.repositories.ciclo_biologico_repository import SqlAlchemyCicloBiologicoRepository
from src.configuration.infrastructure.repositories.dependencia_ciclo_repository import SqlAlchemyDependenciaCicloRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.schema.ciclo_schema import CicloBiologicoResponse, EtapasPorEspecieResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/ciclos", tags=["Configuración - Ciclos Productivos"])

_RECURSO = 17  # modulo1.recursos: 'ciclos_biologicos'


@router.post(
    "",
    response_model=CicloBiologicoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar etapa del ciclo productivo (Flujo A)",
)
def registrar_ciclo(
    dto: RegistrarCicloDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CicloBiologicoResponse:
    use_case = RegistrarCicloUseCase(
        db=db,
        ciclos_repo=SqlAlchemyCicloBiologicoRepository(db),
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaCicloRepository(db),
    )
    ciclo = use_case.execute(dto, usuario_actual)
    return CicloBiologicoResponse.model_validate(ciclo)


@router.get(
    "",
    response_model=EtapasPorEspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar etapas por especie (Flujo D)",
)
def consultar_ciclos(
    id_especie: int = Query(..., description="ID de la especie a consultar."),
    solo_activas: bool = Query(False, description="Si es true, solo devuelve etapas activas."),
    db: Session = Depends(get_db),
) -> EtapasPorEspecieResponse:
    use_case = ConsultarCiclosUseCase(ciclos_repo=SqlAlchemyCicloBiologicoRepository(db))
    ciclos = use_case.execute(id_especie, solo_activas=solo_activas)
    items = [CicloBiologicoResponse.model_validate(c) for c in ciclos]
    return EtapasPorEspecieResponse(total=len(items), items=items)


@router.patch(
    "/{id_ciclo_biologico}",
    response_model=CicloBiologicoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Editar etapa del ciclo productivo (Flujo B)",
)
def editar_ciclo(
    id_ciclo_biologico: int,
    dto: EditarCicloDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CicloBiologicoResponse:
    use_case = EditarCicloUseCase(
        db=db,
        ciclos_repo=SqlAlchemyCicloBiologicoRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaCicloRepository(db),
    )
    ciclo = use_case.execute(id_ciclo_biologico, dto, usuario_actual)
    return CicloBiologicoResponse.model_validate(ciclo)


@router.patch(
    "/{id_ciclo_biologico}/desactivar",
    response_model=CicloBiologicoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar etapa del ciclo productivo (Flujo C)",
)
def desactivar_ciclo(
    id_ciclo_biologico: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CicloBiologicoResponse:
    use_case = DesactivarCicloUseCase(
        db=db,
        ciclos_repo=SqlAlchemyCicloBiologicoRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaCicloRepository(db),
        dependencia_port=SqlAlchemyDependenciaCicloRepository(db),
    )
    ciclo = use_case.execute(id_ciclo_biologico, usuario_actual)
    return CicloBiologicoResponse.model_validate(ciclo)
