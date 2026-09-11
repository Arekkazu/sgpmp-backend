"""Integración RF-01: CAPTCHA obligatorio y validado antes del registro."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from src.identity_access.infrastructure.routers.usuarios_routers import (
    get_captcha_verifier,
)
from src.shared.errors import ServiceUnavailableError

pytestmark = pytest.mark.integration


class CaptchaStub:
    def __init__(self, valido: bool) -> None:
        self.valido = valido
        self.llamadas = []

    def verificar(self, token: str, ip: str | None = None) -> bool:
        self.llamadas.append((token, ip))
        return self.valido


class CaptchaNoDisponibleStub:
    def verificar(self, _token: str, _ip: str | None = None) -> bool:
        raise ServiceUnavailableError(
            code="CAPTCHA_SERVICIO_NO_DISPONIBLE",
            message=(
                "El servicio de validación de seguridad no está disponible "
                "temporalmente. Intente nuevamente más tarde."
            ),
        )


def _registro(correo: str, captcha_token: str = "captcha-prueba") -> dict:
    return {
        "correo_electronico": correo,
        "telefono": "3001234567",
        "tipo_identificacion": "CC",
        "numero_identificacion": str(uuid.uuid4().int % 10**15).zfill(15),
        "nombre": "Captcha",
        "apellidos": "Integración",
        "fecha_nacimiento": "1990-01-01",
        "genero": "M",
        "contrasena": "Segura1!",
        "confirmar_contrasena": "Segura1!",
        "direccion": "Dirección de prueba",
        "captcha_token": captcha_token,
    }


def _cantidad_usuarios(db_session, correo: str) -> int:
    return db_session.execute(
        text(
            "SELECT count(*) FROM modulo1.usuarios "
            "WHERE correo_electronico=:correo"
        ),
        {"correo": correo},
    ).scalar_one()


def test_captcha_es_campo_obligatorio(client) -> None:
    datos = _registro(f"captcha-ausente-{uuid.uuid4().hex}@example.com")
    datos.pop("captcha_token")

    respuesta = client.post("/usuarios/", json=datos)

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "VAL_ENTRADA"
    assert any(
        campo["field"] == "captcha_token"
        for campo in respuesta.json()["fields"]
    )


def test_captcha_rechazado_responde_400_y_no_persiste(
    client,
    integration_app,
    db_session,
) -> None:
    captcha = CaptchaStub(False)
    integration_app.dependency_overrides[get_captcha_verifier] = lambda: captcha
    correo = f"captcha-invalido-{uuid.uuid4().hex}@example.com"

    respuesta = client.post(
        "/usuarios/",
        json=_registro(correo, "token-rechazado"),
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error_code"] == "CAPTCHA_INVALIDO"
    assert respuesta.json()["message"] == (
        "Validación de seguridad fallida. Por favor, confirme que no es un "
        "robot e intente enviar el formulario nuevamente."
    )
    assert respuesta.json()["fields"] == [
        {"field": "captcha_token", "message": respuesta.json()["message"]}
    ]
    assert captcha.llamadas == [("token-rechazado", "sgpmp-integration-tests")]
    assert _cantidad_usuarios(db_session, correo) == 0


def test_captcha_valido_permite_registro(
    client,
    integration_app,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.shared import notificacion_service

    monkeypatch.setattr(notificacion_service, "send_email", lambda **_datos: None)
    captcha = CaptchaStub(True)
    integration_app.dependency_overrides[get_captcha_verifier] = lambda: captcha
    correo = f"captcha-valido-{uuid.uuid4().hex}@example.com"

    respuesta = client.post(
        "/usuarios/",
        json=_registro(correo, "token-valido"),
    )

    assert respuesta.status_code == 201, respuesta.text
    assert captcha.llamadas == [("token-valido", "sgpmp-integration-tests")]
    assert _cantidad_usuarios(db_session, correo) == 1


def test_captcha_no_disponible_responde_503_y_no_persiste(
    client,
    integration_app,
    db_session,
) -> None:
    integration_app.dependency_overrides[get_captcha_verifier] = (
        lambda: CaptchaNoDisponibleStub()
    )
    correo = f"captcha-503-{uuid.uuid4().hex}@example.com"

    respuesta = client.post("/usuarios/", json=_registro(correo))

    assert respuesta.status_code == 503
    assert respuesta.json()["error_code"] == "CAPTCHA_SERVICIO_NO_DISPONIBLE"
    assert _cantidad_usuarios(db_session, correo) == 0
