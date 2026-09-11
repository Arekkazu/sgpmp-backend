"""Caso de uso: Consultar umbrales ambientales por especie (Flujo C — RF-17)."""
from __future__ import annotations

from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository


class ConsultarUmbralesUseCase:

    def __init__(self, umbral_repo: UmbralAmbientalRepository) -> None:
        self.umbral_repo = umbral_repo

    def execute(self, id_especie: int, *, solo_activas: bool = False) -> list[UmbralAmbiental]:
        return self.umbral_repo.listar_por_especie(id_especie, solo_activas=solo_activas)
