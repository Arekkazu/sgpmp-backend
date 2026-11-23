# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Schemas de respuesta para tipos de dispositivo IoT y sus rangos (RF-23)."""
from __future__ import annotations

from pydantic import BaseModel


class TipoDispositivoIotResponse(BaseModel):
    """Tipo de dispositivo con sus rangos de configuración remota."""
    id_tipo_dispositivo: int
    nombre: str
    frecuencia_captura_min: int
    frecuencia_captura_max: int
    intervalo_transmision_min: int
    intervalo_transmision_max: int
    categoria: str

    @classmethod
    def from_entity(cls, tipo) -> TipoDispositivoIotResponse:
        """Construye la respuesta a partir de la entidad de dominio."""
        return cls(
            id_tipo_dispositivo=tipo.id_tipo_dispositivo,
            nombre=tipo.nombre,
            frecuencia_captura_min=tipo.frecuencia_captura_min,
            frecuencia_captura_max=tipo.frecuencia_captura_max,
            intervalo_transmision_min=tipo.intervalo_transmision_min,
            intervalo_transmision_max=tipo.intervalo_transmision_max,
            categoria=tipo.categoria,
        )


class ListaTiposDispositivoIotResponse(BaseModel):
    """Catálogo de tipos de dispositivo."""
    total: int
    items: list[TipoDispositivoIotResponse]
