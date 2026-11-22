# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-140-G003 RF-64: nombre con espacios internos normalizados |
from __future__ import annotations

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


def normalizar_nombre_patologia(valor: str) -> str:
    """Espacios, tabs y saltos repetidos cuentan como uno: 'Estres  termico' es 'Estres termico'."""
    nombre = " ".join(valor.split())
    if not nombre:
        raise ValueError("El nombre de la patología es obligatorio.")
    return nombre


class RegistrarPatologiaDTO(BaseDTO):
    nombre_patologia: str
    especie_aplicable: str = "TODAS"
    variables_sensoricas_asociadas: list[int]
    descripcion_clinica: str

    _nombre = field_validator("nombre_patologia")(normalizar_nombre_patologia)
