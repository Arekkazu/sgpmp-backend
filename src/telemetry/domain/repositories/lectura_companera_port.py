# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: lectura de la variable compañera de una regla compuesta |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto para obtener lecturas compañeras usadas en reglas compuestas."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class LecturaCompanera:
    """Última lectura válida de otra variable del mismo área o dispositivo."""
    id_telemetria: int
    id_sensor: int
    tipo_variable: str
    valor: Decimal
    timestamp_captura: datetime


class LecturaCompaneraPort(ABC):
    """Puerto para buscar la lectura compañera más reciente."""
    @abstractmethod
    def ultima_lectura_valida(self, tipo_variable: str, id_infraestructura: Optional[int],
                              id_dispositivo: Optional[int], momento: datetime,
                              ventana_min: int) -> Optional[LecturaCompanera]:
        """Lectura LECTURA_VALIDA de ``tipo_variable`` más cercana a ``momento`` (± ventana) en la
        misma área (o el mismo dispositivo si no hay área), o ``None``."""
