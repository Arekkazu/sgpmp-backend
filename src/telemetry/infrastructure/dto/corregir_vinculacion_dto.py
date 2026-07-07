from __future__ import annotations

from pydantic import Field

from src.shared.base_dto import BaseDTO


class CorregirVinculacionDTO(BaseDTO):
    """Corrección post-vinculación (RF-61-C). Crea una nueva vinculación reemplazando la original."""

    id_activo_biologico: int
    modelo_manejo: str
    motivo: str = Field(..., min_length=5, max_length=500)
