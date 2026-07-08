"""Router FastAPI para monitoreo de telemetría IoT (`/iot/monitoreo`).

RF-58 — CU04 Modo tiempo real:
  GET /iot/monitoreo/dashboard                   — Dashboard completo del usuario
  GET /iot/monitoreo/dashboard/{id_infraestructura} — Dashboard por unidad productiva

RF-59 — CU04 Modo histórico:
  GET /iot/monitoreo/historial                   — Historial paginado con filtros
  GET /iot/monitoreo/historial/exportar          — Exportación PDF/Excel (stub M08)

Auth: JWT Bearer + RBAC
  - dashboard: recurso 33 (monitoreo_telemetria), acción 2 (Leer)
  - historial: recurso 34 (historial_telemetria), acción 2 (Leer)
  - exportar:  recurso 34 (historial_telemetria), acción 5 (Ejecutar)
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.errors import ServiceUnavailableError, ValidationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.telemetry.application.use_cases.monitoreo.consultar_historial_use_case import ConsultarHistorialUseCase
from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.domain.entities.monitoreo import FiltrosHistorial
from src.telemetry.infrastructure.adapters.umbral_historico_m09_adapter import UmbralHistoricoM09Adapter
from src.telemetry.infrastructure.repositories.historial_telemetria_repository import SqlAlchemyHistorialTelemetriaRepository
from src.telemetry.infrastructure.repositories.monitoreo_repository import SqlAlchemyMonitoreoRepository
from src.telemetry.infrastructure.schema.monitoreo_schema import (
    DashboardResponseSchema,
    EstadoSensorSchema,
    HistorialPageSchema,
    LecturaHistoricaSchema,
    ResumenEstadisticoSchema,
    ResumenUnidadSchema,
)

router = APIRouter(prefix="/iot/monitoreo", tags=["Telemetría IoT - Monitoreo"])


# ---------------------------------------------------------------------------
# RF-58 — Dashboard en tiempo real
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=DashboardResponseSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(33, 2))],
    summary="Dashboard de monitoreo en tiempo real — todas las unidades (RF-58)",
)
def obtener_dashboard(
    id_infraestructura: Optional[int] = Query(default=None, description="Filtrar por unidad productiva"),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=50, description="Máximo 50 sensores por vista (FA-07)"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardResponseSchema:
    use_case = ObtenerDashboardUseCase(monitoreo_repo=SqlAlchemyMonitoreoRepository(db))
    sensores, resumen, total = use_case.execute(
        id_infraestructura=id_infraestructura,
        pagina=pagina,
        por_pagina=por_pagina,
        id_rol_usuario=usuario_actual.id_rol,
    )
    return DashboardResponseSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        resumen_unidades=[ResumenUnidadSchema.model_validate(u.__dict__) for u in resumen],
        sensores=[EstadoSensorSchema.model_validate(s.__dict__) for s in sensores],
    )


@router.get(
    "/dashboard/{id_infraestructura}",
    response_model=DashboardResponseSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(33, 2))],
    summary="Dashboard de monitoreo filtrado por unidad productiva (RF-58)",
)
def obtener_dashboard_por_unidad(
    id_infraestructura: int,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DashboardResponseSchema:
    use_case = ObtenerDashboardUseCase(monitoreo_repo=SqlAlchemyMonitoreoRepository(db))
    sensores, resumen, total = use_case.execute(
        id_infraestructura=id_infraestructura,
        pagina=pagina,
        por_pagina=por_pagina,
        id_rol_usuario=usuario_actual.id_rol,
    )
    return DashboardResponseSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        resumen_unidades=[ResumenUnidadSchema.model_validate(u.__dict__) for u in resumen],
        sensores=[EstadoSensorSchema.model_validate(s.__dict__) for s in sensores],
    )


# ---------------------------------------------------------------------------
# RF-59 — Historial de lecturas
# ---------------------------------------------------------------------------

@router.get(
    "/historial/exportar",
    status_code=503,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(34, 5))],
    summary="Exportar historial en PDF/Excel — pendiente implementación M08 (RF-59)",
)
def exportar_historial(
    formato: str = Query(description="PDF o EXCEL"),
    fecha_inicio: date = Query(),
    fecha_fin: date = Query(),
    sensor_id: Optional[int] = Query(default=None),
    tipo_variable: Optional[str] = Query(default=None),
    categoria_variable: Optional[str] = Query(default=None),
    id_infraestructura: Optional[int] = Query(default=None),
    especie: Optional[str] = Query(default=None),
    estado_dato: Optional[str] = Query(default=None),
    origen_dato: Optional[str] = Query(default=None),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> None:
    filtros = FiltrosHistorial(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sensor_id=sensor_id,
        tipo_variable=tipo_variable,
        categoria_variable=categoria_variable,
        id_infraestructura=id_infraestructura,
        especie=especie,
        estado_dato=estado_dato,
        origen_dato=origen_dato,
    )
    # FA-11: bloquear exportación sin filtros activos
    if not filtros.tiene_filtro_adicional():
        raise ValidationError(
            code='EXPORTAR_SIN_FILTROS',
            message='Debe aplicar al menos un filtro adicional antes de exportar.',
        )
    # M08 aún no implementado
    raise ServiceUnavailableError(
        code='M08_NO_DISPONIBLE',
        message='El módulo de exportación (M08) no está disponible en este entorno. Reintente más tarde.',
    )


@router.get(
    "/historial",
    response_model=HistorialPageSchema,
    status_code=200,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(34, 2))],
    summary="Consultar historial de lecturas con filtros y paginación (RF-59)",
)
def consultar_historial(
    fecha_inicio: date = Query(description="Fecha inicio del rango (YYYY-MM-DD)"),
    fecha_fin: date = Query(description="Fecha fin del rango (YYYY-MM-DD)"),
    sensor_id: Optional[int] = Query(default=None),
    tipo_variable: Optional[str] = Query(default=None),
    categoria_variable: Optional[str] = Query(default=None),
    id_infraestructura: Optional[int] = Query(default=None),
    especie: Optional[str] = Query(default=None),
    estado_dato: Optional[str] = Query(default=None, description="LECTURA_VALIDA / FUERA_DE_RANGO / ERROR_CALIBRACION"),
    origen_dato: Optional[str] = Query(default=None, description="TIEMPO_REAL / BUFFER_LOCAL / EDGE_AGREGADO"),
    incluir_alertas: bool = Query(default=False),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=100, ge=1, le=500),
    orden: str = Query(default='DESC', description="ASC o DESC"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialPageSchema:
    if orden.upper() not in ('ASC', 'DESC'):
        raise ValidationError(code='ORDEN_INVALIDO', message="El parámetro 'orden' debe ser ASC o DESC.")

    filtros = FiltrosHistorial(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sensor_id=sensor_id,
        tipo_variable=tipo_variable,
        categoria_variable=categoria_variable,
        id_infraestructura=id_infraestructura,
        especie=especie,
        estado_dato=estado_dato,
        origen_dato=origen_dato,
        incluir_alertas=incluir_alertas,
        pagina=pagina,
        por_pagina=por_pagina,
        orden=orden.upper(),
    )

    use_case = ConsultarHistorialUseCase(
        historial_repo=SqlAlchemyHistorialTelemetriaRepository(db),
        umbral_port=UmbralHistoricoM09Adapter(),
    )
    lecturas, estadisticas, total, metadatos = use_case.execute(filtros)

    return HistorialPageSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        paginas_totales=metadatos['total_paginas'],
        filtros_aplicados=metadatos['filtros_aplicados'],
        rango_real_datos=metadatos['rango_real_datos'],
        items=[LecturaHistoricaSchema.model_validate(l.__dict__) for l in lecturas],
        estadisticas=[ResumenEstadisticoSchema.model_validate(e.__dict__) for e in estadisticas],
    )
