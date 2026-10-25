# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M03-135/136/137 RF-63: filtros de la bitácora y verificación HTTP |
"""RF-63 por HTTP contra PostgreSQL real.

- INC-M03-136-G178: ``GET /iot/auditoria`` filtra por ``id_usuario`` y ``rf_origen``.
- INC-M03-137-G179: y por ``registro_incompleto`` (CA-13 / E8 verificables por API).
- INC-M03-135-G177: ``verificar-integridad`` exige la ventana de fechas.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, TipoResultado
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    SqlAlchemyBitacoraAuditoriaIotRepository,
)

pytestmark = pytest.mark.integration

CUANDO = datetime(2026, 3, 3, 3, 3, tzinfo=timezone.utc)


@pytest.fixture
def cliente(client, integration_app):
    from src.telemetry.infrastructure.routers.auditoria_iot_router import router
    if not any(getattr(r, 'path', '') == '/iot/auditoria/verificar-integridad' for r in integration_app.routes):
        integration_app.include_router(router)
    return client


@pytest.fixture
def admin(crear_usuario_db, crear_auth_headers):
    usuario = crear_usuario_db(id_rol=1)
    return usuario["id_usuario"], crear_auth_headers(usuario)


def _registrar(db, **campos):
    RegistrarEventoAuditoriaIotUseCase(db, SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(
        resultado=TipoResultado.EXITOSO, fecha_evento=CUANDO, **campos)


def _listar(cliente, headers, **filtros):
    r = cliente.get("/iot/auditoria", headers=headers, params={
        "fecha_desde": (CUANDO - timedelta(seconds=1)).isoformat(),
        "fecha_hasta": (CUANDO + timedelta(seconds=1)).isoformat(), **filtros})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_filtros_id_usuario_rf_origen_y_registro_incompleto(cliente, db_session, admin):
    id_admin, headers = admin
    _registrar(db_session, tipo_evento="HEARTBEAT_RECIBIDO", componente_origen=ComponenteOrigen.RF60, id_usuario=id_admin)
    _registrar(db_session, tipo_evento="TELEMETRIA_RECIBIDA", componente_origen=ComponenteOrigen.RF53)
    _registrar(db_session, tipo_evento=None, componente_origen=None)

    por_usuario = _listar(cliente, headers, id_usuario=id_admin)
    assert [e["tipo_evento"] for e in por_usuario] == ["HEARTBEAT_RECIBIDO"]
    assert [e["tipo_evento"] for e in _listar(cliente, headers, rf_origen="RF53")] == ["TELEMETRIA_RECIBIDA"]
    incompletos = _listar(cliente, headers, registro_incompleto="true")
    assert len(incompletos) == 1 and incompletos[0]["registro_incompleto"] is True
    assert incompletos[0]["clasificacion_registro"] == "NIC41"  # E8
    assert "componente_origen" not in incompletos[0]  # rf_origen filtra, pero no se expone


def test_rf_origen_desconocido_se_rechaza(cliente, admin):
    _, headers = admin
    r = cliente.get("/iot/auditoria", headers=headers, params={"rf_origen": "RF99"})
    assert r.status_code == 400, r.text


@pytest.mark.parametrize("params", [{}, {"fecha_desde": CUANDO.isoformat()}])
def test_verificar_integridad_exige_la_ventana(cliente, admin, params):
    _, headers = admin
    r = cliente.post("/iot/auditoria/verificar-integridad", headers=headers, params=params)
    assert r.status_code == 400, r.text


def test_verificar_integridad_con_ventana_responde(cliente, db_session, admin):
    _, headers = admin
    _registrar(db_session, tipo_evento="TELEMETRIA_RECIBIDA", componente_origen=ComponenteOrigen.RF53)
    r = cliente.post("/iot/auditoria/verificar-integridad", headers=headers, params={
        "fecha_desde": (CUANDO - timedelta(seconds=1)).isoformat(),
        "fecha_hasta": (CUANDO + timedelta(seconds=1)).isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["total_verificados"] >= 1 and r.json()["comprometidos"] == 0
