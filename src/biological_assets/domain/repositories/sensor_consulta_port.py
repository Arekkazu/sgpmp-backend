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


@dataclass(frozen=True)
class CompatibilidadSensorEspecie:
    """Resultado del catalogo M09 para un par sensor-especie."""

    configurada: bool
    es_compatible: bool
    nombre_especie_activo: str
    especies_compatibles: tuple[str, ...]


class SensorConsultaPort(ABC):
    @abstractmethod
    def obtener_sensor_con_contexto(self, sensor_id: int) -> Optional[SensorConsulta]:
        """Retorna el sensor con su dispositivo y área asociada activa, o None si no existe."""

    @abstractmethod
    def obtener_compatibilidad_especie(
        self,
        sensor_id: int,
        especie_id: int,
    ) -> Optional[CompatibilidadSensorEspecie]:
        """Evalua el par contra la lista blanca de compatibilidad de M09.

        Retorna ``None`` solo si la especie objetivo no existe. ``configurada``
        distingue un sensor sin ninguna parametrizacion de uno incompatible.
        """
