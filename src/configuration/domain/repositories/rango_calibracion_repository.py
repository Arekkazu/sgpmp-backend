"""Puerto (ABC) para lectura del rango de calibración por tipo de sensor (RF-24)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.rango_calibracion import RangoCalibracion


class RangoCalibracionRepository(ABC):

    @abstractmethod
    def obtener_por_categoria(self, categoria: str) -> Optional[RangoCalibracion]:
        ...

    @abstractmethod
    def listar(self) -> list[RangoCalibracion]:
        ...
