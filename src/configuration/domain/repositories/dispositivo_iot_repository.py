"""Puerto (ABC) para persistencia de dispositivos IoT (RF-21)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot


class DispositivoIotRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_dispositivo_iot: int) -> Optional[DispositivoIot]:
        ...

    @abstractmethod
    def obtener_por_serial(self, serial: str) -> Optional[DispositivoIot]:
        ...

    @abstractmethod
    def guardar(self, dispositivo: DispositivoIot) -> DispositivoIot:
        ...

    @abstractmethod
    def actualizar(self, dispositivo: DispositivoIot) -> DispositivoIot:
        ...

    @abstractmethod
    def listar(self, *, solo_activos: bool = False) -> list[DispositivoIot]:
        ...
