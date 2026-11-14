# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: definir lectura del histórico de ocupación sin exponer registros técnicos. |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.prediction.domain.entities.ocupacion_lote import MuestraOcupacion


class OcupacionLotePort(ABC):
    @abstractmethod
    def obtener_muestras(self, id_lote: int, *, desde: datetime, hasta: datetime) -> list[MuestraOcupacion]:
        """Estados dentro de la ventana y último previo; solo del lote accesible."""
