# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-103-G164 RF-62: validar HTTP, JWT/RBAC y trazabilidad persistida sobre dev actualizado en PostgreSQL real. |
# | 2026-10-31 | Claude | INC-M03-243-G169 RF-62: R7/R9, serie sin calibración evaluada y versión de límites físicos |
"""Solo TEST_DATABASE_URL exclusiva; usa las protecciones y rollback del fixture común."""
from datetime import timedelta, timezone

import pytest
from sqlalchemy import text

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.telemetry.infrastructure.routers.calidad_router import router
from test_rf62_dev02_aptitud_telemetria import crear_escenario  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def rutas_calidad(integration_app):
    if not any(getattr(r, 'path', None) == '/iot/calidad' for r in integration_app.routes):
        integration_app.include_router(router)


@pytest.fixture
def admin_headers(crear_usuario_db, crear_auth_headers):
    usuario = crear_usuario_db(id_rol=1)
    return usuario, crear_auth_headers(usuario)


@pytest.fixture
def configuracion_calidad(db_session, admin_headers):
    """Datos explícitos de prueba por la interfaz administrativa de DEV-14."""
    usuario, _ = admin_headers
    ConfigurarParametrosMLOpsUseCase(
        db_session, SqlAlchemyParametrosMLOpsRepository(db_session),
    ).execute({
        'rf62_k': 3, 'rf62_m': 5, 'rf62_n': 20,
        'rf62_umbral_drift': 5, 'rf62_p': 3,
    }, usuario['id_usuario'])
    activa = db_session.execute(text(
        'SELECT id_configuracion_global FROM modulo9.configuraciones_globales WHERE es_activo=true'
    )).scalar_one_or_none()
    if activa is None:
        db_session.execute(text('''
            INSERT INTO modulo9.configuraciones_globales
                (frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
            VALUES (5,10,now(),:usuario,true)
        '''), {'usuario': usuario['id_usuario']})
    else:
        db_session.execute(text('''
            UPDATE modulo9.configuraciones_globales SET frecuencia_muestreo=5,heartbeat=10
            WHERE id_configuracion_global=:id
        '''), {'id': activa})
    db_session.commit()


@pytest.mark.parametrize('query', [
    {'clasificacion': 'VALOR_NO_CATALOGADO_ENUM'},
    {'estado_evaluacion': 'ACTIVA'},
    {'fecha_desde': '2026-04-16T23:59:59Z', 'fecha_hasta': '2026-04-14T00:00:00Z'},
    {'pagina': 0}, {'por_pagina': 0}, {'por_pagina': 201},
])
def test_casos_reportados_422_con_autenticacion_y_bd_reales(client, admin_headers, query):
    _, headers = admin_headers
    respuesta = client.get('/iot/calidad', params=query, headers=headers)
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()['error_code'] == 'VAL_ENTRADA'
    assert respuesta.json()['fields']


@pytest.mark.parametrize('estado', ['LECTURA_VALIDA', 'ERROR_CALIBRACION', 'FUERA_DE_RANGO'])
def test_evaluar_persistir_y_consultar_conserva_parametros(
    client, admin_headers, crear_escenario, db_session, configuracion_calidad, estado,
):
    _, headers = admin_headers
    e = crear_escenario(estado=estado)
    antes = db_session.execute(text(
        'SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'
    ), {'id': e.id_telemetria}).scalar_one()
    respuesta = client.post(f'/iot/calidad/{e.id_telemetria}/evaluar', headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    resultado = respuesta.json()
    parametros = resultado['parametros_aplicados']
    assert parametros
    if estado == 'FUERA_DE_RANGO':
        limites = parametros.pop('limites_fisicos_aplicados')
        assert limites['fuente'] == 'modulo9.variables_ambientales'
        assert parametros == {
            'regla_aplicada': 'FUERA_DE_RANGO_RF53', 'indice_calidad': 0,
            'fases_estadisticas_omitidas': True, 'id_variable': 9,
        }
        parametros['limites_fisicos_aplicados'] = limites
        # G169 (R7/R9): la rama FUERA_DE_RANGO también guarda la versión de límites físicos.
        assert resultado['version_limites_fisicos_aplicada'].startswith('va9:')
        assert resultado['indice_calidad'] == 0 and not resultado['apto_para_ia']
    else:
        assert {'k', 'M', 'N', 'umbral_drift', 'P', 'frecuencia_muestreo_min'} <= parametros.keys()
    guardados = db_session.execute(text(
        'SELECT parametros_aplicados FROM modulo3.telemetria_calidad WHERE id_evaluacion=:id'
    ), {'id': resultado['id_evaluacion']}).scalar_one()
    assert guardados == parametros
    detalle = client.get(f'/iot/calidad/{e.id_telemetria}', headers=headers)
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()['parametros_aplicados'] == parametros
    listado = client.get('/iot/calidad', params={'id_sensor': e.sensor}, headers=headers)
    assert listado.status_code == 200, listado.text
    assert listado.json()['total'] == 1
    assert listado.json()['items'][0]['parametros_aplicados'] == parametros
    despues = db_session.execute(text(
        'SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'
    ), {'id': e.id_telemetria}).scalar_one()
    assert despues == antes


def test_parametros_historicos_se_conservan_y_nuevos_usaran_configuracion_real(
    client, admin_headers, crear_escenario, db_session, configuracion_calidad,
):
    usuario, headers = admin_headers
    e = crear_escenario()
    ruta = f'/iot/calidad/{e.id_telemetria}'
    primera = client.post(ruta + '/evaluar', headers=headers)
    assert primera.status_code == 201, primera.text
    primera = primera.json()
    k_nuevo = 4 if primera['parametros_aplicados']['k'] != 4 else 3
    ConfigurarParametrosMLOpsUseCase(
        db_session, SqlAlchemyParametrosMLOpsRepository(db_session),
    ).execute({'rf62_k': k_nuevo}, usuario['id_usuario'])
    # GET devuelve la instantánea del cálculo, no la configuración actual.
    assert client.get(ruta, headers=headers).json()['parametros_aplicados'] == primera['parametros_aplicados']
    segunda = client.post(ruta + '/evaluar', headers=headers)
    assert segunda.status_code == 201, segunda.text
    segunda = segunda.json()
    assert segunda['parametros_aplicados']['k'] == k_nuevo
    assert segunda['id_evaluacion_superada'] == primera['id_evaluacion']
    anterior = client.get('/iot/calidad', params={
        'id_sensor': e.sensor, 'estado_evaluacion': 'SUPERADA',
    }, headers=headers)
    assert anterior.status_code == 200, anterior.text
    assert anterior.json()['total'] == 1
    assert anterior.json()['items'][0]['parametros_aplicados'] == primera['parametros_aplicados']
    assert anterior.json()['items'][0]['motivo_reevaluacion']
    vigente = client.get(ruta, headers=headers)
    assert vigente.json()['id_evaluacion'] == segunda['id_evaluacion']


def test_no_se_inventan_parametros_si_falta_la_configuracion(
    client, admin_headers, crear_escenario, db_session,
):
    _, headers = admin_headers
    e = crear_escenario()
    db_session.execute(text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro='rf62_k'"))
    db_session.commit()
    respuesta = client.post(f'/iot/calidad/{e.id_telemetria}/evaluar', headers=headers)
    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()['error_code'] == 'PARAMETRO_CONFIGURACION_AUSENTE'
    assert e.calidad.obtener_por_lectura(e.id_telemetria) is None


def test_filtros_combinados_paginacion_frontera_y_zonas_horarias(
    client, admin_headers, crear_escenario, db_session,
):
    _, headers = admin_headers
    e = crear_escenario()
    evaluacion = e.caso.execute(**e.datos)
    filtros = {
        'id_sensor': e.sensor, 'clasificacion': evaluacion.clasificacion_calidad.value,
        'estado_evaluacion': 'VIGENTE', 'por_pagina': 1,
        'fecha_desde': evaluacion.timestamp_evaluacion.isoformat(),
        'fecha_hasta': evaluacion.timestamp_evaluacion.astimezone(timezone(timedelta(hours=-5))).isoformat(),
    }
    primera = client.get('/iot/calidad', params=filtros, headers=headers)
    assert primera.status_code == 200, primera.text
    assert primera.json()['total'] == 1
    assert primera.json()['items'][0]['id_evaluacion'] == str(evaluacion.id_evaluacion)
    segunda = client.get('/iot/calidad', params=filtros | {'pagina': 2}, headers=headers)
    assert segunda.status_code == 200 and segunda.json()['total'] == 1
    assert segunda.json()['items'] == []


def test_jwt_y_permiso_de_lectura_se_siguen_exigiendo(
    client, crear_usuario_db, crear_auth_headers, db_session,
):
    assert client.get('/iot/calidad').status_code == 401
    usuario = crear_usuario_db(id_rol=2)
    headers = crear_auth_headers(usuario)
    db_session.execute(text(
        'UPDATE modulo1.permisos SET es_activo=false WHERE id_rol=2 AND id_recurso=38 AND id_accion=2'
    ))
    db_session.commit()
    respuesta = client.get('/iot/calidad', headers=headers)
    assert respuesta.status_code == 403, respuesta.text
