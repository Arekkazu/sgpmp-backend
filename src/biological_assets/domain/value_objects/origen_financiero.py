from enum import Enum


class OrigenFinanciero(str, Enum):
    COMPRA = 'compra'
    NACIMIENTO = 'nacimiento'
    DONACION = 'donacion'
    TRANSFERENCIA_INTERNA = 'transferencia_interna'
