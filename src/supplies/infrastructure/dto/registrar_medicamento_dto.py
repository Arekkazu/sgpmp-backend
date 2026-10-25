# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: E4/E6, observaciones y longitudes  |
"""DTO de entrada para registrar una aplicación de medicamento (RF-76).

``descripcion_clinica`` (NOT NULL en BD, ausente en el RF) se puebla en el caso
de uso a partir de ``motivo_aplicacion``. Los errores de formato responden 400
con el mensaje de cada flujo alterno (E4 dosis, E6 motivo).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO

_MENSAJE_E6 = (
    "El motivo de la aplicación es obligatorio y debe tener al menos 10 caracteres para garantizar "
    "la trazabilidad clínica del tratamiento."
)


class RegistrarMedicamentoDTO(BaseDTO):
    """Campos requeridos para registrar una aplicación de medicamento."""

    id_activo_biologico: int = Field(gt=0)
    nombre_medicamento: str = Field(min_length=1, max_length=50)
    fecha_aplicacion: date
    hora_aplicacion: time
    via_administracion: str = Field(min_length=1, max_length=20)
    dosis_aplicada: Decimal = Field(description="Dosis total administrada (> 0).")
    unidad_dosis: str = Field(min_length=1, max_length=20)
    periodo_retiro_dias: int = Field(default=0, ge=0)
    motivo_aplicacion: str = Field(max_length=500)
    costo_unitario: Decimal = Field(gt=0, description="Costo del medicamento por unidad de dosis (> 0).")
    nombre_veterinario: str = Field(min_length=1, max_length=150)
    id_evento_sanitario: Optional[int] = Field(default=None, gt=0)
    observaciones: Optional[str] = Field(default=None, max_length=500)
    lote: Optional[str] = Field(default=None, max_length=60)
    fecha_vencimiento_lote: Optional[date] = None

    @field_validator("motivo_aplicacion")
    @classmethod
    def validar_motivo(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError(_MENSAJE_E6)
        return v

    @field_validator("nombre_veterinario")
    @classmethod
    def validar_veterinario(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del veterinario responsable es obligatorio.")
        return v

    @model_validator(mode="after")
    def validar_dosis(self) -> "RegistrarMedicamentoDTO":
        if self.dosis_aplicada <= 0:
            raise ValueError(
                f"La dosis aplicada debe ser mayor a cero. Valor ingresado: {self.dosis_aplicada} {self.unidad_dosis}."
            )
        return self
