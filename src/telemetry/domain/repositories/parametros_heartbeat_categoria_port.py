# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04 RF-60: puerto de lectura de parámetros de heartbeat y ventanas de visión |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.parametros_heartbeat_categoria import ConfiguracionHeartbeatLeida, VentanaObservada


class ParametrosHeartbeatCategoriaPort(ABC):

    @abstractmethod
    def leer_configuracion(self) -> ConfiguracionHeartbeatLeida:
        """Valores guardados en ``modulo4.parametros_mlops`` y RF-18; nunca lanza por ausencia."""

    @abstractmethod
    def parametros_ventanas(self) -> tuple[Optional[int], Optional[object], Optional[int]]:
        """(ventanas consecutivas, cobertura mínima, duración en s); None lo que no esté configurado."""

    @abstractmethod
    def categoria_dispositivo(self, id_dispositivo_iot: int, ids_fincas: Optional[list[int]]) -> Optional[str]:
        """Categoría del dispositivo si existe en el alcance del usuario; None si no."""

    @abstractmethod
    def ventanas_recientes(self, id_dispositivo_iot: int, cantidad: int) -> list[VentanaObservada]:
        """Las ``cantidad`` ventanas más recientes de la cámara, de la más nueva a la más vieja."""
