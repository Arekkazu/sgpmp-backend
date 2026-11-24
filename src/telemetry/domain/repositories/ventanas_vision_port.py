# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-60: puerto de ventanas y diagnosticos existentes |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio para consultar ventanas de visión y diagnósticos existentes.

Permite recuperar las ventanas recientes de un dispositivo y saber si una
ventana ya tiene diagnóstico, evitando reprocesarla.
"""
from typing import Protocol
from src.telemetry.domain.entities.secuencia_vision import VentanaVision


class VentanasVisionPort(Protocol):
    """Contrato de acceso a ventanas de secuencia y sus diagnósticos."""

    def recientes(self, identificador: int, cantidad: int) -> list[VentanaVision]:
        """Devuelve las últimas ``cantidad`` ventanas del identificador indicado."""
        ...

    def diagnostico_existente(self, identificador: int) -> bool:
        """Indica si la ventana ya cuenta con un diagnóstico registrado."""
        ...
