"""Estados del activo biológico y sus transiciones permitidas (RF-44).

Los valores coinciden con ``modulo2.estados_activos_biologicos``. BAJA es terminal y
CERRADO solo puede pasar a BAJA.
"""

from enum import IntEnum


class EstadoActivo(IntEnum):
    """Estado operativo del activo; el valor es el id en ``modulo2.estados_activos_biologicos``."""
    ACTIVO = 1
    INACTIVO = 2
    EN_TRATAMIENTO = 3
    AISLADO = 4
    CERRADO = 5
    BAJA = 6


TRANSICIONES_VALIDAS: dict[int, set[int]] = {
    EstadoActivo.ACTIVO:         {EstadoActivo.INACTIVO, EstadoActivo.EN_TRATAMIENTO, EstadoActivo.AISLADO, EstadoActivo.CERRADO, EstadoActivo.BAJA},
    EstadoActivo.INACTIVO:       {EstadoActivo.ACTIVO, EstadoActivo.EN_TRATAMIENTO, EstadoActivo.CERRADO, EstadoActivo.BAJA},
    EstadoActivo.EN_TRATAMIENTO: {EstadoActivo.ACTIVO, EstadoActivo.INACTIVO, EstadoActivo.AISLADO, EstadoActivo.CERRADO, EstadoActivo.BAJA},
    EstadoActivo.AISLADO:        {EstadoActivo.ACTIVO, EstadoActivo.INACTIVO, EstadoActivo.EN_TRATAMIENTO, EstadoActivo.CERRADO, EstadoActivo.BAJA},
    EstadoActivo.CERRADO:        {EstadoActivo.BAJA},
    EstadoActivo.BAJA:           set(),
}
