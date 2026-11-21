# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: la tolerancia T se configura, persiste y expone desde M09 |
"""INC-M03-246-G88 (#889, TC-M03-172): T configurable en /configuracion/umbrales."""
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
def _router_umbrales(integration_app):
    from src.configuration.infrastructure.routers.umbral_router import router
    integration_app.include_router(router)


@pytest.fixture
def headers(crear_usuario_db, crear_auth_headers):
    return crear_auth_headers(crear_usuario_db(id_rol=1))


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


def _crear(client, db_session, headers, **extra):
    id_especie, id_variable = _especie_y_variable(db_session)
    return client.post('/configuracion/umbrales', headers=headers, json={
        'id_especie': id_especie, 'id_variable_ambiental': id_variable,
        'valor_min': 0, 'valor_max': 45, 'niveles': _NIVELES, **extra,
    })


def test_t_se_persiste_y_prevalece_sobre_la_predeterminada(client, db_session, headers) -> None:
    creado = _crear(client, db_session, headers, tolerancia_semaforo=2)
    assert creado.status_code == 201, creado.text
    umbral = creado.json()
    assert float(umbral['tolerancia_semaforo']) == 2
    assert float(umbral['tolerancia_semaforo_efectiva']) == 2
    persistida = db_session.execute(text(
        'SELECT tolerancia_semaforo FROM modulo9.umbrales_ambientales WHERE id_umbral_ambiental = :u'),
        {'u': umbral['id_umbral_ambiental']}).scalar_one()
    assert float(persistida) == 2

    listado = client.get(f"/configuracion/umbrales/{umbral['id_umbral_ambiental']}", headers=headers)
    if listado.status_code == 200:
        assert float(listado.json()['tolerancia_semaforo']) == 2


def test_editar_sin_el_campo_conserva_t_y_null_vuelve_al_10_por_ciento(client, db_session, headers) -> None:
    umbral = _crear(client, db_session, headers, tolerancia_semaforo=2).json()
    url = f"/configuracion/umbrales/{umbral['id_umbral_ambiental']}"

    sin_campo = client.patch(url, headers=headers, json={
        'valor_min': 0, 'valor_max': 45, 'niveles': _NIVELES, 'fecha_actualizacion': umbral['fecha_actualizacion']})
    assert sin_campo.status_code == 200, sin_campo.text
    assert float(sin_campo.json()['tolerancia_semaforo']) == 2

    con_null = client.patch(url, headers=headers, json={
        'valor_min': 0, 'valor_max': 45, 'niveles': _NIVELES, 'tolerancia_semaforo': None,
        'fecha_actualizacion': sin_campo.json()['fecha_actualizacion']})
    assert con_null.status_code == 200, con_null.text
    assert con_null.json()['tolerancia_semaforo'] is None
    assert float(con_null.json()['tolerancia_semaforo_efectiva']) == 4.5


def test_t_negativa_se_rechaza(client, db_session, headers) -> None:
    respuesta = _crear(client, db_session, headers, tolerancia_semaforo=-1)
    assert respuesta.status_code in (400, 422), respuesta.text
