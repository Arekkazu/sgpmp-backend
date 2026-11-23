# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-35: listado de activos filtrable por finca y con la finca de cada activo |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Filtros de ``GET /activos-biologicos`` (RF-35 / RF-36)."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from src.biological_assets.domain.value_objects.tipo_activo import TipoActivo
from src.shared.base_dto import BaseDTO

_TIPOS_VALIDOS = {t.value for t in TipoActivo}


class ListarActivosDTO(BaseDTO):
    """Filtros y paginación del listado; ``tipo``: ``INDIVIDUAL`` | ``POBLACIONAL``."""
    tipo: Optional[str] = None
    id_especie: Optional[int] = None
    id_estado: Optional[int] = None
    id_infraestructura: Optional[int] = None
    id_finca: Optional[int] = Field(default=None, ge=1)
    pagina: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator('tipo', mode='before')
    @classmethod
    def validar_tipo(cls, v: object) -> Optional[str]:
        """Normaliza y valida el tipo de activo opcional."""
        if v is None:
            return None
        v_str = str(v).strip().upper()
        if v_str not in _TIPOS_VALIDOS:
            raise ValueError(
                f'Tipo inválido. Valores permitidos: {", ".join(sorted(_TIPOS_VALIDOS))}.'
            )
        return v_str
