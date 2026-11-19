# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-97: puerto de lectura de M06/M09 para el envelope AAEF |
# | 2026-11-19 | Arekkazu | TC-M07-G019 RF-96: catálogo de LineType de la matriz contable |
"""Puerto de solo lectura sobre lo que M06 y M09 ya calcularon (RF-97 Fase 3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.accounting_integration.domain.services.aaef import ComprobanteNic41, CostoFactura, Periodo, Titular


class FuenteContableRepository(ABC):
    @abstractmethod
    def titular(self, nit: str) -> Optional[Titular]:
        """Titular tributario (RF-19) con al menos una finca activa, sin importar quién consulta."""

    @abstractmethod
    def fincas_titular(self, nit: str) -> set[int]:
        """Fincas activas del titular, sin importar quién consulta (RLS no debe recortarlas)."""

    @abstractmethod
    def fincas_usuario(self, id_usuario: int) -> set[int]: ...

    @abstractmethod
    def periodos(self, nit: str) -> list[Periodo]: ...

    @abstractmethod
    def costos_factura(self, nit: str, desde: date, hasta: date) -> list[CostoFactura]:
        """Costos con vehículo factura de compra cuyo período contable está dentro del rango."""

    @abstractmethod
    def comprobantes(self, nit: str, desde: date, hasta: date) -> list[ComprobanteNic41]: ...

    @abstractmethod
    def lineas_sin_trazabilidad(self, nit: str, desde: date, hasta: date) -> int:
        """Líneas de asiento del rango sin trazabilidad verificada (RF-97 Fase 2)."""

    @abstractmethod
    def linetypes_catalogados(self) -> tuple[frozenset, frozenset]:
        """RF-96 CA-6 / RF-109: (subtipos de costo con cuenta de gasto activa, hechos con cuenta activa).
        Un ``None`` entre los subtipos es una fila de la matriz que aplica a todos."""
