"""RF-01 vs RF-14: cuántas veces se intenta un correo.

RF-01 pide reintentar el token de activación hasta 3 veces; RF-14 prohíbe
reintentar las notificaciones "para evitar duplicidad". ``send_email`` mantiene
3 por defecto y ``NotificacionService`` pasa ``intentos=1``.
"""
import pytest

from src.shared import email as email_module
from src.shared.errors import ServiceUnavailableError


class _SmtpQueFalla:
    llamadas = 0

    def __init__(self, *args, **kwargs) -> None:
        type(self).llamadas += 1
        raise OSError("SMTP caído")


@pytest.fixture
def smtp_caido(monkeypatch):
    _SmtpQueFalla.llamadas = 0
    monkeypatch.setattr(email_module.smtplib, "SMTP", _SmtpQueFalla)
    monkeypatch.setattr(email_module.time, "sleep", lambda _s: None)
    return _SmtpQueFalla


def test_por_defecto_reintenta_3_veces_rf01(smtp_caido) -> None:
    with pytest.raises(ServiceUnavailableError):
        email_module.send_email(to="a@b.co", subject="s", html_body="<p>x</p>")

    assert smtp_caido.llamadas == 3


def test_con_un_intento_no_reintenta_rf14(smtp_caido) -> None:
    with pytest.raises(ServiceUnavailableError):
        email_module.send_email(to="a@b.co", subject="s", html_body="<p>x</p>", intentos=1)

    assert smtp_caido.llamadas == 1
