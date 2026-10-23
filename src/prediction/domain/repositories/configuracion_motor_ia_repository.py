# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-36 RF-65: lectura con bloqueo e historial append-only |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA
from src.prediction.domain.entities.version_configuracion_motor import VersionConfiguracionMotor


class ConfiguracionMotorIARepository(ABC):
    @abstractmethod
    def obtener_por_tipo(self, tipo_modelo: str, *, bloquear: bool = False) -> Optional[ConfiguracionMotorIA]:
        """``bloquear`` toma la fila hasta el commit: dos ediciones concurrentes no
        pueden leer la misma ``config_version`` (RF-65 CA-9)."""

    @abstractmethod
    def listar(self) -> list[ConfiguracionMotorIA]: ...

    @abstractmethod
    def guardar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA: ...

    @abstractmethod
    def actualizar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA: ...

    @abstractmethod
    def listar_historial(self, id_configuracion_motor: int) -> list[VersionConfiguracionMotor]:
        """Versiones anteriores (log append-only de DB-14), de la más reciente a la más antigua."""
