# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-175-G57A RF-57: umbrales para Administrador e Ingeniero de Campo; Veterinario 403 |
"""INC-M03-175-G57A (#880, BUG-G57A-01/02) con permisos reales de modulo1.permisos.

RF-57 R3 / CA-14 / CA-17: crean, editan y desactivan umbrales el Administrador y el
Ingeniero de Campo; el Veterinario y el Productor reciben 403. El Veterinario conserva
la lectura.
"""
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
def cabeceras(db_session, crear_usuario_db, crear_auth_headers):
    def por_rol(nombre):
        id_rol = db_session.execute(text('SELECT id_rol FROM modulo1.roles WHERE nombre_rol = :n'),
                                    {'n': nombre}).scalar_one()
        return crear_auth_headers(crear_usuario_db(id_rol=id_rol))
    return {r: por_rol(r) for r in ('Administrador', 'Ingeniero de Campo', 'Veterinario', 'Productor')}


def _cuerpo(db_session):
    fila = db_session.execute(text(
        "SELECT e.id_especie, v.id_variable_ambiental FROM modulo9.especies e "
        "CROSS JOIN modulo9.variables_ambientales v "
        "WHERE e.es_activo AND v.nombre = 'Temperatura del agua' "
        "AND NOT EXISTS (SELECT 1 FROM modulo9.umbrales_ambientales u WHERE u.id_especie = e.id_especie "
        "AND u.id_variable_ambiental = v.id_variable_ambiental AND u.es_activo) LIMIT 1")).first()
    if fila is None:
        pytest.skip('Se requiere una especie activa sin umbral de temperatura.')
    return {'id_especie': fila.id_especie, 'id_variable_ambiental': fila.id_variable_ambiental,
            'valor_min': 0, 'valor_max': 45, 'niveles': _NIVELES}


def test_ingeniero_de_campo_crea_edita_y_desactiva(client, db_session, cabeceras):
    h = cabeceras['Ingeniero de Campo']
    creado = client.post('/configuracion/umbrales', headers=h, json=_cuerpo(db_session))
    assert creado.status_code == 201, creado.text
    umbral = creado.json()
    url = f"/configuracion/umbrales/{umbral['id_umbral_ambiental']}"

    niveles = [{**n} for n in _NIVELES]
    niveles[0]['limite_superior'] = niveles[1]['limite_inferior'] = 18
    editado = client.patch(url, headers=h, json={'valor_min': 0, 'valor_max': 45, 'niveles': niveles,
                                                 'fecha_actualizacion': umbral['fecha_actualizacion']})
    assert editado.status_code == 200, editado.text
    assert client.patch(url + '/desactivar', headers=h).status_code == 200


@pytest.mark.parametrize('rol', ['Veterinario', 'Productor'])
def test_otros_roles_reciben_403_al_crear_editar_y_desactivar(client, db_session, cabeceras, rol):
    cuerpo = _cuerpo(db_session)
    umbral = client.post('/configuracion/umbrales', headers=cabeceras['Administrador'], json=cuerpo).json()
    url = f"/configuracion/umbrales/{umbral['id_umbral_ambiental']}"
    h = cabeceras[rol]

    assert client.post('/configuracion/umbrales', headers=h, json=cuerpo).status_code == 403
    assert client.patch(url, headers=h, json={'valor_min': 0, 'valor_max': 45, 'niveles': _NIVELES,
                                              'fecha_actualizacion': umbral['fecha_actualizacion']}).status_code == 403
    assert client.patch(url + '/desactivar', headers=h).status_code == 403
    assert db_session.execute(text('SELECT es_activo FROM modulo9.umbrales_ambientales WHERE id_umbral_ambiental = :u'),
                              {'u': umbral['id_umbral_ambiental']}).scalar_one() is True


def test_veterinario_conserva_la_consulta(client, db_session, cabeceras):
    cuerpo = _cuerpo(db_session)
    r = client.get('/configuracion/umbrales', headers=cabeceras['Veterinario'],
                   params={'id_especie': cuerpo['id_especie']})
    assert r.status_code == 200, r.text
