# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-39 RF-58: vista por permiso, GRIS sin umbral y anomalías visibles |
"""Puerto del aviso de RF-58 E7: variable que recibe datos sin umbral configurado en M09."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.telemetry.domain.entities.monitoreo import EstadoSensorActual


class AvisoSinUmbralPort(ABC):
    @abstractmethod
    def avisar(self, sensores: list[EstadoSensorActual]) -> int:
        """Avisa al Administrador para que complete la configuración (best-effort).

        Una implementación no repite el aviso del mismo sensor dentro de su ventana y
        nunca propaga un fallo: el dashboard es una lectura. Devuelve cuántos sensores
        avisó.
        """
