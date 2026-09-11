"""Caso de uso: Consultar catálogo de variables ambientales activas (RF-17)."""
from __future__ import annotations

from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository


class ListarVariablesAmbientalesUseCase:

    def __init__(self, variable_repo: VariableAmbientalRepository) -> None:
        self.variable_repo = variable_repo

    def execute(self) -> list[VariableAmbiental]:
        return self.variable_repo.listar_activas()
