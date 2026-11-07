# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: el motor IA registra resultados, contra PostgreSQL real   |
"""``POST /prediccion/inferencias`` contra PostgreSQL real, con RLS.

Solo el usuario de servicio puede insertar en ``modulo4.resultados_inferencia``
(``pol_resultado_inferencia_servicio_insert``): se comprueba que el endpoint lo hace
como tal, que el reintento no duplica, que la fila queda en sombra con la especie del
activo y que RF-73 registra ``INFERENCIA_EJECUTADA``.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

TOKEN = "token-motor-integracion"


@pytest.fixture(autouse=True)
def montar_router(integration_app, monkeypatch):
    from src.prediction.infrastructure.routers.monitor_prediccion_router import router
    monkeypatch.setenv("IOT_INFERENCIA_M04_TOKEN", TOKEN)
    integration_app.include_router(router)


@pytest.fixture
def escenario(db_session, crear_usuario_db):
    db = db_session
    dueno = crear_usuario_db(id_rol=3)
    db.execute(text("SET LOCAL session_replication_role = replica"))
    _, _, activo = _finca_con_activo(db, dueno["id_usuario"])
    version = db.execute(text(
        "INSERT INTO modulo4.versiones_modelos (nombre_version, tipo_modelo, estado_version) "
        "VALUES (:n, 'MODELO_ESPECIES_GRANDES', 'APROBADO') RETURNING id_version_modelo"),
        {"n": f"ET02-v5-{uuid.uuid4().hex[:6]}"}).scalar_one()
    db.execute(text("SET LOCAL session_replication_role = origin"))
    especie = db.execute(text("SELECT id_especie FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a"),
                         {"a": activo}).scalar_one()
    return dict(activo=activo, version=version, especie=especie)


def _cuerpo(escenario, **cambios) -> dict:
    cuerpo = {
        "id_resultado_inferencia": str(uuid.uuid4()),
        "id_activo_biologico": escenario["activo"],
        "tipo_modelo": "MODELO_ESPECIES_GRANDES",
        "id_version_modelo": escenario["version"],
        "nivel_riesgo": 0,
        "probabilidad_riesgo": {"0": 0.762, "3": 0.058},
        "probabilidad_enfermedad": {"0": 0.762, "7": 0.086},
        "confianza_global": 0.762,
        "contexto_incompleto": False,
        "modo_ejecucion": "SERVIDOR",
        "latencia_ms": 2400,
        "fecha_inicio_ventana": "2026-09-20T14:50:00+00:00",
        "fecha_fin_ventana": "2026-09-20T15:00:00+00:00",
        "fecha_inferencia": "2026-10-25T20:30:49+00:00",
        "modo_sombra": True,
    }
    cuerpo.update(cambios)
    return cuerpo


_AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_guarda_en_sombra_y_el_reintento_no_duplica(client, db_session, escenario):
    cuerpo = _cuerpo(escenario)
    primero = client.post("/prediccion/inferencias", json=cuerpo, headers=_AUTH)
    assert primero.status_code == 201, primero.text
    assert primero.json()["duplicado"] is False and primero.json()["latencia_excedida"] is True

    segundo = client.post("/prediccion/inferencias", json=cuerpo, headers=_AUTH)
    assert (segundo.status_code, segundo.json()["duplicado"]) == (200, True)

    filas = db_session.execute(text(
        "SELECT modo_sombra, id_especie, latencia_excedida, tiene_alerta_generada "
        "FROM modulo4.resultados_inferencia WHERE id_resultado_inferencia = :id"),
        {"id": cuerpo["id_resultado_inferencia"]}).all()
    assert filas == [(True, escenario["especie"], True, False)]

    eventos = db_session.execute(text(
        "SELECT tipo_evento::text FROM modulo4.eventos_auditoria_m04 WHERE id_referencia = :id "
        "ORDER BY tipo_evento"), {"id": cuerpo["id_resultado_inferencia"]}).scalars().all()
    assert eventos == ["INFERENCIA_EJECUTADA", "LATENCIA_EXCEDIDA"]


@pytest.mark.parametrize("cambios,status,codigo", [
    ({"modo_sombra": False}, 422, "INFERENCIA_VINCULANTE_NO_DISPONIBLE"),
    ({"tipo_modelo": "MODELO_AVES"}, 422, "TIPO_MODELO_NO_COINCIDE"),
    ({"id_activo_biologico": 2_000_000_000}, 404, "ACTIVO_NO_ENCONTRADO"),
])
def test_rechazos(client, escenario, cambios, status, codigo):
    r = client.post("/prediccion/inferencias", json=_cuerpo(escenario, **cambios), headers=_AUTH)
    assert (r.status_code, r.json()["error_code"]) == (status, codigo), r.text


def test_version_inexistente_404(client, escenario):
    r = client.post("/prediccion/inferencias", json=_cuerpo(escenario, id_version_modelo=2_000_000_000),
                    headers=_AUTH)
    assert (r.status_code, r.json()["error_code"]) == (404, "VERSION_MODELO_NO_ENCONTRADA")


def test_sin_token_401(client, escenario):
    assert client.post("/prediccion/inferencias", json=_cuerpo(escenario)).status_code == 401
