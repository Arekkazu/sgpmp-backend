from enum import IntEnum


class EstadoActivo(IntEnum):
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
