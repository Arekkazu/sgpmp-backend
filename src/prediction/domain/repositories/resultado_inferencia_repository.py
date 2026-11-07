# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: puerto de escritura de resultados del motor IA            |
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia


class ResultadoInferenciaRepository(ABC):
    @abstractmethod
    def obtener(self, id_resultado: uuid.UUID) -> Optional[ResultadoInferencia]: ...

    @abstractmethod
    def guardar(self, resultado: ResultadoInferencia) -> ResultadoInferencia: ...
