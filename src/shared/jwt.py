# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02: token de canal AgroFusion (audiencia propia, corto, sin sesión) |
"""Utilidades de creación y verificación de tokens JWT.

Usa ``python-jose`` con algoritmo HS256. La clave secreta y el tiempo de
expiración se leen de las variables de entorno ``SECRET_KEY`` y
``JWT_EXPIRE_HOURS`` (por defecto 8 horas, según RF-02). El refresh token
(opaco, no JWT — ver ``sesion_comun.py``) usa por separado
``REFRESH_TOKEN_EXPIRE_DAYS`` (por defecto 7 días).

El payload del token contiene:
    - ``sub``: ID del usuario (string).
    - ``jti``: ID de la sesión en DB, permite invalidación individual.
    - ``rol``: ID del rol del usuario.
    - ``exp``: Marca de expiración (timestamp UTC).
    - ``iat``: Marca de emisión (timestamp UTC).
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import ExpiredSignatureError, JWTError, jwt

from src.shared.errors import AuthenticationError

load_dotenv()

JWT_EXPIRE_HOURS_DEFAULT = 8
REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT = 7
JWT_LEEWAY_SECONDS_DEFAULT = 30


def _leer_horas_expiracion() -> int:
    """Lee la vigencia configurable del JWT usando el valor RF-02 por defecto."""
    return int(os.getenv("JWT_EXPIRE_HOURS", str(JWT_EXPIRE_HOURS_DEFAULT)))


def _leer_dias_expiracion_refresco() -> int:
    """Lee la vigencia configurable del refresh token (por defecto 7 días)."""
    return int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", str(REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT)))


def _leer_leeway_segundos() -> int:
    """Lee la tolerancia de skew de reloj al verificar ``exp`` (por defecto 30s).

    Sin tolerancia, un reloj del servidor apenas 1 segundo por detrás del
    emisor convierte un token recién emitido en ``TOKEN_EXPIRADO`` espurio.
    """
    return int(os.getenv("JWT_LEEWAY_SECONDS", str(JWT_LEEWAY_SECONDS_DEFAULT)))


_SECRET_KEY = os.getenv("SECRET_KEY")
_ALGORITHM = "HS256"
_EXPIRE_HOURS = _leer_horas_expiracion()
_REFRESH_EXPIRE_DAYS = _leer_dias_expiracion_refresco()
_LEEWAY_SECONDS = _leer_leeway_segundos()


def create_token(jti: int, id_usuario: int, id_rol: int) -> tuple[str, datetime]:
    """Genera un JWT firmado con los datos de sesión del usuario.

    Args:
        jti: ID de la sesión en DB. Se incluye en el payload para permitir
            la invalidación individual del token sin cambiar la clave secreta.
        id_usuario: ID del usuario autenticado.
        id_rol: ID del rol asignado al usuario.

    Returns:
        Tupla ``(token_string, fecha_expiracion)`` donde ``fecha_expiracion``
        es un datetime UTC con la marca en que el token deja de ser válido.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=_EXPIRE_HOURS)
    payload = {
        "sub": str(id_usuario),
        "jti": str(jti),
        "rol": id_rol,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)
    return token, expire


def token_expiration() -> datetime:
    """Calcula la fecha de expiración para un token emitido ahora.

    Returns:
        Datetime UTC correspondiente a ``ahora + JWT_EXPIRE_HOURS``.
    """
    return datetime.now(timezone.utc) + timedelta(hours=_EXPIRE_HOURS)


def refresh_token_expiration() -> datetime:
    """Calcula la fecha de expiración para un refresh token emitido ahora.

    Returns:
        Datetime UTC correspondiente a ``ahora + REFRESH_TOKEN_EXPIRE_DAYS``.
    """
    return datetime.now(timezone.utc) + timedelta(days=_REFRESH_EXPIRE_DAYS)


def verify_token(token: str) -> dict:
    """Verifica y decodifica un JWT.

    Args:
        token: String del JWT recibido en el header ``Authorization: Bearer``.

    Returns:
        Diccionario con el payload decodificado del token.

    Raises:
        AuthenticationError: Código ``TOKEN_EXPIRADO`` si el token es válido
            pero ya expiró (el frontend puede intentar refrescar en silencio);
            código ``TOKEN_INVALIDO`` si está mal formado o la firma no
            corresponde. Ambos HTTP 401.
    """
    try:
        payload = jwt.decode(
            token,
            _SECRET_KEY,
            algorithms=[_ALGORITHM],
            options={"leeway": _LEEWAY_SECONDS},
        )
        return payload
    except ExpiredSignatureError:
        raise AuthenticationError(
            code="TOKEN_EXPIRADO",
            message="El token de acceso ha expirado.",
        )
    except JWTError:
        raise AuthenticationError(
            code="TOKEN_INVALIDO",
            message="El token es inválido o ha expirado.",
        )


# --- Token de canal (RF-SSO02, RFC-019 D-19.4) ------------------------------------------------------
# Lleva ``aud``: ``verify_token`` (la app web) no pasa audiencia y python-jose rechaza un token con
# ``aud`` en ese caso, así que un token de canal nunca opera la aplicación web. No crea sesión ni
# refresh token, por eso tampoco cierra la sesión interactiva del usuario.
AUDIENCIA_CANAL = "sgpmp-canal-integracion"


def create_token_canal(id_usuario: int, id_rol: int, id_cliente_externo: int, canal: str, minutos: int) -> tuple[str, int]:
    """Emite un token de canal para ``id_usuario`` a nombre del cliente externo.

    Returns:
        Tupla ``(token, segundos_de_vigencia)``.
    """
    ahora = datetime.now(timezone.utc)
    payload = {
        # ``rol`` como lista: AgroFusion decodifica este token para saber los roles del usuario al editarlo.
        "sub": str(id_usuario), "rol": [id_rol], "cli": id_cliente_externo, "canal": canal, "aud": AUDIENCIA_CANAL,
        "jti": uuid.uuid4().hex, "iat": ahora, "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM), minutos * 60


def verify_token_canal(token: str) -> dict:
    """Verifica un token de canal. Cualquier fallo (firma, vigencia, audiencia) es ``NO_AUTENTICADO`` (401)."""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM], audience=AUDIENCIA_CANAL,
                             options={"leeway": _LEEWAY_SECONDS})
    except JWTError:
        payload = None
    if not payload or not payload.get("canal") or not str(payload.get("cli", "")).isdigit():
        raise AuthenticationError(code="NO_AUTENTICADO",
                                  message="La credencial de acceso no es válida o venció. Solicite un acceso nuevo.")
    return payload
