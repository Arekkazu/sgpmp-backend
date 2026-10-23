# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: 202 del RF, exportación y descarga |
"""Router FastAPI de RF-77 — Reporte de Gastos Acumulados.

  POST /suministros/reportes-gastos                         — Generar (200, o 202 si es asíncrono)
  POST /suministros/reportes-gastos/{id}/exportacion        — Exportar a PDF/CSV (archivo de 24 h)
  GET  /suministros/reportes-gastos/exportaciones/{id}      — Descargar (410 si venció)
  GET  /suministros/reportes-gastos/historial               — Historial de reportes del usuario
  GET  /suministros/reportes-gastos/{id}/regenerar          — Regenerar con los parámetros guardados
  GET  /suministros/reportes-gastos/trabajos/{id_cola}      — Estado de un trabajo async
  GET  /suministros/reportes-gastos/{id_reporte}            — Consultar un reporte generado

RBAC: recurso 51 (`reporte_gastos_suministros`). E=5 (generar/exportar), R=2 (consultar).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import TrabajoReporteGasto
from src.supplies.infrastructure.dto.generar_reporte_gastos_dto import (
    ExportarReporteGastosDTO,
    GenerarReporteGastosDTO,
)
from src.supplies.infrastructure.factories.reporte_gastos_factory import (
    build_consultar_estado_trabajo_reporte_use_case,
    build_consultar_reporte_gastos_use_case,
    build_exportar_reporte_gastos_use_case,
    build_generar_reporte_gastos_use_case,
    build_listar_historial_reportes_use_case,
)
from src.supplies.infrastructure.schema.reporte_gasto_schema import (
    ArchivoExportacionResponse,
    EstadoTrabajoReporteResponse,
    HistorialReportesResponse,
    ReporteGastoResponse,
    TrabajoReporteResponse,
)

router = APIRouter(prefix="/suministros/reportes-gastos", tags=["Suministros - Reporte de Gastos (RF-77)"])

_RECURSO = 51
_PREFIJO_DESCARGA = "/suministros/reportes-gastos/exportaciones"


@router.post(
    "",
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        202: {"model": TrabajoReporteResponse},
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Generar el reporte de gastos acumulados (RF-77) — 200 o 202 asíncrono",
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
    resultado = use_case.execute(filtros, usuario_actual, dto.formato_exportacion)

    if isinstance(resultado, TrabajoReporteGasto):
        response.status_code = 202
        minutos = use_case.tiempo_estimado_minutos()
        if filtros.es_agregado:
            mensaje = (
                f"La consulta involucra {filtros.meses} meses, lo que supera el límite de procesamiento "
                "sincrónico. El reporte se generará de forma asíncrona. Recibirá una notificación cuando esté "
                f"disponible. Tiempo estimado: {minutos} minutos."
            )
        else:
            mensaje = (
                f"El reporte solicitado cubre un período de {filtros.meses} meses y se generará de forma "
                "asíncrona. Recibirá una notificación cuando esté disponible para descarga. "
                f"Tiempo estimado: {minutos} minutos."
            )
        return TrabajoReporteResponse.desde_entidad(resultado, mensaje=mensaje)

    respuesta = ReporteGastoResponse.desde_entidad(resultado)
    if dto.formato_exportacion:
        archivo = build_exportar_reporte_gastos_use_case(db).execute(
            resultado.id_reporte_gasto_acumulado, dto.formato_exportacion, usuario_actual, reporte=resultado
        )
        respuesta.archivo = ArchivoExportacionResponse.desde_entidad(archivo, _PREFIJO_DESCARGA)
    return respuesta


@router.post(
    "/{id_reporte_gasto_acumulado}/exportacion",
    response_model=ArchivoExportacionResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Exportar un reporte de gastos a PDF o CSV (RF-77 paso 8, E6)",
)
def exportar_reporte(
    id_reporte_gasto_acumulado: int,
    dto: ExportarReporteGastosDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ArchivoExportacionResponse:
    archivo = build_exportar_reporte_gastos_use_case(db).execute(
        id_reporte_gasto_acumulado, dto.formato_exportacion, usuario_actual
    )
    return ArchivoExportacionResponse.desde_entidad(archivo, _PREFIJO_DESCARGA)


@router.get(
    "/exportaciones/{id_archivo}",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               410: {"model": ErrorResponse}},
    summary="Descargar un archivo exportado de RF-77 (vigencia 24 h, E6d)",
)
def descargar_exportacion(
    id_archivo: UUID,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    archivo = build_exportar_reporte_gastos_use_case(db).descargar(id_archivo, usuario_actual)
    return StreamingResponse(
        iter([archivo.contenido]),
        media_type=archivo.tipo_contenido,
        headers={"Content-Disposition": f'attachment; filename="{archivo.nombre_archivo}"'},
    )


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
    "/{id_reporte_gasto_acumulado}/regenerar",
    response_model=ReporteGastoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Regenerar un reporte del historial con los datos actuales (RNF de RF-77)",
)
def regenerar_reporte(
    id_reporte_gasto_acumulado: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReporteGastoResponse:
    reporte, advertencia = build_consultar_reporte_gastos_use_case(db).regenerar(
        id_reporte_gasto_acumulado, usuario_actual
    )
    respuesta = ReporteGastoResponse.desde_entidad(reporte)
    respuesta.advertencia = advertencia
    return respuesta


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
