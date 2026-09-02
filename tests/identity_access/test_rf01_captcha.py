"""Pruebas unitarias del CAPTCHA de registro RF-01."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from src.identity_access.application.use_cases.registro.crear_usuario_use_case import (
    CrearUsuarioUseCase,
)
from src.identity_access.infrastructure.adapters import google_recaptcha_adapter as modulo
from src.identity_access.infrastructure.adapters.google_recaptcha_adapter import (
    GoogleRecaptchaAdapter,
)
from src.shared.errors import ServiceUnavailableError, ValidationError


class CaptchaStub:
    def __init__(self, valido: bool) -> None:
        self.valido = valido
        self.llamadas = []

    def verificar(self, token: str, ip: str | None = None) -> bool:
        self.llamadas.append((token, ip))
        return self.valido


class DbSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_caso_de_uso_rechaza_captcha_antes_de_persistir() -> None:
    captcha = CaptchaStub(False)
    db = DbSpy()
    use_case = CrearUsuarioUseCase(
        usuarios_repo=object(),
        cuentas_repo=object(),
        eventos_repo=object(),
        correo_activacion_port=object(),
        captcha_verifier=captcha,
        db=db,
    )

    with pytest.raises(ValidationError) as error:
        use_case.execute(
            SimpleNamespace(captcha_token="captcha-rechazado"),
            "203.0.113.10",
            "pytest",
        )

    assert error.value.code == "CAPTCHA_INVALIDO"
    assert error.value.status_code == 400
    assert error.value.field == "captcha_token"
    assert captcha.llamadas == [("captcha-rechazado", "203.0.113.10")]
    assert db.commits == 0
    assert db.rollbacks == 0


def test_adaptador_envia_secreto_token_e_ip_sin_exponerlos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamada = {}

    def post(url, *, data, timeout):
        llamada.update(url=url, data=data, timeout=timeout)
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"success": True, "hostname": "frontend.example.com"},
        )

    monkeypatch.setattr(modulo.httpx, "post", post)

    assert GoogleRecaptchaAdapter(secret_key="secreto-backend").verificar(
        "token-frontend",
        "203.0.113.10",
    )
    assert llamada == {
        "url": modulo.RECAPTCHA_VERIFY_URL,
        "data": {
            "secret": "secreto-backend",
            "response": "token-frontend",
            "remoteip": "203.0.113.10",
        },
        "timeout": modulo.RECAPTCHA_TIMEOUT_SECONDS,
    }


@pytest.mark.parametrize(
    "errores",
    [
        ["invalid-input-response"],
        ["timeout-or-duplicate"],
        ["missing-input-response"],
    ],
)
def test_adaptador_retorna_falso_para_token_rechazado(
    monkeypatch: pytest.MonkeyPatch,
    errores: list[str],
) -> None:
    monkeypatch.setattr(
        modulo.httpx,
        "post",
        lambda url, **_kwargs: httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"success": False, "error-codes": errores},
        ),
    )

    assert not GoogleRecaptchaAdapter(secret_key="secreto").verificar("token")


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"success": False, "error-codes": ["invalid-input-secret"]},
        {"respuesta": "sin-veredicto"},
    ],
)
def test_adaptador_falla_cerrado_ante_configuracion_o_respuesta_invalida(
    monkeypatch: pytest.MonkeyPatch,
    cuerpo: dict,
) -> None:
    monkeypatch.setattr(
        modulo.httpx,
        "post",
        lambda url, **_kwargs: httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json=cuerpo,
        ),
    )

    with pytest.raises(ServiceUnavailableError) as error:
        GoogleRecaptchaAdapter(secret_key="secreto").verificar("token")

    assert error.value.code == "CAPTCHA_SERVICIO_NO_DISPONIBLE"
    assert error.value.status_code == 503


def test_adaptador_falla_cerrado_si_no_hay_clave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RECAPTCHA_SECRET_KEY", raising=False)

    with pytest.raises(ServiceUnavailableError) as error:
        GoogleRecaptchaAdapter().verificar("token")

    assert error.value.code == "CAPTCHA_SERVICIO_NO_DISPONIBLE"


def test_adaptador_traduce_fallo_de_red(monkeypatch: pytest.MonkeyPatch) -> None:
    def post(_url, **_kwargs):
        raise httpx.ConnectError(
            "Google no disponible",
            request=httpx.Request("POST", modulo.RECAPTCHA_VERIFY_URL),
        )

    monkeypatch.setattr(modulo.httpx, "post", post)

    with pytest.raises(ServiceUnavailableError) as error:
        GoogleRecaptchaAdapter(secret_key="secreto").verificar("token")

    assert error.value.code == "CAPTCHA_SERVICIO_NO_DISPONIBLE"
    assert isinstance(error.value.original_error, httpx.ConnectError)
