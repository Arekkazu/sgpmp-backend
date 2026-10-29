"""Puerto ``CamaraAreaRepository`` — cámaras asociadas a un área (RF-21 v2.0 / RF-22)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot


class CamaraAreaRepository(ABC):
    """Contrato de lectura de las cámaras instaladas en un área."""

    @abstractmethod
    def listar_por_area(self, id_infraestructura: int) -> list[DispositivoIot]:
        """Dispositivos de categoría CAMARA instalados en el área, activos o no."""
        raise NotImplementedError
