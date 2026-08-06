"""Router FastAPI del panel de administración del motor async de RF-81.

  POST /suministros/historial/batch/ejecutar — Disparo manual (debug/panel admin)
  GET  /suministros/historial/batch/cola      — Trabajos pendientes
  GET  /suministros/historial/batch/fallos    — Fallos persistentes

RBAC: recurso 54 (`administracion_batch_historial_suministros`). E=5, R=2.
Restringido a Administrador: el panel muestra cola/fallos de trabajos de
otros usuarios (incl. Gestor de Granja) — ver matriz RBAC en
``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.infrastructure.factories.historial_suministros_factory import (
    build_procesar_cola_historial_suministros_use_case,
)
from src.supplies.infrastructure.repositories.fallo_historial_suministro_repository import (
    SqlAlchemyFalloHistorialSuministroRepository,
)
from src.supplies.infrastructure.repositories.trabajo_historial_suministro_repository import (
    SqlAlchemyTrabajoHistorialSuministroRepository,
)

router = APIRouter(
    prefix="/suministros/historial/batch", tags=["Suministros - Batch Historial de Suministros (RF-81)"]
)

_RECURSO = 54


@router.post(
    "/ejecutar",
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Disparar manualmente un ciclo del worker de historial (debug/panel admin)",
)
async def ejecutar_ciclo(db: Session = Depends(get_db)) -> dict:
    use_case = build_procesar_cola_historial_suministros_use_case(db)
    procesados = await use_case.ejecutar()
    return {"trabajos_procesados": procesados}


@router.get(
    "/cola",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar la cola de trabajos pendientes de historial",
)
def consultar_cola(db: Session = Depends(get_db)) -> dict:
    pendientes = SqlAlchemyTrabajoHistorialSuministroRepository(db).listar_pendientes(limite=50)
    return {
        "total": len(pendientes),
        "items": [
            {
                "id_cola": t.id_cola,
                "tipo_trabajo": t.tipo_trabajo,
                "estado": t.estado.value,
                "fecha_solicitud": t.fecha_solicitud,
            }
            for t in pendientes
        ],
    }


@router.get(
    "/fallos",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Consultar los fallos persistentes del motor de historial",
)
def consultar_fallos(db: Session = Depends(get_db)) -> dict:
    fallos = SqlAlchemyFalloHistorialSuministroRepository(db).listar_no_resueltos()
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
