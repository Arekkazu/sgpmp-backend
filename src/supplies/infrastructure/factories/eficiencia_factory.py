"""Fábricas de wiring del CU-02 (RF-74).

Cablean puertos → repositorios/adapters concretos y devuelven use cases listos.
Se usan desde los routers, desde los workers del batch (una sesión por activo) y
desde el scheduler nocturno. Concentrar el wiring evita duplicarlo.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.database import SessionLocal
from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.application.use_cases.eficiencia.ejecutar_batch_ica_use_case import (
    EjecutarBatchICAUseCase,
)
from src.supplies.application.use_cases.eficiencia.interrumpir_batch_ica_use_case import (
    InterrumpirBatchICAUseCase,
)
from src.supplies.application.use_cases.eficiencia.reintentar_ica_manual_use_case import (
    ReintentarICAManualUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.adapters.activos_batch_m02_adapter import ActivosBatchM02Adapter
from src.supplies.infrastructure.adapters.alerta_ica_m03_adapter import AlertaICAM03Adapter
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.adapters.pesaje_m02_adapter import PesajeM02Adapter
from src.supplies.infrastructure.repositories.cola_calculo_ica_repository import (
    SqlAlchemyColaCalculoICARepository,
)
from src.supplies.infrastructure.repositories.configuracion_batch_ica_repository import (
    SqlAlchemyConfiguracionBatchICARepository,
)
from src.supplies.infrastructure.repositories.consumo_ica_read_repository import (
    SqlAlchemyConsumoICAReadRepository,
)
from src.supplies.infrastructure.repositories.ejecucion_batch_ica_repository import (
    SqlAlchemyEjecucionBatchICARepository,
)
from src.supplies.infrastructure.repositories.fallo_calculo_ica_repository import (
    SqlAlchemyFalloCalculoICARepository,
)
from src.supplies.infrastructure.repositories.resultado_ica_repository import (
    SqlAlchemyResultadoICARepository,
)


def build_calcular_ica_use_case(db: Session) -> CalcularICAUseCase:
    """Construye el use case núcleo de cálculo ICA con todas sus dependencias."""
    return CalcularICAUseCase(
        db=db,
        resultado_repo=SqlAlchemyResultadoICARepository(db),
        consumo_read_port=SqlAlchemyConsumoICAReadRepository(db),
        pesaje_port=PesajeM02Adapter(db),
        activo_port=ActivoM02Adapter(db),
        ciclo_port=CicloM02Adapter(db),
        alerta_port=AlertaICAM03Adapter(db),
    )


def build_ejecutar_batch_use_case(db: Session) -> EjecutarBatchICAUseCase:
    """Construye el motor batch ICA. Usa ``SessionLocal`` para las sesiones por activo."""
    return EjecutarBatchICAUseCase(
        db=db,
        ejecucion_repo=SqlAlchemyEjecucionBatchICARepository(db),
        cola_repo=SqlAlchemyColaCalculoICARepository(db),
        config_repo=SqlAlchemyConfiguracionBatchICARepository(db),
        activos_batch_port=ActivosBatchM02Adapter(db),
        resultado_repo=SqlAlchemyResultadoICARepository(db),
        session_factory=SessionLocal,
        construir_calculo=build_calcular_ica_use_case,
        construir_fallo_repo=SqlAlchemyFalloCalculoICARepository,
    )


def build_interrumpir_batch_use_case(db: Session) -> InterrumpirBatchICAUseCase:
    return InterrumpirBatchICAUseCase(
        db=db, ejecucion_repo=SqlAlchemyEjecucionBatchICARepository(db)
    )


def build_reintentar_ica_use_case(db: Session) -> ReintentarICAManualUseCase:
    return ReintentarICAManualUseCase(
        db=db,
        calcular_uc=build_calcular_ica_use_case(db),
        fallo_repo=SqlAlchemyFalloCalculoICARepository(db),
    )
