# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-05 | Arekkazu | M06 RF-88: eventos sanitarios del activo para elegir el del deterioro |
"""Puerto de lectura de M02/M09 para M06: el activo, su finca y su titular."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.entities.activo_financiero import DatosActivo


class ActivoFinancieroPort(ABC):
    @abstractmethod
    def obtener(self, id_activo_biologico: int) -> Optional[DatosActivo]: ...

    @abstractmethod
    def listar_sin_reconocimiento(self) -> list[DatosActivo]:
        """Activos visibles para el usuario sin reconocimiento CONFIRMADO (propuestas de RF-82)."""

    @abstractmethod
    def listar_reconocidos(self, numero_id_tributaria: str) -> list[DatosActivo]:
        """Activos ACTIVO/EN_TRATAMIENTO del titular con reconocimiento CONFIRMADO (cierre, RF-87)."""

    @abstractmethod
    def especie(self, id_especie: int) -> Optional[dict]: ...

    @abstractmethod
    def metrica_produccion(self, id_metrica_produccion: int) -> Optional[dict]:
        """Producto de RF-43 (nombre y unidad de medida) de un evento productivo."""

    @abstractmethod
    def evento_sanitario_del_activo(self, id_evento: int, id_activo_biologico: int) -> bool: ...

    @abstractmethod
    def eventos_sanitarios_del_activo(self, id_activo_biologico: int) -> list[dict]:
        """Eventos sanitarios del activo (fecha, tipo y diagnóstico), para elegir el que sustenta un deterioro."""