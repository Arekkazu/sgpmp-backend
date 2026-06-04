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
_RETRY_DELAY = 5


def send_email(to: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(_SMTP_USER, _SMTP_PASSWORD)
                server.sendmail(_SMTP_USER, to, msg.as_string())
            return
        except Exception as e:
            last_error = e
            logger.warning("Intento %d/%d fallido al enviar correo a %s: %r", attempt, _MAX_RETRIES, to, e)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)

    raise ServiceUnavailableError(
        code="EMAIL_NO_DISPONIBLE",
        message="El servicio de notificaciones no está disponible. Tu token se enviará automáticamente en los próximos 10 minutos.",
        original_error=last_error,
    )
