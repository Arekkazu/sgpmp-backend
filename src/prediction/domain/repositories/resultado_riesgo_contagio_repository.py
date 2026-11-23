# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de resultados de riesgo de contagio."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.riesgo_contagio import ResultadoRiesgoContagio


class ResultadoRiesgoContagioRepository(ABC):
    """Puerto de persistencia de resultados de riesgo de contagio."""

    @abstractmethod
    def guardar(self, resultado: ResultadoRiesgoContagio) -> ResultadoRiesgoContagio:
        """Paso 9: persiste el resultado vinculado al lote (historial RF-67, auditoría RF-73)."""

    @abstractmethod
    def ultimos_por_lote(self, id_lote: int, cantidad: int) -> list[ResultadoRiesgoContagio]:
        """Los últimos cálculos del lote, del más reciente al más antiguo."""

    @abstractmethod
    def asociar_alerta(self, id_resultado: int, id_alerta: int) -> None:
        """Deja el id de la alerta RF-57 en el snapshot del resultado."""
