"""DTO de entrada para encolar un trabajo pesado de historial de suministros (RF-81)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.supplies.domain.value_objects.historial_suministro_enums import (
    OrigenPrecioFiltro,
    TipoSuministroFiltro,
    TipoTrabajoHistorial,
)


class SolicitarTrabajoHistorialDTO(BaseDTO):
    """``tipo_trabajo`` = CONSULTA_PESADA (nivel 3/4) o EXPORTACION (> 10.000 registros)."""

    tipo_trabajo: TipoTrabajoHistorial
    id_activo_biologico: int = Field(gt=0)
    id_ciclo_productivo: Optional[int] = Field(default=None, gt=0)
    fecha_inicio_filtro: Optional[date] = None
    fecha_fin_filtro: Optional[date] = None
    tipo_suministro_filtro: TipoSuministroFiltro = TipoSuministroFiltro.TODOS
    origen_precio_filtro: OrigenPrecioFiltro = OrigenPrecioFiltro.TODOS
    costo_min: Optional[Decimal] = Field(default=None, ge=0)
    costo_max: Optional[Decimal] = Field(default=None, ge=0)
    registros_por_pagina: int = Field(default=50, ge=1, le=200)
