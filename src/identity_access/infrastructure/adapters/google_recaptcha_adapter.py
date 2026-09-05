"""Adaptador de Google reCAPTCHA v2 para el registro de usuarios RF-01."""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

from src.identity_access.domain.repositories.captcha_verifier_port import (
    CaptchaVerifierPort,
)
from src.shared.errors import ServiceUnavailableError

load_dotenv()

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
RECAPTCHA_TIMEOUT_SECONDS = 5.0
MENSAJE_CAPTCHA_NO_DISPONIBLE = (
    "El servicio de validación de seguridad no está disponible temporalmente. "
    "Intente nuevamente más tarde."
)

_ERRORES_CONFIGURACION = {
    "missing-input-secret",
    "invalid-input-secret",
    "bad-request",
}


class GoogleRecaptchaAdapter(CaptchaVerifierPort):
    """Verifica en Google el token de un desafío reCAPTCHA v2.

    La clave secreta nunca se recibe desde el cliente ni se registra en logs.
    Un fallo de configuración, red o formato de respuesta no se confunde con
    un desafío rechazado: se informa como indisponibilidad y el registro no
    continúa.
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        verify_url: str = RECAPTCHA_VERIFY_URL,
        timeout_seconds: float = RECAPTCHA_TIMEOUT_SECONDS,
    ) -> None:
        self._secret_key = (
            secret_key if secret_key is not None else os.getenv("RECAPTCHA_SECRET_KEY")
        )
        self._verify_url = verify_url
        self._timeout_seconds = timeout_seconds

    def verificar(self, token: str, ip: Optional[str] = None) -> bool:
        """Envía el token a ``siteverify`` y retorna su veredicto."""
        if not self._secret_key:
            raise ServiceUnavailableError(
                code="CAPTCHA_SERVICIO_NO_DISPONIBLE",
                message=MENSAJE_CAPTCHA_NO_DISPONIBLE,
            )

        datos = {
            "secret": self._secret_key,
            "response": token,
        }
        if ip and ip != "unknown":
            datos["remoteip"] = ip

        try:
            respuesta = httpx.post(
                self._verify_url,
                data=datos,
                timeout=self._timeout_seconds,
            )
            respuesta.raise_for_status()
            cuerpo = respuesta.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceUnavailableError(
                code="CAPTCHA_SERVICIO_NO_DISPONIBLE",
                message=MENSAJE_CAPTCHA_NO_DISPONIBLE,
                original_error=exc,
            ) from exc

        return self._interpretar_respuesta(cuerpo)

    @staticmethod
    def _interpretar_respuesta(cuerpo: Any) -> bool:
        if not isinstance(cuerpo, dict) or not isinstance(cuerpo.get("success"), bool):
            error = ValueError("Respuesta inválida del servicio reCAPTCHA")
            raise ServiceUnavailableError(
                code="CAPTCHA_SERVICIO_NO_DISPONIBLE",
                message=MENSAJE_CAPTCHA_NO_DISPONIBLE,
                original_error=error,
            ) from error

        errores = cuerpo.get("error-codes", [])
        if isinstance(errores, str):
            errores = [errores]
        if not isinstance(errores, list):
            errores = []

        if _ERRORES_CONFIGURACION.intersection(str(error) for error in errores):
            error = RuntimeError("Configuración inválida del servicio reCAPTCHA")
            raise ServiceUnavailableError(
                code="CAPTCHA_SERVICIO_NO_DISPONIBLE",
                message=MENSAJE_CAPTCHA_NO_DISPONIBLE,
                original_error=error,
            ) from error

        return cuerpo["success"]
