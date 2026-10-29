# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: verificar orden temporal, rechazo auditado y timestamps originales en HTTP. |
"""Contrato del backend; los dobles no prueban la generación de fechas en Edge."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as modulo
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.routers import evento_edge_router


def _payload(delta_us=0, origen="TIEMPO_REAL"):
    captura = datetime.now(timezone.utc) - timedelta(minutes=1)
    return {
        "device_id": 3, "sensor_id": 7, "serial": "EDGE-G42",
        "clasificacion_rf55": "NORMAL", "severidad": None,
        "variables_involucradas": [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "25", "unidad": "°C"}],
        "timestamp_captura": captura.isoformat(),
        "timestamp_procesamiento_edge": (captura + timedelta(microseconds=delta_us)).isoformat(),
        "origen": origen, "estado_conectividad": origen == "TIEMPO_REAL",
    }


@pytest.fixture
def flujo(monkeypatch):
    monkeypatch.setattr(modulo, "registrar_llamada", lambda *args: None)
    db, eventos, dispositivos, paquetes, motor, auditoria = (Mock() for _ in range(6))
    dispositivos.obtener_dispositivo_activo.return_value = SimpleNamespace(
        id_dispositivo_iot=3, id_sensor=7, id_infraestructura=9,
        es_activo_dispositivo=True, es_activo_sensor=True,
    )

    def guardar(evento):
        evento.id_evento_edge_computing = 17
        return evento

    eventos.guardar.side_effect = guardar
    uc = modulo.RecibirEventoEdgeUseCase(db, eventos, paquetes, dispositivos, motor, Mock(), auditoria)
    return SimpleNamespace(uc=uc, db=db, eventos=eventos, dispositivos=dispositivos,
                           paquetes=paquetes, motor=motor, auditoria=auditoria)


@pytest.mark.parametrize("origen", ["TIEMPO_REAL", "BUFFER_LOCAL"])
@pytest.mark.parametrize("delta_us", [-1, -1_000_000])
def test_procesamiento_anterior_se_rechaza_y_audita_sin_persistir_evento(flujo, origen, delta_us):
    dto = RecibirEventoEdgeDTO(**_payload(delta_us, origen))
    with pytest.raises(ValidationError) as exc:
        flujo.uc.execute(dto)
    assert exc.value.code == "ORDEN_TEMPORAL_INVALIDO"
    assert exc.value.field == "timestamp_procesamiento_edge"
    flujo.eventos.guardar.assert_not_called()
    flujo.dispositivos.obtener_dispositivo_activo.assert_not_called()
    assert flujo.paquetes.mock_calls == []
    assert flujo.motor.mock_calls == []
    evento = flujo.auditoria.registrar.call_args.args[0]
    assert evento.tipo_evento == "EVENTO_EDGE_RECHAZADO"
    assert evento.accion_detallada["codigo_error"] == "ORDEN_TEMPORAL_INVALIDO"
    assert datetime.fromisoformat(evento.accion_detallada["evento"]["timestamp_captura"]) == dto.timestamp_captura
    assert datetime.fromisoformat(evento.accion_detallada["evento"]["timestamp_procesamiento_edge"]) == dto.timestamp_procesamiento_edge


@pytest.mark.parametrize("origen", ["TIEMPO_REAL", "BUFFER_LOCAL"])
@pytest.mark.parametrize("delta_us", [0, 1, 500_000])
def test_igualdad_y_procesamiento_posterior_conservan_ambos_instantes(flujo, origen, delta_us):
    dto = RecibirEventoEdgeDTO(**_payload(delta_us, origen))
    resultado = flujo.uc.execute(dto)
    guardado = flujo.eventos.guardar.call_args.args[0]
    assert guardado.fecha_captura == resultado.fecha_captura == dto.timestamp_captura
    assert guardado.fecha_procesamiento == resultado.fecha_procesamiento == dto.timestamp_procesamiento_edge
    flujo.db.commit.assert_called_once()


@pytest.fixture
def http(monkeypatch, flujo):
    monkeypatch.setenv("BROKER_SERVICE_TOKEN", "g42-token-local-pruebas")
    monkeypatch.setattr(evento_edge_router, "SqlAlchemyEventoEdgeRepository", lambda db: flujo.eventos)
    monkeypatch.setattr(evento_edge_router, "SqlAlchemyPaqueteInferenciaRepository", lambda db: flujo.paquetes)
    monkeypatch.setattr(evento_edge_router, "DispositivoM09Adapter", lambda db: flujo.dispositivos)
    monkeypatch.setattr(evento_edge_router, "MotorInferenciaStubAdapter", lambda: flujo.motor)
    monkeypatch.setattr(evento_edge_router, "SqlAlchemyParametrosMLOpsRepository", lambda db: Mock())
    monkeypatch.setattr(evento_edge_router, "ParametrosAlertasMLOpsAdapter", lambda repo: Mock())
    monkeypatch.setattr(evento_edge_router, "SqlAlchemyBitacoraAuditoriaIotRepository", lambda db: flujo.auditoria)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(evento_edge_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: flujo.db
    with TestClient(app, headers={"Authorization": "Bearer g42-token-local-pruebas"}) as client:
        yield client


def test_http_rechaza_orden_invertido_con_error_publico_y_bitacora(http, flujo):
    response = http.post("/iot/eventos-edge", json=_payload(-1))
    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == "ORDEN_TEMPORAL_INVALIDO"
    assert "timestamp_procesamiento_edge" in str(response.json()["fields"])
    flujo.eventos.guardar.assert_not_called()
    flujo.auditoria.registrar.assert_called_once()


@pytest.mark.parametrize("delta_us", [0, 1])
def test_http_devuelve_captura_y_procesamiento_originales_en_utc(http, delta_us):
    payload = _payload(delta_us)
    captura = datetime.fromisoformat(payload["timestamp_captura"])
    procesamiento = datetime.fromisoformat(payload["timestamp_procesamiento_edge"])
    payload["timestamp_captura"] = captura.astimezone(timezone(timedelta(hours=-5))).isoformat()
    response = http.post("/iot/eventos-edge", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id_evento_edge_computing"] == 17
    assert datetime.fromisoformat(body["fecha_captura"]) == captura
    assert datetime.fromisoformat(body["fecha_procesamiento"]) == procesamiento
    assert datetime.fromisoformat(body["fecha_captura"]).utcoffset() == timedelta(0)


def test_http_compara_instantes_con_offsets_distintos_y_no_sus_horas_locales(http):
    payload = _payload(-1)
    procesamiento = datetime.fromisoformat(payload["timestamp_procesamiento_edge"])
    payload["timestamp_procesamiento_edge"] = procesamiento.astimezone(timezone(timedelta(hours=5))).isoformat()
    response = http.post("/iot/eventos-edge", json=payload)
    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == "ORDEN_TEMPORAL_INVALIDO"
