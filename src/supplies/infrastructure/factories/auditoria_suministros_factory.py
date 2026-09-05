"""Factory de wiring para los use cases de la bitácora de auditoría de M05 (RF-80, CU-06)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.supplies.application.use_cases.auditoria.consultar_auditoria_suministros_use_case import (
    ConsultarAuditoriaSuministrosUseCase,
)
from src.supplies.application.use_cases.auditoria.exportar_auditoria_suministros_use_case import (
    ExportarAuditoriaSuministrosUseCase,
)
from src.supplies.infrastructure.repositories.auditoria_suministro_read_repository import (
    SqlAlchemyAuditoriaSuministroReadRepository,
)


def build_consultar_auditoria_use_case(db: Session) -> ConsultarAuditoriaSuministrosUseCase:
    return ConsultarAuditoriaSuministrosUseCase(read_port=SqlAlchemyAuditoriaSuministroReadRepository(db))


def build_exportar_auditoria_use_case(db: Session) -> ExportarAuditoriaSuministrosUseCase:
    return ExportarAuditoriaSuministrosUseCase(read_port=SqlAlchemyAuditoriaSuministroReadRepository(db))
