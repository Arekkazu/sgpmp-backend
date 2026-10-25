"""
TC-M01-012 - Reintento automatico de envio del correo de activacion
ante fallo del servicio SMTP, hasta 3 intentos.

RF relacionado: RF-01
Categoria: Manejo de errores (RESILIENCIA)

Este test mockea smtplib.SMTP para simular un servidor SMTP caido,
sin necesidad de tumbar ningun servidor real ni depender del entorno
desplegado. Tambien mockea time.sleep para que el test corra en
milisegundos en vez de tardar los 15 segundos reales de las pausas
entre reintentos (3 intentos x 5s de _RETRY_DELAY).

Como correrlo (desde la raiz del repo sgpmp-backend, con el venv activo):

    pytest tests/test_tc_m01_012_reintentos_smtp.py -v \
        --html=reporte-TC-M01-012.html --self-contained-html

Ajusta la ruta del import de "src.shared.email" si tu estructura de
carpetas difiere.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.shared.email import send_email, _MAX_RETRIES
from src.shared.errors import ServiceUnavailableError


class TestTCM01012ReintentosSMTP:
    """Suite de pruebas para el mecanismo de reintentos de envio de correo."""

    @patch("src.shared.email.time.sleep")
    @patch("src.shared.email.smtplib.SMTP")
    def test_falla_los_3_intentos_y_lanza_service_unavailable(
        self, mock_smtp_class, mock_sleep
    ):
        """
        Escenario principal de TC-M01-012: el servidor SMTP esta caido
        de forma persistente (los 3 intentos fallan).

        Se espera:
        - Se intenten exactamente 3 conexiones SMTP (ni mas, ni menos).
        - Se levante ServiceUnavailableError con code=EMAIL_NO_DISPONIBLE.
        - El mensaje de error sea el de "se enviara automaticamente en
          los proximos 10 minutos" (el mensaje que el usuario final
          veria reflejado indirectamente en el flujo de registro).
        - Haya una pausa (time.sleep) entre cada intento, pero no
          despues del ultimo (2 pausas para 3 intentos).
        """
        # El "with smtplib.SMTP(...)" siempre lanza excepcion al conectar.
        mock_smtp_class.side_effect = ConnectionRefusedError(
            "Servidor SMTP simulado caido"
        )

        with pytest.raises(ServiceUnavailableError) as exc_info:
            send_email(
                to="ana.martinez.qa1@sgpmp-test.com",
                subject="Activa tu cuenta en SGPMP",
                html_body="<p>contenido de prueba</p>",
            )

        error = exc_info.value
        assert error.code == "EMAIL_NO_DISPONIBLE"
        assert "10 minutos" in error.message

        # Se intento conectar exactamente 3 veces (_MAX_RETRIES).
        assert mock_smtp_class.call_count == _MAX_RETRIES == 3

        # Pausa entre intentos, pero no despues del ultimo fallo.
        assert mock_sleep.call_count == _MAX_RETRIES - 1 == 2

    @patch("src.shared.email.time.sleep")
    @patch("src.shared.email.smtplib.SMTP")
    def test_recupera_en_el_segundo_intento_sin_agotar_reintentos(
        self, mock_smtp_class, mock_sleep
    ):
        """
        Escenario de resiliencia parcial: el SMTP falla en el primer
        intento pero se recupera en el segundo. No debe intentar un
        tercer intento (no debe seguir reintentando si ya tuvo exito),
        y no debe lanzar ninguna excepcion.
        """
        servidor_ok = MagicMock()
        servidor_ok.__enter__.return_value = servidor_ok

        mock_smtp_class.side_effect = [
            ConnectionRefusedError("Primer intento falla"),
            servidor_ok,
        ]

        send_email(
            to="ana.martinez.qa1@sgpmp-test.com",
            subject="Activa tu cuenta en SGPMP",
            html_body="<p>contenido de prueba</p>",
        )

        assert mock_smtp_class.call_count == 2
        servidor_ok.sendmail.assert_called_once()
        # Solo hubo una pausa (entre el intento 1 fallido y el 2 exitoso).
        assert mock_sleep.call_count == 1

    @patch("src.shared.email.time.sleep")
    @patch("src.shared.email.smtplib.SMTP")
    def test_exito_en_el_primer_intento_no_reintenta_ni_hace_pausas(
        self, mock_smtp_class, mock_sleep
    ):
        """Caso feliz: SMTP funciona a la primera, cero reintentos."""
        servidor_ok = MagicMock()
        servidor_ok.__enter__.return_value = servidor_ok
        mock_smtp_class.return_value = servidor_ok

        send_email(
            to="ana.martinez.qa1@sgpmp-test.com",
            subject="Activa tu cuenta en SGPMP",
            html_body="<p>contenido de prueba</p>",
        )

        assert mock_smtp_class.call_count == 1
        mock_sleep.assert_not_called()