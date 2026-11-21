# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Salida de los ciclos productivos con sus fases en orden."""
from __future__ import annotations

from pydantic import BaseModel

from src.configuration.domain.entities.ciclo_productivo import CicloProductivo


class FaseCicloProductivoResponse(BaseModel):
    orden: int
    id_ciclo_biologico: int
    nombre: str
    duracion_dias: int


class CicloProductivoResponse(BaseModel):
    id_ciclo_productivo: int
    nombre: str
    id_especie: int
    duracion_dias: int
    en_uso: bool
    fases: list[FaseCicloProductivoResponse]

    @classmethod
    def desde(cls, ciclo: CicloProductivo) -> "CicloProductivoResponse":
        return cls(id_ciclo_productivo=ciclo.id_ciclo_productivo, nombre=ciclo.nombre, id_especie=ciclo.id_especie,
                   duracion_dias=ciclo.duracion_dias, en_uso=ciclo.en_uso,
                   fases=[FaseCicloProductivoResponse(orden=i, id_ciclo_biologico=f.id_ciclo_biologico, nombre=f.nombre,
                                                      duracion_dias=f.duracion_dias)
                          for i, f in enumerate(ciclo.fases, start=1)])


class CiclosProductivosResponse(BaseModel):
    total: int
    items: list[CicloProductivoResponse]
