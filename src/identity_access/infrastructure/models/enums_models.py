import enum

class EnumAccionCuenta(str, enum.Enum):
    ACTIVAR = 'activar'
    INACTIVAR = 'inactivar'
    ELIMINAR = 'eliminar'
    BLOQUEAR = 'bloquear'
    PENDIENTE = 'pendiente'


class EnumEstadoEnvio(str, enum.Enum):
    EN_COLA = 'en_cola'
    ENVIADO = 'enviado'
    FALLIDO = 'fallido'


class EnumEventoResultado(str, enum.Enum):
    EXITOSO = 'exitoso'
    FALLIDO = 'fallido'


class EnumTokenTipo(str, enum.Enum):
    RECUPERACION = 'recuperacion'
    VERIFICACION_CORREO = 'verificacion_correo'
    ACCESO = 'acceso'


class EnumUsuarioGenero(str, enum.Enum):
    M = 'M'
    X = 'X'
    F = 'F'
    T = 'T'