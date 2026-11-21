# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-03 | Arekkazu | QA-M04 ronda 2 CU01 H-14/H-16, CU09 H-05 RF-64/RF-73: catálogo bajo RLS y filtros de auditoría |
"""Re-pruebas M04 ronda 2 contra el esquema real.

Con ``TEST_ROL_APP=sgpmp_app`` los requests corren bajo RLS, como en dev:
ahí ``patologias_variables_sensoricas`` no tenía política DELETE y editar o
inactivar respondía 409 "Ya existe un registro con esos datos" (CU01 H-14).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

_BASE = "/prediccion/patologias"
_DESCRIPCION = "Fiebre y taquicardia sostenidas en el animal indican un proceso infeccioso sistémico en curso."


def _variables(db_session) -> list[int]:
    return [
        fila[0]
        for fila in db_session.execute(
            text(
                "SELECT id_variable_ambiental FROM modulo9.variables_ambientales "
                "WHERE es_activo AND nombre IN ('Temperatura Corporal', 'Frecuencia Cardiaca', "
                "'Frecuencia Respiratoria') ORDER BY id_variable_ambiental"
            )
        )
    ]


@pytest.fixture
def admin(crear_usuario_db, crear_auth_headers, integration_app):
    from src.prediction.infrastructure.routers.auditoria_m04_router import router as auditoria
    from src.prediction.infrastructure.routers.patologia_m04_router import router as patologias

    for router in (patologias, auditoria):
        if not any(getattr(r, "path", None) == router.prefix for r in integration_app.routes):
            integration_app.include_router(router)
    return crear_auth_headers(crear_usuario_db(id_rol=1))


@pytest.fixture
def especie(db_session) -> str:
    return str(db_session.execute(text("SELECT min(id_especie) FROM modulo9.especies WHERE es_activo")).scalar_one())


def _registrar(client, admin, especie, variables) -> dict:
    respuesta = client.post(
        _BASE,
        headers=admin,
        json={
            "nombre_patologia": f"QA ronda dos {uuid.uuid4().hex[:8]}",
            "especie_aplicable": especie,
            "variables_sensoricas_asociadas": variables,
            "descripcion_clinica": _DESCRIPCION,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_inactivar_patologia_personalizada(client, admin, especie, db_session):
    v = _variables(db_session)
    creada = _registrar(client, admin, especie, v[:2])

    respuesta = client.patch(f"{_BASE}/{creada['id_patologia']}/desactivar", headers=admin)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["es_activo"] is False
    assert cuerpo["version_catalogo"] == creada["version_catalogo"] + 1
    assert {x["id_variable_ambiental"] for x in cuerpo["variables_sensoricas_asociadas"]} == set(v[:2])


def test_editar_descripcion_y_cambiar_variables(client, admin, especie, db_session):
    v = _variables(db_session)
    creada = _registrar(client, admin, especie, v[:2])
    url = f"{_BASE}/{creada['id_patologia']}"

    solo_descripcion = client.patch(url, headers=admin, json={
        "nombre_patologia": creada["nombre_patologia"],
        "descripcion_clinica": _DESCRIPCION + " Retest",
        "variables_sensoricas_asociadas": v[:2],
    })
    assert solo_descripcion.status_code == 200, solo_descripcion.text
    assert solo_descripcion.json()["descripcion_clinica"].endswith("Retest")

    # Quitar una variable exige DELETE sobre la tabla hija bajo RLS.
    otras = client.patch(url, headers=admin, json={
        "nombre_patologia": creada["nombre_patologia"],
        "descripcion_clinica": _DESCRIPCION,
        "variables_sensoricas_asociadas": [v[0], v[2]],
        "fecha_actualizacion": solo_descripcion.json()["fecha_actualizacion"],
    })
    assert otras.status_code == 200, otras.text
    assert {x["id_variable_ambiental"] for x in otras.json()["variables_sensoricas_asociadas"]} == {v[0], v[2]}


def test_intento_rechazado_queda_en_la_bitacora(client, admin, especie, db_session):
    v = _variables(db_session)
    a = _registrar(client, admin, especie, v[:2])
    b = _registrar(client, admin, especie, [v[0], v[2]])

    # CU01 H-11: renombrar b con el nombre de a se rechaza y debe quedar auditado.
    rechazo = client.patch(f"{_BASE}/{b['id_patologia']}", headers=admin, json={
        "nombre_patologia": a["nombre_patologia"],
        "descripcion_clinica": _DESCRIPCION,
        "variables_sensoricas_asociadas": [v[0], v[2]],
    })
    assert rechazo.status_code == 409, rechazo.text

    evento = db_session.execute(text(
        "SELECT resultado_operacion::text, codigo_error FROM modulo4.eventos_auditoria_m04 "
        "WHERE tipo_evento = 'CATALOGO_PATOLOGIA_MODIFICADA' AND id_referencia = :id"
    ), {"id": str(b["id_patologia"])}).one()
    assert tuple(evento) == ("FALLIDO", "NOMBRE_PATOLOGIA_DUPLICADO")


@pytest.mark.parametrize("parametro", [
    "tipo_evento=MODELO_REGISTRADO",
    "tipo_evento=PATOLOGIA_MODIFICADA",
    "severidad_evento=FOO",
])
def test_filtro_de_auditoria_invalido_no_es_500(client, admin, parametro):
    # El listado publica 422 para parámetros inválidos (INC-M04-208-G089); la exportación, 400.
    for ruta, codigo in (("/prediccion/auditoria", 422), ("/prediccion/auditoria/exportar", 400)):
        respuesta = client.get(f"{ruta}?{parametro}", headers=admin)
        assert respuesta.status_code == codigo, (ruta, respuesta.text)


def test_filtro_de_auditoria_valido_sigue_funcionando(client, admin):
    respuesta = client.get("/prediccion/auditoria?tipo_evento=CATALOGO_PATOLOGIA_AGREGADA&severidad_evento=INFO", headers=admin)
    assert respuesta.status_code == 200, respuesta.text
