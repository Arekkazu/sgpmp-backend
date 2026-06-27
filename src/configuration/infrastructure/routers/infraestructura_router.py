"""Router FastAPI para áreas productivas (`/configuracion/infraestructuras`).

RF-20 — CU04:
  A) POST  /configuracion/infraestructuras          — Registrar (Admin)
  B) GET   /configuracion/infraestructuras          — Listar por finca (query param finca_id)
  C) GET   /configuracion/infraestructuras/{id}    — Detalle
  D) PATCH /configuracion/infraestructuras/{id}    — Editar (Admin; 412 concurrencia)
  E) PATCH /configuracion/infraestructuras/{id}/desactivar — Desactivar (Admin)

RBAC: id_recurso=10 (infraestructuras).
  Admin: C=1, R=2, U=3, D=4  |  Prod/Vet/Ing: R=2
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.infraestructuras.consultar_infraestructuras_use_case import ConsultarInfraestructurasUseCase
from src.configuration.application.use_cases.infraestructuras.desactivar_infraestructura_use_case import DesactivarInfraestructuraUseCase
from src.configuration.application.use_cases.infraestructuras.editar_infraestructura_use_case import EditarInfraestructuraUseCase
from src.configuration.application.use_cases.infraestructuras.registrar_infraestructura_use_case import RegistrarInfraestructuraUseCase
from src.configuration.infrastructure.adapters.infraestructura_stub_adapter import InfraestructuraStubAdapter
from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
from src.configuration.infrastructure.dto.registrar_infraestructura_dto import RegistrarInfraestructuraDTO
from src.configuration.infrastructure.repositories.auditoria_infraestructura_repository import SqlAlchemyAuditoriaInfraestructuraRepository
from src.configuration.infrastructure.repositories.finca_repository import SqlAlchemyFincaRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.schema.infraestructura_schema import InfraestructuraResponse, ListaInfraestructurasResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/infraestructuras", tags=["Configuración - Infraestructura Productiva"])

_RECURSO = 10  # modulo1.recursos: 'infraestructuras'


@router.post(
    "",
    response_model=InfraestructuraResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar área productiva (Flujo A)",
)
def registrar_infraestructura(
    dto: RegistrarInfraestructuraDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> InfraestructuraResponse:
    use_case = RegistrarInfraestructuraUseCase(
        db=db,
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        finca_repo=SqlAlchemyFincaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaInfraestructuraRepository(db),
    )
    infra = use_case.execute(dto, usuario_actual)
    return InfraestructuraResponse.from_entity(infra)


@router.get(
    "",
    response_model=ListaInfraestructurasResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar áreas productivas por finca (Flujo B)",
)
def listar_infraestructuras(
    finca_id: int = Query(..., description="ID de la finca cuyas áreas se quieren consultar."),
    solo_activas: bool = Query(False, description="Si true, solo áreas activas."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaInfraestructurasResponse:
    use_case = ConsultarInfraestructurasUseCase(
        db=db,
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaInfraestructuraRepository(db),
    )
    infraestructuras = use_case.listar_por_finca(finca_id, usuario_actual, solo_activas=solo_activas)
    items = [InfraestructuraResponse.from_entity(i) for i in infraestructuras]
    return ListaInfraestructurasResponse(total=len(items), items=items)


@router.get(
    "/{id_infraestructura}",
    response_model=InfraestructuraResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Detalle de área productiva (Flujo C)",
)
def obtener_infraestructura(
    id_infraestructura: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> InfraestructuraResponse:
    use_case = ConsultarInfraestructurasUseCase(
        db=db,
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaInfraestructuraRepository(db),
    )
    infra = use_case.obtener(id_infraestructura)
    return InfraestructuraResponse.from_entity(infra)


@router.patch(
    "/{id_infraestructura}",
    response_model=InfraestructuraResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Editar área productiva (Flujo D)",
)
def editar_infraestructura(
    id_infraestructura: int,
    dto: EditarInfraestructuraDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> InfraestructuraResponse:
    use_case = EditarInfraestructuraUseCase(
        db=db,
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        finca_repo=SqlAlchemyFincaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaInfraestructuraRepository(db),
    )
    infra = use_case.execute(id_infraestructura, dto, usuario_actual)
    return InfraestructuraResponse.from_entity(infra)


@router.patch(
    "/{id_infraestructura}/desactivar",
    response_model=InfraestructuraResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar área productiva (Flujo E)",
)
def desactivar_infraestructura(
    id_infraestructura: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> InfraestructuraResponse:
    use_case = DesactivarInfraestructuraUseCase(
        db=db,
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaInfraestructuraRepository(db),
        dependency_port=InfraestructuraStubAdapter(),
    )
    infra = use_case.execute(id_infraestructura, usuario_actual)
    return InfraestructuraResponse.from_entity(infra)
