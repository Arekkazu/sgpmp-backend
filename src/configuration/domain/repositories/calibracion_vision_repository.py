"""Puertos de persistencia de la calibración por visión (RF-24 v2.0, RFC-011)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.calibracion_vision import CalibracionVision, LineaBaseVision


class CalibracionVisionRepository(ABC):
    """Contrato del historial de intentos de calibración por visión."""

    @abstractmethod
    def guardar(self, calibracion: CalibracionVision) -> CalibracionVision:
        """Registra un intento (exitoso o no) en el historial inmutable."""
        raise NotImplementedError

    @abstractmethod
    def listar_por_area(self, id_infraestructura: int) -> list[CalibracionVision]:
        """Historial del área, el intento más reciente primero."""
        raise NotImplementedError


class LineaBaseVisionRepository(ABC):
    """Contrato de la línea base vigente por (área, especie)."""

    @abstractmethod
    def obtener_vigente(self, id_infraestructura: int, id_especie: int) -> Optional[LineaBaseVision]:
        """Línea base vigente del par (área, especie), o ``None`` si nunca se calibró.
        """
        raise NotImplementedError

    @abstractmethod
    def publicar(self, linea_base: LineaBaseVision) -> LineaBaseVision:
        """Reemplaza la línea base vigente del par (área, especie), o la crea."""
        raise NotImplementedError
