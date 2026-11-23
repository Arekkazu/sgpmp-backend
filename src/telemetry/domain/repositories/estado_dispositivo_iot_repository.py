# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: contrato de lectura de estado bloqueada |
# | 2026-10-24 | Arekkazu | USAB-M03 M3-10 RF-60: listado de dispositivos con estado |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia del estado de comunicación de los dispositivos IoT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.telemetry.domain.entities.dispositivo_con_estado import DispositivoConEstado
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT


class EstadoDispositivoIoTRepository(ABC):
    """Puerto de persistencia del estado de los dispositivos IoT."""

    def bloquear_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIoT]:
        """Devuelve el estado del dispositivo bloqueando su fila."""
        raise NotImplementedError

    def pertenece_a_fincas(self, id_dispositivo_iot: int, fincas: list[int]) -> bool:
        """Indica si el dispositivo pertenece a alguna de las fincas."""
        raise NotImplementedError

    def listar_con_estado(
        self, ids_fincas_permitidas: Optional[list[int]], estado: Optional[str] = None,
    ) -> list[DispositivoConEstado]:
        """Dispositivos activos con estado, batería y señal; primero los que fallan."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIoT]:
        """Devuelve el estado del dispositivo, o None."""
        ...

    @abstractmethod
    def listar_activos(self) -> List[EstadoDispositivoIoT]:
        """Lista el estado de los dispositivos activos."""
        ...

    @abstractmethod
    def guardar(self, estado: EstadoDispositivoIoT) -> EstadoDispositivoIoT:
        """Guarda un estado nuevo."""
        ...

    @abstractmethod
    def actualizar(self, estado: EstadoDispositivoIoT) -> EstadoDispositivoIoT:
        """Actualiza un estado existente."""
        ...
