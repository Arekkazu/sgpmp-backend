"""DTO de entrada para registrar un suministro directo (RF-78 — SERVICIO_VETERINARIO/INSEMINACION).

ALIMENTO/MEDICAMENTO no se aceptan aquí — se acumulan automáticamente desde
RF-75/RF-76. ``id_idempotencia`` es obligatorio (Restricción 14 de RF-78).
``justificacion_precio`` siempre se exige: no hay integración M40 en este
sistema (precedente de CU-01), así que ``origen_precio`` es siempre MANUAL.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarSuministroDirectoDTO(BaseDTO):
    """Campos requeridos para registrar un suministro SERVICIO_VETERINARIO/INSEMINACION."""

    id_activo_biologico: int = Field(gt=0)
    tipo_suministro: Literal["SERVICIO_VETERINARIO", "INSEMINACION"]
    cantidad: Decimal = Field(gt=0, description="Cantidad aplicada del suministro (> 0).")
    unidad_medida: str = Field(min_length=1, max_length=20)
    precio_unitario: Decimal = Field(gt=0, description="Precio unitario manual (> 0).")
    fecha_aplicacion: date
    justificacion_precio: str = Field(min_length=20, max_length=500)
    id_idempotencia: UUID
    observacion: Optional[str] = Field(default=None, max_length=500)
