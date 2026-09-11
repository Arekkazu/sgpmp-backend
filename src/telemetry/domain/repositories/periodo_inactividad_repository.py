from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad


class PeriodoInactividadRepository(ABC):

    @abstractmethod
    def abrir(self, periodo: PeriodoInactividad) -> PeriodoInactividad: ...

    @abstractmethod
    def obtener_abierto_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[PeriodoInactividad]: ...

    @abstractmethod
    def cerrar(self, periodo: PeriodoInactividad) -> PeriodoInactividad: ...
