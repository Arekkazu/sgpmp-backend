"""Dependencias de autenticación para los endpoints de FastAPI.

`get_current_user` valida el token Bearer, verifica la blacklist, obtiene el rol
vigente desde la base y aplica el timeout de inactividad de 30 minutos. Se usa
como `Depends` en los endpoints que requieren autenticación.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.tokens_model import Tokens
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.database import get_db
from src.shared.errors import AuthenticationError
from src.shared.jwt import verify_token

INACTIVIDAD_MINUTOS = 30


@dataclass
class UsuarioActual:
    """Identidad autenticada con el rol vigente verificado contra la DB."""

    id_usuario: int
    id_token: int
    id_rol: int


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> UsuarioActual:
    """Valida el token Bearer y retorna el usuario autenticado.

    Args:
        authorization: Cabecera `Authorization: Bearer <token>`.
        db: Sesión de base de datos inyectada por FastAPI.

    Returns:
        `UsuarioActual` con la identidad del JWT y el rol vigente en la base.

    Raises:
        AuthenticationError: Si falta el token, está revocado o la sesión
            expiró por inactividad (30 min sin actividad). HTTP 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError(
            code="TOKEN_REQUERIDO",
            message="Se requiere autenticación. Proporciona un token Bearer válido.",
        )

    token_str = authorization.removeprefix("Bearer ")
    payload = verify_token(token_str)

    id_token = int(payload["jti"])
    id_usuario = int(payload["sub"])

    # Verificar blacklist
    token = db.query(Tokens).filter(Tokens.id_token == id_token).first()
    if token is None or token.fecha_uso is not None:
        raise AuthenticationError(
            code="TOKEN_REVOCADO",
            message="El token de sesión ha sido revocado o es inválido.",
        )

    # El claim ``rol`` se conserva en el JWT por compatibilidad, pero no es
    # autoridad para RBAC. Consultar el rol vigente en cada request permite
    # aplicar una reasignación administrativa sin cerrar la sesión del usuario.
    id_rol_vigente = (
        db.query(Usuarios.id_rol)
        .filter(Usuarios.id_usuario == id_usuario)
        .scalar()
    )
    if id_rol_vigente is None:
        raise AuthenticationError(
            code="USUARIO_SESION_INVALIDO",
            message="El usuario asociado a la sesión ya no existe.",
        )

    # Verificar inactividad de 30 minutos
    ahora = datetime.now(timezone.utc)
    cuenta = db.query(CuentasUsuarios).filter(CuentasUsuarios.id_usuario == id_usuario).first()

    if cuenta is not None and cuenta.ultimo_acceso is not None:
        ultimo_acceso = cuenta.ultimo_acceso
        if ultimo_acceso.tzinfo is None:
            ultimo_acceso = ultimo_acceso.replace(tzinfo=timezone.utc)

        if ahora - ultimo_acceso > timedelta(minutes=INACTIVIDAD_MINUTOS):
            sesion = (
                db.query(Sesiones)
                .filter(Sesiones.id_token == id_token, Sesiones.es_activa.is_(True))
                .first()
            )
            if sesion is not None:
                sesion.es_activa = False
                sesion.fecha_finalizacion = ahora
            token.fecha_uso = ahora
            db.commit()
            raise AuthenticationError(
                code="SESION_EXPIRADA_INACTIVIDAD",
                message="Su sesión ha expirado por inactividad. Por favor, inicie sesión nuevamente.",
            )

    # Actualizar último acceso
    if cuenta is not None:
        cuenta.ultimo_acceso = ahora
        db.commit()

    return UsuarioActual(
        id_usuario=id_usuario,
        id_token=id_token,
        id_rol=id_rol_vigente,
    )
