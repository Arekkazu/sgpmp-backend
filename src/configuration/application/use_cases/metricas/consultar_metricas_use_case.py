"""Caso de uso: Consultar métricas de producción por especie (Flujo L — RF-16)."""
from __future__ import annotations

from src.configuration.domain.entities.metrica_produccion import MetricaProduccion
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository


class ConsultarMetricasUseCase:

    def __init__(self, metricas_repo: MetricaProduccionRepository) -> None:
        self.metricas_repo = metricas_repo

    def execute(self, id_especie: int, *, solo_activas: bool = False) -> list[MetricaProduccion]:
        return self.metricas_repo.listar_por_especie(id_especie, solo_activas=solo_activas)
