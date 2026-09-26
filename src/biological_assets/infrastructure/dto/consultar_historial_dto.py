from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_CATEGORIAS_VALIDAS = {
    'ESTADO', 'FASE', 'EVENTO_BIOLOGICO', 'CRECIMIENTO',
    'SANITARIO', 'REPRODUCTIVO', 'PRODUCTIVO', 'BAJA', 'TRANSFERENCIA',
}


class ConsultarHistorialDTO(BaseDTO):
    # fecha_inicio > fecha_fin lo rechaza ConsultarHistorialUseCase: RF-46 E-03 pide 422,
    # y un model_validator de Pydantic saldría como 400.
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    categoria_evento: Optional[str] = None
    pagina: int = 1
    page_size: int = 20

    @field_validator('categoria_evento', mode='before')
    @classmethod
    def validar_categoria(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip().upper()
        if v_str not in _CATEGORIAS_VALIDAS:
            raise ValueError(
                f'Categoría inválida. Valores permitidos: {", ".join(sorted(_CATEGORIAS_VALIDAS))}.'
            )
        return v_str

    @field_validator('pagina', mode='before')
    @classmethod
    def validar_pagina(cls, v: object) -> int:
        val = int(v)
        if val < 1:
            raise ValueError('La página debe ser mayor o igual a 1.')
        return val

    @field_validator('page_size', mode='before')
    @classmethod
    def validar_page_size(cls, v: object) -> int:
        val = int(v)
        if val < 1 or val > 100:
            raise ValueError('El tamaño de página debe estar entre 1 y 100.')
        return val
