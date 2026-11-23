# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-36 RF-65: concurrencia optimista (config_version) e historial append-only |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de la configuración del motor de IA."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA


class ConfiguracionMotorIARepository(ABC):
    """Puerto de persistencia de la configuración del motor."""
    @abstractmethod
    def obtener_por_tipo(self, tipo_modelo: str, *, bloquear: bool = False) -> Optional[ConfiguracionMotorIA]:
        """bloquear=True toma la fila hasta el commit (RF-65 CA-9: dos ediciones no se cruzan)."""

    @abstractmethod
    def listar(self) -> list[ConfiguracionMotorIA]:
        """Lista todas las configuraciones."""
        ...

    @abstractmethod
    def guardar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA:
        """Guarda una configuración nueva."""
        ...

    @abstractmethod
    def actualizar(self, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIA:
        """Actualiza la configuración."""
        ...
