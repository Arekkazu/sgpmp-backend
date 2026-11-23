# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: Consultar catálogo de tipos de área (RF-20)."""
from __future__ import annotations

from src.configuration.domain.entities.tipo_area import TipoArea
from src.configuration.domain.repositories.tipo_area_repository import TipoAreaRepository


class ListarTiposAreaUseCase:
    """Retorna el catálogo de tipos de área, ordenado por nombre."""

    def __init__(self, tipo_area_repo: TipoAreaRepository) -> None:
        self.tipo_area_repo = tipo_area_repo

    def execute(self, *, solo_activos: bool = False) -> list[TipoArea]:
        """Lista los tipos de área."""
        return self.tipo_area_repo.listar(solo_activos=solo_activos)
