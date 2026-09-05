"""Caso de uso: restablecimiento de contraseña mediante token de recuperación.

Verifica el token, su expiración (15 min), aplica la nueva contraseña e
invalida todas las sesiones activas. El token de recuperación se destruye
tras el uso exitoso.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO
from src.shared.errors import AuthenticationError, ConflictError, GoneError, LockedError

MINUTOS_EXPIRACION_TOKEN = 15
TIPO_RESTABLECIMIENTO = 8


class RestablecerContrasenaUseCase:
    """Orquesta el restablecimiento de contraseña vía token de recuperación."""

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
            cuentas_repo: Repositorio de dominio del agregado Cuenta (token y bloqueo).
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

    def execute(self, dto: RestablecerContrasenaDTO, ip: str) -> None:
        """Restablece la contraseña usando el token de recuperación.

        Args:
            dto: Token de recuperación y nueva contraseña deseada.
            ip: IP del cliente, registrada en el evento de auditoría.

        Raises:
            AuthenticationError: Si el token no existe o es inválido. HTTP 401.
            LockedError: Si hay bloqueo por intentos fallidos. HTTP 423.
            GoneError: Si el token expiró (más de 15 min desde su generación). HTTP 410.
            ConflictError: Si la nueva contraseña fue usada recientemente. HTTP 409.
        """
        # 1. Buscar cuenta por token
        cuenta = self.cuentas_repo.obtener_por_hash_token(calcular_hash_token(dto.token))
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
        usuario = self.usuarios_repo.obtener_por_id(cuenta.id_usuario)

        # 5. Comparar el texto transitorio con el hash actual antes de cifrar.
        if usuario.contrasena.verificar(dto.nueva_contrasena):
            raise ConflictError(
                code="CONTRASENA_REUTILIZADA",
                message="La nueva contraseña no puede ser igual a la anterior.",
            )

        # 6. Aplicar nueva contraseña.
        usuario.cambiar_contrasena(Contrasena.cifrar(dto.nueva_contrasena))

        try:
            self.usuarios_repo.cambiar_contrasena(usuario)

            # 7. Consumir token de recuperación, resetear intentos e invalidar sesiones
            cuenta.limpiar_token()
            cuenta.resetear_cambio_contrasena()
            self.cuentas_repo.guardar(cuenta)
            self.sesiones_repo.invalidar_todas_sesiones(cuenta.id_cuenta_usuario)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_RESTABLECIMIENTO,
                exitoso=True,
                id_usuario=cuenta.id_usuario,
                detalle={"ip": ip},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_RESTABLECIMIENTO,
                id_usuario=cuenta.id_usuario,
                correo_destino=str(usuario.correo),
            )
