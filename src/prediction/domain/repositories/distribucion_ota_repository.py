# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-204-G43/207-G46 RF-70: modo PROGRAMADO espera su ventana (E1) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de distribuciones OTA."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.distribucion_ota import DistribucionOta


class DistribucionOtaRepository(ABC):
    """``modulo4.distribuciones_ota`` (DB-04, DEV-15)."""

    @abstractmethod
    def guardar(self, entidad: DistribucionOta) -> DistribucionOta:
        """Guarda la distribución."""
        ...

    @abstractmethod
    def obtener_por_id(self, id_distribucion: int, *, bloquear: bool = False) -> Optional[DistribucionOta]:
        """Devuelve la distribución, opcionalmente bloqueada, o ``None``."""
        ...

    @abstractmethod
    def actualizar(self, entidad: DistribucionOta) -> DistribucionOta:
        """Actualiza la distribución."""
        ...

    @abstractmethod
    def listar_programadas_en_ventana(self, ahora: datetime) -> list[DistribucionOta]:
        """Distribuciones PROGRAMADO en curso cuya ventana contiene ``ahora`` (RF-70 E1)."""
