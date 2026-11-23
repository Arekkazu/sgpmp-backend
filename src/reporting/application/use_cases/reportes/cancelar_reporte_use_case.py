# | Fecha      | Nombre   | Que se hizo                                         |
# |------------|----------|-----------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: cancelar un reporte en segundo plano    |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: el usuario cancela un reporte que todavía se genera en segundo plano (estado CANCELADO)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.reporting.domain.repositories.solicitud_reporte_repository import SolicitudReporteRepository
from src.reporting.domain.reportes.solicitud import SolicitudReporte
from src.shared.errors import NotFoundError


class CancelarReporteUseCase:
    """Cancela un reporte en proceso del usuario."""

    def __init__(self, db: Session, repo: SolicitudReporteRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, id_reporte: UUID, id_usuario: int) -> SolicitudReporte:
        """Cancela el reporte y lo devuelve.

        Raises:
            NotFoundError: Si el reporte no existe.
        """
        try:
            solicitud = self.repo.obtener(id_reporte, bloquear=True)
            if solicitud is None:
                raise NotFoundError(code="REPORTE_INEXISTENTE", message="Ese reporte no existe.", field="id_reporte")
            solicitud.cancelar(id_usuario)
            solicitud = self.repo.guardar(solicitud)
            self.db.commit()
            return solicitud
        except Exception:
            self.db.rollback()
            raise
