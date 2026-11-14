# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: formato PDF/EXCEL de la exportación |
# | 2026-11-09 | LuisfNarvaez01   | INC-M05-283-G42 RF-81: más de 200 por página se limita a 200, no se rechaza |
"""DTO de entrada para encolar un trabajo pesado de historial de suministros (RF-81)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO
from src.supplies.domain.value_objects.historial_suministro_enums import (
    OrigenPrecioFiltro,
    TipoSuministroFiltro,
    TipoTrabajoHistorial,
)


MAX_REGISTROS_POR_PAGINA = 200


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
    # RF-81 (Entradas): "máx: 200 ... El sistema aplica el límite máximo si se excede".
    registros_por_pagina: int = Field(default=50, ge=1)
    formato_exportacion: Literal["PDF", "EXCEL"] = "EXCEL"

    @field_validator("registros_por_pagina")
    @classmethod
    def _limitar_pagina(cls, valor: int) -> int:
        return min(valor, MAX_REGISTROS_POR_PAGINA)
