"""Router FastAPI de RF-77 — Reporte de Gastos Acumulados.

  POST /suministros/reportes-gastos                    — Generar (sync 200 o async 202)
  GET  /suministros/reportes-gastos/{id_reporte}        — Consultar un reporte generado
  GET  /suministros/reportes-gastos/historial           — Historial de reportes del usuario
  GET  /suministros/reportes-gastos/trabajos/{id_cola}  — Estado de un trabajo async

RBAC: recurso 51 (`reporte_gastos_suministros`). E=5 (generar), R=2 (consultar).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import TrabajoReporteGasto
from src.supplies.infrastructure.dto.generar_reporte_gastos_dto import GenerarReporteGastosDTO
from src.supplies.infrastructure.factories.reporte_gastos_factory import (
    build_consultar_estado_trabajo_reporte_use_case,
    build_consultar_reporte_gastos_use_case,
    build_generar_reporte_gastos_use_case,
    build_listar_historial_reportes_use_case,
)
from src.supplies.infrastructure.schema.reporte_gasto_schema import (
    EstadoTrabajoReporteResponse,
    HistorialReportesResponse,
    ReporteGastoResponse,
    TrabajoReporteResponse,
)

router = APIRouter(prefix="/suministros/reportes-gastos", tags=["Suministros - Reporte de Gastos (RF-77)"])

_RECURSO = 51


@router.post(
    "",
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    summary="Generar el reporte de gastos acumulados (RF-77) — sync 200 o async 202",
)
def generar_reporte(
    dto: GenerarReporteGastosDTO,
    response: Response,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = build_generar_reporte_gastos_use_case(db)
    filtros = FiltrosReporteGasto(
        fecha_inicio=dto.fecha_inicio_reporte,
        fecha_fin=dto.fecha_fin_reporte,
        tipo_periodo=dto.tipo_periodo.value,
        id_activo_biologico=dto.activo_biologico_id,
        id_infraestructura=dto.id_infraestructura,
        id_especie=dto.id_especie,
        categorias_incluidas=[c.value for c in dto.categorias_incluidas] if dto.categorias_incluidas else None,
    )
    resultado = use_case.execute(filtros, usuario_actual.id_usuario)

    if isinstance(resultado, TrabajoReporteGasto):
        response.status_code = 202
        return TrabajoReporteResponse.desde_entidad(
            resultado,
            mensaje=(
                f"El reporte solicitado se generará de forma asíncrona (id_cola={resultado.id_cola}). "
                "Consulte GET /suministros/reportes-gastos/trabajos/{id_cola} para ver el avance."
            ),
        )
    return ReporteGastoResponse.desde_entidad(resultado)


@router.get(
    "/historial",
    response_model=HistorialReportesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Historial de reportes generados por el usuario (RNF de RF-77)",
)
def listar_historial(
    limite: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialReportesResponse:
    use_case = build_listar_historial_reportes_use_case(db)
    reportes = use_case.execute(usuario_actual.id_usuario, limite)
    items = [ReporteGastoResponse.desde_entidad(r) for r in reportes]
    return HistorialReportesResponse(total=len(items), items=items)


@router.get(
    "/trabajos/{id_cola}",
    response_model=EstadoTrabajoReporteResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar el estado de un trabajo async de generación de reporte",
)
def consultar_estado_trabajo(
    id_cola: int,
    db: Session = Depends(get_db),
) -> EstadoTrabajoReporteResponse:
    use_case = build_consultar_estado_trabajo_reporte_use_case(db)
    estado = use_case.execute(id_cola)
    reporte = None
    if estado.ultima_ejecucion is not None and estado.ultima_ejecucion.id_reporte_resultado is not None:
        reporte = build_consultar_reporte_gastos_use_case(db).execute(estado.ultima_ejecucion.id_reporte_resultado)
    return EstadoTrabajoReporteResponse.desde_entidades(estado.trabajo, estado.ultima_ejecucion, reporte)


@router.get(
    "/{id_reporte_gasto_acumulado}",
    response_model=ReporteGastoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar un reporte de gastos ya generado",
)
def consultar_reporte(
    id_reporte_gasto_acumulado: int,
    db: Session = Depends(get_db),
) -> ReporteGastoResponse:
    use_case = build_consultar_reporte_gastos_use_case(db)
    reporte = use_case.execute(id_reporte_gasto_acumulado)
    return ReporteGastoResponse.desde_entidad(reporte)
