"""Puerto (ABC) para persistencia de dispositivos IoT (RF-21)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot


class DispositivoIotRepository(ABC):
    """Contrato de acceso a datos para :class:`DispositivoIot`."""

    @abstractmethod
    def obtener_por_id(
        self,
        id_dispositivo_iot: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[DispositivoIot]:
        """Obtiene el dispositivo por id, o ``None`` si no existe o está fuera de
        ``ids_fincas_permitidas``.
        """
        ...

    @abstractmethod
    def obtener_por_serial(self, serial: str) -> Optional[DispositivoIot]:
        """Obtiene el dispositivo por serial, o ``None`` si no existe."""
        ...

    @abstractmethod
    def guardar(self, dispositivo: DispositivoIot) -> DispositivoIot:
        """Inserta el dispositivo y devuelve la entidad con su id asignado."""
        ...

    @abstractmethod
    def actualizar(self, dispositivo: DispositivoIot) -> DispositivoIot:
        """Persiste los cambios del dispositivo y devuelve la entidad actualizada.
        """
        ...

    @abstractmethod
    def listar_por_gateway(self, id_dispositivo_gateway: int) -> list[DispositivoIot]:
        """Dispositivos activos que atiende el Gateway Edge indicado."""
        ...

    @abstractmethod
    def listar(
        self,
        *,
        solo_activos: bool = False,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[DispositivoIot]:
        """Lista dispositivos, opcionalmente solo activos y limitados a las fincas
        permitidas.
        """
        ...
