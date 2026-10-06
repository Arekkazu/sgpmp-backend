"""Puerto para verificar dependencias activas de un área antes de desactivarla (RF-20 FA-04)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class InfraestructuraDependencyPort(ABC):

    @abstractmethod
    def tiene_dependencias_activas(self, id_infraestructura: int) -> bool:
        """Retorna True si el área tiene dispositivos IoT o activos biológicos activos."""
        raise NotImplementedError

    @abstractmethod
    def contar_activos_de_otra_especie(self, id_infraestructura: int, id_especie: int) -> tuple[int, Optional[str]]:
        """RF-20 v1.1: activos vigentes alojados en el área cuya especie no es ``id_especie``.

        Devuelve (cantidad, nombre de la especie más frecuente entre ellos).
        """
        raise NotImplementedError
