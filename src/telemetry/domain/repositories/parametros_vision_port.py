# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-62: puerto de snapshot de calidad de vision |
from typing import Protocol
from src.telemetry.domain.entities.calidad_vision import ParametrosCalidadVision
from src.telemetry.domain.entities.secuencia_vision import ParametrosVentanasVision


class ParametrosVisionPort(Protocol):
    def obtener(self, fps_configurado: int) -> ParametrosCalidadVision: ...
    def obtener_ventanas(self) -> ParametrosVentanasVision: ...
