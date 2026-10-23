# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: contrato de lectura de estado bloqueada |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT


class EstadoDispositivoIoTRepository(ABC):

    def bloquear_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIoT]:
        raise NotImplementedError

    def pertenece_a_fincas(self, id_dispositivo_iot: int, fincas: list[int]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def obtener_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIoT]: ...

    @abstractmethod
    def listar_activos(self) -> List[EstadoDispositivoIoT]: ...

    @abstractmethod
    def guardar(self, estado: EstadoDispositivoIoT) -> EstadoDispositivoIoT: ...

    @abstractmethod
    def actualizar(self, estado: EstadoDispositivoIoT) -> EstadoDispositivoIoT: ...
