"""Caso de uso: cambio de contraseña por el propio usuario.

Verifica la contraseña actual, aplica límite de intentos (bloqueo de 30 min
tras 5 fallos), aplica el nuevo hash e invalida todas las sesiones activas.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.contrasena_dto import CambiarContrasenaDTO
from src.shared.errors import AuthenticationError, AuthorizationError, BusinessRuleError, ConflictError, InfrastructureError, LockedError

logger = logging.getLogger(__name__)

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 30
TIPO_CAMBIO_CONTRASENA = 6


class CambiarContrasenaUseCase:
    """Orquesta el cambio voluntario de contraseña de un usuario autenticado."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta (intentos y bloqueos).
            sesiones_repo: Repositorio de dominio de sesiones (invalidación).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, id_usuario: int, dto: CambiarContrasenaDTO, usuario_actual: UsuarioActual) -> None:
        """Cambia la contraseña del usuario verificando la contraseña actual.

        Tras un cambio exitoso invalida todas las sesiones activas del usuario,
        forzando un nuevo login en todos los dispositivos. Si falla la invalidación,
        conserva la contraseña confirmada y devuelve un error controlado.

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
            InfrastructureError: Si falla la invalidación tras confirmar
                la contraseña y su auditoría. HTTP 500.
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

        usuario = self.usuarios_repo.obtener_por_id(id_usuario)
        cuenta = self.cuentas_repo.obtener_por_usuario(id_usuario)

        # 2. Cuenta debe estar activa
        if cuenta is None or not cuenta.esta_activa():
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
        if not usuario.contrasena.verificar(dto.contrasena_actual):
            alcanzado_limite = False
            try:
                cuenta.incrementar_intentos(ahora)
                alcanzado_limite = cuenta.intentos_fallidos >= MAX_INTENTOS
                if alcanzado_limite:
                    cuenta.bloquear_cambio_contrasena(ahora)
                self.cuentas_repo.guardar(cuenta)
                self.eventos_repo.registrar(
                    tipo_evento=TIPO_CAMBIO_CONTRASENA,
                    exitoso=False,
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

        # 5. Comparar contra el hash actual antes de generar uno nuevo. Dos hashes
        # bcrypt de la misma clave son distintos por el salt y no pueden compararse.
        if usuario.contrasena.verificar(dto.nueva_contrasena):
            raise ConflictError(
                code="CONTRASENA_REUTILIZADA",
                message=(
                    "No se permite reutilizar la contraseña actual. "
                    "Defina una clave completamente nueva."
                ),
            )

        # 6. Aplicar nueva contraseña.
        try:
            nueva_contrasena = Contrasena.cifrar(dto.nueva_contrasena)
        except Exception as exc:
            self.db.rollback()
            raise InfrastructureError(
                code="ERROR_CIFRADO_CONTRASENA",
                message=(
                    "Error interno de seguridad al cifrar la nueva credencial. "
                    "La contraseña anterior sigue vigente."
                ),
                original_error=exc,
            ) from exc
        usuario.cambiar_contrasena(nueva_contrasena)

        try:
            self.usuarios_repo.cambiar_contrasena(usuario)
            cuenta.resetear_cambio_contrasena()
            self.cuentas_repo.guardar(cuenta)
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CAMBIO_CONTRASENA,
                exitoso=True,
                id_usuario=id_usuario,
                detalle={"motivo": "cambio_voluntario"},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # RF-07 conserva la contraseña y su auditoría aunque falle el cierre.
        # RF-09 tiene una política distinta: no compartir esta separación allí.
        error_invalidacion = None
        try:
            self.sesiones_repo.invalidar_todas_sesiones(cuenta.id_cuenta_usuario)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()  # Solo revierte la transacción de sesiones.
            logger.exception("Fallo al invalidar sesiones tras cambio de contraseña: usuario=%s", id_usuario)
            error_invalidacion = InfrastructureError(
                code="CAMBIO_CONTRASENA_INVALIDACION_FALLIDA",
                message=(
                    "Contraseña actualizada, pero ocurrió un error al cerrar las sesiones "
                    "en otros dispositivos. Se recomienda cerrar sesión manualmente en "
                    "todos sus equipos para garantizar la seguridad."
                ),
                original_error=exc,
            )

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_CAMBIO_CONTRASENA,
                id_usuario=id_usuario,
                correo_destino=str(usuario.correo),
            )

        if error_invalidacion is not None:
            raise error_invalidacion from error_invalidacion.original_error
