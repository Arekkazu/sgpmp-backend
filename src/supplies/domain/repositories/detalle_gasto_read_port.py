"""Puerto de lectura de las líneas de gasto fuente del reporte (RF-77).

Consolida los registros VALIDADOS de RF-75 (consumo de alimento) y RF-76
(aplicación de medicamentos) en un formato uniforme. Es de solo lectura; no
muta ningún dato.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.supplies.domain.entities.reporte_gasto import LineaGasto


class DetalleGastoReadPort(ABC):
    @abstractmethod
    def consultar(
        self,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        id_activo_biologico: Optional[int] = None,
        id_infraestructura: Optional[int] = None,
        id_especie: Optional[int] = None,
        categorias: Optional[list[str]] = None,
    ) -> list[LineaGasto]:
        """Líneas VALIDADO de ALIMENTACION/MEDICACION en el rango y filtros dados."""
        raise NotImplementedError
