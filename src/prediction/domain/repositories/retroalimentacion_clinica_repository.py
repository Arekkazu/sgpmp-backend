# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: conteo de retroalimentaciones nuevas por modelo individual  |
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
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

    @abstractmethod
    def contar_nuevas_por_tipo_modelo(
        self, tipos_modelo: list[str]
    ) -> dict[str, tuple[int, Optional[datetime]]]:
        """``{tipo_modelo: (resultados retroalimentados después de su última versión, fecha de esa
        versión o None)}``. Cada resultado cuenta una vez y solo retroalimentaciones ACTIVAS."""
