# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: validar rechazo auditado y fechas originales en PostgreSQL con rol API. |
"""HTTP y persistencia reales; no ejecuta firmware ni demuestra TC-M03-103."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import declarar_identidad_sistema, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import evento_edge_router
from tests.integration.test_rf56_dev17_paquetes_pendientes import _crear_hardware, _payload
from tests.integration.test_rf56_dev17_paquetes_pendientes import modelos as modelos

pytestmark = pytest.mark.integration


@pytest.fixture
def hardware(db_session):
    return _crear_hardware(db_session)


@pytest.fixture
def http_g42(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(evento_edge_router.router)

    def sesion_api():
        db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
        declarar_identidad_sistema(db_session)
        contexto = db_session.execute(text(
            "SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )).one()
        assert tuple(contexto) == ("sgpmp_app", False, False)
        try:
            yield db_session
        finally:
            db_session.execute(text("RESET ROLE"))

    app.dependency_overrides[get_db_sistema] = sesion_api
    with TestClient(app, headers=headers_broker, raise_server_exceptions=False) as client:
        yield client


def _filas(db, tabla, hardware):
    # Las tablas proceden de los literales de estas pruebas, nunca del cliente.
    return db.execute(text(
        f"SELECT count(*) FROM modulo3.{tabla} WHERE id_dispositivo_iot=:id"
    ), {"id": hardware["device"]}).scalar_one()


@pytest.mark.parametrize("origen", ["TIEMPO_REAL", "BUFFER_LOCAL"])
def test_orden_invertido_no_crea_evento_ni_paquete_y_conserva_rechazo(http_g42, db_session, hardware, origen):
    payload = _payload(hardware)
    captura = datetime.fromisoformat(payload["timestamp_captura"])
    payload["timestamp_procesamiento_edge"] = (captura - timedelta(microseconds=1)).isoformat()
    payload["origen"] = origen
    payload["estado_conectividad"] = origen == "TIEMPO_REAL"
    response = http_g42.post("/iot/eventos-edge", json=payload)
    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == "ORDEN_TEMPORAL_INVALIDO"
    assert _filas(db_session, "eventos_edge_computing", hardware) == 0
    assert _filas(db_session, "paquetes_inferencia", hardware) == 0
    acciones = db_session.execute(text(
        "SELECT accion_detallada FROM modulo3.bitacora_auditoria_iot "
        "WHERE tipo_evento='EVENTO_EDGE_RECHAZADO' AND entidad_afectada_id=:serial"
    ), {"serial": hardware["serial"]}).scalars().all()
    assert len(acciones) == 1
    assert acciones[0]["codigo_error"] == "ORDEN_TEMPORAL_INVALIDO"
    auditado = acciones[0]["evento"]
    for campo in ("timestamp_captura", "timestamp_procesamiento_edge"):
        assert datetime.fromisoformat(auditado[campo]) == datetime.fromisoformat(payload[campo])


@pytest.mark.parametrize("delta_us", [0, 1, 500_000])
@pytest.mark.parametrize("clasificacion", ["NORMAL", "DESVIACION_SIMPLE"])
def test_respuesta_y_bd_conservan_ambas_fechas_sin_reconstruirlas(
    http_g42, db_session, hardware, delta_us, clasificacion,
):
    payload = _payload(hardware, clasificacion)
    captura = datetime.fromisoformat(payload["timestamp_captura"])
    procesamiento = captura + timedelta(microseconds=delta_us)
    payload["timestamp_captura"] = captura.astimezone(timezone(timedelta(hours=-5))).isoformat()
    payload["timestamp_procesamiento_edge"] = procesamiento.isoformat()
    response = http_g42.post("/iot/eventos-edge", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    persistido = db_session.execute(text(
        "SELECT fecha_captura,fecha_procesamiento FROM modulo3.eventos_edge_computing "
        "WHERE id_evento_edge_computing=:id"
    ), {"id": body["id_evento_edge_computing"]}).one()
    assert tuple(persistido) == (captura, procesamiento)
    assert datetime.fromisoformat(body["fecha_captura"]) == persistido.fecha_captura
    assert datetime.fromisoformat(body["fecha_procesamiento"]) == persistido.fecha_procesamiento
    if clasificacion == "DESVIACION_SIMPLE":
        metadatos = db_session.execute(text(
            "SELECT metadatos FROM modulo3.paquetes_inferencia WHERE id_evento_edge_computing=:id"
        ), {"id": body["id_evento_edge_computing"]}).scalar_one()
        assert datetime.fromisoformat(metadatos["timestamp_captura"]) == captura
        assert datetime.fromisoformat(metadatos["timestamp_procesamiento_edge"]) == procesamiento


@pytest.mark.parametrize("caso,codigo", [("futuro", "TIMESTAMP_FUTURO"), ("expirado", "TIMESTAMP_EXPIRADO")])
def test_conserva_rechazos_temporales_previos(http_g42, hardware, caso, codigo):
    payload = _payload(hardware, "NORMAL")
    captura = datetime.now(timezone.utc) + (timedelta(seconds=31) if caso == "futuro" else -timedelta(hours=73))
    payload["timestamp_captura"] = captura.isoformat()
    payload["timestamp_procesamiento_edge"] = captura.isoformat()
    if caso == "expirado":
        payload["origen"] = "BUFFER_LOCAL"
    response = http_g42.post("/iot/eventos-edge", json=payload)
    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == codigo
