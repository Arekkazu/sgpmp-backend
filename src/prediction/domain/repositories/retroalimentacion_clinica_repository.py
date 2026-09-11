from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.retroalimentacion_clinica import RetroalimentacionClinica


class RetroalimentacionClinicaRepository(ABC):
    @abstractmethod
    def guardar(self, entidad: RetroalimentacionClinica) -> RetroalimentacionClinica: ...

    @abstractmethod
    def obtener_por_resultado_y_usuario(
        self, id_resultado: uuid.UUID, id_usuario: int
    ) -> Optional[RetroalimentacionClinica]: ...

    @abstractmethod
    def listar_por_resultado(
        self, id_resultado: uuid.UUID
    ) -> list[RetroalimentacionClinica]: ...
