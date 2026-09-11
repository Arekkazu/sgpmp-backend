"""Caso de uso: reenvío del token de activación de cuenta.

Genera un nuevo token, lo guarda en la cuenta PENDIENTE y envía el correo.
Aplica rate limiting por IP (máx 3 por hora) para que el endpoint no sirva
como vector de bombardeo de correo, y responde siempre el mismo mensaje
genérico para no revelar qué correos están registrados.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.usuario_dto import ReenviarTokenDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email
from src.shared.errors import BusinessRuleError

MAX_REENVIOS_POR_HORA = 3

# Se reutiliza SOLICITUD_RECUPERACION: el flujo de recuperación ya registra este
# tipo cuando rota un token de activación para una cuenta PENDIENTE, y así ambos
# flujos que envían correo comparten la misma ventana de rate limiting por IP.
TIPO_SOLICITUD_RECUPERACION = 7

_MENSAJE_GENERICO = (
    "Si el correo corresponde a una cuenta pendiente de activación, "
    "recibirás un nuevo enlace en unos minutos."
)


class ReenviarTokenUseCase:
    """Orquesta el reenvío del correo de activación con un token nuevo."""

    def __init__(
        self,
        cuentas_repo: CuentaRepository,
        usuarios_repo: UsuarioRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            cuentas_repo: Repositorio de dominio del agregado Cuenta.
            usuarios_repo: Repositorio de dominio del agregado Usuario (busca por correo).
            eventos_repo: Repositorio de dominio de eventos (rate limiting y auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.cuentas_repo = cuentas_repo
        self.usuarios_repo = usuarios_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, dto: ReenviarTokenDTO, ip: str) -> str:
        """Genera un nuevo token de activación y lo envía por correo.

        Si el correo no existe o la cuenta no está PENDIENTE no se envía nada,
        pero la respuesta es idéntica al caso exitoso para no permitir
        enumeración de usuarios registrados.

        Args:
            dto: Correo electrónico del usuario que solicita el reenvío.
            ip: IP del cliente, usada para el rate limiting por hora.

        Returns:
            Mensaje genérico que no revela si el correo está registrado.

        Raises:
            BusinessRuleError: Si se supera el límite de reenvíos por hora desde
                la misma IP. HTTP 422.
        """
        ahora = datetime.now(timezone.utc)
        hace_una_hora = ahora - timedelta(hours=1)
        solicitudes = self.eventos_repo.contar_solicitudes_recuperacion_por_ip(ip, hace_una_hora)
        if solicitudes >= MAX_REENVIOS_POR_HORA:
            primera_solicitud = (
                self.eventos_repo.obtener_primera_solicitud_recuperacion_por_ip(
                    ip,
                    hace_una_hora,
                )
            )
            proxima_vez = (primera_solicitud or ahora) + timedelta(hours=1)
            raise BusinessRuleError(
                code="LIMITE_SOLICITUDES_EXCEDIDO",
                message=(
                    f"Límite de solicitudes excedido para su conexión. Por seguridad, solo se "
                    f"permiten {MAX_REENVIOS_POR_HORA} envíos de correo por hora. "
                    f"Podrá intentarlo de nuevo a las {proxima_vez.strftime('%H:%M:%S')}."
                ),
            )

        correo = str(dto.correo_electronico)
        usuario = self.usuarios_repo.obtener_por_correo(Email(correo))
        if usuario is None:
            return _MENSAJE_GENERICO

        cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)
        if cuenta is None or not cuenta.esta_pendiente():
            return _MENSAJE_GENERICO

        token = secrets.token_urlsafe(32)
        try:
            cuenta.asignar_token_activacion(calcular_hash_token(token), ahora)
            self.cuentas_repo.guardar(cuenta)
            self.eventos_repo.registrar(
                tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={"ip": ip, "motivo": "reenvio_token_activacion"},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        send_email(
            to=correo,
            subject="Nuevo token de activación - SGPMP",
            html_body=activation_email(usuario.nombre, token),
        )
        return _MENSAJE_GENERICO
