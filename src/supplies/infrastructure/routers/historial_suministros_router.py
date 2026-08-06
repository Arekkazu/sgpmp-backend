"""Router FastAPI de RF-81 — Historial/Trazabilidad de Suministros.

  GET  /suministros/historial                       — Consulta paginada (nivel 1, síncrona)
  GET  /suministros/historial/exportar               — Exportación CSV síncrona (<= 10.000)
  POST /suministros/historial/trabajos                — Encolar CONSULTA_PESADA | EXPORTACION
  GET  /suministros/historial/trabajos/{id_cola}      — Estado de un trabajo async
  GET  /suministros/historial/trabajos/{id_cola}/descargar — Descargar resultado de exportación

RBAC: recurso 52 (`historial_suministros`). R=2 (lecturas), E=5 (encolar trabajo pesado).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro
from src.supplies.domain.value_objects.historial_suministro_enums import (
    OrigenPrecioFiltro,
    TipoSuministroFiltro,
    TipoTrabajoHistorial,
)
from src.supplies.infrastructure.dto.solicitar_trabajo_historial_dto import SolicitarTrabajoHistorialDTO
from src.supplies.infrastructure.factories.historial_suministros_factory import (
    build_consultar_estado_trabajo_historial_use_case,
    build_consultar_historial_use_case,
    build_descargar_resultado_trabajo_historial_use_case,
    build_exportar_historial_use_case,
    build_solicitar_trabajo_historial_use_case,
)
from src.supplies.infrastructure.schema.historial_suministro_schema import (
    EstadoTrabajoHistorialResponse,
    HistorialSuministroListResponse,
    LineaHistorialResponse,
    ResumenHistorialResponse,
    TrabajoHistorialResponse,
)

router = APIRouter(prefix="/suministros/historial", tags=["Suministros - Historial de Suministros (RF-81)"])

_RECURSO = 52


def _filtros_desde_query(
    id_activo_biologico: int,
    id_ciclo_productivo: Optional[int],
    fecha_inicio_filtro: Optional[date],
    fecha_fin_filtro: Optional[date],
    tipo_suministro_filtro: TipoSuministroFiltro,
    origen_precio_filtro: OrigenPrecioFiltro,
    costo_min: Optional[Decimal],
    costo_max: Optional[Decimal],
    pagina: int,
    registros_por_pagina: int,
) -> FiltrosHistorialSuministro:
    return FiltrosHistorialSuministro(
        id_activo_biologico=id_activo_biologico,
        id_ciclo_productivo=id_ciclo_productivo,
        fecha_inicio_filtro=fecha_inicio_filtro,
        fecha_fin_filtro=fecha_fin_filtro,
        tipo_suministro_filtro=tipo_suministro_filtro.value,
        origen_precio_filtro=origen_precio_filtro.value,
        costo_min=costo_min,
        costo_max=costo_max,
        pagina=pagina,
        registros_por_pagina=min(registros_por_pagina, 200),
    )


@router.get(
    "",
    response_model=HistorialSuministroListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Consultar el historial de suministros de un activo (RF-81, síncrono nivel 1)",
)
def consultar_historial(
    id_activo_biologico: int = Query(gt=0),
    id_ciclo_productivo: Optional[int] = Query(default=None, gt=0),
    fecha_inicio_filtro: Optional[date] = Query(default=None),
    fecha_fin_filtro: Optional[date] = Query(default=None),
    tipo_suministro_filtro: TipoSuministroFiltro = Query(default=TipoSuministroFiltro.TODOS),
    origen_precio_filtro: OrigenPrecioFiltro = Query(default=OrigenPrecioFiltro.TODOS),
    costo_min: Optional[Decimal] = Query(default=None, ge=0),
    costo_max: Optional[Decimal] = Query(default=None, ge=0),
    pagina: int = Query(default=1, ge=1),
    registros_por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialSuministroListResponse:
    filtros = _filtros_desde_query(
        id_activo_biologico, id_ciclo_productivo, fecha_inicio_filtro, fecha_fin_filtro,
        tipo_suministro_filtro, origen_precio_filtro, costo_min, costo_max, pagina, registros_por_pagina,
    )
    use_case = build_consultar_historial_use_case(db)
    resultado = use_case.execute(filtros, id_usuario=usuario_actual.id_usuario, id_rol=usuario_actual.id_rol)
    return HistorialSuministroListResponse(
        items=[LineaHistorialResponse.desde_entidad(l) for l in resultado.lineas],
        resumen=ResumenHistorialResponse.desde_entidad(resultado.resumen),
    )


@router.get(
    "/exportar",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Exportar el historial en CSV, vía síncrona (RF-81, <= 10.000 registros)",
)
def exportar_historial(
    id_activo_biologico: int = Query(gt=0),
    id_ciclo_productivo: Optional[int] = Query(default=None, gt=0),
    fecha_inicio_filtro: Optional[date] = Query(default=None),
    fecha_fin_filtro: Optional[date] = Query(default=None),
    tipo_suministro_filtro: TipoSuministroFiltro = Query(default=TipoSuministroFiltro.TODOS),
    origen_precio_filtro: OrigenPrecioFiltro = Query(default=OrigenPrecioFiltro.TODOS),
    costo_min: Optional[Decimal] = Query(default=None, ge=0),
    costo_max: Optional[Decimal] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    filtros = _filtros_desde_query(
        id_activo_biologico, id_ciclo_productivo, fecha_inicio_filtro, fecha_fin_filtro,
        tipo_suministro_filtro, origen_precio_filtro, costo_min, costo_max, 1, 200,
    )
    use_case = build_exportar_historial_use_case(db)
    contenido, nombre_archivo, _total = use_case.execute(
        filtros, id_usuario=usuario_actual.id_usuario, id_rol=usuario_actual.id_rol
    )
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.post(
    "/trabajos",
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    summary="Encolar un trabajo pesado de historial (CONSULTA_PESADA o EXPORTACION)",
)
def solicitar_trabajo(
    dto: SolicitarTrabajoHistorialDTO,
    response: Response,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TrabajoHistorialResponse:
    filtros = FiltrosHistorialSuministro(
        id_activo_biologico=dto.id_activo_biologico,
        id_ciclo_productivo=dto.id_ciclo_productivo,
        fecha_inicio_filtro=dto.fecha_inicio_filtro,
        fecha_fin_filtro=dto.fecha_fin_filtro,
        tipo_suministro_filtro=dto.tipo_suministro_filtro.value,
        origen_precio_filtro=dto.origen_precio_filtro.value,
        costo_min=dto.costo_min,
        costo_max=dto.costo_max,
        registros_por_pagina=dto.registros_por_pagina,
    )
    use_case = build_solicitar_trabajo_historial_use_case(db)
    trabajo = use_case.execute(
        dto.tipo_trabajo.value, filtros, usuario_actual.id_usuario, usuario_actual.id_rol
    )
    response.status_code = 202
    mensaje = (
        f"El trabajo {dto.tipo_trabajo.value} fue encolado (id_cola={trabajo.id_cola}). "
        "Consulte GET /suministros/historial/trabajos/{id_cola} para ver el avance."
    )
    return TrabajoHistorialResponse.desde_entidad(trabajo, mensaje)


@router.get(
    "/trabajos/{id_cola}",
    response_model=EstadoTrabajoHistorialResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar el estado de un trabajo pesado de historial",
)
def consultar_estado_trabajo(id_cola: int, db: Session = Depends(get_db)) -> EstadoTrabajoHistorialResponse:
    use_case = build_consultar_estado_trabajo_historial_use_case(db)
    estado = use_case.execute(id_cola)
    return EstadoTrabajoHistorialResponse.desde_entidades(estado.trabajo, estado.ultima_ejecucion)


@router.get(
    "/trabajos/{id_cola}/descargar",
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Descargar el resultado de una exportación async ya completada",
)
def descargar_resultado(id_cola: int, db: Session = Depends(get_db)) -> StreamingResponse:
    use_case = build_descargar_resultado_trabajo_historial_use_case(db)
    contenido, nombre_archivo = use_case.execute(id_cola)
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
