"""Caso de uso: inicio de sesión de usuario.

Valida credenciales, aplica política de bloqueo por intentos fallidos,
crea sesión y emite JWT. Implementa la política de sesión única:
invalida la sesión activa anterior si existe.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.sesiones.sesion_comun import (
    emitir_sesion,
    verificar_estado_cuenta,
)
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dto.usuario_dto import LoginDTO
from src.shared.errors import AuthenticationError, LockedError

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
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case con sus dependencias.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta.
            sesiones_repo: Repositorio de dominio de sesiones y tokens.
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones. ``None`` deshabilita
                las notificaciones sin afectar el flujo principal.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(
        self, dto: LoginDTO, ip: str, user_agent: str
    ) -> tuple[str, datetime, bool, int, str, datetime]:
        """Autentica al usuario y crea una nueva sesión activa.

        Args:
            dto: Credenciales del usuario (correo y contraseña).
            ip: Dirección IP del cliente, registrada en la sesión y auditoría.
            user_agent: Cadena User-Agent del cliente, truncada a 255 caracteres.

        Returns:
            Tupla ``(jwt_str, fecha_expiracion, sesion_previa_cerrada, id_usuario,
            refresh_raw, fecha_expiracion_refresco)`` donde ``sesion_previa_cerrada``
            indica si se invalidó una sesión activa anterior (política de sesión
            única) y ``refresh_raw`` es el valor en claro del refresh token
            (se transporta por cookie, nunca en el JSON de respuesta).

        Raises:
            AuthenticationError: Credenciales incorrectas. HTTP 401.
            AuthorizationError: Cuenta pendiente de activación o deshabilitada. HTTP 403.
            LockedError: Cuenta bloqueada temporalmente por intentos fallidos. HTTP 423.
        """
        # 1. Buscar usuario por correo
        usuario = self.usuarios_repo.obtener_por_correo(Email(dto.correo_electronico))
        if usuario is None:
            raise AuthenticationError(
                code="CREDENCIALES_INVALIDAS",
                message="Credenciales incorrectas. Verifica tu correo electrónico y contraseña.",
            )

        # 2. Buscar cuenta asociada
        cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)

        # 3. Verificar estado de la cuenta
        ahora = datetime.now(timezone.utc)
        verificar_estado_cuenta(cuenta, usuario, self.cuentas_repo, self.db, ahora)

        # 4. Verificar contraseña
        if not usuario.contrasena.verificar(dto.contrasena):
            try:
                cuenta.incrementar_intentos(ahora)
                alcanzado_limite = cuenta.intentos_fallidos >= MAX_INTENTOS
                if alcanzado_limite:
                    cuenta.bloquear(ahora)
                self.cuentas_repo.guardar(cuenta)
                self.eventos_repo.registrar(
                    tipo_evento=TIPO_LOGIN_FALLIDO,
                    exitoso=False,
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
                        correo_destino=str(usuario.correo),
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
        jwt_str, fecha_expiracion, sesion_previa_cerrada, refresh_raw, fecha_expiracion_refresco = emitir_sesion(
            usuario=usuario,
            cuenta=cuenta,
            ip=ip,
            user_agent=user_agent,
            tipo_evento_exitoso=TIPO_LOGIN_EXITOSO,
            sesiones_repo=self.sesiones_repo,
            cuentas_repo=self.cuentas_repo,
            eventos_repo=self.eventos_repo,
            db=self.db,
            ahora=ahora,
        )

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_LOGIN_EXITOSO,
                id_usuario=usuario.id_usuario,
                correo_destino=str(usuario.correo),
            )

        return (
            jwt_str,
            fecha_expiracion,
            sesion_previa_cerrada,
            usuario.id_usuario,
            refresh_raw,
            fecha_expiracion_refresco,
        )
