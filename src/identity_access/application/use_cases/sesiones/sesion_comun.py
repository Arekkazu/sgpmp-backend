"""Lógica de sesión compartida entre los distintos caminos de autenticación.

``LoginUseCase`` (contraseña), ``SsoLoginUseCase`` (handoff RS256 de
AgroFusion) y ``EmitirTokenAgroFusionUseCase`` (M2M, sin contraseña) verifican
identidad de formas completamente distintas, pero una vez la identidad está
verificada, el resto del flujo — chequear que el estado de la cuenta permite
continuar, invalidar la sesión previa, emitir el JWT y registrar la sesión —
es idéntico. Este módulo extrae esa parte común para no triplicarla.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.shared.errors import AuthorizationError, LockedError
from src.shared.jwt import create_token, token_expiration


def verificar_estado_cuenta(
    cuenta: Cuenta,
    usuario: Usuario,
    cuentas_repo: CuentaRepository,
    db: Session,
    ahora: datetime,
) -> None:
    """Verifica que el estado de la cuenta permite continuar el inicio de sesión.

    Si el bloqueo temporal por intentos fallidos ya expiró, desbloquea la
    cuenta automáticamente (efecto secundario con su propio ``commit``, igual
    que hacía originalmente ``LoginUseCase``).

    Args:
        cuenta: Cuenta asociada al usuario que intenta autenticarse.
        usuario: Usuario dueño de la cuenta (solo se usa para el mensaje de
            error de cuenta pendiente, que referencia su correo).
        cuentas_repo: Puerto de persistencia de cuentas.
        db: Sesión SQLAlchemy activa del request.
        ahora: Instante de referencia (UTC) para comparar bloqueos.

    Raises:
        LockedError: Cuenta bloqueada y el bloqueo sigue vigente. HTTP 423.
        AuthorizationError: Cuenta pendiente de activación o deshabilitada
            (inactiva/eliminada). HTTP 403.
    """
    if cuenta.esta_bloqueada():
        bloqueado_hasta = cuenta.bloqueado_hasta
        if bloqueado_hasta is not None:
            if bloqueado_hasta.tzinfo is None:
                bloqueado_hasta = bloqueado_hasta.replace(tzinfo=timezone.utc)
            if bloqueado_hasta > ahora:
                raise LockedError(
                    code="CUENTA_BLOQUEADA",
                    message=(
                        f"Cuenta bloqueada por seguridad debido a múltiples intentos fallidos. "
                        f"Podrá intentar acceder nuevamente a las {bloqueado_hasta.strftime('%H:%M:%S')} "
                        f"(dentro de 15 minutos exactos)."
                    ),
                )
        # Tiempo de bloqueo expiró → desbloquear automáticamente
        try:
            cuenta.desbloquear()
            cuentas_repo.guardar(cuenta)
            db.commit()
        except Exception:
            db.rollback()
            raise

    if cuenta.esta_pendiente():
        raise AuthorizationError(
            code="CUENTA_PENDIENTE",
            message=(
                f"Acceso denegado. Su cuenta no ha sido activada. Por favor, haga clic en el enlace "
                f"enviado a su correo {usuario.correo} o utilice la opción "
                f"'Re-enviar token de activación'."
            ),
        )

    if cuenta.id_estado_cuenta in (Cuenta.ESTADO_INACTIVO, Cuenta.ESTADO_ELIMINADO):
        raise AuthorizationError(
            code="CUENTA_DESHABILITADA",
            message=(
                "Acceso restringido. Su cuenta ha sido desactivada por políticas de seguridad "
                "o administración. Por favor, contacte al soporte técnico para más información."
            ),
        )


def emitir_sesion(
    usuario: Usuario,
    cuenta: Cuenta,
    ip: str,
    user_agent: str,
    tipo_evento_exitoso: int,
    sesiones_repo: SesionRepository,
    cuentas_repo: CuentaRepository,
    eventos_repo: EventoRepository,
    db: Session,
    ahora: datetime,
    detalle_extra: Optional[dict] = None,
) -> tuple[str, datetime, bool]:
    """Invalida la sesión previa (política de sesión única) y emite una nueva.

    Se asume que la identidad ya fue verificada por el llamador (contraseña,
    SSO externo, o confianza M2M) — esta función no vuelve a verificarla, solo
    orquesta la persistencia de la nueva sesión. Hace ``commit()``: es la única
    escritura de este flujo, el llamador no debe volver a commitear la misma
    transacción.

    Args:
        usuario: Usuario que inicia sesión.
        cuenta: Cuenta asociada, ya validada por :func:`verificar_estado_cuenta`.
        ip: Dirección IP del cliente.
        user_agent: Cadena User-Agent del cliente (se trunca a 255 caracteres).
        tipo_evento_exitoso: ``id_tipo_evento`` a registrar en la auditoría
            (distingue login normal, login SSO, o emisión M2M).
        detalle_extra: Campos adicionales a fusionar en el ``detalle`` del
            evento de auditoría (ej. ``{"mecanismo": "sso"}``).

    Returns:
        Tupla ``(jwt_str, fecha_expiracion, sesion_previa_cerrada)``.
    """
    try:
        cuenta.resetear_intentos()

        sesion_previa_cerrada = False
        sesion_previa = sesiones_repo.buscar_sesion_activa(cuenta.id_cuenta_usuario)
        if sesion_previa is not None:
            sesiones_repo.invalidar_sesion(sesion_previa)
            sesion_previa_cerrada = True

        fecha_expiracion = token_expiration()
        token = sesiones_repo.crear_token_acceso(fecha_expiracion)
        jwt_str, _ = create_token(token.id_token, usuario.id_usuario, usuario.id_rol)

        sesion = sesiones_repo.crear_sesion(
            id_cuenta_usuario=cuenta.id_cuenta_usuario,
            id_token=token.id_token,
            direccion_ip=ip,
            agente_usuario=user_agent[:255],
            fecha_expiracion=fecha_expiracion,
        )

        cuenta.registrar_acceso(ahora)
        cuentas_repo.guardar(cuenta)

        detalle = {"ip": ip, "user_agent": user_agent[:255], "sesion_previa_cerrada": sesion_previa_cerrada}
        if detalle_extra:
            detalle.update(detalle_extra)

        eventos_repo.registrar(
            tipo_evento=tipo_evento_exitoso,
            exitoso=True,
            id_usuario=usuario.id_usuario,
            detalle=detalle,
            id_sesion=sesion.id_sesion,
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return jwt_str, fecha_expiracion, sesion_previa_cerrada
