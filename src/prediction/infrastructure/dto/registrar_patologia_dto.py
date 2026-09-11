from __future__ import annotations

from src.shared.base_dto import BaseDTO


class RegistrarPatologiaDTO(BaseDTO):
    nombre_patologia: str
    especie_aplicable: str = "TODAS"
    variables_sensoricas_asociadas: list[int]
    descripcion_clinica: str
