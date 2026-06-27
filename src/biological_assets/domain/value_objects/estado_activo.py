from enum import IntEnum


class EstadoActivo(IntEnum):
    ACTIVO = 1
    INACTIVO = 2
    EN_TRATAMIENTO = 3
    AISLADO = 4
    CERRADO = 5
    BAJA = 6
