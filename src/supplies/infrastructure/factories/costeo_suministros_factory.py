"""Fábricas de wiring de RF-78 (Costeo Directo de Suministros — CU-05).

Cablean puertos → repositorios/adapters concretos y devuelven use cases listos.
Se usan desde ``costeo_suministros_router.py``.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.supplies.application.use_cases.costeo_suministros.consultar_acumulado_ciclo_use_case import (
    ConsultarAcumuladoCicloUseCase,
)
from src.supplies.application.use_cases.costeo_suministros.registrar_correccion_suministro_use_case import (
    RegistrarCorreccionSuministroUseCase,
)
from src.supplies.application.use_cases.costeo_suministros.registrar_suministro_directo_use_case import (
    RegistrarSuministroDirectoUseCase,
)
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.repositories.acumulado_ciclo_repository import (
    SqlAlchemyAcumuladoCicloRepository,
)
from src.supplies.infrastructure.repositories.auditoria_suministro_repository import (
    SqlAlchemyAuditoriaSuministroRepository,
)
from src.supplies.infrastructure.repositories.registro_suministro_repository import (
    SqlAlchemyRegistroSuministroRepository,
)


def build_registrar_suministro_directo_use_case(db: Session) -> RegistrarSuministroDirectoUseCase:
    return RegistrarSuministroDirectoUseCase(
        db=db,
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        ciclo_port=CicloM02Adapter(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_registrar_correccion_suministro_use_case(db: Session) -> RegistrarCorreccionSuministroUseCase:
    return RegistrarCorreccionSuministroUseCase(
        db=db,
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        acumulado_repo=SqlAlchemyAcumuladoCicloRepository(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_consultar_acumulado_ciclo_use_case(db: Session) -> ConsultarAcumuladoCicloUseCase:
    return ConsultarAcumuladoCicloUseCase(
        acumulado_repo=SqlAlchemyAcumuladoCicloRepository(db),
        ciclo_port=CicloM02Adapter(db),
    )
