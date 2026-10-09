"""Puerto (ABC) para lectura del rango de calibración por tipo de sensor (RF-24)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.rango_calibracion import RangoCalibracion


class RangoCalibracionRepository(ABC):
    """Contrato de lectura de rangos de calibración por tipo de sensor."""

    @abstractmethod
    def obtener_por_categoria(self, categoria: str) -> Optional[RangoCalibracion]:
        """Rango de calibración del tipo de sensor, o ``None`` si no está configurado.
        """
        ...

    @abstractmethod
    def listar(self) -> list[RangoCalibracion]:
        """Todos los rangos de calibración configurados."""
        ...
