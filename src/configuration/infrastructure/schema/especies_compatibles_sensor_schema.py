# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Esquemas de respuesta de especies compatibles con un sensor."""
from __future__ import annotations

from pydantic import BaseModel

from src.configuration.domain.entities.especie import Especie


class EspecieCompatibleResponse(BaseModel):
    """Especie compatible con un sensor."""
    id_especie: int
    nombre: str


class EspeciesCompatiblesSensorResponse(BaseModel):
    """Especies compatibles con un sensor."""
    id_sensor: int
    especies: list[EspecieCompatibleResponse]

    @classmethod
    def desde(cls, id_sensor: int, especies: list[Especie]) -> "EspeciesCompatiblesSensorResponse":
        """Construye la respuesta a partir de la entidad de dominio."""
        return cls(id_sensor=id_sensor, especies=[
            EspecieCompatibleResponse(id_especie=e.id_especie, nombre=e.nombre.valor) for e in especies if e
        ])
