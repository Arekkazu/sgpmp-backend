# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Ciclos productivos de una especie con sus fases (RF-16)."""
from __future__ import annotations

from src.configuration.domain.entities.ciclo_productivo import CicloProductivo
from src.configuration.domain.repositories.ciclo_productivo_repository import CicloProductivoRepository


class ListarCiclosProductivosUseCase:
    def __init__(self, ciclos: CicloProductivoRepository) -> None:
        self.ciclos = ciclos

    def execute(self, id_especie: int) -> list[CicloProductivo]:
        return self.ciclos.listar_por_especie(id_especie)
