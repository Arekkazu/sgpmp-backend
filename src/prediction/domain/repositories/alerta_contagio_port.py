# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.riesgo_contagio import ResultadoRiesgoContagio


class AlertaContagioPort(ABC):
    """Puente a RF-57: alerta RIESGO_CONTAGIO del lote."""

    @abstractmethod
    def area_del_lote(self, id_lote: int) -> Optional[int]:
        """Área productiva (id_infraestructura) del lote, o None si no existe."""

    @abstractmethod
    def emitir(self, resultado: ResultadoRiesgoContagio) -> int:
        """Crea la alerta, o consolida la que el lote ya tenga activa. Devuelve su id (sin commit)."""
