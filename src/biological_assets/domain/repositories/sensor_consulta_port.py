from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SensorConsulta:
    id_sensor: int
    nombre: str
    es_activo: bool
    id_dispositivo_iot: int
    dispositivo_es_activo: bool
    id_infraestructura_dispositivo: int
    categoria: Optional[str] = None
    id_infraestructura_area: Optional[int] = None  # de sensores_areas_asociadas activa


class SensorConsultaPort(ABC):
    @abstractmethod
    def obtener_sensor_con_contexto(self, sensor_id: int) -> Optional[SensorConsulta]:
        """Retorna el sensor con su dispositivo y área asociada activa, o None si no existe."""
