# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Entrada de los ciclos productivos (RF-16): nombre y etapas en el orden en que se recorren."""
from __future__ import annotations

from pydantic import Field, PositiveInt

from src.shared.base_dto import BaseDTO


class EditarCicloProductivoDTO(BaseDTO):
    nombre: str = Field(min_length=3, max_length=100)
    id_ciclos_biologicos: list[PositiveInt] = Field(min_length=1, max_length=50,
                                                    description="Etapas del ciclo en el orden en que se recorren.")


class RegistrarCicloProductivoDTO(EditarCicloProductivoDTO):
    id_especie: PositiveInt
