# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: definir lectura del histórico de ocupación sin exponer registros técnicos. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de ocupación histórica de lotes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.prediction.domain.entities.ocupacion_lote import MuestraOcupacion


class OcupacionLotePort(ABC):
    """Puerto para obtener las muestras de ocupación de un lote."""
    @abstractmethod
    def obtener_muestras(self, id_lote: int, *, desde: datetime, hasta: datetime) -> list[MuestraOcupacion]:
        """Estados dentro de la ventana y último previo; solo del lote accesible."""
