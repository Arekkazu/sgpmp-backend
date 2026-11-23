# | Fecha      | Nombre   | Que se hizo                                           |
# |------------|----------|-------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: borrar los archivos vencidos (48 h)       |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: borra el contenido de los reportes con más de 48 h y los deja EXPIRADOS (RNF-04)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.reporting.domain.repositories.solicitud_reporte_repository import SolicitudReporteRepository


class ExpirarReportesUseCase:
    """Expira los reportes generados cuya vigencia terminó."""

    def __init__(self, db: Session, repo: SolicitudReporteRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, ahora: Optional[datetime] = None, limite: int = 200) -> int:
        """Expira hasta ``limite`` reportes vencidos y devuelve cuántos expiró."""
        ahora = ahora or datetime.now(timezone.utc)
        try:
            vencidas = self.repo.tomar_vencidas(ahora, limite)
            for solicitud in vencidas:
                self.repo.borrar_contenido(solicitud.id_solicitud_reporte)
                solicitud.expirar(ahora)
                self.repo.guardar(solicitud)
            self.db.commit()
            return len(vencidas)
        except Exception:
            self.db.rollback()
            raise
