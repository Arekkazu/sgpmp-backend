"""CU-M09-03 (RF-17): editar y desactivar un umbral respondía 500.

El repositorio reemplaza los niveles del umbral (delete-then-insert) y la tabla
``niveles_alerta_ambientales`` no tenía política de DELETE: con el rol de la
API (``TEST_ROL_APP=sgpmp_app``) el DELETE borraba 0 filas y el INSERT chocaba
con los niveles viejos en el trigger de solapamiento (P0113). Con superusuario
RLS no aplica, así que la regresión solo se reproduce con ``TEST_ROL_APP``.

También cubre RF-18/RF-19: las respuestas traen el nombre del usuario, no solo
su id.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

_NIVELES = [
    {'nivel': 'critico', 'limite_inferior': 0, 'limite_superior': 20},
    {'nivel': 'precaucion', 'limite_inferior': 20, 'limite_superior': 24},
    {'nivel': 'normal', 'limite_inferior': 24, 'limite_superior': 45},
]


@pytest.fixture(scope='module', autouse=True)
def _routers_m09(integration_app):
    from src.configuration.infrastructure.routers.configuracion_global_router import router as parametros
    from src.configuration.infrastructure.routers.finca_router import router as fincas
    from src.configuration.infrastructure.routers.umbral_router import router as umbrales

    for r in (umbrales, parametros, fincas):
        integration_app.include_router(r)


@pytest.fixture
def admin(db_session, crear_usuario_db, crear_auth_headers):
    usuario = crear_usuario_db(id_rol=1, nombre='Ana', apellidos='Umbral')
    return usuario, crear_auth_headers(usuario)


def _especie_y_variable(db_session) -> tuple[int, int]:
    fila = db_session.execute(text(
        "SELECT e.id_especie, v.id_variable_ambiental FROM modulo9.especies e "
        "CROSS JOIN modulo9.variables_ambientales v "
        "WHERE e.es_activo AND v.nombre = 'Temperatura del agua' "
        "AND NOT EXISTS (SELECT 1 FROM modulo9.umbrales_ambientales u WHERE u.id_especie = e.id_especie "
        "AND u.id_variable_ambiental = v.id_variable_ambiental AND u.es_activo) LIMIT 1"
    )).first()
    if fila is None:
        pytest.skip('Se requiere una especie activa sin umbral de temperatura.')
    return fila.id_especie, fila.id_variable_ambiental


def test_editar_y_desactivar_umbral(client, db_session, admin) -> None:
    _, headers = admin
    id_especie, id_variable = _especie_y_variable(db_session)
    creado = client.post('/configuracion/umbrales', headers=headers, json={
        'id_especie': id_especie, 'id_variable_ambiental': id_variable,
        'valor_min': 0, 'valor_max': 45, 'niveles': _NIVELES,
    })
    assert creado.status_code == 201, creado.text
    umbral = creado.json()

    nuevos = [{**n} for n in _NIVELES]
    nuevos[0]['limite_superior'] = nuevos[1]['limite_inferior'] = 18
    editado = client.patch(f"/configuracion/umbrales/{umbral['id_umbral_ambiental']}", headers=headers, json={
        'valor_min': 0, 'valor_max': 45, 'niveles': nuevos, 'fecha_actualizacion': umbral['fecha_actualizacion'],
    })
    assert editado.status_code == 200, editado.text
    critico = next(n for n in editado.json()['niveles'] if n['nivel'] == 'critico')
    assert float(critico['limite_superior']) == 18

    desactivado = client.patch(f"/configuracion/umbrales/{umbral['id_umbral_ambiental']}/desactivar", headers=headers)
    assert desactivado.status_code == 200, desactivado.text
    assert desactivado.json()['es_activo'] is False


def test_parametros_y_fincas_traen_el_nombre_del_usuario(client, db_session, admin) -> None:
    usuario, headers = admin
    actual = client.get('/configuracion/parametros', headers=headers).json()
    if actual:
        guardado = client.patch(f"/configuracion/parametros/{actual['id_configuracion_global']}", headers=headers, json={
            'frecuencia_muestreo': actual['frecuencia_muestreo'], 'heartbeat': actual['heartbeat'],
            'fecha_actualizacion': actual['fecha_actualizacion'],
        })
    else:
        guardado = client.post('/configuracion/parametros', headers=headers, json={'frecuencia_muestreo': 10, 'heartbeat': 20})
    assert guardado.status_code in (200, 201), guardado.text
    assert guardado.json()['nombre_usuario'] == 'Ana Umbral'

    id_finca = db_session.execute(text(
        "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo) "
        "VALUES ('Finca Nombre Productor', '{}'::jsonb, 10, now(), now(), true) RETURNING id_finca"
    )).scalar_one()
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
                       {'u': usuario['id_usuario'], 'f': id_finca})
    db_session.flush()
    fincas = client.get('/configuracion/fincas', headers=headers)
    assert fincas.status_code == 200, fincas.text
    finca = next(f for f in fincas.json()['items'] if f['id_finca'] == id_finca)
    assert finca['nombre_usuario'] == 'Ana Umbral'
