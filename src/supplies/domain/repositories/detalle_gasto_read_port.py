# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: alcance, existencia y bajas RF-45  |
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
        ids_permitidos: Optional[list[int]] = None,
    ) -> list[LineaGasto]:
        """Líneas VALIDADO de ALIMENTACION/MEDICACION en el rango y filtros dados.

        ``ids_permitidos`` limita a los activos que el usuario puede ver (``None`` = sin límite).
        """
        raise NotImplementedError

    @abstractmethod
    def existe_infraestructura(self, id_infraestructura: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def existe_especie(self, id_especie: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def contar_bajas(self, id_activo_biologico: int, fecha_inicio: date, fecha_fin: date) -> int:
        """Individuos dados de baja (RF-45) en el período, para la nota del promedio (RF-77 R6)."""
        raise NotImplementedError
