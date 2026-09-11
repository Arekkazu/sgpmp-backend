"""Caso de uso: consultar el historial de resultados ICA de un activo (RF-74, Flujo B).

Devuelve todos los resultados (vigente + no vigentes), opcionalmente filtrados por
período. El reemplazo del vigente convierte el anterior en histórico (``es_vigente=false``).
"""
from __future__ import annotations

from typing import Optional

from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.repositories.resultado_ica_repository import ResultadoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


class ConsultarHistorialICAUseCase:
    def __init__(self, resultado_repo: ResultadoICARepository) -> None:
        self.resultado_repo = resultado_repo

    def execute(
        self, id_activo_biologico: int, periodo: Optional[PeriodoEvaluacion] = None
    ) -> list[ResultadoICA]:
        return self.resultado_repo.listar_historial(id_activo_biologico, periodo)
