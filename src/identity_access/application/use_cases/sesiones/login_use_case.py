"""Caso de uso: inicio de sesión de usuario.

Valida credenciales, aplica política de bloqueo por intentos fallidos,
crea sesión y emite JWT. Implementa la política de sesión única:
invalida la sesión activa anterior si existe.
"""
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import AuthenticationError, AuthorizationError, LockedError
from src.shared.jwt import create_token, token_expiration

ESTADO_PENDIENTE = 1
ESTADO_ACTIVO = 2
ESTADO_INACTIVO = 3
ESTADO_BLOQUEADO = 4
ESTADO_ELIMINADO = 5

MAX_INTENTOS = 5
TIPO_LOGIN_EXITOSO = 3
TIPO_LOGIN_FALLIDO = 4


class LoginUseCase:
    """Orquesta el flujo completo de autenticación de un usuario.

    Aplica las reglas de negocio de bloqueo temporal (15 min tras 5 intentos
    fallidos), valida el estado de la cuenta y emite un JWT vinculado a una
    sesión persistida en DB.
    """

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        cuentas_port: CuentasPort,
        sesiones_port: SesionesPort,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case con sus dependencias.

        Args:
            usuarios_port: Acceso a datos de usuarios.
            cuentas_port: Acceso a datos de cuentas y control de intentos.
            sesiones_port: Creación de sesiones y registro de eventos.
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones. ``None`` deshabilita
                las notificaciones sin afectar el flujo principal.
        """
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.sesiones_port = sesiones_port
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, dto: LoginDTO, ip: str, user_agent: str) -> tuple[str, datetime, bool, int]:
        """Autentica al usuario y crea una nueva sesión activa.

        Args:
            dto: Credenciales del usuario (correo y contraseña).
            ip: Dirección IP del cliente, registrada en la sesión y auditoría.
            user_agent: Cadena User-Agent del cliente, truncada a 255 caracteres.

        Returns:
            Tupla ``(jwt_str, fecha_expiracion, sesion_previa_cerrada, id_usuario)``
            donde ``sesion_previa_cerrada`` indica si se invalidó una sesión activa
            anterior (política de sesión única).

        Raises:
            AuthenticationError: Credenciales incorrectas. HTTP 401.
            AuthorizationError: Cuenta pendiente de activación o deshabilitada. HTTP 403.
            LockedError: Cuenta bloqueada temporalmente por intentos fallidos. HTTP 423.
        """
        # 1. Buscar usuario por correo
        usuario = self.usuarios_port.buscar_por_correo(dto.correo_electronico)
        if usuario is None:
            raise AuthenticationError(
                code="CREDENCIALES_INVALIDAS",
                message="Credenciales incorrectas. Verifica tu correo electrónico y contraseña.",
            )

        # 2. Buscar cuenta asociada
        cuenta = self.cuentas_port.buscar_cuenta_por_usuario(usuario.id_usuario)

        # 3. Verificar estado de la cuenta
        ahora = datetime.now(timezone.utc)

        if cuenta.id_estado_cuenta == ESTADO_BLOQUEADO:
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
                cuenta.id_estado_cuenta = ESTADO_ACTIVO
                self.db.flush()
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

        if cuenta.id_estado_cuenta == ESTADO_PENDIENTE:
            raise AuthorizationError(
                code="CUENTA_PENDIENTE",
                message=(
                    f"Acceso denegado. Su cuenta no ha sido activada. Por favor, haga clic en el enlace "
                    f"enviado a su correo {usuario.correo_electronico} o utilice la opción "
                    f"'Re-enviar token de activación'."
                ),
            )

        if cuenta.id_estado_cuenta in (ESTADO_INACTIVO, ESTADO_ELIMINADO):
            raise AuthorizationError(
                code="CUENTA_DESHABILITADA",
                message=(
                    "Acceso restringido. Su cuenta ha sido desactivada por políticas de seguridad "
                    "o administración. Por favor, contacte al soporte técnico para más información."
                ),
            )

        # 4. Verificar contraseña
        if not bcrypt.checkpw(dto.contrasena.encode("utf-8"), usuario.contrasena_cifrada.encode("utf-8")):
            try:
                self.cuentas_port.incrementar_intentos_fallidos(cuenta)
                alcanzado_limite = cuenta.intentos_fallidos >= MAX_INTENTOS
                if alcanzado_limite:
                    self.cuentas_port.bloquear_cuenta(cuenta)
                self.sesiones_port.registrar_evento(
                    tipo_evento=TIPO_LOGIN_FALLIDO,
                    resultado=EnumEventoResultado.FALLIDO,
                    id_usuario=usuario.id_usuario,
                    detalle={
                        "ip": ip,
                        "intentos_fallidos": cuenta.intentos_fallidos,
                        "motivo": "credenciales_invalidas",
                    },
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

            if alcanzado_limite:
                bloqueado_hasta = cuenta.bloqueado_hasta
                if bloqueado_hasta is not None and bloqueado_hasta.tzinfo is None:
                    bloqueado_hasta = bloqueado_hasta.replace(tzinfo=timezone.utc)
                if self.notificacion_service:
                    self.notificacion_service.notificar(
                        tipo_evento=TIPO_LOGIN_FALLIDO,
                        id_usuario=usuario.id_usuario,
                        correo_destino=usuario.correo_electronico,
                    )
                raise LockedError(
                    code="CUENTA_BLOQUEADA",
                    message=(
                        f"Cuenta bloqueada por seguridad debido a múltiples intentos fallidos. "
                        f"Podrá intentar acceder nuevamente a las {bloqueado_hasta.strftime('%H:%M:%S')} "
                        f"(dentro de 15 minutos exactos)."
                    ),
                )

            raise AuthenticationError(
                code="CREDENCIALES_INVALIDAS",
                message=(
                    f"Credenciales incorrectas. Intento {cuenta.intentos_fallidos} de 5. "
                    f"Tras el quinto intento fallido, su cuenta será bloqueada por 15 minutos por seguridad."
                ),
            )

        # 5. Login exitoso
        sesion_previa_cerrada = False
        try:
            self.cuentas_port.resetear_intentos(cuenta)

            sesion_previa = self.sesiones_port.buscar_sesion_activa(cuenta.id_cuenta_usuario)
            if sesion_previa is not None:
                self.sesiones_port.invalidar_sesion(sesion_previa)
                sesion_previa_cerrada = True

            fecha_expiracion = token_expiration()
            token_db = self.sesiones_port.crear_token_acceso(fecha_expiracion)
            jwt_str, _ = create_token(token_db.id_token, usuario.id_usuario, usuario.id_rol)

            sesion = self.sesiones_port.crear_sesion(
                id_cuenta_usuario=cuenta.id_cuenta_usuario,
                id_token=token_db.id_token,
                direccion_ip=ip,
                agente_usuario=user_agent[:255],
                fecha_expiracion=fecha_expiracion,
            )

            self.cuentas_port.actualizar_ultimo_acceso(cuenta)

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_LOGIN_EXITOSO,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario.id_usuario,
                detalle={
                    "ip": ip,
                    "user_agent": user_agent[:255],
                    "sesion_previa_cerrada": sesion_previa_cerrada,
                },
                id_sesion=sesion.id_sesion,
            )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_LOGIN_EXITOSO,
                id_usuario=usuario.id_usuario,
                correo_destino=usuario.correo_electronico,
            )

        return jwt_str, fecha_expiracion, sesion_previa_cerrada, usuario.id_usuario
