# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
"""Puerto de la cadena de trazabilidad telemetría → evento → valoración → asiento (RF-91)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.entities.contabilidad import LineaAsiento


class TrazabilidadRepository(ABC):
    @abstractmethod
    def eslabones(self, linea: LineaAsiento) -> dict:
        """Hechos verificables de la cadena de la línea (existencia y coherencia de cada eslabón)."""

    @abstractmethod
    def registrar_verificacion(self, id_linea: int, estado: str, tipo_evidencia: str, eslabones: dict,
                               id_usuario: Optional[int]) -> None: ...

    @abstractmethod
    def cadena(self, id_linea: int) -> Optional[dict]: ...
