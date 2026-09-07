"""Caso de uso: solicitud de recuperación de contraseña.

Aplica rate limiting por IP (máx 3 por hora), genera un token de recuperación
y programa el correo correspondiente en segundo plano. Retorna siempre un
mensaje genérico para evitar enumeración de usuarios registrados, tanto en
contenido como en tiempo de respuesta (el envío SMTP nunca bloquea el request).
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.repositories.correo_recuperacion_port import (
    CorreoRecuperacionPort,
)
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.intento_anonimo_repository import IntentoAnonimoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.shared.errors import TooManyRequestsError

MAX_SOLICITUDES_POR_HORA = 3
TIPO_SOLICITUD_RECUPERACION = 7
TIPO_INTENTO_SOLICITUD_RECUPERACION = "SOLICITUD_RECUPERACION"

_MENSAJE_GENERICO = "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña en unos minutos."


class SolicitarRecuperacionUseCase:
    """Orquesta el inicio del flujo de recuperación de contraseña."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        eventos_repo: EventoRepository,
        intentos_anonimos_repo: IntentoAnonimoRepository,
        db: Session,
        correo_recuperacion_port: CorreoRecuperacionPort,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta (token de recuperación).
            eventos_repo: Repositorio de dominio de eventos (auditoría de solicitudes de usuarios reales).
            intentos_anonimos_repo: Repositorio de intentos por IP para el rate
                limit, independiente de si el correo corresponde a un usuario real.
            db: Sesión SQLAlchemy activa del request.
            correo_recuperacion_port: Puerto que agenda los correos después
                de confirmar el token y el evento, sin bloquear la respuesta.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.eventos_repo = eventos_repo
        self.intentos_anonimos_repo = intentos_anonimos_repo
        self.db = db
        self.correo_recuperacion_port = correo_recuperacion_port

    def execute(self, dto: SolicitarRecuperacionDTO, ip: str) -> str:
        """Inicia el proceso de recuperación de contraseña para el correo indicado.

        Si la cuenta está en estado PENDIENTE, redirige al flujo de activación
        en lugar del de recuperación. Si el correo no existe o la cuenta está
        eliminada, retorna el mensaje genérico sin revelar información — ni en
        el contenido de la respuesta ni en su tiempo, ya que el correo se
        programa en segundo plano y nunca bloquea este request.

        Args:
            dto: Correo electrónico del usuario que solicita la recuperación.
            ip: IP del cliente, usada para el rate limiting por hora.

        Returns:
            Mensaje genérico que no revela si el correo está registrado.

        Raises:
            TooManyRequestsError: Si se supera el límite de 3 solicitudes por
                hora desde la misma IP. HTTP 429.
        """
        # 1. Rate limit por IP: máx 3 solicitudes por hora.
        # Se cuenta TODO intento (exista o no el correo) en una tabla propia sin
        # actor identificado: modulo1.eventos no sirve porque id_usuario es
        # NOT NULL con FK a usuarios, y contar solo cuando el correo existe es
        # justamente el bug INC-M01-09-043 (el límite nunca se aplicaba a
        # correos inexistentes, porque ese caso retornaba antes de registrar
        # ningún evento).
        ahora = datetime.now(timezone.utc)
        hace_una_hora = ahora - timedelta(hours=1)
        try:
            self.intentos_anonimos_repo.registrar(TIPO_INTENTO_SOLICITUD_RECUPERACION, ip)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        solicitudes = self.intentos_anonimos_repo.contar_por_ip(
            TIPO_INTENTO_SOLICITUD_RECUPERACION, ip, hace_una_hora
        )
        if solicitudes > MAX_SOLICITUDES_POR_HORA:
            # La ventana libera cupo cuando la solicitud MÁS ANTIGUA de las que
            # cuentan actualmente cumple una hora — no "ahora + 1h" (eso da
            # siempre la hora actual, ver INC-M01-20-112) ni "hace_una_hora + 1h"
            # (eso da siempre "ahora", el mismo bug con otro nombre).
            mas_antigua = self.intentos_anonimos_repo.obtener_fecha_mas_antigua_por_ip(
                TIPO_INTENTO_SOLICITUD_RECUPERACION, ip, hace_una_hora
            )
            proxima_vez = (mas_antigua or ahora) + timedelta(hours=1)
            raise TooManyRequestsError(
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

        # 3. Cuenta en PENDIENTE: rotar y programar un token de activación.
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
            self.correo_recuperacion_port.programar_activacion(
                correo=correo,
                nombre=usuario.nombre,
                token=token_activacion,
                id_usuario=usuario.id_usuario,
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

        # 5. Programar el correo después del commit, sin bloquear el request.
        self.correo_recuperacion_port.programar_recuperacion(
            correo=correo,
            nombre=usuario.nombre,
            token=token,
            id_usuario=usuario.id_usuario,
        )

        return _MENSAJE_GENERICO
