# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
"""Puerto de la valoración NIC 41: cálculos (RF-84), reconocimientos (RF-82), mediciones y
variaciones (RF-83/86), productos agrícolas (RF-85) y valoración por costo (RF-88)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional

from src.financial_valuation.domain.entities.valoracion import (
    CalculoValor,
    Medicion,
    Reconocimiento,
    ValoracionCosto,
    VariacionRegistro,
)


class ValoracionRepository(ABC):
    @abstractmethod
    def agregar_calculo(self, calculo: CalculoValor) -> int: ...

    @abstractmethod
    def ultimo_calculo(self, id_activo_biologico: int, hasta: Optional[date] = None) -> Optional[CalculoValor]: ...

    @abstractmethod
    def agregar_medicion(self, medicion: Medicion) -> int: ...

    @abstractmethod
    def agregar_variacion(self, variacion: VariacionRegistro) -> int: ...

    @abstractmethod
    def reconocimiento_confirmado(self, id_activo_biologico: int) -> Optional[Reconocimiento]: ...

    @abstractmethod
    def agregar_reconocimiento(self, datos: dict) -> int: ...

    @abstractmethod
    def revertir_reconocimiento(self, id_reconocimiento: int, motivo: str, id_usuario: int,
                                monto: Decimal, cuenta_debito: str, cuenta_credito: str) -> int: ...

    @abstractmethod
    def dependientes_reconocimiento(self, reconocimiento: Reconocimiento) -> list[dict]:
        """Mediciones, variaciones y cierres que impiden revertir (RF-82 R2 b)."""

    @abstractmethod
    def reconocimientos_del_activo(self, id_activo_biologico: int) -> list[dict]: ...

    @abstractmethod
    def agregar_valoracion_costo(self, valoracion: ValoracionCosto) -> int: ...

    @abstractmethod
    def valoracion_costo_activa(self, id_activo_biologico: int) -> Optional[ValoracionCosto]: ...

    @abstractmethod
    def actualizar_valoracion_costo(self, valoracion: ValoracionCosto) -> None: ...

    @abstractmethod
    def agregar_deterioro(self, id_valoracion: int, id_evento_sanitario: int, monto: Decimal, justificacion: str,
                          id_usuario: int) -> int: ...

    @abstractmethod
    def agregar_producto(self, datos: dict) -> int: ...

    @abstractmethod
    def activos_valorados(self) -> list[dict]: ...

    @abstractmethod
    def historial_activo(self, id_activo_biologico: int) -> dict: ...
