"""Pruebas de configuración de vigencia JWT para RF-02."""
from datetime import timedelta
from pathlib import Path

from src.shared import jwt as jwt_module


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
