# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: outbox a M06, sin consolidar manual |
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
from src.supplies.application.use_cases.provision_nic41.despachar_provisiones_m06_use_case import (
    DespacharProvisionesM06UseCase,
)
from src.shared.database import id_usuario_servicio, sesion_sistema
from src.supplies.infrastructure.adapters.ciclo_m02_adapter import CicloM02Adapter
from src.supplies.infrastructure.adapters.notificacion_suministros_m01_adapter import (
    NotificacionSuministrosM01Adapter,
)
from src.supplies.infrastructure.adapters.provision_m06_adapter import ProvisionM06Adapter
from src.supplies.infrastructure.repositories.acumulado_ciclo_repository import (
    SqlAlchemyAcumuladoCicloRepository,
)
from src.supplies.infrastructure.repositories.auditoria_suministro_repository import (
    SqlAlchemyAuditoriaSuministroRepository,
)
from src.supplies.infrastructure.repositories.outbox_provision_m06_repository import (
    SqlAlchemyOutboxProvisionM06Repository,
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
        outbox_repo=SqlAlchemyOutboxProvisionM06Repository(db),
        notificador=NotificacionSuministrosM01Adapter(db),
    )


def build_corregir_provision_use_case(db: Session) -> CorregirProvisionUseCase:
    return CorregirProvisionUseCase(
        db=db,
        provision_repo=SqlAlchemyProvisionNic41Repository(db),
        consolidar=build_consolidar_ciclo_use_case(db),
    )


def build_despachar_provisiones_m06_use_case(db: Session) -> DespacharProvisionesM06UseCase:
    """Despachador del outbox hacia M06; corre como usuario de servicio (tarea de fondo)."""
    return DespacharProvisionesM06UseCase(
        db=db,
        outbox_repo=SqlAlchemyOutboxProvisionM06Repository(db),
        provision_repo=SqlAlchemyProvisionNic41Repository(db),
        auditoria_port=SqlAlchemyAuditoriaSuministroRepository(db),
        m06_port=ProvisionM06Adapter(sesion_sistema),
        notificador=NotificacionSuministrosM01Adapter(db),
        id_usuario_sistema=id_usuario_servicio(db),
    )


def build_consultar_provision_use_case(db: Session) -> ConsultarProvisionUseCase:
    return ConsultarProvisionUseCase(provision_repo=SqlAlchemyProvisionNic41Repository(db))


def build_listar_versiones_provision_use_case(db: Session) -> ListarVersionesProvisionUseCase:
    return ListarVersionesProvisionUseCase(provision_repo=SqlAlchemyProvisionNic41Repository(db))
