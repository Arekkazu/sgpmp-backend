# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: aristas activas de una finca               |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso del listado de aristas de transmisión."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.domain.repositories.arista_transmision_repository import AristaTransmisionRepository
from src.shared.errors import NotFoundError


class ListarAristasTransmisionUseCase:
    """Lista las aristas de transmisión de una finca."""

    def __init__(self, arista_repo: AristaTransmisionRepository) -> None:
        self.arista_repo = arista_repo

    def execute(self, id_finca: int, ids_fincas_permitidas: Optional[list[int]] = None) -> list[AristaTransmision]:
        """Lista las aristas activas de la finca si es visible."""
        if ids_fincas_permitidas is not None and id_finca not in ids_fincas_permitidas:
            raise NotFoundError(code="FINCA_NO_ENCONTRADA", message=f"No existe la finca {id_finca}.",
                                field="id_finca")
        return self.arista_repo.listar_activas_por_finca(id_finca)
