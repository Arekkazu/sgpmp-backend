# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio de los periodos de inactividad de dispositivos IoT.

Un periodo se abre cuando el dispositivo deja de reportar y se cierra cuando
vuelve, calculando su duración y diagnóstico.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad


class PeriodoInactividadRepository(ABC):
    """Contrato para abrir, consultar y cerrar periodos de inactividad."""

    @abstractmethod
    def abrir(self, periodo: PeriodoInactividad) -> PeriodoInactividad:
        """Registra el inicio de un periodo de inactividad."""
        ...

    @abstractmethod
    def obtener_abierto_por_dispositivo(self, id_dispositivo_iot: int) -> Optional[PeriodoInactividad]:
        """Devuelve el periodo abierto del dispositivo, o ``None`` si reporta con normalidad."""
        ...

    @abstractmethod
    def cerrar(self, periodo: PeriodoInactividad) -> PeriodoInactividad:
        """Cierra el periodo con su fecha de fin y duración calculada."""
        ...
