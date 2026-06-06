import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.identity_access.infrastructure.email_templates import activation_email, recovery_email
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.email import send_email
from src.shared.errors import BusinessRuleError

ESTADO_ELIMINADO = 5
ESTADO_PENDIENTE = 1
MAX_SOLICITUDES_POR_HORA = 3
TIPO_SOLICITUD_RECUPERACION = 7

_MENSAJE_GENERICO = "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña en unos minutos."


class SolicitarRecuperacionUseCase:

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        cuentas_port: CuentasPort,
        sesiones_port: SesionesPort,
        db: Session,
        notificacion_service=None,
    ):
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.sesiones_port = sesiones_port
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, dto: SolicitarRecuperacionDTO, ip: str) -> str:
        # 1. Rate limit por IP: máx 3 solicitudes por hora
        hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
        solicitudes = self.sesiones_port.contar_solicitudes_recuperacion_por_ip(ip, hace_una_hora)
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
        usuario = self.usuarios_port.buscar_por_correo(correo)

        if usuario is None or (
            self.cuentas_port.buscar_cuenta_por_usuario(usuario.id_usuario) is not None
            and self.cuentas_port.buscar_cuenta_por_usuario(usuario.id_usuario).id_estado_cuenta == ESTADO_ELIMINADO
        ):
            return _MENSAJE_GENERICO

        cuenta = self.cuentas_port.buscar_cuenta_por_usuario(usuario.id_usuario)
        if cuenta is None:
            return _MENSAJE_GENERICO

        # 3. Cuenta en PENDIENTE: enviar email de activación en su lugar
        if cuenta.id_estado_cuenta == ESTADO_PENDIENTE:
            token_activacion = cuenta.token_activacion_actual
            if token_activacion:
                try:
                    self.sesiones_port.registrar_evento(
                        tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                        resultado=EnumEventoResultado.EXITOSO,
                        id_usuario=usuario.id_usuario,
                        detalle={"ip": ip, "motivo": "cuenta_pendiente_redirigido_a_activacion"},
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
            self.cuentas_port.guardar_token_recuperacion(cuenta, token)
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_SOLICITUD_RECUPERACION,
                resultado=EnumEventoResultado.EXITOSO,
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
