from __future__ import annotations

from src.shared.base_dto import BaseDTO


class ResolverVinculacionDTO(BaseDTO):
    """Resolución manual de una vinculación en estado AMBIGUA (RF-61-C)."""

    id_activo_biologico: int
    modelo_manejo: str
