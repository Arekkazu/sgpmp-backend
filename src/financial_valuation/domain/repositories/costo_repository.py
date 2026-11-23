# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de los costos del activo (RF-90 v2.0) y de la bandeja de provisiones de M05 (RF-79)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision


class CostoRepository(ABC):
    """Puerto de persistencia de costos de activos."""
    @abstractmethod
    def agregar(self, datos: dict) -> int:
        """Registra un costo y devuelve su id."""
        ...

    @abstractmethod
    def obtener(self, id_registro_costo: int) -> Optional[dict]:
        """Devuelve el costo, o ``None``."""
        ...

    @abstractmethod
    def clasificar(self, id_registro_costo: int, naturaleza: str, politica: Optional[str], vehiculo: str,
                   cuenta_debito: Optional[str], cuenta_credito: Optional[str], justificacion: str) -> None:
        """Guarda la clasificación del costo."""
        ...

    @abstractmethod
    def factura_registrada(self, tercero_nit: str, factura_prefijo: Optional[str], factura_numero: str) -> Optional[dict]:
        """Devuelve el costo con esa factura del tercero, o ``None``."""
        ...

    @abstractmethod
    def listar(self, filtros: dict) -> list[dict]:
        """Lista los costos con filtros."""
        ...

    @abstractmethod
    def del_periodo(self, id_periodo_contable: int, filtros: Optional[dict] = None) -> list[dict]:
        """Lista los costos del periodo."""
        ...

    @abstractmethod
    def pendientes_clasificacion(self, id_periodo_contable: int) -> list[dict]:
        """Lista los costos del periodo sin clasificar."""
        ...

    @abstractmethod
    def recepciones_pendientes(self, limite: int) -> list[tuple[int, RecepcionProvision]]:
        """Lista las provisiones recibidas pendientes de procesar."""
        ...

    @abstractmethod
    def marcar_recepcion(self, id_recepcion: int, resultado: str) -> None:
        """Registra el resultado de procesar una recepción."""
        ...

    @abstractmethod
    def recepciones_pendientes_titular(self, numero_id_tributaria: str, hasta: date) -> int:
        """Cuenta las recepciones pendientes del titular hasta la fecha."""
        ...

    @abstractmethod
    def fecha_aplicacion_m05(self, id_registro_suministro: str) -> Optional[date]:
        """Fecha de aplicación del suministro de origen, o ``None``."""
        ...
