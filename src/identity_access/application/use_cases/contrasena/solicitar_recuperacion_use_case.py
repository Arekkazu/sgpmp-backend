"""Caso de uso: solicitud de recuperación de contraseña.

Aplica rate limiting por IP (máx 3 por hora), genera un token de recuperación
y envía el correo correspondiente. Retorna siempre un mensaje genérico para
evitar enumeración de usuarios registrados.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.identity_access.infrastructure.email_templates import activation_email, recovery_email
from src.shared.email import send_email
from src.shared.errors import BusinessRuleError

MAX_SOLICITUDES_POR_HORA = 3
TIPO_SOLICITUD_RECUPERACION = 7

_MENSAJE_GENERICO = "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña en unos minutos."


class SolicitarRecuperacionUseCase:
    """Orquesta el inicio del flujo de recuperación de contraseña."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        eventos_repo: EventoRepository,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta (token de recuperación).
            eventos_repo: Repositorio de dominio de eventos (rate limiting y auditoría).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.eventos_repo = eventos_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, dto: SolicitarRecuperacionDTO, ip: str) -> str:
        """Inicia el proceso de recuperación de contraseña para el correo indicado.

        Si la cuenta está en estado PENDIENTE, redirige al flujo de activación
        en lugar del de recuperación. Si el correo no existe o la cuenta está
        eliminada, retorna el mensaje genérico sin revelar información.

        Args:
            dto: Correo electrónico del usuario que solicita la recuperación.
            ip: IP del cliente, usada para el rate limiting por hora.

        Returns:
            Mensaje genérico que no revela si el correo está registrado.

        Raises:
            BusinessRuleError: Si se supera el límite de 3 solicitudes por hora
                desde la misma IP. HTTP 422.
        """
        # 1. Rate limit por IP: máx 3 solicitudes por hora
        ahora = datetime.now(timezone.utc)
        hace_una_hora = ahora - timedelta(hours=1)
        solicitudes = self.eventos_repo.contar_solicitudes_recuperacion_por_ip(ip, hace_una_hora)
        if solicitudes >= MAX_SOLICITUDES_POR_HORA:
            primera_solicitud = (
                self.eventos_repo.obtener_primera_solicitud_recuperacion_por_ip(
                    ip,
                    hace_una_hora,
                )
            )
            # El conteo y el mínimo usan exactamente la misma ventana. El fallback
            # defensivo evita informar una hora ya vencida si un adaptador externo
            # entrega datos inconsistentes entre ambas consultas.
            proxima_vez = (primera_solicitud or ahora) + timedelta(hours=1)
            raise BusinessRuleError(
                code="LIMITE_SOLICITUDES_EXCEDIDO",
                message=(
                    f"Límite de solicitudes excedido para su conexión. Por seguridad, solo se "
                    f"permiten {MAX_SOLICITUDES_POR_HORA} intentos de recuperación por hora. "
                    f"Podrá intentarlo de nuevo a las {proxima_vez.strftime('%H:%M:%S')}."
                ),
            )

        # 2. Buscar usuario — flujo interno solo si existe y no está eliminado
        correo = str(dto.correo_electronico)
        usuario = self.usuarios_repo.obtener_por_correo(Email(correo))
        if usuario is None:
            return _MENSAJE_GENERICO

        cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)
        if cuenta is None or cuenta.id_estado_cuenta == Cuenta.ESTADO_ELIMINADO:
            return _MENSAJE_GENERICO

        # 3. Cuenta en PENDIENTE: rotar y enviar un token de activación.
        # El valor anterior no se puede recuperar porque la BD solo guarda su hash.
        if cuenta.esta_pendiente():
            token_activacion = secrets.token_urlsafe(32)
            try:
                cuenta.asignar_token_activacion(calcular_hash_token(token_activacion), ahora)
                self.cuentas_repo.guardar(cuenta)
                self.eventos_repo.registrar(
                    tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                    exitoso=True,
                    id_usuario=usuario.id_usuario,
                    detalle={"ip": ip, "motivo": "cuenta_pendiente_token_activacion_rotado"},
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            send_email(
                to=correo,
                subject="Activa tu cuenta en SGPMP",
                html_body=activation_email(usuario.nombre, token_activacion),
            )
            return _MENSAJE_GENERICO

        # 4. Generar token de recuperación y guardarlo
        token = secrets.token_urlsafe(32)
        try:
            cuenta.asignar_token_recuperacion(calcular_hash_token(token), ahora)
            self.cuentas_repo.guardar(cuenta)
            self.eventos_repo.registrar(
                tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={"ip": ip, "motivo": "token_generado"},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # 5. Enviar email de recuperación (post-commit)
        send_email(
            to=correo,
            subject="Restablece tu contraseña en SGPMP",
            html_body=recovery_email(usuario.nombre, token),
        )

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                id_usuario=usuario.id_usuario,
                correo_destino=correo,
            )

        return _MENSAJE_GENERICO
