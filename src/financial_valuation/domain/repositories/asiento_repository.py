# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-10 | Arekkazu | INC-M06-351-G45 RF-87: lectura de una línea y de sus ajustes posteriores |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de las líneas de asiento NIC 41 (RF-86 v2.0) y su trazabilidad (RF-91)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.entities.contabilidad import LineaAsiento


class AsientoRepository(ABC):
    """Puerto de persistencia de líneas de asiento contable."""
    @abstractmethod
    def agregar(self, linea: LineaAsiento) -> LineaAsiento:
        """Agrega una línea de asiento."""
        ...

    @abstractmethod
    def obtener(self, id_linea: int) -> Optional[LineaAsiento]:
        """Devuelve la línea, o ``None``."""
        ...

    @abstractmethod
    def ajustes_de(self, id_linea: int) -> list[LineaAsiento]:
        """Líneas que corrigen a ``id_linea`` (reversos y ajustes de período anterior)."""

    @abstractmethod
    def lineas_de_origen(self, tabla_origen: str, id_origen: int) -> list[LineaAsiento]:
        """Lista las líneas generadas por un registro de origen."""
        ...

    @abstractmethod
    def pendientes_de_cuenta(self, id_periodo_contable: Optional[int] = None) -> list[LineaAsiento]:
        """Lista las líneas sin cuenta asignada."""
        ...

    @abstractmethod
    def registrar_cuentas(self, id_linea: int, cuenta_debito: str, cuenta_credito: str) -> None:
        """Asigna las cuentas débito y crédito a la línea."""
        ...

    @abstractmethod
    def del_periodo(self, id_periodo_contable: int) -> list[LineaAsiento]:
        """Lista las líneas del periodo."""
        ...

    @abstractmethod
    def cambiar_trazabilidad(self, id_linea: int, estado: str) -> None:
        """Cambia el estado de trazabilidad de la línea."""
        ...

    @abstractmethod
    def mover_a_periodo(self, ids_lineas: list[int], id_periodo_contable: int) -> None:
        """Traslada las líneas a otro periodo."""
        ...

    @abstractmethod
    def asignar_comprobante(self, ids_lineas: list[int], id_comprobante: int) -> None:
        """Asocia las líneas a un comprobante."""
        ...

    @abstractmethod
    def del_activo(self, id_activo_biologico: int) -> list[LineaAsiento]:
        """Lista las líneas del activo."""
        ...
