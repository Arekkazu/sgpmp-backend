"""DTO de entrada para crear una nueva plantilla de configuración (RF-31)."""
from __future__ import annotations

from typing import Any

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_CLAVES_PERMITIDAS = {
    'schema_version',
    'ciclos_biologicos',
    'patologias',
    'metricas_produccion',
    'umbrales_ambientales',
}

_CLAVES_FUERA_DE_ALCANCE = {
    'dispositivos_iot', 'infraestructuras', 'dashboard', 'identidad_visual',
    'fincas', 'sensores', 'configuraciones_globales',
}


class RegistrarPlantillaDTO(BaseDTO):
    """Campos requeridos para crear una plantilla."""

    template_name: str
    id_especie: int
    params_snapshot: dict[str, Any]

    @field_validator('template_name')
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError('El nombre debe tener entre 3 y 50 caracteres.')
        return v

    @field_validator('params_snapshot')
    @classmethod
    def validar_snapshot(cls, v: dict) -> dict:
        claves_invalidas = set(v.keys()) & _CLAVES_FUERA_DE_ALCANCE
        if claves_invalidas:
            raise ValueError(
                f"El snapshot contiene parámetros fuera de alcance: {sorted(claves_invalidas)}. "
                "Solo se permiten parámetros productivos y umbrales ambientales."
            )
        claves_desconocidas = set(v.keys()) - _CLAVES_PERMITIDAS
        if claves_desconocidas:
            raise ValueError(
                f"Claves no reconocidas en params_snapshot: {sorted(claves_desconocidas)}."
            )
        categorias = ('ciclos_biologicos', 'patologias', 'metricas_produccion', 'umbrales_ambientales')
        tiene_items = any(v.get(k) for k in categorias)
        if not tiene_items:
            raise ValueError(
                'El snapshot debe contener al menos un parámetro en alguna de las categorías: '
                'ciclos_biologicos, patologias, metricas_produccion, umbrales_ambientales.'
            )
        return v
