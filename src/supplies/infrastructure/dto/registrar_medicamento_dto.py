"""DTO de entrada para registrar una aplicación de medicamento (RF-76).

Nota: ``registros_medicamentos`` no tiene columna ``observaciones``; el campo
del RF no se persiste. ``descripcion_clinica`` (NOT NULL en BD, ausente en el
RF) se puebla en el caso de uso a partir de ``motivo_aplicacion``.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class RegistrarMedicamentoDTO(BaseDTO):
    """Campos requeridos para registrar una aplicación de medicamento."""

    id_activo_biologico: int = Field(gt=0)
    nombre_medicamento: str = Field(min_length=1, max_length=100)
    fecha_aplicacion: date
    hora_aplicacion: time
    via_administracion: str = Field(min_length=1, max_length=20)
    dosis_aplicada: Decimal = Field(gt=0, description="Dosis total administrada (> 0).")
    unidad_dosis: str = Field(min_length=1, max_length=20)
    periodo_retiro_dias: int = Field(default=0, ge=0)
    motivo_aplicacion: str = Field(min_length=10, max_length=500)
    costo_unitario: Decimal = Field(gt=0, description="Costo del medicamento por unidad de dosis (> 0).")
    nombre_veterinario: str = Field(min_length=1, max_length=150)
    id_evento_sanitario: Optional[int] = Field(default=None, gt=0)
    lote: Optional[str] = Field(default=None, max_length=60)
    fecha_vencimiento_lote: Optional[date] = None

    @field_validator("motivo_aplicacion")
    @classmethod
    def validar_motivo(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError(
                "El motivo de la aplicación es obligatorio y debe tener al menos 10 caracteres."
            )
        return v
