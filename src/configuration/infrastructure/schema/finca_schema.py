"""Schemas de respuesta para los endpoints de fincas (RF-19)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class UbicacionFincaResponse(BaseModel):
    departamento: str
    municipio: str
    vereda: str
    latitud: Decimal
    longitud: Decimal


class FincaResponse(BaseModel):
    id_finca: int
    nombre: str
    ubicacion: UbicacionFincaResponse
    tamano_h: Decimal
    es_activo: bool
    fecha_creacion: datetime.datetime
    fecha_actualizacion: datetime.datetime
    id_usuario: Optional[int]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, finca) -> FincaResponse:
        return cls(
            id_finca=finca.id_finca,
            nombre=finca.nombre.valor,
            ubicacion=UbicacionFincaResponse(
                departamento=finca.ubicacion.departamento,
                municipio=finca.ubicacion.municipio,
                vereda=finca.ubicacion.vereda,
                latitud=finca.ubicacion.latitud,
                longitud=finca.ubicacion.longitud,
            ),
            tamano_h=finca.tamano_h.valor,
            es_activo=finca.es_activo,
            fecha_creacion=finca.fecha_creacion,
            fecha_actualizacion=finca.fecha_actualizacion,
            id_usuario=finca.id_usuario,
        )


class ListaFincasResponse(BaseModel):
    total: int
    items: list[FincaResponse]
