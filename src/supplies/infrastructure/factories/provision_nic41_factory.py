"""Fábricas de wiring de RF-79 (Provisión NIC-41 — CU-05).

Cablean puertos → repositorios/adapters concretos y devuelven use cases listos.
Se usan desde ``provision_nic41_router.py``.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.supplies.application.use_cases.provision_nic41.consolidar_ciclo_use_case import (
    ConsolidarCicloUseCase,
)
from src.supplies.application.use_cases.provision_nic41.consultar_provision_use_case import (
    ConsultarProvisionUseCase,
    ListarVersionesProvisionUseCase,
)
from src.supplies.application.use_cases.provision_nic41.corregir_provision_use_case import (
    CorregirProvisionUseCase,
)
from src.supplies.application.use_cases.provision_nic41.generar_provision_manual_use_case import (
    GenerarProvisionManualUseCase,
)
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.repositories.acumulado_ciclo_repository import (
    SqlAlchemyAcumuladoCicloRepository,
)
from src.supplies.infrastructure.repositories.auditoria_suministro_repository import (
    SqlAlchemyAuditoriaSuministroRepository,
)
from src.supplies.infrastructure.repositories.provision_nic41_repository import (
    SqlAlchemyProvisionNic41Repository,
)
from src.supplies.infrastructure.repositories.registro_suministro_repository import (
    SqlAlchemyRegistroSuministroRepository,
)


def build_consolidar_ciclo_use_case(db: Session) -> ConsolidarCicloUseCase:
    return ConsolidarCicloUseCase(
        db=db,
        ciclo_port=CicloM02Adapter(db),
        acumulado_repo=SqlAlchemyAcumuladoCicloRepository(db),
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        provision_repo=SqlAlchemyProvisionNic41Repository(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_generar_provision_manual_use_case(db: Session) -> GenerarProvisionManualUseCase:
    return GenerarProvisionManualUseCase(
        db=db,
        acumulado_repo=SqlAlchemyAcumuladoCicloRepository(db),
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        provision_repo=SqlAlchemyProvisionNic41Repository(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_corregir_provision_use_case(db: Session) -> CorregirProvisionUseCase:
    return CorregirProvisionUseCase(
        db=db,
        acumulado_repo=SqlAlchemyAcumuladoCicloRepository(db),
        registro_repo=SqlAlchemyRegistroSuministroRepository(db),
        provision_repo=SqlAlchemyProvisionNic41Repository(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
    )


def build_consultar_provision_use_case(db: Session) -> ConsultarProvisionUseCase:
    return ConsultarProvisionUseCase(provision_repo=SqlAlchemyProvisionNic41Repository(db))


def build_listar_versiones_provision_use_case(db: Session) -> ListarVersionesProvisionUseCase:
    return ListarVersionesProvisionUseCase(provision_repo=SqlAlchemyProvisionNic41Repository(db))
