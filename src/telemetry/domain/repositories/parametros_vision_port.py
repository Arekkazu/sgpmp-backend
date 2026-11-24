# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-62: puerto de snapshot de calidad de vision |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio para obtener los parámetros de calidad de visión (RF-62).

Expone los umbrales de calidad de imagen y los de las ventanas de secuencia,
sin acoplar el dominio a la configuración concreta.
"""
from typing import Protocol
from src.telemetry.domain.entities.calidad_vision import ParametrosCalidadVision
from src.telemetry.domain.entities.secuencia_vision import ParametrosVentanasVision


class ParametrosVisionPort(Protocol):
    """Contrato de parámetros de calidad y ventanas de visión."""

    def obtener(self, fps_configurado: int) -> ParametrosCalidadVision:
        """Devuelve los umbrales de calidad para la tasa de cuadros configurada."""
        ...

    def obtener_ventanas(self) -> ParametrosVentanasVision:
        """Devuelve los parámetros de las ventanas de secuencia de visión."""
        ...
