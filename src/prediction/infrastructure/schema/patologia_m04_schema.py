# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M04 M4-02 RF-64: nombre y unidad de variables y nombre de la especie (read-model) |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PatologiaVariableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_variable_ambiental: int
    peso_evidencia: Decimal
    es_variable_critica: bool
    # M4-02: del catálogo I3P-1; antes el front mostraba "Variable 13".
    nombre_variable: Optional[str] = None
    unidad: Optional[str] = None


class PatologiaM04Response(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_patologia: int
    nombre_patologia: str
    especie_aplicable: str
    # M4-02: nombre de la especie; None cuando especie_aplicable es TODAS.
    nombre_especie: Optional[str] = None
    descripcion_clinica: str
    es_base: bool
    es_activo: bool
    version_catalogo: int
    variables_sensoricas_asociadas: list[PatologiaVariableResponse]
    fecha_creacion_m04: datetime
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def from_entity(cls, entidad) -> PatologiaM04Response:
        return cls(
            id_patologia=entidad.id_patologia,
            nombre_patologia=entidad.nombre,
            especie_aplicable=entidad.especie_aplicable,
            nombre_especie=entidad.nombre_especie,
            descripcion_clinica=entidad.descripcion_clinica,
            es_base=entidad.es_base,
            es_activo=entidad.es_activo,
            version_catalogo=entidad.version_catalogo,
            variables_sensoricas_asociadas=[
                PatologiaVariableResponse(
                    id_variable_ambiental=v.id_variable_ambiental,
                    peso_evidencia=v.peso_evidencia,
                    es_variable_critica=v.es_variable_critica,
                    nombre_variable=v.nombre,
                    unidad=v.unidad,
                )
                for v in entidad.variables
            ],
            fecha_creacion_m04=entidad.fecha_creacion_m04,
            fecha_actualizacion=entidad.fecha_actualizacion,
        )


class PatologiaM04ListResponse(BaseModel):
    total: int
    items: list[PatologiaM04Response]
