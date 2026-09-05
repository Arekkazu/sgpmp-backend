"""Schemas de respuesta para los endpoints del catálogo de especies (RF-15).

``EspecieResponse`` se usa en todas las operaciones que devuelven una especie
(registrar, editar, desactivar, reactivar).
``CatalogoEspeciesResponse`` envuelve el listado de la consulta del catálogo.
"""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class EspecieResponse(BaseModel):
    """Datos completos de una especie retornados por el sistema."""

    id_especie: int
    nombre: str
    descripcion: Optional[str]
    es_activo: bool
    fecha_creacion: datetime.datetime
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

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
