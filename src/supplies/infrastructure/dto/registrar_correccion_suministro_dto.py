"""DTO de entrada para corregir un registro de suministro existente (RF-78 E7, CORRECCION).

``id_registro_original`` viaja en la URL (``POST /{id_registro_original}/correccion``,
mismo patrón que ``POST /{id_medicamento}/anulacion``), no en el cuerpo.
Acepta corregir un registro de cualquier tipo de suministro (ALIMENTO,
MEDICAMENTO, SERVICIO_VETERINARIO, INSEMINACION) — ver Gap 10 de
``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarCorreccionSuministroDTO(BaseDTO):
    """Campos requeridos para registrar una corrección de un suministro existente."""

    cantidad_corregida: Decimal = Field(gt=0, description="Cantidad corregida (> 0).")
    precio_unitario_corregido: Decimal = Field(gt=0, description="Precio unitario corregido (> 0).")
    justificacion_precio: str = Field(min_length=20, max_length=500)
    motivo_correccion: str = Field(min_length=20, max_length=500)
    id_idempotencia: UUID
