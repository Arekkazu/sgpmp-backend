import logging
import os

logger = logging.getLogger(__name__)

_app = None


def _get_app():
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
    """Envía una notificación push via Firebase. Retorna True si tuvo éxito."""
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
