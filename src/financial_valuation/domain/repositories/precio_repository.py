# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto del repositorio de precios de mercado de referencia (RF-89, append-only)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.services.precios import Precio


class PrecioRepository(ABC):
    """Puerto de persistencia de precios de mercado."""
    @abstractmethod
    def agregar(self, precio: Precio, region: Optional[str], origen: str, id_usuario: int, estado_inicial: str) -> Precio:
        """Registra el precio y lo devuelve."""
        ...

    @abstractmethod
    def obtener(self, id_precio_mercado: int) -> Optional[Precio]:
        """Devuelve el precio, o ``None``."""
        ...

    @abstractmethod
    def de_especie(self, id_especie: int, categoria: str, id_metrica_produccion: Optional[int] = None) -> list[Precio]:
        """Lista los precios de la especie y categoría."""
        ...

    @abstractmethod
    def listar(self, id_especie: Optional[int]) -> list[Precio]:
        """Lista los precios, opcionalmente de una especie."""
        ...

    @abstractmethod
    def por_vencer(self, desde, hasta) -> list[Precio]:
        """Lista los precios que vencen en el rango."""
        ...
