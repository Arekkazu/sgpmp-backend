"""Política de flags de la cookie refresh (COOKIE_SECURE / COOKIE_SAMESITE).

QA TC-DIS-22/24/27: la sesión moría al navegar porque los flags dependían de
que ``ENV`` valiera literalmente "production" — si no, la cookie salía
``SameSite=Strict`` sin ``Secure`` y el frontend (en otro sitio) nunca la
enviaba. Las variables explícitas corrigen el problema sin romper despliegues
existentes (sin variables se conserva el comportamiento previo).
"""
from __future__ import annotations

from pathlib import Path

from src.identity_access.infrastructure.routers.sesiones_routers import _leer_politica_cookie


def _sin_flags(monkeypatch) -> None:
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)


def test_variables_explicitas_mandan_sobre_env(monkeypatch) -> None:
    """COOKIE_SECURE=true fuerza la cookie cross-site aunque ENV diga otra cosa."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)

    assert _leer_politica_cookie() == (True, "none")


def test_sin_variables_se_conserva_el_comportamiento_previo(monkeypatch) -> None:
    _sin_flags(monkeypatch)
    monkeypatch.setenv("ENV", "production")
    assert _leer_politica_cookie() == (True, "none")

    monkeypatch.setenv("ENV", "development")
    assert _leer_politica_cookie() == (False, "strict")


def test_samesite_explicito_independiente_de_secure(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_SAMESITE", "lax")

    assert _leer_politica_cookie() == (False, "lax")


def test_samesite_none_sin_secure_se_auto_corrige(monkeypatch) -> None:
    """SameSite=None exige Secure: los navegadores descartan la cookie si no.
    Una combinación mal configurada se fuerza a secure=true en vez de emitir
    una cookie que el navegador tirará a la basura."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_SAMESITE", "none")

    assert _leer_politica_cookie() == (True, "none")


def test_secure_acepta_valores_positivos_variados(monkeypatch) -> None:
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    for valor in ("1", "true", "yes", "si", "SÍ"):
        monkeypatch.setenv("COOKIE_SECURE", valor)
        assert _leer_politica_cookie()[0] is True


def test_env_example_declara_flags_de_cookie() -> None:
    raiz_proyecto = Path(__file__).resolve().parents[2]
    contenido = (raiz_proyecto / ".env.example").read_text(encoding="utf-8")

    assert "COOKIE_SECURE=" in contenido.splitlines()
    assert "COOKIE_SAMESITE=" in contenido.splitlines()
