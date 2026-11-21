# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #391 RF-16: densidad y biomasa máximas de la etapa con aviso preventivo |
"""Densidad máxima de una etapa (#391): animales por m², biomasa opcional en kg por m² y aviso preventivo."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class ConfigurarDensidadEtapaDTO(BaseDTO):
    densidad_maxima: Decimal = Field(gt=0, le=200, max_digits=6, decimal_places=2,
                                     description="Animales por m² que admite un lote en esta etapa.")
    biomasa_maxima: Optional[Decimal] = Field(default=None, gt=0, max_digits=8, decimal_places=2,
                                              description="Kg por m². Opcional.")
    aviso_preventivo_pct: Literal[80, 85, 90, 95] = 90
    fecha_actualizacion: Optional[FechaHoraUtc] = Field(
        default=None, description="La leída de la etapa: si otro usuario la cambió, responde 412.")
