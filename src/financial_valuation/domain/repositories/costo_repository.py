# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
"""Puerto de los costos del activo (RF-90 v2.0) y de la bandeja de provisiones de M05 (RF-79)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision


class CostoRepository(ABC):
    @abstractmethod
    def agregar(self, datos: dict) -> int: ...

    @abstractmethod
    def obtener(self, id_registro_costo: int) -> Optional[dict]: ...

    @abstractmethod
    def clasificar(self, id_registro_costo: int, naturaleza: str, politica: Optional[str], vehiculo: str,
                   cuenta_debito: Optional[str], cuenta_credito: Optional[str], justificacion: str) -> None: ...

    @abstractmethod
    def factura_registrada(self, tercero_nit: str, factura_prefijo: Optional[str], factura_numero: str) -> Optional[dict]: ...

    @abstractmethod
    def listar(self, filtros: dict) -> list[dict]: ...

    @abstractmethod
    def del_periodo(self, id_periodo_contable: int, filtros: Optional[dict] = None) -> list[dict]: ...

    @abstractmethod
    def pendientes_clasificacion(self, id_periodo_contable: int) -> list[dict]: ...

    @abstractmethod
    def recepciones_pendientes(self, limite: int) -> list[tuple[int, RecepcionProvision]]: ...

    @abstractmethod
    def marcar_recepcion(self, id_recepcion: int, resultado: str) -> None: ...

    @abstractmethod
    def recepciones_pendientes_titular(self, numero_id_tributaria: str, hasta: date) -> int: ...

    @abstractmethod
    def fecha_aplicacion_m05(self, id_registro_suministro: str) -> Optional[date]: ...
