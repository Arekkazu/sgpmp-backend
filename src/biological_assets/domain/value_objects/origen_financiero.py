"""Origen financiero del activo al registrarlo (RF-33)."""

from enum import Enum


class OrigenFinanciero(str, Enum):
    """Cómo ingresó el activo a la finca; también tipifica los ingresos a un lote
    (RF-36).
    """
    COMPRA = 'compra'
    NACIMIENTO = 'nacimiento'
    DONACION = 'donacion'
    TRANSFERENCIA_INTERNA = 'transferencia_interna'
