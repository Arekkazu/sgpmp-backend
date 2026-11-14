"""TC-M04-G041 — RF-65 / CU-02.

Subcasos: TC-M04-009 (403 RBAC), TC-M04-024 (401 autenticación).
App mínima con el router real, get_db anulado. Sin PostgreSQL ni tokens de producción.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.infrastructure.routers.motor_ia_router import router as motor_router
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AuthenticationError
from src.shared.jwt import verify_token


class _DbSinPermiso:
    def query(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return None

    def join(self, *_a, **_k):
        return self


def _app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(motor_router)
    app.dependency_overrides[get_db] = lambda: _DbSinPermiso()
    return app


_PAYLOAD = {
    "tipo_modelo": "MODELO_ESPECIES_GRANDES",
    "umbral_riesgo_alto": 0.70,
    "umbral_alerta_critica": 0.80,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
}


def test_tc_m04_024_sin_token_401_no_procesa() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.post("/prediccion/motor-ia", json=_PAYLOAD)
    assert r.status_code == 401
    body = r.json()
    assert body.get("error_code") == "TOKEN_REQUERIDO"


def test_tc_m04_024_token_expirado_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.shared.jwt._SECRET_KEY", "clave-prueba-g041")
    expire = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jose_jwt.encode(
        {"sub": "1", "jti": "1", "rol": 1, "exp": expire, "iat": expire - timedelta(hours=1)},
        "clave-prueba-g041",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError) as exc:
        verify_token(token)
    assert exc.value.code == "TOKEN_EXPIRADO"
    assert exc.value.status_code == 401


def test_tc_m04_024_firma_invalida_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.shared.jwt._SECRET_KEY", "clave-prueba-g041")
    token = jose_jwt.encode(
        {
            "sub": "1",
            "jti": "1",
            "rol": 1,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "otra-clave",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError) as exc:
        verify_token(token)
    assert exc.value.code == "TOKEN_INVALIDO"
    assert exc.value.status_code == 401


def test_tc_m04_009_autenticado_sin_permiso_403() -> None:
    app = _app()

    def _usuario():
        return UsuarioActual(id_usuario=2, id_token=2, id_rol=2, id_estado_cuenta=2)

    app.dependency_overrides[get_current_user] = _usuario
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/prediccion/motor-ia", json=_PAYLOAD)
    assert r.status_code == 403
    assert r.json().get("error_code") == "ACCESO_DENEGADO"
