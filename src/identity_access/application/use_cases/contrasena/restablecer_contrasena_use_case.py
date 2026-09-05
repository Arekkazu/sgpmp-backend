"""Caso de uso: restablecimiento de contraseña mediante token de recuperación.

Verifica el token, su expiración (15 min), aplica la nueva contraseña e
invalida todas las sesiones activas. El token de recuperación se destruye
tras el uso exitoso.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.intento_anonimo_repository import IntentoAnonimoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.contrasena_dto import RestablecerContrasenaDTO
from src.shared.errors import AuthenticationError, ConflictError, GoneError, LockedError

MINUTOS_EXPIRACION_TOKEN = 15
TIPO_RESTABLECIMIENTO = 8

MAX_INTENTOS_TOKEN_INVALIDO = 5
MINUTOS_BLOQUEO_TOKEN_INVALIDO = 30
TIPO_INTENTO_TOKEN_INVALIDO = "RESTABLECER_TOKEN_INVALIDO"


class RestablecerContrasenaUseCase:
    """Orquesta el restablecimiento de contraseña vía token de recuperación."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        intentos_anonimos_repo: IntentoAnonimoRepository,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta (token y bloqueo).
            sesiones_repo: Repositorio de dominio de sesiones (invalidación).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            intentos_anonimos_repo: Repositorio de intentos por IP sin actor
                identificado (bloqueo tras tokens inválidos repetidos).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.intentos_anonimos_repo = intentos_anonimos_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, dto: RestablecerContrasenaDTO, ip: str) -> None:
        """Restablece la contraseña usando el token de recuperación.

        Args:
            dto: Token de recuperación y nueva contraseña deseada.
            ip: IP del cliente, registrada en el evento de auditoría.

        Raises:
            AuthenticationError: Si el token no existe o es inválido. HTTP 401.
            LockedError: Si hay bloqueo por intentos fallidos (de la cuenta, o
                por IP tras varios tokens inválidos). HTTP 423.
            GoneError: Si el token expiró (más de 15 min desde su generación). HTTP 410.
            ConflictError: Si el token ya fue consumido en un restablecimiento
                exitoso previo, o si la nueva contraseña fue usada
                recientemente. HTTP 409.
        """
        ahora = datetime.now(timezone.utc)

        # 1. Buscar cuenta por token. Un hash que no coincide con ninguna cuenta
        #    no distingue por sí solo "nunca existió" de "ya se generó uno nuevo",
        #    así que aquí solo cabe el 401 genérico. El caso "este MISMO token ya
        #    se usó con éxito" se resuelve más abajo (paso 1.1): el hash se
        #    conserva al consumirlo, así que si existe pero está usado, sí hay
        #    cuenta que encontrar.
        cuenta = self.cuentas_repo.obtener_por_hash_token(calcular_hash_token(dto.token))
        if cuenta is None:
            self._registrar_intento_token_invalido_o_bloquear(ip, ahora)
            raise AuthenticationError(
                code="TOKEN_INVALIDO",
                message=(
                    "Error de autenticidad. El token de recuperación es inválido o ha sido alterado. "
                    "Por favor, inicie un nuevo proceso de recuperación."
                ),
            )

        # 1.1 Token encontrado pero ya consumido en un restablecimiento anterior.
        if cuenta.token_usado:
            raise ConflictError(
                code="TOKEN_YA_UTILIZADO",
                message=(
                    "Este token de recuperación ya fue utilizado para restablecer la "
                    "contraseña. Solicite un nuevo correo de recuperación si necesita "
                    "cambiarla de nuevo."
                ),
            )

        # 2. Verificar bloqueo por intentos fallidos
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
            cuenta.marcar_token_usado()
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

    def _registrar_intento_token_invalido_o_bloquear(self, ip: str, ahora: datetime) -> None:
        """Cuenta los tokens inválidos recibidos desde ``ip`` y bloquea al 5º.

        No hay una `Cuenta` a la que atarle un contador de intentos (el token
        no coincide con ninguna), así que el bloqueo se hace por IP en una
        tabla aparte (ver ``IntentoAnonimoRepository``). El registro debe
        sobrevivir aunque el método termine lanzando una excepción, por eso el
        commit va aquí y no en el bloque try/except del flujo principal.
        """
        ventana = ahora - timedelta(minutes=MINUTOS_BLOQUEO_TOKEN_INVALIDO)
        try:
            self.intentos_anonimos_repo.registrar(TIPO_INTENTO_TOKEN_INVALIDO, ip)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        intentos = self.intentos_anonimos_repo.contar_por_ip(TIPO_INTENTO_TOKEN_INVALIDO, ip, ventana)
        if intentos < MAX_INTENTOS_TOKEN_INVALIDO:
            return

        mas_antiguo = self.intentos_anonimos_repo.obtener_fecha_mas_antigua_por_ip(
            TIPO_INTENTO_TOKEN_INVALIDO, ip, ventana
        )
        bloqueado_hasta = (mas_antiguo or ahora) + timedelta(minutes=MINUTOS_BLOQUEO_TOKEN_INVALIDO)
        raise LockedError(
            code="RESTABLECIMIENTO_BLOQUEADO",
            message=(
                f"Demasiados intentos con tokens inválidos desde su conexión. Por "
                f"seguridad, la funcionalidad de restablecimiento ha sido bloqueada "
                f"temporalmente. Intente nuevamente a las {bloqueado_hasta.strftime('%H:%M:%S')}."
            ),
        )
