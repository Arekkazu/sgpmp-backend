# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: puerto de escritura de resultados del motor IA            |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de resultados de inferencia."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia


class ResultadoInferenciaRepository(ABC):
    """Puerto de persistencia de resultados de inferencia."""
    @abstractmethod
    def obtener(self, id_resultado: uuid.UUID) -> Optional[ResultadoInferencia]:
        """Devuelve el resultado, o ``None``."""
        ...

    @abstractmethod
    def guardar(self, resultado: ResultadoInferencia) -> ResultadoInferencia:
        """Guarda el resultado."""
        ...
