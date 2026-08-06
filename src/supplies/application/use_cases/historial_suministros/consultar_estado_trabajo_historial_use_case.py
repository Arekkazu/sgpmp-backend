"""Caso de uso: consultar el estado de un trabajo pesado de historial (RF-81).

Polling del cliente tras recibir un HTTP 202 con ``id_cola`` (E7/FA-09 de RF-81).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.trabajo_historial_suministro import (
    EjecucionHistorialSuministro,
    TrabajoHistorialSuministro,
)
from src.supplies.domain.repositories.trabajo_historial_suministro_repository import (
    TrabajoHistorialSuministroRepository,
)


@dataclass(frozen=True)
class EstadoTrabajoHistorial:
    trabajo: TrabajoHistorialSuministro
    ultima_ejecucion: Optional[EjecucionHistorialSuministro]


class ConsultarEstadoTrabajoHistorialUseCase:
    def __init__(self, trabajo_repo: TrabajoHistorialSuministroRepository) -> None:
        self.trabajo_repo = trabajo_repo

    def execute(self, id_cola: int) -> EstadoTrabajoHistorial:
        trabajo = self.trabajo_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="TRABAJO_NO_ENCONTRADO",
                message=f"El trabajo de historial {id_cola} no existe.",
                field="id_cola",
            )
        ultima_ejecucion = self.trabajo_repo.obtener_ultima_ejecucion(id_cola)
        return EstadoTrabajoHistorial(trabajo=trabajo, ultima_ejecucion=ultima_ejecucion)
