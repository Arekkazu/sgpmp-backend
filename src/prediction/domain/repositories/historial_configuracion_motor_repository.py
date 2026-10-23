# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.historial_configuracion_motor import VersionConfiguracionMotor


class HistorialConfiguracionMotorRepository(ABC):
    """Lectura del log append-only de la configuración del motor (RF-65 Restricción 5).

    Solo lectura: las filas las escribe el trigger de DB-14 en cada UPDATE/DELETE.
    """

    @abstractmethod
    def listar_por_tipo(self, tipo_modelo: str) -> list[VersionConfiguracionMotor]:
        """Versiones reemplazadas del tipo_modelo, de la más reciente a la más antigua."""
