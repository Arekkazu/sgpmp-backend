"""DTOs de entrada para el CU-02 (RF-74): cálculo, batch, reintento e interrupción."""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


class CalcularICADTO(BaseDTO):
    """Cálculo manual del ICA de un activo para un período (Flujo A)."""

    id_activo_biologico: int = Field(gt=0)
    periodo_evaluacion: PeriodoEvaluacion


class EjecutarBatchDTO(BaseDTO):
    """Disparo/reactivación manual del batch ICA.

    ``solo_cola`` reactiva únicamente los activos ya encolados (FA-07/reactivación)
    sin volver a barrer todos los activos ACTIVO.
    """

    solo_cola: bool = False


class InterrumpirBatchDTO(BaseDTO):
    """Interrupción manual de una corrida en curso (FA-12)."""

    motivo: Optional[str] = None
