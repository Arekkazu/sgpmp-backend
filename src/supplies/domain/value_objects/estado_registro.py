"""Estados posibles de un registro de suministro (RF-75 / RF-76).

Mapea el enum PG ``modulo5.enum_estado_registro``. Un registro nace ``VALIDADO``
(inmutable) y solo puede transicionar a ``ANULADO``. Un ``ANULADO`` no puede
reactivarse.
"""
from __future__ import annotations

from enum import Enum


class EstadoRegistro(str, Enum):
    VALIDADO = "VALIDADO"
    ANULADO = "ANULADO"
