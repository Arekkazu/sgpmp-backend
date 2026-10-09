"""Puerto de lectura del estado de conexión de dispositivos IoT (M03), usado en RF-49.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class EstadoDispositivoIot:
    """Último contacto conocido de un dispositivo IoT."""
    id_dispositivo_iot: int
    fecha_ultimo_contacto: Optional[datetime]


class DispositivoIotEstadoPort(ABC):
    """Consulta a M03 del último contacto de un dispositivo, para advertir si está fuera
    de línea.
    """

    @abstractmethod
    def obtener_estado(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIot]:
        """Retorna el último contacto conocido del dispositivo (M03), o None si M03 nunca lo evaluó."""
