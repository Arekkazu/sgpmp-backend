# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: entrada del PATCH de es_critica (RFC-016) |
"""DTO de entrada para marcar una variable ambiental como crítica (RFC-016 B.7)."""
from __future__ import annotations

from src.shared.base_dto import BaseDTO


class ActualizarVariableAmbientalDTO(BaseDTO):
    """Solo ``es_critica`` es editable: unidad y rango físico son catálogo fijo."""
    es_critica: bool
