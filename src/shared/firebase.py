"""Adaptador para Firebase Cloud Messaging (FCM).

Inicializa el SDK de Firebase de forma lazy usando la variable de entorno
``FIREBASE_CREDENTIALS_PATH``. Si la variable no está configurada o las
credenciales son inválidas, las funciones degradan silenciosamente sin
lanzar excepciones, permitiendo que el sistema opere sin notificaciones push.
"""
import logging
import os

logger = logging.getLogger(__name__)

_app = None


def _get_app():
    """Retorna la instancia de Firebase Admin, inicializándola si es necesario.

    Implementa el patrón singleton lazy: inicializa el SDK solo en el primer
    llamado. Si ``FIREBASE_CREDENTIALS_PATH`` no está definida o las
    credenciales fallan, retorna ``None`` y registra una advertencia.

    Returns:
        La instancia de ``firebase_admin.App`` o ``None`` si Firebase no
        está configurado o no pudo inicializarse.
    """
    global _app
    if _app is not None:
        return _app

    credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not credentials_path:
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(credentials_path)
        _app = firebase_admin.initialize_app(cred)
    except Exception as exc:
        logger.warning("Firebase no pudo inicializarse: %s", exc)
        _app = None

    return _app


def send_push(token: str, titulo: str, cuerpo: str) -> bool:
    """Envía una notificación push a un dispositivo vía Firebase Cloud Messaging.

    Nunca lanza excepciones. Si Firebase no está configurado o el envío
    falla por cualquier razón, registra el error en el log y retorna ``False``.

    Args:
        token: FCM token del dispositivo destino. Debe ser no vacío.
        titulo: Título visible de la notificación push.
        cuerpo: Texto del cuerpo de la notificación push.

    Returns:
        ``True`` si el mensaje fue aceptado por FCM, ``False`` en cualquier
        otro caso (Firebase no configurado, token inválido, error de red, etc.).
    """
    if not token:
        return False

    app = _get_app()
    if app is None:
        logger.warning("Firebase no está configurado — notificación push omitida.")
        return False

    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=titulo, body=cuerpo),
            token=token,
        )
        messaging.send(message)
        return True
    except Exception as exc:
        logger.error("Error enviando push notification: %s", exc)
        return False
