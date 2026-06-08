"""Caso de uso: cambio de contraseña por el propio usuario.

Verifica la contraseña actual, aplica límite de intentos (bloqueo de 30 min
tras 5 fallos), genera el nuevo hash e invalida todas las sesiones activas.
"""
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.contrasena_dto import CambiarContrasenaDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import AuthenticationError, AuthorizationError, BusinessRuleError, LockedError

ESTADO_ACTIVO = 2
MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 30
TIPO_CAMBIO_CONTRASENA = 6


class CambiarContrasenaUseCase:
    """Orquesta el cambio voluntario de contraseña de un usuario autenticado."""

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        cuentas_port: CuentasPort,
        sesiones_port: SesionesPort,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_port: Acceso a datos de usuarios y contraseñas.
            cuentas_port: Control de intentos fallidos y bloqueos.
            sesiones_port: Invalidación de sesiones y auditoría.
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.sesiones_port = sesiones_port
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, id_usuario: int, dto: CambiarContrasenaDTO, usuario_actual: UsuarioActual) -> None:
        """Cambia la contraseña del usuario verificando la contraseña actual.

        Tras un cambio exitoso invalida todas las sesiones activas del usuario,
        forzando un nuevo login en todos los dispositivos.

        Args:
            id_usuario: ID del usuario que cambia su contraseña.
            dto: Contraseña actual y nueva contraseña deseada.
            usuario_actual: Usuario autenticado que realiza la operación.

        Raises:
            AuthorizationError: Si el usuario intenta cambiar la contraseña
                de otra cuenta. HTTP 403.
            BusinessRuleError: Si la cuenta no está activa. HTTP 422.
            LockedError: Si la funcionalidad está bloqueada por intentos fallidos. HTTP 423.
            AuthenticationError: Si la contraseña actual es incorrecta. HTTP 401.
            ConflictError: Si la nueva contraseña fue usada recientemente
                (validado por trigger de DB). HTTP 409.
        """
        # 1. Solo el propio usuario puede cambiar su contraseña
        if id_usuario != usuario_actual.id_usuario:
            raise AuthorizationError(
                code="CAMBIO_NO_AUTORIZADO",
                message=(
                    "Acción no autorizada. Un usuario no puede modificar la contraseña "
                    "de otra cuenta. Este incidente ha sido reportado al log de auditoría."
                ),
            )

        usuario = self.usuarios_port.buscar_por_id(id_usuario)
        cuenta = self.cuentas_port.buscar_cuenta_por_usuario(id_usuario)

        # 2. Cuenta debe estar activa
        if cuenta is None or cuenta.id_estado_cuenta != ESTADO_ACTIVO:
            raise BusinessRuleError(
                code="CUENTA_NO_ACTIVA",
                message="El cambio de contraseña solo está disponible para cuentas activas.",
            )

        # 3. Verificar bloqueo por intentos fallidos de cambio
        ahora = datetime.now(timezone.utc)
        if cuenta.bloqueado_hasta is not None:
            bloqueado_hasta = cuenta.bloqueado_hasta
            if bloqueado_hasta.tzinfo is None:
                bloqueado_hasta = bloqueado_hasta.replace(tzinfo=timezone.utc)
            if bloqueado_hasta > ahora:
                raise LockedError(
                    code="CAMBIO_CONTRASENA_BLOQUEADO",
                    message=(
                        f"Funcionalidad bloqueada temporalmente por múltiples intentos fallidos. "
                        f"Podrá intentar cambiar su contraseña nuevamente a las "
                        f"{bloqueado_hasta.strftime('%H:%M:%S')} (dentro de {MINUTOS_BLOQUEO} minutos)."
                    ),
                )

        # 4. Verificar contraseña actual
        if not bcrypt.checkpw(
            dto.contrasena_actual.encode("utf-8"),
            usuario.contrasena_cifrada.encode("utf-8"),
        ):
            alcanzado_limite = False
            try:
                self.cuentas_port.incrementar_intentos_cambio_contrasena(cuenta)
                alcanzado_limite = cuenta.intentos_fallidos >= MAX_INTENTOS
                if alcanzado_limite:
                    self.cuentas_port.bloquear_cambio_contrasena(cuenta)
                self.sesiones_port.registrar_evento(
                    tipo_evento=TIPO_CAMBIO_CONTRASENA,
                    resultado=EnumEventoResultado.FALLIDO,
                    id_usuario=id_usuario,
                    detalle={
                        "motivo": "contrasena_actual_incorrecta",
                        "intentos_fallidos": cuenta.intentos_fallidos,
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
                raise LockedError(
                    code="CAMBIO_CONTRASENA_BLOQUEADO",
                    message=(
                        f"Funcionalidad bloqueada temporalmente por múltiples intentos fallidos. "
                        f"Podrá intentar cambiar su contraseña nuevamente a las "
                        f"{bloqueado_hasta.strftime('%H:%M:%S')} (dentro de {MINUTOS_BLOQUEO} minutos)."
                    ),
                )

            raise AuthenticationError(
                code="CONTRASENA_ACTUAL_INCORRECTA",
                message=(
                    f"Verificación de identidad fallida. La contraseña actual es incorrecta. "
                    f"Intento {cuenta.intentos_fallidos} de {MAX_INTENTOS}. Al alcanzar el límite, "
                    f"la opción de cambio se bloqueará por {MINUTOS_BLOQUEO} minutos."
                ),
            )

        # 5. Aplicar nueva contraseña (trigger valida no-reuso → ConflictError 409)
        nuevo_hash = bcrypt.hashpw(dto.nueva_contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        try:
            self.usuarios_port.cambiar_contrasena(usuario, nuevo_hash)
            self.cuentas_port.resetear_intentos_cambio_contrasena(cuenta)
            self.sesiones_port.invalidar_todas_sesiones(cuenta.id_cuenta_usuario)
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CAMBIO_CONTRASENA,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=id_usuario,
                detalle={"motivo": "cambio_voluntario"},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_CAMBIO_CONTRASENA,
                id_usuario=id_usuario,
                correo_destino=usuario.correo_electronico,
            )
