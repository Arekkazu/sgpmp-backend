from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import AuthenticationError, GoneError, LockedError

MAX_INTENTOS = 5
MINUTOS_EXPIRACION_TOKEN = 15
MINUTOS_BLOQUEO = 30
TIPO_RESTABLECIMIENTO = 8


class RestablecerContrasenaUseCase:

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        cuentas_port: CuentasPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, dto: RestablecerContrasenaDTO, ip: str) -> None:
        # 1. Buscar cuenta por token
        cuenta = self.cuentas_port.buscar_cuenta_por_token_recuperacion(dto.token)
        if cuenta is None:
            raise AuthenticationError(
                code="TOKEN_INVALIDO",
                message=(
                    "Error de autenticidad. El token de recuperación es inválido o ha sido alterado. "
                    "Por favor, inicie un nuevo proceso de recuperación."
                ),
            )

        # 2. Verificar bloqueo por intentos fallidos
        ahora = datetime.now(timezone.utc)
        if cuenta.bloqueado_hasta is not None:
            bloqueado_hasta = cuenta.bloqueado_hasta
            if bloqueado_hasta.tzinfo is None:
                bloqueado_hasta = bloqueado_hasta.replace(tzinfo=timezone.utc)
            if bloqueado_hasta > ahora:
                raise LockedError(
                    code="RESTABLECIMIENTO_BLOQUEADO",
                    message=(
                        f"Demasiados intentos fallidos. Por seguridad, la funcionalidad de "
                        f"restablecimiento ha sido bloqueada temporalmente. "
                        f"Intente nuevamente a las {bloqueado_hasta.strftime('%H:%M:%S')}."
                    ),
                )

        # 3. Verificar expiración del token (15 minutos desde fecha_cambio_estado)
        fecha_generacion = cuenta.fecha_cambio_estado
        if fecha_generacion is not None:
            if fecha_generacion.tzinfo is None:
                fecha_generacion = fecha_generacion.replace(tzinfo=timezone.utc)
            if ahora > fecha_generacion + timedelta(minutes=MINUTOS_EXPIRACION_TOKEN):
                raise GoneError(
                    code="TOKEN_EXPIRADO",
                    message=(
                        "El enlace de recuperación ha expirado. Por seguridad, estos tokens solo "
                        f"son válidos durante {MINUTOS_EXPIRACION_TOKEN} minutos. "
                        "Solicite un nuevo correo de recuperación."
                    ),
                )

        # 4. Obtener usuario asociado
        usuario = self.usuarios_port.buscar_por_id(cuenta.id_usuario)

        # 5. Aplicar nueva contraseña (trigger valida no-reuso → ConflictError 409)
        nuevo_hash = bcrypt.hashpw(dto.nueva_contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        try:
            self.usuarios_port.cambiar_contrasena(usuario, nuevo_hash)

            # 6. Invalidar token de recuperación
            cuenta.token_activacion_actual = None

            # 7. Resetear intentos e invalidar todas las sesiones
            self.cuentas_port.resetear_intentos_cambio_contrasena(cuenta)
            self.sesiones_port.invalidar_todas_sesiones(cuenta.id_cuenta_usuario)

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_RESTABLECIMIENTO,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=cuenta.id_usuario,
                detalle={"ip": ip},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
