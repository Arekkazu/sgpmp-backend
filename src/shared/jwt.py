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
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import ExpiredSignatureError, JWTError, jwt

from src.shared.errors import AuthenticationError

load_dotenv()

JWT_EXPIRE_HOURS_DEFAULT = 8
REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT = 7


def _leer_horas_expiracion() -> int:
    """Lee la vigencia configurable del JWT usando el valor RF-02 por defecto."""
    return int(os.getenv("JWT_EXPIRE_HOURS", str(JWT_EXPIRE_HOURS_DEFAULT)))


def _leer_dias_expiracion_refresco() -> int:
    """Lee la vigencia configurable del refresh token (por defecto 7 días)."""
    return int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", str(REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT)))


_SECRET_KEY = os.getenv("SECRET_KEY")
_ALGORITHM = "HS256"
_EXPIRE_HOURS = _leer_horas_expiracion()
_REFRESH_EXPIRE_DAYS = _leer_dias_expiracion_refresco()


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
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
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
