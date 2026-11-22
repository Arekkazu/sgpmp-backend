# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: activos por especie y carga del área (RFC-012) |
"""Puerto para verificar dependencias activas de un área antes de desactivarla (RF-20 FA-04)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class InfraestructuraDependencyPort(ABC):
    """Puerto que consulta dependencias de un área (activos, sensores) antes de
    desactivarla o cambiar su especie.
    """

    @abstractmethod
    def tiene_dependencias_activas(self, id_infraestructura: int) -> bool:
        """Retorna True si el área tiene dispositivos IoT o activos biológicos activos."""
        raise NotImplementedError

    @abstractmethod
    def contar_activos_por_especie(self, id_infraestructura: int) -> dict[int, int]:
        """RFC-012: activos vigentes alojados en el área, por ``id_especie``."""
        raise NotImplementedError

    @abstractmethod
    def calcular_carga(self, id_infraestructura: int) -> int:
        """RFC-012: Σ individuos vigentes del área (INDIVIDUAL cuenta 1, POBLACIONAL su cantidad)."""
        raise NotImplementedError
