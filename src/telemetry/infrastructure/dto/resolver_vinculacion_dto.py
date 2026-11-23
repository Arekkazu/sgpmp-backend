# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""DTO de resolución manual de una vinculación ambigua."""
from __future__ import annotations

from src.shared.base_dto import BaseDTO


class ResolverVinculacionDTO(BaseDTO):
    """Resolución manual de una vinculación en estado AMBIGUA (RF-61-C)."""

    id_activo_biologico: int
    modelo_manejo: str
