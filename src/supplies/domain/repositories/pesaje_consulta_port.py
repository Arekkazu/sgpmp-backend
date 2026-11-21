# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74 E6: pesajes fuera de rango          |
"""Puerto de consulta de pesaje del activo (RF-40) para el cálculo ICA (RF-74).

El peso real vive en ``modulo2.eventos_crecimeinto`` enlazado al activo vía
``modulo2.eventos_activos``. Para el ICA se necesitan el peso al inicio y al fin del
período: el pesaje más reciente en o antes de una fecha dada.

- INDIVIDUAL  → ``valor_medicion``.
- POBLACIONAL → ``nuevo_peso_promedio`` (peso promedio por individuo).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional


class PesajeConsultaPort(ABC):
    @abstractmethod
    def obtener_peso_en_o_antes(
        self, id_activo_biologico: int, fecha: date, es_poblacional: bool
    ) -> Optional[Decimal]:
        """Peso (kg) válido (> 0) del pesaje más reciente con fecha ``<= fecha``, o ``None``.

        Los pesajes con valor ≤ 0 se descartan y se busca el siguiente (RF-74 E6).
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_peso_invalido_en_o_antes(
        self, id_activo_biologico: int, fecha: date, es_poblacional: bool
    ) -> Optional[tuple[date, Decimal]]:
        """(fecha, valor) del pesaje fuera de rango más reciente ``<= fecha`` (RF-74 E6), o ``None``."""
        raise NotImplementedError
