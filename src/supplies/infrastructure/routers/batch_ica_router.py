"""Router FastAPI del motor batch ICA (RF-74, Flujo C — panel de administración).

  POST /suministros/eficiencia-alimenticia/batch/ejecutar               — Disparar/reactivar
  POST /suministros/eficiencia-alimenticia/batch/{id}/interrumpir       — Interrumpir (FA-12)
  POST /suministros/eficiencia-alimenticia/batch/activos/{id}/reintentar — Reintento manual (E5)
  GET  /suministros/eficiencia-alimenticia/batch/estado                 — Panel de corridas
  GET  /suministros/eficiencia-alimenticia/batch/cola                   — Cola pendiente
  GET  /suministros/eficiencia-alimenticia/batch/fallos                 — Fallos persistentes

Autorización RBAC: recurso ``administracion_batch_ica`` = id_recurso 50; acciones
E=5 (ejecutar/interrumpir/reintentar), R=2 (panel/cola/fallos).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.infrastructure.dto.calcular_ica_dto import EjecutarBatchDTO, InterrumpirBatchDTO
from src.supplies.infrastructure.factories.eficiencia_factory import (
    build_ejecutar_batch_use_case,
    build_interrumpir_batch_use_case,
    build_reintentar_ica_use_case,
)
from src.supplies.infrastructure.repositories.cola_calculo_ica_repository import (
    SqlAlchemyColaCalculoICARepository,
)
from src.supplies.infrastructure.repositories.ejecucion_batch_ica_repository import (
    SqlAlchemyEjecucionBatchICARepository,
)
from src.supplies.infrastructure.repositories.fallo_calculo_ica_repository import (
    SqlAlchemyFalloCalculoICARepository,
)
from src.supplies.infrastructure.schema.eficiencia_schema import (
    ColaICAResponse,
    EstadoBatchResponse,
    FalloICAResponse,
    FallosICAResponse,
    HistorialICAResponse,
    ItemColaResponse,
    ResultadoICAResponse,
)

router = APIRouter(
    prefix="/suministros/eficiencia-alimenticia/batch",
    tags=["Suministros - Batch ICA (RF-74)"],
)

_RECURSO = 50  # modulo1.recursos: 'administracion_batch_ica'


@router.post(
    "/ejecutar",
    response_model=EstadoBatchResponse,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Disparar (o reactivar la cola de) el batch ICA (RF-74, Flujo C)",
)
async def ejecutar_batch(
    dto: EjecutarBatchDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EstadoBatchResponse:
    use_case = build_ejecutar_batch_use_case(db)
    ejecucion = await use_case.ejecutar(
        tipo_disparo="MANUAL",
        id_usuario=usuario_actual.id_usuario,
        solo_cola=dto.solo_cola,
    )
    return EstadoBatchResponse.desde_entidad(ejecucion)


@router.post(
    "/{id_ejecucion}/interrumpir",
    response_model=EstadoBatchResponse,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Interrumpir una corrida del batch ICA (RF-74, FA-12)",
)
def interrumpir_batch(
    id_ejecucion: int,
    dto: InterrumpirBatchDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EstadoBatchResponse:
    use_case = build_interrumpir_batch_use_case(db)
    ejecucion = use_case.execute(id_ejecucion, usuario_actual.id_usuario, dto.motivo)
    return EstadoBatchResponse.desde_entidad(ejecucion)


@router.post(
    "/activos/{id_activo_biologico}/reintentar",
    response_model=HistorialICAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Reintento manual del cálculo ICA de un activo (RF-74, E5)",
)
def reintentar_activo(
    id_activo_biologico: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialICAResponse:
    use_case = build_reintentar_ica_use_case(db)
    resultados = use_case.execute(id_activo_biologico, usuario_actual.id_usuario)
    items = [ResultadoICAResponse.desde_entidad(r) for r in resultados]
    return HistorialICAResponse(
        id_activo_biologico=id_activo_biologico, total=len(items), items=items
    )


@router.get(
    "/estado",
    response_model=list[EstadoBatchResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Panel de corridas del batch ICA (más recientes primero)",
)
def estado_batch(
    db: Session = Depends(get_db),
) -> list[EstadoBatchResponse]:
    ejecuciones = SqlAlchemyEjecucionBatchICARepository(db).listar_recientes(limite=20)
    return [EstadoBatchResponse.desde_entidad(e) for e in ejecuciones]


@router.get(
    "/cola",
    response_model=ColaICAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar la cola de activos pendientes de cálculo ICA",
)
def consultar_cola(
    db: Session = Depends(get_db),
) -> ColaICAResponse:
    pendientes = SqlAlchemyColaCalculoICARepository(db).listar_pendientes()
    items = [ItemColaResponse.desde_entidad(i) for i in pendientes]
    return ColaICAResponse(total=len(items), items=items)


@router.get(
    "/fallos",
    response_model=FallosICAResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar los fallos persistentes del cálculo ICA (CA_FALLO_PERSISTENTE)",
)
def consultar_fallos(
    db: Session = Depends(get_db),
) -> FallosICAResponse:
    fallos = SqlAlchemyFalloCalculoICARepository(db).listar_no_resueltos()
    items = [FalloICAResponse.desde_entidad(f) for f in fallos]
    return FallosICAResponse(total=len(items), items=items)
