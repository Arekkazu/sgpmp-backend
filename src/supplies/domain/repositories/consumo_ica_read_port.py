"""Puerto de lectura del alimento consumido VALIDADO en un período (RF-74).

Suma ``cantidad_suministrada`` de ``modulo5.registros_consumo_alimentos`` para el
activo en el rango de fechas, considerando solo registros ``VALIDADO``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional


class ConsumoICAReadPort(ABC):
    @abstractmethod
    def sumar_alimento_validado(
        self, id_activo_biologico: int, fecha_desde: date, fecha_hasta: date
    ) -> Optional[Decimal]:
        """Suma de kg de alimento VALIDADO en ``[fecha_desde, fecha_hasta]``.

        Devuelve ``None`` si no hay ningún registro VALIDADO en el período (para
        distinguir "sin registros" de "cero")."""
        raise NotImplementedError
