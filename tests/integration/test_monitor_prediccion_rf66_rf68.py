# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción contra Postgres        |
"""Monitor de inferencia (RF-66) y riesgo de contagio (RF-68) contra PostgreSQL real.

Las pestañas Monitor y Contagio pintaban datos simulados. Se siembra una inferencia y
un cálculo de contagio en una finca del Veterinario (``session_replication_role =
replica``, sin FKs) y se lee por HTTP con JWT real: el dueño los ve con nombres, otro
usuario del mismo rol no, y los filtros se validan.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

VETERINARIO = 3


@pytest.fixture(autouse=True)
def montar_routers(integration_app):
    from src.prediction.infrastructure.routers.monitor_prediccion_router import router as monitor
    from src.prediction.infrastructure.routers.riesgo_contagio_router import router as contagio
    integration_app.include_router(monitor)
    integration_app.include_router(contagio)


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers):
    db = db_session
    dueno = crear_usuario_db(id_rol=VETERINARIO)
    ajeno = crear_usuario_db(id_rol=VETERINARIO)
    db.execute(text("SET LOCAL session_replication_role = replica"))
    finca, _, activo = _finca_con_activo(db, dueno["id_usuario"])
    sufijo = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8])
    patologia = db.execute(text(
        "INSERT INTO modulo9.patologias (nombre, es_activo, es_base, version_catalogo) "
        "VALUES (:n, true, false, 1) RETURNING id_patologia"), {"n": f"Patologia Monitor {sufijo}"}).scalar_one()
    inferencia = db.execute(text(
        "INSERT INTO modulo4.resultados_inferencia (id_resultado_inferencia, id_activo_biologico, id_especie, "
        "tipo_modelo, id_version_modelo, nivel_riesgo, probabilidad_riesgo, probabilidad_enfermedad, "
        "confianza_global, modo_ejecucion, latencia_ms, id_patologia) VALUES "
        "(gen_random_uuid(), :a, 1, 'MODELO_ESPECIES_GRANDES', -1, 3, '{\"3\": 0.91}', '{}', 0.86, 'EDGE', 390, :p) "
        "RETURNING id_resultado_inferencia"), {"a": activo, "p": patologia}).scalar_one()
    contagio = db.execute(text(
        "INSERT INTO modulo4.resultados_riesgo_contagio (id_activo_biologico, id_configuracion_motor, "
        "factor_sanitario_fs, w_fs_aplicado, w_fa_aplicado, w_fd_aplicado, probabilidad_contagio, "
        "nivel_riesgo_contagio) VALUES (:a, -1, 0.5, 0.5, 0.3, 0.2, 0.62, 2) RETURNING id_resultado_contagio"),
        {"a": activo}).scalar_one()
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return dict(
        activo=activo, finca=finca, inferencia=str(inferencia), contagio=contagio,
        patologia=f"Patologia Monitor {sufijo}",
        dueno=crear_auth_headers(dueno), ajeno=crear_auth_headers(ajeno),
    )


def _mias(respuesta, campo, valor):
    assert respuesta.status_code == 200, respuesta.text
    return [r for r in respuesta.json() if str(r[campo]) == str(valor)]


def test_monitor_trae_la_inferencia_con_nombres_y_respeta_la_finca(client, escenario):
    (fila,) = _mias(client.get("/prediccion/inferencias", headers=escenario["dueno"]),
                    "id_resultado_inferencia", escenario["inferencia"])
    assert (fila["nivel_riesgo"], fila["modo_ejecucion"], fila["latencia_ms"]) == (3, "EDGE", 390)
    assert fila["nombre_patologia"] == escenario["patologia"]
    assert fila["paradigma"] == "INDIVIDUAL" and fila["nombre_finca"] and fila["nombre_area"]
    assert _mias(client.get("/prediccion/inferencias", headers=escenario["ajeno"]),
                 "id_resultado_inferencia", escenario["inferencia"]) == []


def test_monitor_filtra_por_nivel_y_tipo(client, escenario):
    def ids(**params):
        return _mias(client.get("/prediccion/inferencias", params=params, headers=escenario["dueno"]),
                     "id_resultado_inferencia", escenario["inferencia"])
    assert len(ids(nivel_riesgo=3, tipo_modelo="MODELO_ESPECIES_GRANDES")) == 1
    assert ids(nivel_riesgo=1) == [] and ids(tipo_modelo="MODELO_AVES") == []


def test_contagio_trae_el_calculo_del_lote_y_respeta_la_finca(client, escenario):
    (fila,) = _mias(client.get("/prediccion/riesgo-contagio", headers=escenario["dueno"]),
                    "id_resultado_contagio", escenario["contagio"])
    assert fila["nivel_riesgo_contagio"] == 2 and float(fila["probabilidad_contagio"]) == 0.62
    assert _mias(client.get("/prediccion/riesgo-contagio", headers=escenario["ajeno"]),
                 "id_resultado_contagio", escenario["contagio"]) == []


@pytest.mark.parametrize("ruta,params,codigo", [
    ("/prediccion/inferencias", {"nivel_riesgo": 7}, "NIVEL_RIESGO_INVALIDO"),
    ("/prediccion/inferencias", {"tipo_modelo": "CONTAGIO"}, "TIPO_MODELO_INVALIDO"),
    ("/prediccion/riesgo-contagio", {"desde": "2026-10-29T00:00:00Z", "hasta": "2026-10-01T00:00:00Z"},
     "RANGO_FECHAS_INVALIDO"),
])
def test_filtros_invalidos_son_400(client, escenario, ruta, params, codigo):
    r = client.get(ruta, params=params, headers=escenario["dueno"])
    assert r.status_code == 400, r.text
    assert r.json()["error_code"] == codigo


def test_sin_token_es_401(client):
    assert client.get("/prediccion/inferencias").status_code == 401
    assert client.get("/prediccion/riesgo-contagio").status_code == 401
