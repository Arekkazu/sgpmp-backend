# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
"""Puerto del repositorio de precios de mercado de referencia (RF-89, append-only)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.services.precios import Precio


class PrecioRepository(ABC):
    @abstractmethod
    def agregar(self, precio: Precio, region: Optional[str], origen: str, id_usuario: int, estado_inicial: str) -> Precio: ...

    @abstractmethod
    def obtener(self, id_precio_mercado: int) -> Optional[Precio]: ...

    @abstractmethod
    def de_especie(self, id_especie: int, categoria: str, id_metrica_produccion: Optional[int] = None) -> list[Precio]: ...

    @abstractmethod
    def listar(self, id_especie: Optional[int]) -> list[Precio]: ...

    @abstractmethod
    def por_vencer(self, desde, hasta) -> list[Precio]: ...
