# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: la respuesta trae esperanza_vida_dias (RFC-014) |
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: la respuesta trae densidad_poblacional_max y deja el nombre anterior deprecado |
"""Schemas de respuesta para los endpoints del catálogo de especies (RF-15).

``EspecieResponse`` se usa en todas las operaciones que devuelven una especie
(registrar, editar, desactivar, reactivar).
``CatalogoEspeciesResponse`` envuelve el listado de la consulta del catálogo.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EspecieResponse(BaseModel):
    """Datos completos de una especie retornados por el sistema."""

    id_especie: int
    nombre: str
    descripcion: Optional[str]
    # RFC-012: ind/m² con el nombre de la ficha.
    densidad_poblacional_max: Optional[Decimal] = None
    densidad_maxima_por_especie: Optional[Decimal] = Field(
        json_schema_extra={"deprecated": True}, description="Alias deprecado de densidad_poblacional_max.",
    )
    grupo_manejo: Optional[str] = None
    # RFC-014: días; None = no definida.
    esperanza_vida_dias: Optional[int] = None
    # Derivado de grupo_manejo (solo lectura): el formulario de áreas lo usa para
    # preseleccionar el modelo coherente (RF-20).
    tipo_modelo: Optional[str] = None
    es_activo: bool
    fecha_creacion: datetime.datetime
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def copiar_densidad(self):
        self.densidad_poblacional_max = self.densidad_maxima_por_especie
        return self

    @field_validator("nombre", mode="before")
    @classmethod
    def extraer_nombre(cls, v: object) -> str:
        """Convierte ``NombreEspecie`` → ``str`` al construir desde la entidad."""
        if hasattr(v, "valor"):
            return v.valor  # type: ignore[attr-defined]
        return str(v)


class CatalogoEspeciesResponse(BaseModel):
    """Resultado de la consulta del catálogo de especies productivas."""

    total: int
    items: list[EspecieResponse]
