"""Caso de uso: Consultar etapas del ciclo productivo por especie (Flujo D — RF-16)."""
from __future__ import annotations

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository


class ConsultarCiclosUseCase:

    def __init__(self, ciclos_repo: CicloBiologicoRepository) -> None:
        self.ciclos_repo = ciclos_repo

    def execute(self, id_especie: int, *, solo_activas: bool = False) -> list[CicloBiologico]:
        return self.ciclos_repo.listar_por_especie(id_especie, solo_activas=solo_activas)
