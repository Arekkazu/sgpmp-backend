"""Puerto (ABC) para lectura de tipos de dispositivo IoT y sus rangos (RF-23)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot


class TipoDispositivoIotRepository(ABC):
    """Contrato de lectura del catálogo de tipos de dispositivo IoT."""

    @abstractmethod
    def obtener_por_id(self, id_tipo_dispositivo: int) -> Optional[TipoDispositivoIot]:
        """Obtiene el tipo de dispositivo por id, o ``None`` si no existe."""
        ...

    @abstractmethod
    def listar(self) -> list[TipoDispositivoIot]:
        """Todos los tipos de dispositivo con sus rangos."""
        ...
