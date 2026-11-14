# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: 202 automático, archivos y purga   |
"""Fábricas de wiring de RF-81 (Historial/Trazabilidad de Suministros).

Cablean puertos → repositorios/adapters concretos y devuelven use cases
listos. Se usan desde el router, y desde el scheduler async del `main.py`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.database import id_usuario_servicio, sesion_sistema
from src.supplies.application.use_cases.exportacion.purgar_archivos_vencidos_use_case import (
    PurgarArchivosVencidosUseCase,
)
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
from src.supplies.infrastructure.adapters.notificacion_suministros_m01_adapter import (
    NotificacionSuministrosM01Adapter,
)
from src.supplies.infrastructure.repositories.archivo_exportacion_repository import (
    SqlAlchemyArchivoExportacionRepository,
)
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
        solicitar=build_solicitar_trabajo_historial_use_case(db),
    )


def build_exportar_historial_use_case(db: Session) -> ExportarHistorialSincronoUseCase:
    return ExportarHistorialSincronoUseCase(
        historial_port=SqlAlchemyHistorialSuministroReadRepository(db),
        alcance_port=AlcanceActivoM02Adapter(db),
        activo_port=ActivoM02Adapter(db),
        config_repo=SqlAlchemyConfiguracionBatchHistorialRepository(db),
        db=db,
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
        solicitar=build_solicitar_trabajo_historial_use_case(db),
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
        trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository(db),
        archivo_repo=SqlAlchemyArchivoExportacionRepository(db),
    )


def build_purgar_archivos_vencidos_use_case(db: Session) -> PurgarArchivosVencidosUseCase:
    return PurgarArchivosVencidosUseCase(
        db=db,
        archivo_repo=SqlAlchemyArchivoExportacionRepository(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
        id_usuario_sistema=id_usuario_servicio(db),
    )


def build_procesar_cola_historial_suministros_use_case(db: Session) -> ProcesarColaHistorialSuministrosUseCase:
    """Construye el worker del motor async. Usa ``sesion_sistema`` (usuario de servicio, D1) para las sesiones por trabajo."""
    return ProcesarColaHistorialSuministrosUseCase(
        trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository(db),
        config_repo=SqlAlchemyConfiguracionBatchHistorialRepository(db),
        session_factory=sesion_sistema,
        construir_trabajo_repo=SqlAlchemyTrabajoHistorialSuministroRepository,
        construir_fallo_repo=SqlAlchemyFalloHistorialSuministroRepository,
        construir_consultar=build_consultar_historial_use_case,
        construir_exportar=build_exportar_historial_use_case,
        construir_archivo_repo=SqlAlchemyArchivoExportacionRepository,
        construir_notificador=NotificacionSuministrosM01Adapter,
    )
