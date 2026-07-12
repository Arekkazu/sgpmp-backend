from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.despliegue_ota import DespliegueOta


class DespliegueOtaRepository(ABC):
    @abstractmethod
    def obtener_por_version(
        self,
        id_version: int,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
    ) -> list[DespliegueOta]: ...

    @abstractmethod
    def listar(
        self,
        id_version: Optional[int] = None,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DespliegueOta], int]: ...

    @abstractmethod
    def obtener_por_id(self, id_despliegue: int) -> Optional[DespliegueOta]: ...
