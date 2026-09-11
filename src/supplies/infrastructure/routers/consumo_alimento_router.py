"""Router FastAPI para el registro de consumo de alimento (`/suministros/consumo-alimentos`).

Expone los flujos de RF-75 (CU-01):
  POST   /suministros/consumo-alimentos               — Registrar consumo
  POST   /suministros/consumo-alimentos/{id}/anulacion — Anular consumo
  GET    /suministros/consumo-alimentos               — Consultar/buscar consumos

Autorización delegada al RBAC centralizado (``src/shared/rbac.py``):
  recurso ``consumo_alimentos`` = id_recurso 47; acciones C=1, R=2, D=4.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.application.use_cases.suministros.anular_consumo_alimento_use_case import (
    AnularConsumoAlimentoUseCase,
)
from src.supplies.application.use_cases.suministros.consultar_consumos_use_case import ConsultarConsumosUseCase
from src.supplies.application.use_cases.suministros.registrar_consumo_alimento_use_case import (
    RegistrarConsumoAlimentoUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO
from src.supplies.infrastructure.dto.registrar_consumo_alimento_dto import RegistrarConsumoAlimentoDTO
from src.supplies.infrastructure.repositories.consumo_alimento_repository import (
    SqlAlchemyConsumoAlimentoRepository,
)
from src.supplies.infrastructure.schema.consumo_alimento_schema import (
    ConsultaConsumosResponse,
    ConsumoAlimentoResponse,
)

router = APIRouter(prefix="/suministros/consumo-alimentos", tags=["Suministros - Consumo de alimentos"])

_RECURSO = 47  # modulo1.recursos: 'consumo_alimentos'


@router.post(
    "",
    response_model=ConsumoAlimentoResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar consumo de alimento (RF-75)",
)
def registrar_consumo(
    dto: RegistrarConsumoAlimentoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConsumoAlimentoResponse:
    use_case = RegistrarConsumoAlimentoUseCase(
        db=db,
        consumo_repo=SqlAlchemyConsumoAlimentoRepository(db),
        activo_port=ActivoM02Adapter(db),
        ciclo_port=CicloM02Adapter(db),
    )
    consumo = use_case.execute(dto, usuario_actual)
    return ConsumoAlimentoResponse.model_validate(consumo)


@router.post(
    "/{id_consumo}/anulacion",
    response_model=ConsumoAlimentoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Anular un registro de consumo VALIDADO (RF-75)",
)
def anular_consumo(
    id_consumo: int,
    dto: AnularRegistroDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConsumoAlimentoResponse:
    use_case = AnularConsumoAlimentoUseCase(
        db=db,
        consumo_repo=SqlAlchemyConsumoAlimentoRepository(db),
    )
    consumo = use_case.execute(id_consumo, dto, usuario_actual)
    return ConsumoAlimentoResponse.model_validate(consumo)


@router.get(
    "",
    response_model=ConsultaConsumosResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar/buscar registros de consumo (RF-75)",
)
def consultar_consumos(
    id_activo_biologico: Optional[int] = Query(None, description="Filtrar por activo biológico."),
    fecha_desde: Optional[date] = Query(None, description="Fecha de consumo mínima (inclusive)."),
    fecha_hasta: Optional[date] = Query(None, description="Fecha de consumo máxima (inclusive)."),
    tipo_alimento: Optional[str] = Query(None, description="Filtrar por tipo de alimento."),
    estado_registro: Optional[str] = Query(None, description="VALIDADO o ANULADO."),
    db: Session = Depends(get_db),
) -> ConsultaConsumosResponse:
    use_case = ConsultarConsumosUseCase(consumo_repo=SqlAlchemyConsumoAlimentoRepository(db))
    consumos = use_case.execute(
        id_activo_biologico=id_activo_biologico,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_alimento=tipo_alimento,
        estado_registro=estado_registro,
    )
    items = [ConsumoAlimentoResponse.model_validate(c) for c in consumos]
    return ConsultaConsumosResponse(total=len(items), items=items)
