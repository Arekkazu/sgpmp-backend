# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-60: puerto de ventanas y diagnosticos existentes |
from typing import Protocol
from src.telemetry.domain.entities.secuencia_vision import VentanaVision


class VentanasVisionPort(Protocol):
    def recientes(self, identificador: int, cantidad: int) -> list[VentanaVision]: ...
    def diagnostico_existente(self, identificador: int) -> bool: ...
