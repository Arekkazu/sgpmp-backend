"""DEV-06 (D3, AIOT-DEV-03): los endpoints /iot/* de dispositivo exigen el token de
servicio del broker; el serial deja de ser credencial y viaja en el cuerpo."""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from main import app
from src.shared.database import get_db_sistema
from src.telemetry.infrastructure.routers import alerta_router

TOKEN = "token-de-prueba"

ENDPOINTS = [
    "/iot/telemetria",
    "/iot/telemetria/batch",
    "/iot/telemetria/vision",
    "/iot/heartbeat",
    "/iot/eventos-edge",
    "/iot/alertas",
]


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("BROKER_SERVICE_TOKEN", TOKEN)
    app.dependency_overrides[get_db_sistema] = lambda: Mock()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db_sistema, None)


@pytest.mark.parametrize("ruta", ENDPOINTS)
def test_sin_token_responde_401(cliente, ruta):
    r = cliente.post(ruta, json={})
    assert r.status_code == 401, r.text
    assert r.json()["error_code"] == "TOKEN_SERVICIO_INVALIDO"


@pytest.mark.parametrize("ruta", ENDPOINTS)
def test_token_incorrecto_responde_401(cliente, ruta):
    r = cliente.post(ruta, json={}, headers={"Authorization": "Bearer otro"})
    assert r.status_code == 401, r.text


def test_access_key_igual_al_serial_ya_no_autentica(cliente):
    # El contrato anterior: el serial como access_key, sin token. Hoy es 401.
    r = cliente.post("/iot/heartbeat", json={}, headers={"X-Device-API-Key": "GW-001", "X-Device-Id": "1"})
    assert r.status_code == 401, r.text


def test_token_con_caracteres_no_ascii_es_401_no_500(cliente):
    r = cliente.post("/iot/alertas", json={}, headers={"Authorization": "Bearer tökén".encode("latin-1")})
    assert r.status_code == 401, r.text


def test_sin_token_configurado_responde_503(cliente, monkeypatch):
    monkeypatch.delenv("BROKER_SERVICE_TOKEN")
    r = cliente.post("/iot/alertas", json={}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 503, r.text
    assert r.json()["error_code"] == "TOKEN_SERVICIO_NO_CONFIGURADO"


def test_con_token_el_serial_debe_corresponder_al_dispositivo(cliente, monkeypatch):
    puerto = Mock()
    puerto.obtener_dispositivo_activo.return_value = None  # device_id no es de ese serial
    monkeypatch.setattr(alerta_router, "DispositivoM09Adapter", lambda db: puerto)
    r = cliente.post(
        "/iot/alertas",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "device_id": 3, "sensor_id": 9, "serial": "GW-001",
            "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "31.5", "unidad": "C",
            "timestamp_evento": "2026-10-17T10:00:00Z", "estado_dato": "LECTURA_VALIDA",
            "severidad_edge": "MODERADO", "origen_evento": "EDGE",
        },
    )
    assert r.status_code == 401, r.text
    assert r.json()["error_code"] == "DISPOSITIVO_NO_AUTORIZADO"
    puerto.obtener_dispositivo_activo.assert_called_once_with(device_id=3, sensor_id=9, serial="GW-001")
