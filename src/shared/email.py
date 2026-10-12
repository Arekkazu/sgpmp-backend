"""Utilidad de envío de correos electrónicos vía SMTP.

Configura la conexión SMTP con las variables de entorno ``SMTP_HOST``,
``SMTP_PORT``, ``SMTP_USER`` y ``SMTP_PASSWORD``. Implementa reintentos
automáticos con pausa entre intentos para absorber fallos transitorios
del servidor de correo.
"""
import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from src.shared.errors import ServiceUnavailableError

load_dotenv()

logger = logging.getLogger(__name__)

_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER")
_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

_MAX_RETRIES = 3
#: Intentos para correos que llevan un token (RF-01 activación, RF-08
#: recuperación): el RF-01 exige reintentar hasta 3 veces. Las notificaciones
#: de RF-14 usan 1 (ver ``NotificacionService``).
INTENTOS_CORREO_CON_TOKEN = _MAX_RETRIES
_RETRY_DELAY = 5
# QA M01 2.2: smtplib.SMTP() sin timeout bloquea indefinidamente si el host
# no responde (no hay limite de socket por defecto). Acotado bien por debajo
# de los 15s que el frontend espera antes de abortar la request.
_SMTP_TIMEOUT = 8


def send_email(to: str, subject: str, html_body: str, intentos: int = _MAX_RETRIES) -> None:
    """Envía un correo HTML al destinatario indicado.

    Intenta el envío hasta ``intentos`` veces con una pausa de
    ``_RETRY_DELAY`` segundos entre intentos. Si todos los intentos fallan,
    lanza ``ServiceUnavailableError``.

    Args:
        to: Dirección de correo del destinatario.
        subject: Asunto del mensaje.
        html_body: Cuerpo del mensaje en formato HTML.
        intentos: Intentos SMTP antes de rendirse. Por defecto
            ``INTENTOS_CORREO_CON_TOKEN`` (RF-01: hasta 3). Las notificaciones
            de RF-14 pasan ``1``: el RF prohíbe reintentarlas para no
            duplicar el correo.

    Raises:
        ServiceUnavailableError: Si el servidor SMTP no responde después de
            agotar todos los reintentos. Código ``EMAIL_NO_DISPONIBLE``, HTTP 503.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    last_error: Exception | None = None

    for attempt in range(1, intentos + 1):
        try:
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=_SMTP_TIMEOUT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(_SMTP_USER, _SMTP_PASSWORD)
                server.sendmail(_SMTP_USER, to, msg.as_string())
            return
        except Exception as e:
            last_error = e
            logger.warning("Intento %d/%d fallido al enviar correo a %s: %r", attempt, intentos, to, e)
            if attempt < intentos:
                time.sleep(_RETRY_DELAY)

    raise ServiceUnavailableError(
        code="EMAIL_NO_DISPONIBLE",
        message="El servicio de notificaciones no está disponible. Tu token se enviará automáticamente en los próximos 10 minutos.",
        original_error=last_error,
    )
