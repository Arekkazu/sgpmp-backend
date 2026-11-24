# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: Consultar patologías asociadas a una especie (Flujo H — RF-16)."""
from __future__ import annotations

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository


class ConsultarPatologiasUseCase:
    """Lista las patologías de una especie, opcionalmente solo las activas."""

    def __init__(self, especie_patologia_repo: EspeciePatologiaRepository) -> None:
        self.especie_patologia_repo = especie_patologia_repo

    def execute(self, id_especie: int, *, solo_activas: bool = False) -> list[EspeciePatologia]:
        """Lista las patologías de la especie."""
        return self.especie_patologia_repo.listar_por_especie(id_especie, solo_activas=solo_activas)
