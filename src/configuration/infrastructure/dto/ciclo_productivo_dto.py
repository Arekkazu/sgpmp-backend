# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Entrada de los ciclos productivos (RF-16): nombre y etapas en el orden en que se recorren."""
from __future__ import annotations

from pydantic import Field, PositiveInt

from src.shared.base_dto import BaseDTO


class EditarCicloProductivoDTO(BaseDTO):
    """Nombre y etapas de un ciclo productivo."""
    nombre: str = Field(min_length=3, max_length=100)
    id_ciclos_biologicos: list[PositiveInt] = Field(min_length=1, max_length=50,
                                                    description="Etapas del ciclo en el orden en que se recorren.")


class RegistrarCicloProductivoDTO(EditarCicloProductivoDTO):
    """Datos de un ciclo productivo nuevo."""
    id_especie: PositiveInt
