"""Caso de uso: Consultar catálogo de especies productivas (Flujo E — RF-15).

Disponible para cualquier usuario autenticado. Permite filtrar por estado
activo/inactivo para que el Administrador vea el catálogo completo y el
Ingeniero de Campo solo las especies disponibles.
"""
from __future__ import annotations

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.especie_repository import EspecieRepository


class ConsultarCatalogoUseCase:
    """Retorna el listado de especies, ordenadas por nombre."""

    def __init__(self, especies_repo: EspecieRepository) -> None:
        self.especies_repo = especies_repo

    def execute(self, *, solo_activas: bool = False) -> list[Especie]:
        return self.especies_repo.listar(solo_activas=solo_activas)
