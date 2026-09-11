"""Fábricas de wiring de RF-77 (Reporte de Gastos Acumulados).

Cablean puertos → repositorios/adapters concretos y devuelven use cases
listos. Se usan desde el router, y desde el scheduler async del `main.py`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.database import SessionLocal
from src.supplies.application.use_cases.reporte_gastos.consultar_estado_trabajo_reporte_use_case import (
    ConsultarEstadoTrabajoReporteUseCase,
)
from src.supplies.application.use_cases.reporte_gastos.consultar_reporte_gastos_use_case import (
    ConsultarReporteGastosUseCase,
)
from src.supplies.application.use_cases.reporte_gastos.generar_reporte_gastos_use_case import (
    GenerarReporteGastosUseCase,
)
from src.supplies.application.use_cases.reporte_gastos.listar_historial_reportes_use_case import (
    ListarHistorialReportesUseCase,
)
from src.supplies.application.use_cases.reporte_gastos.procesar_cola_reportes_gastos_use_case import (
    ProcesarColaReportesGastosUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.repositories.configuracion_batch_reporte_gasto_repository import (
    SqlAlchemyConfiguracionBatchReporteGastoRepository,
)
from src.supplies.infrastructure.repositories.detalle_gasto_read_repository import (
    SqlAlchemyDetalleGastoReadRepository,
)
from src.supplies.infrastructure.repositories.fallo_reporte_gasto_repository import (
    SqlAlchemyFalloReporteGastoRepository,
)
from src.supplies.infrastructure.repositories.reporte_gasto_repository import SqlAlchemyReporteGastoRepository
from src.supplies.infrastructure.repositories.trabajo_reporte_gasto_repository import (
    SqlAlchemyTrabajoReporteGastoRepository,
)


def build_generar_reporte_gastos_use_case(db: Session) -> GenerarReporteGastosUseCase:
    return GenerarReporteGastosUseCase(
        db=db,
        detalle_port=SqlAlchemyDetalleGastoReadRepository(db),
        activo_port=ActivoM02Adapter(db),
        reporte_repo=SqlAlchemyReporteGastoRepository(db),
        trabajo_repo=SqlAlchemyTrabajoReporteGastoRepository(db),
        config_repo=SqlAlchemyConfiguracionBatchReporteGastoRepository(db),
    )


def build_consultar_reporte_gastos_use_case(db: Session) -> ConsultarReporteGastosUseCase:
    return ConsultarReporteGastosUseCase(reporte_repo=SqlAlchemyReporteGastoRepository(db))


def build_listar_historial_reportes_use_case(db: Session) -> ListarHistorialReportesUseCase:
    return ListarHistorialReportesUseCase(reporte_repo=SqlAlchemyReporteGastoRepository(db))


def build_consultar_estado_trabajo_reporte_use_case(db: Session) -> ConsultarEstadoTrabajoReporteUseCase:
    return ConsultarEstadoTrabajoReporteUseCase(trabajo_repo=SqlAlchemyTrabajoReporteGastoRepository(db))


def build_procesar_cola_reportes_gastos_use_case(db: Session) -> ProcesarColaReportesGastosUseCase:
    """Construye el worker del motor async. Usa ``SessionLocal`` para las sesiones por trabajo."""
    return ProcesarColaReportesGastosUseCase(
        trabajo_repo=SqlAlchemyTrabajoReporteGastoRepository(db),
        config_repo=SqlAlchemyConfiguracionBatchReporteGastoRepository(db),
        session_factory=SessionLocal,
        construir_trabajo_repo=SqlAlchemyTrabajoReporteGastoRepository,
        construir_fallo_repo=SqlAlchemyFalloReporteGastoRepository,
        construir_generador=build_generar_reporte_gastos_use_case,
    )
