"""Router FastAPI para el catálogo de tipos de área (`/configuracion/tipos-area`).

RF-20 — catálogo administrable que reemplaza el enum fijo de `tipo_area`:
  A) POST  /configuracion/tipos-area              — Registrar tipo (Admin)
  B) GET   /configuracion/tipos-area              — Consultar catálogo (autenticado)
  C) PATCH /configuracion/tipos-area/{id}/desactivar — Desactivar (Admin)

RBAC: id_recurso=58 (tipos_area).
  Admin: C=1, R=2, D=4  |  Productor: R=2
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.tipos_area.desactivar_tipo_area_use_case import DesactivarTipoAreaUseCase
from src.configuration.application.use_cases.tipos_area.listar_tipos_area_use_case import ListarTiposAreaUseCase
from src.configuration.application.use_cases.tipos_area.registrar_tipo_area_use_case import RegistrarTipoAreaUseCase
from src.configuration.infrastructure.dto.registrar_tipo_area_dto import RegistrarTipoAreaDTO
from src.configuration.infrastructure.repositories.tipo_area_repository import SqlAlchemyTipoAreaRepository
from src.configuration.infrastructure.schema.tipo_area_schema import ListaTiposAreaResponse, TipoAreaResponse
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/tipos-area", tags=["Configuración - Tipos de Área"])

_RECURSO = 58  # modulo1.recursos: 'tipos_area' — confirmar contra la BD antes de aplicar el RBAC


@router.post(
    "",
    response_model=TipoAreaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar tipo de área",
)
def registrar_tipo_area(
    dto: RegistrarTipoAreaDTO,
    db: Session = Depends(get_db),
) -> TipoAreaResponse:
    use_case = RegistrarTipoAreaUseCase(db=db, tipo_area_repo=SqlAlchemyTipoAreaRepository(db))
    tipo_area = use_case.execute(dto)
    return TipoAreaResponse.model_validate(tipo_area)


@router.get(
    "",
    response_model=ListaTiposAreaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar catálogo de tipos de área",
)
def consultar_tipos_area(
    solo_activos: bool = Query(False, description="Si es true, solo devuelve tipos activos."),
    db: Session = Depends(get_db),
) -> ListaTiposAreaResponse:
    use_case = ListarTiposAreaUseCase(tipo_area_repo=SqlAlchemyTipoAreaRepository(db))
    tipos = use_case.execute(solo_activos=solo_activos)
    items = [TipoAreaResponse.model_validate(t) for t in tipos]
    return ListaTiposAreaResponse(total=len(items), items=items)


@router.patch(
    "/{id_tipo_area}/desactivar",
    response_model=TipoAreaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar tipo de área",
)
def desactivar_tipo_area(
    id_tipo_area: int,
    db: Session = Depends(get_db),
) -> TipoAreaResponse:
    use_case = DesactivarTipoAreaUseCase(db=db, tipo_area_repo=SqlAlchemyTipoAreaRepository(db))
    tipo_area = use_case.execute(id_tipo_area)
    return TipoAreaResponse.model_validate(tipo_area)
