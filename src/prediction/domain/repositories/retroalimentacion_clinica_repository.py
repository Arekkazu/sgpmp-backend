# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: conteo de retroalimentaciones nuevas por modelo individual  |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de retroalimentación clínica."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.retroalimentacion_clinica import RetroalimentacionClinica


class RetroalimentacionClinicaRepository(ABC):
    """Puerto de persistencia de retroalimentación clínica."""
    @abstractmethod
    def guardar(self, entidad: RetroalimentacionClinica) -> RetroalimentacionClinica:
        """Guarda la retroalimentación."""
        ...

    @abstractmethod
    def obtener_por_resultado_y_usuario(
        self, id_resultado: uuid.UUID, id_usuario: int
    ) -> Optional[RetroalimentacionClinica]:
        """Devuelve la retroalimentación del usuario sobre el resultado, o ``None``."""
        ...

    @abstractmethod
    def listar_por_resultado(
        self, id_resultado: uuid.UUID
    ) -> list[RetroalimentacionClinica]:
        """Lista las retroalimentaciones del resultado."""
        ...

    @abstractmethod
    def contar_nuevas_por_tipo_modelo(
        self, tipos_modelo: list[str]
    ) -> dict[str, tuple[int, Optional[datetime]]]:
        """``{tipo_modelo: (resultados retroalimentados después de su última versión, fecha de esa
        versión o None)}``. Cada resultado cuenta una vez y solo retroalimentaciones ACTIVAS."""
