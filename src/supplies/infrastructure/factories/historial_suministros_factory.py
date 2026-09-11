"""Fábricas de wiring de RF-81 (Historial/Trazabilidad de Suministros).

Cablean puertos → repositorios/adapters concretos y devuelven use cases
listos. Se usan desde el router, y desde el scheduler async del `main.py`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.database import SessionLocal
from src.supplies.application.use_cases.historial_suministros.consultar_estado_trabajo_historial_use_case import (
    ConsultarEstadoTrabajoHistorialUseCase,
)
from src.supplies.application.use_cases.historial_suministros.consultar_historial_suministros_use_case import (
    ConsultarHistorialSuministrosUseCase,
)
from src.supplies.application.use_cases.historial_suministros.descargar_resultado_trabajo_historial_use_case import (
    DescargarResultadoTrabajoHistorialUseCase,
)
from src.supplies.application.use_cases.historial_suministros.exportar_historial_sincrono_use_case import (
    ExportarHistorialSincronoUseCase,
)
from src.supplies.application.use_cases.historial_suministros.procesar_cola_historial_suministros_use_case import (
    ProcesarColaHistorialSuministrosUseCase,
)
from src.supplies.application.use_cases.historial_suministros.solicitar_trabajo_historial_use_case import (
    SolicitarTrabajoHistorialUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.adapters.alcance_activo_m02_adapter import AlcanceActivoM02Adapter
from src.supplies.infrastructure.repositories.auditoria_suministro_repository import (
    SqlAlchemyAuditoriaSuministroRepository,
)
from src.supplies.infrastructure.repositories.configuracion_batch_historial_repository import (
    SqlAlchemyConfiguracionBatchHistorialRepository,
)
from src.supplies.infrastructure.repositories.fallo_historial_suministro_repository import (
    SqlAlchemyFalloHistorialSuministroRepository,
)
from src.supplies.infrastructure.repositories.historial_suministro_read_repository import (
    SqlAlchemyHistorialSuministroReadRepository,
)
from src.supplies.infrastructure.repositories.trabajo_historial_suministro_repository import (
    SqlAlchemyTrabajoHistorialSuministroRepository,
)


def build_consultar_historial_use_case(db: Session) -> ConsultarHistorialSuministrosUseCase:
    return ConsultarHistorialSuministrosUseCase(
        historial_port=SqlAlchemyHistorialSuministroReadRepository(db),
        alcance_port=AlcanceActivoM02Adapter(db),
        activo_port=ActivoM02Adapter(db),
        config_repo=SqlAlchemyConfiguracionBatchHistorialRepository(db),
        db=db,
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_exportar_historial_use_case(db: Session) -> ExportarHistorialSincronoUseCase:
    return ExportarHistorialSincronoUseCase(
        historial_port=SqlAlchemyHistorialSuministroReadRepository(db),
        alcance_port=AlcanceActivoM02Adapter(db),
        activo_port=ActivoM02Adapter(db),
        config_repo=SqlAlchemyConfiguracionBatchHistorialRepository(db),
        db=db,
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_solicitar_trabajo_historial_use_case(db: Session) -> SolicitarTrabajoHistorialUseCase:
    return SolicitarTrabajoHistorialUseCase(
        db=db,
        trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository(db),
        config_repo=SqlAlchemyConfiguracionBatchHistorialRepository(db),
    )


def build_consultar_estado_trabajo_historial_use_case(db: Session) -> ConsultarEstadoTrabajoHistorialUseCase:
    return ConsultarEstadoTrabajoHistorialUseCase(
        trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository(db)
    )


def build_descargar_resultado_trabajo_historial_use_case(db: Session) -> DescargarResultadoTrabajoHistorialUseCase:
    return DescargarResultadoTrabajoHistorialUseCase(
        trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository(db)
    )


def build_procesar_cola_historial_suministros_use_case(db: Session) -> ProcesarColaHistorialSuministrosUseCase:
    """Construye el worker del motor async. Usa ``SessionLocal`` para las sesiones por trabajo."""
    return ProcesarColaHistorialSuministrosUseCase(
        trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository(db),
        config_repo=SqlAlchemyConfiguracionBatchHistorialRepository(db),
        session_factory=SessionLocal,
        construir_trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository,
        construir_fallo_repo=SqlAlchemyFalloHistorialSuministroRepository,
        construir_consultar=build_consultar_historial_use_case,
        construir_exportar=build_exportar_historial_use_case,
    )
