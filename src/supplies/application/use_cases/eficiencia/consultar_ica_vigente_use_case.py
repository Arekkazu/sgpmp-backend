"""Caso de uso: consultar el resultado ICA vigente de un activo/período (RF-74, Flujo B).

Si no hay resultado (FA-03) devuelve ``None``; el router responde 200 con un mensaje
"sin resultado", no un 404.
"""
from __future__ import annotations

from typing import Optional

from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.repositories.resultado_ica_repository import ResultadoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


class ConsultarICAVigenteUseCase:
    def __init__(self, resultado_repo: ResultadoICARepository) -> None:
        self.resultado_repo = resultado_repo

    def execute(
        self, id_activo_biologico: int, periodo: PeriodoEvaluacion
    ) -> Optional[ResultadoICA]:
        return self.resultado_repo.obtener_vigente(id_activo_biologico, periodo)
