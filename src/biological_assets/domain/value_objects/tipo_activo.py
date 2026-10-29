"""Tipo de activo biológico."""

from enum import Enum


class TipoActivo(str, Enum):
    """INDIVIDUAL = un animal identificado; POBLACIONAL = un lote contado en conjunto.
    """
    INDIVIDUAL = 'INDIVIDUAL'
    POBLACIONAL = 'POBLACIONAL'
