from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

# RF-36 (tarea Taiga "Ficha de gestión de lote, densidad máxima, ingreso de
# individuos"): mismos 4 valores de origen_financiero que ya usa el registro
# inicial del activo (registrar_activo_dto.py) -- una alta posterior a un
# lote existente es, conceptualmente, el mismo catálogo de procedencias.
_TIPOS_INGRESO = {'compra', 'nacimiento', 'donacion', 'transferencia_interna'}


class RegistrarEventoIngresoDTO(BaseDTO):
    tipo_ingreso: str
    fecha_ingreso: date
    cantidad_ingresada: int
    motivo_ingreso: str

    @field_validator('tipo_ingreso')
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _TIPOS_INGRESO:
            raise ValueError(f"El tipo de ingreso debe ser uno de: {', '.join(sorted(_TIPOS_INGRESO))}.")
        return v

    @field_validator('cantidad_ingresada')
    @classmethod
    def cantidad_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('La cantidad ingresada debe ser un entero positivo.')
        return v

    @field_validator('motivo_ingreso')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('El motivo de ingreso no puede estar vacío.')
        return v
