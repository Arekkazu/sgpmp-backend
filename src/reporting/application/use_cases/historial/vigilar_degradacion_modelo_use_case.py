# | Fecha      | Nombre   | Que se hizo                                                               |
# |------------|----------|---------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-106: aviso al Administrador cuando la TVCO del modelo baja del umbral |
"""Caso de uso: tras registrar una retroalimentación clínica, revisa la tasa de validación del modelo (RF-106,
dependencia con RF-105).

Si la TVCO de los últimos 90 días queda bajo el umbral configurado en M09 (``umbral_tvco_degradacion``), avisa a
los Administradores con una ADVERTENCIA. Con menos de 10 inferencias validadas no hay muestra suficiente y no se
avisa; tampoco se repite el aviso en el mismo día."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

MUESTRA_MINIMA = 10
DIAS_MUESTRA = 90
UMBRAL_POR_DEFECTO = 60


class TasaValidacionPort(ABC):

    @abstractmethod
    def tvco_global(self, dias: int) -> tuple[Optional[float], int]:
        """(porcentaje, inferencias validadas sin conflicto) del modelo en los últimos ``dias``."""

    @abstractmethod
    def umbral(self) -> Optional[float]: ...

    @abstractmethod
    def avisado_hoy(self) -> bool: ...

    @abstractmethod
    def avisar_administradores(self, mensaje: str, detalle: dict) -> None: ...


class VigilarDegradacionModeloUseCase:

    def __init__(self, puerto: TasaValidacionPort) -> None:
        self.puerto = puerto

    def execute(self) -> bool:
        """``True`` si avisó. Nunca propaga errores: el registro de la retroalimentación ya quedó guardado."""
        try:
            porcentaje, validadas = self.puerto.tvco_global(DIAS_MUESTRA)
            umbral = self.puerto.umbral() or UMBRAL_POR_DEFECTO
            if porcentaje is None or validadas < MUESTRA_MINIMA or porcentaje >= umbral or self.puerto.avisado_hoy():
                return False
            self.puerto.avisar_administradores(
                f"La tasa de validación clínica del modelo de predicción bajó a {porcentaje:g} % (umbral {umbral:g} %) "
                f"según las evaluaciones de los veterinarios de los últimos {DIAS_MUESTRA} días. Revisa el desempeño "
                "del modelo y considera reentrenarlo.",
                {"tvco": porcentaje, "umbral": umbral, "validadas": validadas, "dias": DIAS_MUESTRA})
            return True
        except Exception:
            logger.exception("RF-106: no se pudo revisar la degradación del modelo.")
            return False
