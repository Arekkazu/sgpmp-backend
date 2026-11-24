# | Fecha      | Nombre   | Que se hizo                                       |
# |------------|----------|---------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: reportes propios con su estado y partes |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: «Mis reportes» — los últimos reportes del usuario con su estado y las partes descargables."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from src.reporting.domain.repositories.solicitud_reporte_repository import SolicitudReporteRepository
from src.reporting.domain.reportes.catalogo import CATALOGO
from src.reporting.domain.reportes.solicitud import EXPIRADO, GENERADO

_LIMITE = 50


class ListarReportesUseCase:
    """Lista los reportes solicitados por el usuario."""

    def __init__(self, repo: SolicitudReporteRepository) -> None:
        self.repo = repo

    def execute(self, id_usuario: int, ahora: Optional[datetime] = None) -> list[dict[str, Any]]:
        """Lista los reportes recientes del usuario con su estado."""
        ahora = ahora or datetime.now(timezone.utc)
        salida = []
        for s in self.repo.listar_por_usuario(id_usuario, _LIMITE):
            vencida = s.vencida(ahora)
            partes = self.repo.listar_archivos(s.id_solicitud_reporte) if s.estado == GENERADO and not vencida else []
            salida.append({"solicitud": s, "titulo": CATALOGO[s.tipo_reporte].titulo,
                           "estado": EXPIRADO if vencida else s.estado, "partes": partes})
        return salida
