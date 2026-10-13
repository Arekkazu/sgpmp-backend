"""Caso de uso: ciclos productivos en los que una métrica es producto (RF-43 E-04)."""
from __future__ import annotations

from src.configuration.domain.entities.ciclo_metrica import CicloMetrica
from src.configuration.domain.repositories.ciclo_metrica_repository import CicloMetricaRepository
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.shared.errors import NotFoundError


class ConsultarCiclosMetricaUseCase:
    """Ciclos productivos de la especie de la métrica, marcados si la habilitan."""

    def __init__(self, metricas_repo: MetricaProduccionRepository, ciclos_repo: CicloMetricaRepository) -> None:
        self.metricas_repo = metricas_repo
        self.ciclos_repo = ciclos_repo

    def execute(self, id_metrica_produccion: int) -> list[CicloMetrica]:
        metrica = self.metricas_repo.obtener_por_id(id_metrica_produccion)
        if metrica is None:
            raise NotFoundError(
                code="METRICA_NO_ENCONTRADA",
                message=f"No existe una métrica con ID {id_metrica_produccion}.",
            )
        return self.ciclos_repo.listar_por_metrica(id_metrica_produccion, metrica.id_especie)
