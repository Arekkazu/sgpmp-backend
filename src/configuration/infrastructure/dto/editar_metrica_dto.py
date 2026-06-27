"""DTO de entrada para editar una métrica de producción (Flujo J — RF-16).

Incluye ``fecha_actualizacion`` para control de concurrencia optimista.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_NOMBRE_METRICA = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-()/]*$")

_TIPOS_VALIDOS = {'PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO'}
_APLICA_VALIDOS = {'INDIVIDUAL', 'LOTE', 'AMBOS'}


class EditarMetricaDTO(BaseDTO):
    nombre: str
    unidad_medida: str
    tipo_medicion: str
    aplica_a_tipo_activo: str
    fecha_actualizacion: Optional[datetime] = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 60:
            raise ValueError("El nombre de la métrica debe tener entre 3 y 60 caracteres.")
        if not _NOMBRE_METRICA.match(v):
            raise ValueError(
                "El nombre de la métrica solo puede contener letras, números, espacios, guiones, paréntesis y barras."
            )
        return v

    @field_validator("unidad_medida")
    @classmethod
    def validar_unidad_medida(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La unidad de medida es obligatoria.")
        if len(v) > 20:
            raise ValueError("La unidad de medida no puede superar los 20 caracteres.")
        return v

    @field_validator("tipo_medicion")
    @classmethod
    def validar_tipo_medicion(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in _TIPOS_VALIDOS:
            raise ValueError(f"El tipo de medición debe ser uno de: {', '.join(sorted(_TIPOS_VALIDOS))}.")
        return v

    @field_validator("aplica_a_tipo_activo")
    @classmethod
    def validar_aplica(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in _APLICA_VALIDOS:
            raise ValueError(f"El valor de aplica_a_tipo_activo debe ser uno de: {', '.join(sorted(_APLICA_VALIDOS))}.")
        return v
