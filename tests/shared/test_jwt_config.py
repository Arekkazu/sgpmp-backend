"""Pruebas de configuración de vigencia JWT para RF-02."""
from datetime import timedelta
from pathlib import Path

import pytest
from jose import jwt as jose_jwt

from src.shared import jwt as jwt_module
from src.shared.errors import AuthenticationError


def test_vigencia_jwt_por_defecto_es_ocho_horas(monkeypatch) -> None:
    monkeypatch.delenv("JWT_EXPIRE_HOURS", raising=False)

    assert jwt_module._leer_horas_expiracion() == 8


def test_vigencia_jwt_admite_configuracion_explicita(monkeypatch) -> None:
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "6")

    assert jwt_module._leer_horas_expiracion() == 6


def test_token_expiration_usa_ocho_horas(monkeypatch) -> None:
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    antes = jwt_module.datetime.now(jwt_module.timezone.utc)

    expiracion = jwt_module.token_expiration()

    despues = jwt_module.datetime.now(jwt_module.timezone.utc)
    assert antes + timedelta(hours=8) <= expiracion <= despues + timedelta(hours=8)


def test_env_example_declara_vigencia_jwt() -> None:
    raiz_proyecto = Path(__file__).resolve().parents[2]
    contenido = (raiz_proyecto / ".env.example").read_text(encoding="utf-8")

    assert "JWT_EXPIRE_HOURS=8" in contenido.splitlines()


def test_env_example_declara_vigencia_refresh_token() -> None:
    raiz_proyecto = Path(__file__).resolve().parents[2]
    contenido = (raiz_proyecto / ".env.example").read_text(encoding="utf-8")

    assert "REFRESH_TOKEN_EXPIRE_DAYS=7" in contenido.splitlines()


def test_refresh_token_expiration_usa_siete_dias(monkeypatch) -> None:
    monkeypatch.setattr(jwt_module, "_REFRESH_EXPIRE_DAYS", 7)
    antes = jwt_module.datetime.now(jwt_module.timezone.utc)

    expiracion = jwt_module.refresh_token_expiration()

    despues = jwt_module.datetime.now(jwt_module.timezone.utc)
    assert antes + timedelta(days=7) <= expiracion <= despues + timedelta(days=7)


def test_verify_token_distingue_expirado_de_invalido(monkeypatch) -> None:
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "clave-de-prueba")

    payload_expirado = {
        "sub": "1",
        "jti": "1",
        "rol": 2,
        "iat": jwt_module.datetime(2020, 1, 1, tzinfo=jwt_module.timezone.utc),
        "exp": jwt_module.datetime(2020, 1, 1, tzinfo=jwt_module.timezone.utc),
    }
    token_expirado = jose_jwt.encode(payload_expirado, "clave-de-prueba", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc_info:
        jwt_module.verify_token(token_expirado)
    assert exc_info.value.code == "TOKEN_EXPIRADO"

    with pytest.raises(AuthenticationError) as exc_info:
        jwt_module.verify_token("esto-no-es-un-jwt-valido")
    assert exc_info.value.code == "TOKEN_INVALIDO"
