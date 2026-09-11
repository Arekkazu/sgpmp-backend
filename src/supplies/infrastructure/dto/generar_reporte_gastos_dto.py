"""DTO de entrada para generar el reporte de gastos acumulados (RF-77)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.supplies.domain.value_objects.reporte_gasto_enums import CategoriaGasto, GranularidadDesglose


class GenerarReporteGastosDTO(BaseDTO):
    """Parámetros de generación del reporte. Ver RF-77 'Entradas'."""

    fecha_inicio_reporte: date
    fecha_fin_reporte: date
    tipo_periodo: GranularidadDesglose = GranularidadDesglose.CICLO_COMPLETO
    activo_biologico_id: Optional[int] = Field(default=None, gt=0)
    id_infraestructura: Optional[int] = Field(default=None, gt=0)
    id_especie: Optional[int] = Field(default=None, gt=0)
    categorias_incluidas: Optional[list[CategoriaGasto]] = None
