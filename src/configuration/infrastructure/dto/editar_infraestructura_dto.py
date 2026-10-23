# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: especies (1..N) con especie_id como alias deprecado, nivel_criticidad |
"""DTO de entrada para editar un área productiva (PATCH RF-20).

Incluye ``fecha_actualizacion`` para concurrencia optimista (FA-14).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from src.shared.tipo_modelo import TipoModelo


class EditarInfraestructuraDTO(BaseDTO):
    """Campos editables del área productiva; ``tipo_area`` debe existir en el catálogo de tipos de área.

    ``fecha_actualizacion`` debe ser la leída del registro (concurrencia optimista, 412 si cambió).
    """
    nombre_infraestructura: str
    tipo_area: str
    superficie: Decimal
    descripcion_infraestructura: Optional[str] = None
    # RFC-012: 1..N especies del mismo grupo de manejo (el use case valida, 422).
    # ``especie_id`` es el campo único anterior: se acepta mientras el front migra.
    especies: Optional[list[int]] = Field(default=None, min_length=1)
    especie_id: Optional[int] = Field(
        default=None, json_schema_extra={"deprecated": True}, description="Alias deprecado de especies (una sola).",
    )
    # RF-20 v1.1 (RFC-009): el modelo de IA es opcional y el use case valida su
    # coherencia con el grupo de manejo común (422).
    tipo_modelo_asignado: Optional[TipoModelo] = None
    # RFC-016: si no se envía, se conserva el valor actual del área.
    nivel_criticidad: Optional[Literal["ALTA", "MEDIA", "BAJA"]] = None
    fecha_actualizacion: Optional[datetime] = None

    @field_validator("nombre_infraestructura")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del área productiva es obligatorio.")
        if len(v.strip()) > 50:
            raise ValueError("El nombre no puede superar los 50 caracteres.")
        return v

    @field_validator("tipo_area")
    @classmethod
    def validar_tipo_area(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El tipo de área es obligatorio.")
        return v

    @field_validator("superficie")
    @classmethod
    def validar_superficie(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError(f"La superficie debe ser mayor a cero. Valor recibido: {v}.")
        return v

    @field_validator("descripcion_infraestructura")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError("La descripción no puede superar los 100 caracteres.")
        return v

    @model_validator(mode="after")
    def unificar_especies(self):
        if self.especies is None:
            if self.especie_id is None:
                raise ValueError("Debe indicar al menos una especie del área (especies).")
            self.especies = [self.especie_id]
        elif self.especie_id is not None and self.especie_id not in self.especies:
            raise ValueError("especie_id está deprecado: si envía especies, no lo envíe o inclúyalo en la lista.")
        self.especies = list(dict.fromkeys(self.especies))
        return self
