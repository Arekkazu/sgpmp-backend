"""Router FastAPI del panel de administración del motor async de RF-77.

  POST /suministros/reportes-gastos/batch/ejecutar — Disparo manual (debug/panel admin)
  GET  /suministros/reportes-gastos/batch/cola      — Trabajos pendientes
  GET  /suministros/reportes-gastos/batch/fallos    — Fallos persistentes

RBAC: recurso 53 (`administracion_batch_reportes_gastos`). E=5, R=2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.infrastructure.factories.reporte_gastos_factory import (
    build_procesar_cola_reportes_gastos_use_case,
)
from src.supplies.infrastructure.repositories.fallo_reporte_gasto_repository import (
    SqlAlchemyFalloReporteGastoRepository,
)
from src.supplies.infrastructure.repositories.trabajo_reporte_gasto_repository import (
    SqlAlchemyTrabajoReporteGastoRepository,
)

router = APIRouter(
    prefix="/suministros/reportes-gastos/batch", tags=["Suministros - Batch Reportes de Gastos (RF-77)"]
)

_RECURSO = 53


@router.post(
    "/ejecutar",
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Disparar manualmente un ciclo del worker de reportes de gastos (debug/panel admin)",
)
async def ejecutar_ciclo(db: Session = Depends(get_db)) -> dict:
    use_case = build_procesar_cola_reportes_gastos_use_case(db)
    procesados = await use_case.ejecutar()
    return {"trabajos_procesados": procesados}


@router.get(
    "/cola",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar la cola de trabajos pendientes de generación de reportes",
)
def consultar_cola(db: Session = Depends(get_db)) -> dict:
    pendientes = SqlAlchemyTrabajoReporteGastoRepository(db).listar_pendientes(limite=50)
    return {
        "total": len(pendientes),
        "items": [
            {"id_cola": t.id_cola, "estado": t.estado.value, "fecha_solicitud": t.fecha_solicitud}
            for t in pendientes
        ],
    }


@router.get(
    "/fallos",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar los fallos persistentes del motor de reportes de gastos",
)
def consultar_fallos(db: Session = Depends(get_db)) -> dict:
    fallos = SqlAlchemyFalloReporteGastoRepository(db).listar_no_resueltos()
    return {
        "total": len(fallos),
        "items": [
            {
                "id_fallo": f.id_fallo,
                "id_cola": f.id_cola,
                "causa_fallo": f.causa_fallo,
                "intentos": f.intentos,
                "timestamp_ultimo_intento": f.timestamp_ultimo_intento,
            }
            for f in fallos
        ],
    }
