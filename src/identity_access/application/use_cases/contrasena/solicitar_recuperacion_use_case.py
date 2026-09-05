"""Caso de uso: solicitud de recuperación de contraseña.

Aplica rate limiting por IP (máx 3 por hora), genera un token de recuperación
y envía el correo correspondiente. Retorna siempre un mensaje genérico para
evitar enumeración de usuarios registrados.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.notificacion_repository import (
    NotificacionRepository,
)
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.identity_access.infrastructure.email_templates import activation_email, recovery_email
from src.shared.email import send_email
from src.shared.errors import BusinessRuleError

MAX_SOLICITUDES_POR_HORA = 3
TIPO_SOLICITUD_RECUPERACION = 7
ID_CANAL_INTERNO = 2

# Las alertas operativas se entregan a quienes pueden consultar la auditoría.
# Así el destinatario se resuelve mediante RBAC y no con un id de rol fijo.
RECURSO_AUDITORIA = 6
ACCION_LEER = 2

_MENSAJE_GENERICO = "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña en unos minutos."
_MENSAJE_ALERTA_SMTP = (
    "Fallo crítico del servicio SMTP: no se pudo enviar un correo de "
    "recuperación de contraseña después de agotar los reintentos."
)

logger = logging.getLogger(__name__)


class SolicitarRecuperacionUseCase:
    """Orquesta el inicio del flujo de recuperación de contraseña."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        eventos_repo: EventoRepository,
        db: Session,
        notificacion_service=None,
        notificaciones_repo: NotificacionRepository | None = None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta (token de recuperación).
            eventos_repo: Repositorio de dominio de eventos (rate limiting y auditoría).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
            notificaciones_repo: Repositorio usado para crear alertas internas
                dirigidas a los responsables de auditoría.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.eventos_repo = eventos_repo
        self.db = db
        self.notificacion_service = notificacion_service
        self.notificaciones_repo = notificaciones_repo

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
            proxima_vez = hace_una_hora + timedelta(hours=1)
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
            if not self._enviar_correo(
                to=correo,
                subject="Activa tu cuenta en SGPMP",
                html_body=activation_email(usuario.nombre, token_activacion),
                id_usuario=usuario.id_usuario,
                ip=ip,
                contexto="ACTIVACION_CUENTA_PENDIENTE",
            ):
                return _MENSAJE_GENERICO
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
        if not self._enviar_correo(
            to=correo,
            subject="Restablece tu contraseña en SGPMP",
            html_body=recovery_email(usuario.nombre, token),
            id_usuario=usuario.id_usuario,
            ip=ip,
            contexto="RECUPERACION_CONTRASENA",
        ):
            return _MENSAJE_GENERICO

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                id_usuario=usuario.id_usuario,
                correo_destino=correo,
            )

        return _MENSAJE_GENERICO

    def _enviar_correo(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        id_usuario: int,
        ip: str,
        contexto: str,
    ) -> bool:
        """Envía el correo sin exponer al cliente un fallo del SMTP.

        El token y su evento ya fueron confirmados antes de llegar aquí. Ante
        un fallo, se conserva esa primera transacción, se registra el error en
        logs y se intenta crear una alerta interna en una transacción nueva.
        """
        try:
            send_email(to=to, subject=subject, html_body=html_body)
            return True
        except Exception as exc:
            logger.exception(
                "Fallo SMTP agotando reintentos en %s para usuario=%s",
                contexto,
                id_usuario,
            )
            self._alertar_administradores_fallo_smtp(
                id_usuario=id_usuario,
                ip=ip,
                contexto=contexto,
                error=exc,
            )
            return False

    def _alertar_administradores_fallo_smtp(
        self,
        *,
        id_usuario: int,
        ip: str,
        contexto: str,
        error: Exception,
    ) -> None:
        """Crea una notificación interna para los responsables de auditoría.

        La alerta es best-effort porque un segundo fallo técnico no puede
        cambiar la respuesta genérica exigida por RF-08. La notificación se
        enlaza al evento de recuperación ya confirmado para no registrar un
        segundo evento tipo 7 que alteraría el rate limit.
        """
        if self.notificaciones_repo is None:
            logger.error(
                "No se creó la alerta interna de fallo SMTP: repositorio no configurado"
            )
            return

        try:
            destinatarios = self.usuarios_repo.listar_ids_con_permiso(
                id_recurso=RECURSO_AUDITORIA,
                id_accion=ACCION_LEER,
            )
            if not destinatarios:
                logger.error(
                    "No se creó la alerta interna de fallo SMTP: sin destinatarios RBAC"
                )
                return

            id_evento = self.notificaciones_repo.buscar_ultimo_evento_id(
                id_usuario=id_usuario,
                tipo_evento=TIPO_SOLICITUD_RECUPERACION,
            )
            if id_evento is None:
                logger.error(
                    "No se creó la alerta interna de fallo SMTP: evento de recuperación ausente"
                )
                return

            codigo_error = getattr(error, "code", type(error).__name__)
            mensaje = (
                f"{_MENSAJE_ALERTA_SMTP} Usuario relacionado: {id_usuario}. "
                f"Contexto: {contexto}. Código: {codigo_error}."
            )
            for id_destinatario in destinatarios:
                self.notificaciones_repo.registrar(
                    id_evento=id_evento,
                    id_usuario=id_destinatario,
                    id_canal=ID_CANAL_INTERNO,
                    mensaje=mensaje,
                    estado="enviado",
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception(
                "No se pudo persistir la alerta interna por fallo SMTP "
                "en %s para usuario=%s ip=%s",
                contexto,
                id_usuario,
                ip,
            )
