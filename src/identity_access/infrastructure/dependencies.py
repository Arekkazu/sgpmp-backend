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
from src.shared.audit_context import establecer_id_token
from src.shared.database import get_db
from src.shared.errors import AuthenticationError
from src.shared.jwt import verify_token

INACTIVIDAD_MINUTOS = 30


@dataclass
class UsuarioActual:
    """Identidad autenticada con el rol y el estado de cuenta vigentes en la DB."""

    id_usuario: int
    id_token: int
    id_rol: int
    # RF-04 exige que los permisos solo sean efectivos para cuentas activas.
    # ``require_permission`` lo comprueba leyendo este campo, así se evita que
    # RBAC tenga que volver a consultar la cuenta. El default ``None`` deja el
    # chequeo cerrado por omisión para cualquier construcción manual.
    id_estado_cuenta: Optional[int] = None


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> UsuarioActual:
    """Valida el token Bearer y retorna el usuario autenticado.

    Args:
        authorization: Cabecera `Authorization: Bearer <token>`.
        db: Sesión de base de datos inyectada por FastAPI.

    Returns:
        `UsuarioActual` con la identidad del JWT y el rol y estado de cuenta
        vigentes en la base.

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
    # aplicar una reasignación administrativa sin cerrar la sesión del usuario
    # (RF-04). Se lee junto con la cuenta en una sola consulta porque el bloque
    # de inactividad de abajo necesita esa fila de todos modos.
    fila = (
        db.query(Usuarios.id_rol, CuentasUsuarios)
        .outerjoin(CuentasUsuarios, CuentasUsuarios.id_usuario == Usuarios.id_usuario)
        .filter(Usuarios.id_usuario == id_usuario)
        .first()
    )
    if fila is None:
        # RF-06 prohíbe el borrado físico de usuarios, así que llegar aquí
        # significa que la sesión apunta a una fila que ya no existe. Para el
        # cliente es indistinguible de un token revocado.
        raise AuthenticationError(
            code="TOKEN_REVOCADO",
            message="El token de sesión ha sido revocado o es inválido.",
        )

    id_rol_vigente, cuenta = fila

    # Verificar inactividad de 30 minutos
    ahora = datetime.now(timezone.utc)

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

    # RF-10: de este token el repositorio de auditoría deriva la sesión con la
    # que se registra cada evento del request.
    establecer_id_token(id_token)

    return UsuarioActual(
        id_usuario=id_usuario,
        id_token=id_token,
        id_rol=id_rol_vigente,
        id_estado_cuenta=cuenta.id_estado_cuenta if cuenta is not None else None,
    )
