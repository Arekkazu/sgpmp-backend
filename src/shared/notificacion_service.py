import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.notificaciones_ports import NotificacionesPort
from src.identity_access.infrastructure.models.enums_models import EnumEstadoEnvio
from src.shared.email import send_email
from src.shared.firebase import send_push

logger = logging.getLogger(__name__)

ID_CANAL_EMAIL = 1
ID_CANAL_INTERNO = 2

ESTADO_INACTIVO = 3
ESTADO_BLOQUEADO = 4

VENTANA_ANTI_SPAM_MINUTOS = 5

# Tipos de evento considerados de seguridad — se envían incluso si la cuenta está bloqueada
TIPOS_EVENTO_SEGURIDAD = {4, 10}

_MENSAJES: dict[int, tuple[str, str]] = {
    1:  ("Bienvenido a SGPMP", "Tu cuenta ha sido registrada exitosamente."),
    2:  ("Cuenta activada", "Tu cuenta ha sido activada. Ya puedes iniciar sesión."),
    3:  ("Inicio de sesión", "Hemos registrado un nuevo inicio de sesión en tu cuenta."),
    4:  ("Intento de acceso fallido", "Se registró un intento de inicio de sesión fallido en tu cuenta."),
    6:  ("Contraseña cambiada", "Tu contraseña ha sido actualizada exitosamente."),
    7:  ("Solicitud de recuperación", "Se ha iniciado el proceso de recuperación de contraseña."),
    8:  ("Contraseña restablecida", "Tu contraseña ha sido restablecida exitosamente."),
    9:  ("Perfil actualizado", "La información de tu perfil ha sido actualizada."),
    10: ("Cambio de estado en cuenta", "El estado de tu cuenta ha sido modificado por un administrador."),
}


class NotificacionService:

    def __init__(self, port: NotificacionesPort, db: Session):
        self.port = port
        self.db = db

    def notificar(
        self,
        tipo_evento: int,
        id_usuario: int,
        correo_destino: Optional[str] = None,
    ) -> None:
        """
        Punto de entrada único para enviar notificaciones.
        Se llama después del commit del use case principal.
        Nunca propaga excepciones — las notificaciones son best-effort.
        """
        try:
            self._procesar(tipo_evento, id_usuario, correo_destino)
        except Exception as exc:
            logger.error(
                "Error al procesar notificación tipo=%s usuario=%s: %s",
                tipo_evento, id_usuario, exc,
            )

    def _procesar(
        self,
        tipo_evento: int,
        id_usuario: int,
        correo_destino: Optional[str],
    ) -> None:
        titulo, cuerpo = _MENSAJES.get(tipo_evento, ("Notificación", "Se ha registrado una actividad en tu cuenta."))

        id_estado = self.port.buscar_estado_cuenta(id_usuario)

        # Cuenta inactiva → no recibe ninguna notificación
        if id_estado == ESTADO_INACTIVO:
            return

        # Cuenta bloqueada → solo eventos de seguridad
        if id_estado == ESTADO_BLOQUEADO and tipo_evento not in TIPOS_EVENTO_SEGURIDAD:
            return

        id_evento = self.port.buscar_ultimo_evento_id(id_usuario, tipo_evento)
        if id_evento is None:
            return

        fcm_tokens = self.port.buscar_fcm_tokens(id_usuario)

        self._enviar_canal(
            canal=ID_CANAL_EMAIL,
            tipo_evento=tipo_evento,
            id_evento=id_evento,
            id_usuario=id_usuario,
            titulo=titulo,
            cuerpo=cuerpo,
            correo=correo_destino,
            fcm_tokens=[],
        )

        self._enviar_canal(
            canal=ID_CANAL_INTERNO,
            tipo_evento=tipo_evento,
            id_evento=id_evento,
            id_usuario=id_usuario,
            titulo=titulo,
            cuerpo=cuerpo,
            correo=None,
            fcm_tokens=fcm_tokens,
        )

    def _enviar_canal(
        self,
        canal: int,
        tipo_evento: int,
        id_evento: int,
        id_usuario: int,
        titulo: str,
        cuerpo: str,
        correo: Optional[str],
        fcm_tokens: list[str],
    ) -> None:
        if self.port.verificar_anti_spam(id_usuario, tipo_evento, canal, VENTANA_ANTI_SPAM_MINUTOS):
            return

        try:
            notificacion = self.port.registrar(
                id_evento=id_evento,
                id_usuario=id_usuario,
                id_canal=canal,
                mensaje=cuerpo,
                estado_envio=EnumEstadoEnvio.EN_COLA,
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error("Error guardando notificación (canal=%s): %s", canal, exc)
            return

        enviado = False
        try:
            if canal == ID_CANAL_EMAIL and correo:
                send_email(to=correo, subject=titulo, html_body=f"<p>{cuerpo}</p>")
                enviado = True
            elif canal == ID_CANAL_INTERNO and fcm_tokens:
                resultados = [send_push(token=t, titulo=titulo, cuerpo=cuerpo) for t in fcm_tokens]
                enviado = any(resultados)
        except Exception as exc:
            logger.error("Error enviando por canal=%s: %s", canal, exc)

        try:
            estado_final = EnumEstadoEnvio.ENVIADO if enviado else EnumEstadoEnvio.FALLIDO
            self.port.actualizar_estado(notificacion, estado_final)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error("Error actualizando estado notificación: %s", exc)
