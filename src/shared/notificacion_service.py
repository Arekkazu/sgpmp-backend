"""Servicio transversal de notificaciones para todos los módulos del sistema.

Orquesta el envío de notificaciones por dos canales: EMAIL (id=1) e INTERNO
(push Firebase, id=2). Se invoca desde los use cases después del commit
principal. Nunca propaga excepciones — las notificaciones son best-effort.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.notificacion_repository import NotificacionRepository
from src.shared.email import send_email
from src.shared.firebase import send_push

logger = logging.getLogger(__name__)

ID_CANAL_EMAIL = 1
ID_CANAL_INTERNO = 2

ESTADO_INACTIVO = 3
ESTADO_BLOQUEADO = 4

VENTANA_ANTI_SPAM_MINUTOS = 5

# Estados de envío como texto (coinciden con los valores de enum_estado_envio en DB)
ESTADO_ENVIO_EN_COLA = "en_cola"
ESTADO_ENVIO_ENVIADO = "enviado"
ESTADO_ENVIO_FALLIDO = "fallido"

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
    """Servicio de notificaciones multi-canal.

    Gestiona el ciclo completo de una notificación: verificación del estado
    del usuario, control anti-spam, persistencia en DB y despacho por canal.
    Debe instanciarse por request, no como singleton, ya que recibe una
    sesión de base de datos activa.
    """

    def __init__(self, port: NotificacionRepository, db: Session):
        """Inicializa el servicio con sus dependencias.

        Args:
            port: Repositorio de notificaciones (puerto de dominio) para acceso a DB.
            db: Sesión SQLAlchemy activa del request actual.
        """
        self.port = port
        self.db = db

    def notificar(
        self,
        tipo_evento: int,
        id_usuario: int,
        correo_destino: Optional[str] = None,
        asunto_email: Optional[str] = None,
        contenido_html_email: Optional[str] = None,
        resolver_correo_destino: bool = False,
    ) -> None:
        """Punto de entrada único para enviar notificaciones.

        Debe llamarse después del commit del use case principal. Captura
        cualquier excepción interna y la registra en el log sin propagarla,
        garantizando que un fallo de notificación nunca interrumpa el flujo
        principal de negocio.

        Args:
            tipo_evento: ID del tipo de evento que originó la notificación.
                Debe existir en la tabla ``tipo_eventos``.
            id_usuario: ID del usuario destinatario.
            correo_destino: Dirección de correo para el canal EMAIL. Si es
                ``None``, el canal EMAIL se omite.
            asunto_email: Asunto específico para EMAIL. Si se omite se usa el
                título general del tipo de evento.
            contenido_html_email: HTML específico para EMAIL. No se persiste
                en la notificación interna, evitando almacenar tokens o links
                sensibles en la bandeja.
            resolver_correo_destino: Si es ``True`` y no se recibió correo,
                el servicio lo consulta mediante su puerto.
        """
        try:
            self._procesar(
                tipo_evento,
                id_usuario,
                correo_destino,
                asunto_email,
                contenido_html_email,
                resolver_correo_destino,
            )
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
        asunto_email: Optional[str],
        contenido_html_email: Optional[str],
        resolver_correo_destino: bool,
    ) -> None:
        """Ejecuta la lógica de filtrado y despacho por canal.

        Aplica las siguientes reglas antes de enviar:
        - Cuentas INACTIVAS (id=3) no reciben ninguna notificación.
        - Cuentas BLOQUEADAS (id=4) solo reciben eventos de seguridad
          (tipos definidos en ``TIPOS_EVENTO_SEGURIDAD``).
        - Si no existe un evento registrado para el usuario y tipo, se omite.

        Args:
            tipo_evento: ID del tipo de evento.
            id_usuario: ID del usuario destinatario.
            correo_destino: Dirección de correo o ``None``.
        """
        titulo, cuerpo = _MENSAJES.get(tipo_evento, ("Notificación", "Se ha registrado una actividad en tu cuenta."))

        id_estado = self.port.buscar_estado_cuenta(id_usuario)

        if id_estado == ESTADO_INACTIVO:
            return

        if id_estado == ESTADO_BLOQUEADO and tipo_evento not in TIPOS_EVENTO_SEGURIDAD:
            return

        id_evento = self.port.buscar_ultimo_evento_id(id_usuario, tipo_evento)
        if id_evento is None:
            return

        if resolver_correo_destino and correo_destino is None:
            correo_destino = self.port.buscar_correo_usuario(id_usuario)

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
            asunto_email=asunto_email,
            contenido_html_email=contenido_html_email,
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
            asunto_email=None,
            contenido_html_email=None,
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
        asunto_email: Optional[str],
        contenido_html_email: Optional[str],
    ) -> None:
        """Persiste y despacha la notificación para un canal específico.

        Flujo interno:
        1. Verifica anti-spam; si hay una notificación reciente del mismo tipo
           y canal, retorna sin hacer nada.
        2. Registra la notificación en DB con estado ``en_cola`` y hace commit.
        3. Despacha por el canal correspondiente (EMAIL o INTERNO).
        4. Actualiza el estado a ``enviado`` o ``fallido`` según el resultado.

        Para el canal INTERNO, la persistencia constituye la entrega a la
        bandeja. El push de Firebase es complementario: se intenta para todos
        los dispositivos, pero su ausencia o fallo no invalida la entrega
        interna ya confirmada.

        Args:
            canal: ID del canal (1=EMAIL, 2=INTERNO).
            tipo_evento: ID del tipo de evento para el filtro anti-spam.
            id_evento: ID del evento de auditoría que origina la notificación.
            id_usuario: ID del usuario destinatario.
            titulo: Asunto del mensaje.
            cuerpo: Cuerpo del mensaje.
            correo: Dirección de correo para EMAIL, o ``None``.
            fcm_tokens: Lista de tokens FCM para INTERNO. Lista vacía omite el envío push.
            asunto_email: Asunto exclusivo del canal EMAIL, si aplica.
            contenido_html_email: HTML exclusivo del canal EMAIL, si aplica.
        """
        if self.port.verificar_anti_spam(id_usuario, tipo_evento, canal, VENTANA_ANTI_SPAM_MINUTOS):
            return

        try:
            id_notificacion = self.port.registrar(
                id_evento=id_evento,
                id_usuario=id_usuario,
                id_canal=canal,
                mensaje=cuerpo,
                estado=ESTADO_ENVIO_EN_COLA,
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error("Error guardando notificación (canal=%s): %s", canal, exc)
            return

        enviado = canal == ID_CANAL_INTERNO
        try:
            if canal == ID_CANAL_EMAIL and correo:
                send_email(
                    to=correo,
                    subject=asunto_email or titulo,
                    html_body=contenido_html_email or f"<p>{cuerpo}</p>",
                )
                enviado = True
            elif canal == ID_CANAL_INTERNO and fcm_tokens:
                for token in fcm_tokens:
                    send_push(token=token, titulo=titulo, cuerpo=cuerpo)
        except Exception as exc:
            logger.error("Error enviando por canal=%s: %s", canal, exc)

        try:
            estado_final = ESTADO_ENVIO_ENVIADO if enviado else ESTADO_ENVIO_FALLIDO
            self.port.actualizar_estado(id_notificacion, estado_final)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error("Error actualizando estado notificación: %s", exc)
