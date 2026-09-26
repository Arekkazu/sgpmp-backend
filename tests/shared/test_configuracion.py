"""Validación de configuración al arranque (QA V2 M01)."""
from __future__ import annotations

import pytest

from src.shared import configuracion


def _limpia_entorno(monkeypatch, *variables: str) -> None:
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)


def test_sin_secret_key_no_arranca(monkeypatch) -> None:
    _limpia_entorno(monkeypatch, "SECRET_KEY", "COOKIE_SAMESITE", "COOKIE_SECURE")
    monkeypatch.setenv("ENV", "development")

    with pytest.raises(RuntimeError) as exc_info:
        configuracion.validar_configuracion()
    assert "SECRET_KEY" in str(exc_info.value)


def test_samesite_con_typo_no_arranca(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    monkeypatch.setenv("COOKIE_SAMESITE", "non")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ENV", "development")

    with pytest.raises(RuntimeError) as exc_info:
        configuracion.validar_configuracion()
    assert "COOKIE_SAMESITE" in str(exc_info.value)
    assert "non" in str(exc_info.value)


def test_secure_con_valor_invalido_no_arranca(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    monkeypatch.setenv("COOKIE_SECURE", "a-veces")
    monkeypatch.setenv("ENV", "development")

    with pytest.raises(RuntimeError) as exc_info:
        configuracion.validar_configuracion()
    assert "COOKIE_SECURE" in str(exc_info.value)


def test_leeway_no_numerico_no_arranca(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    monkeypatch.setenv("JWT_LEEWAY_SECONDS", "treinta")
    monkeypatch.setenv("ENV", "development")

    with pytest.raises(RuntimeError) as exc_info:
        configuracion.validar_configuracion()
    assert "JWT_LEEWAY_SECONDS" in str(exc_info.value)


def test_produccion_sin_flags_de_cookie_no_arranca(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    _limpia_entorno(monkeypatch, "COOKIE_SAMESITE", "COOKIE_SECURE")
    monkeypatch.setenv("ENV", "production")

    with pytest.raises(RuntimeError) as exc_info:
        configuracion.validar_configuracion()
    mensaje = str(exc_info.value)
    assert "COOKIE_SECURE" in mensaje
    assert "COOKIE_SAMESITE" in mensaje


def test_produccion_con_flags_validos_arranca(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("COOKIE_SAMESITE", "lax")

    configuracion.validar_configuracion()


def test_desarrollo_sin_flags_de_cookie_arranca(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    _limpia_entorno(monkeypatch, "COOKIE_SAMESITE", "COOKIE_SECURE", "ALLOWED_ORIGINS")
    monkeypatch.setenv("ENV", "development")

    configuracion.validar_configuracion()


def test_acumula_todos_los_problemas_en_un_solo_error(monkeypatch) -> None:
    _limpia_entorno(monkeypatch, "SECRET_KEY", "COOKIE_SAMESITE", "COOKIE_SECURE")
    monkeypatch.setenv("COOKIE_SAMESITE", "non")
    monkeypatch.setenv("ENV", "production")

    with pytest.raises(RuntimeError) as exc_info:
        configuracion.validar_configuracion()
    mensaje = str(exc_info.value)
    assert "SECRET_KEY" in mensaje
    assert "COOKIE_SAMESITE" in mensaje
    assert "COOKIE_SECURE" in mensaje


def test_avisa_sin_bloquear_con_origins_cross_site_en_no_produccion(monkeypatch, caplog) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    _limpia_entorno(monkeypatch, "COOKIE_SAMESITE", "COOKIE_SECURE")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://inmero.co")

    with caplog.at_level("WARNING"):
        configuracion.validar_configuracion()

    assert any("COOKIE_SECURE/COOKIE_SAMESITE" in r.message for r in caplog.records)


def test_no_avisa_con_origins_localhost(monkeypatch, caplog) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    _limpia_entorno(monkeypatch, "COOKIE_SAMESITE", "COOKIE_SECURE")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")

    with caplog.at_level("WARNING"):
        configuracion.validar_configuracion()

    assert not any("COOKIE_SECURE/COOKIE_SAMESITE" in r.message for r in caplog.records)
