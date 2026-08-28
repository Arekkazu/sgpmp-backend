"""Puerto (ABC) para lectura de tipos de dispositivo IoT y sus rangos (RF-23)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot


class TipoDispositivoIotRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_tipo_dispositivo: int) -> Optional[TipoDispositivoIot]:
        ...

    @abstractmethod
    def listar(self) -> list[TipoDispositivoIot]:
        ...
