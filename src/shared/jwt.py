import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import JWTError, jwt

from src.shared.errors import AuthenticationError

load_dotenv()

_SECRET_KEY = os.getenv("SECRET_KEY")
_ALGORITHM = "HS256"
_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


def create_token(jti: int, id_usuario: int, id_rol: int) -> tuple[str, datetime]:
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
    return datetime.now(timezone.utc) + timedelta(hours=_EXPIRE_HOURS)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return payload
    except JWTError:
        raise AuthenticationError(
            code="TOKEN_INVALIDO",
            message="El token es inválido o ha expirado.",
        )
