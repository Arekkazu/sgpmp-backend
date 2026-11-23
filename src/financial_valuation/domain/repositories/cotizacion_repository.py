# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de las cotizaciones de venta (RF-COT v1.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class CotizacionRepository(ABC):
    """Puerto de persistencia de cotizaciones."""
    @abstractmethod
    def agregar(self, datos: dict) -> int:
        """Registra la cotización y devuelve su id."""
        ...

    @abstractmethod
    def obtener(self, id_cotizacion: int) -> Optional[dict]:
        """Devuelve la cotización, o ``None``."""
        ...

    @abstractmethod
    def actualizar(self, id_cotizacion: int, version: int, cambios: dict) -> bool:
        """Control optimista: False si la versión cambió (RF-COT 5.9, FA-11)."""

    @abstractmethod
    def listar(self, filtros: dict) -> list[dict]:
        """Lista las cotizaciones con filtros."""
        ...

    @abstractmethod
    def vencer(self, hoy: date) -> list[dict]:
        """Vence las cotizaciones caducadas y las devuelve."""
        ...

    @abstractmethod
    def fijar_estado_al_cierre(self, id_periodo_contable: int) -> None:
        """Congela el estado de las cotizaciones al cierre del periodo."""
        ...
