from datetime import datetime, timezone

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

    def execute(self, id_usuario: int, dto: CambiarContrasenaDTO, usuario_actual: UsuarioActual) -> None:
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
