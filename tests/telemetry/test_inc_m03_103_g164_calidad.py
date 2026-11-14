# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-103-G164 RF-62: verificar consultas, contrato HTTP y parametros auditables sobre dev actualizado. |
"""Regresiones de #625 con repositorios falsos; no demuestran persistencia real."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from src.shared import rbac
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError
from src.identity_access.infrastructure.dependencies import get_current_user
from src.telemetry.application.use_cases.calidad.consultar_calidad_use_case import ConsultarCalidadUseCase
from src.telemetry.domain.entities.telemetria_calidad import ClasificacionCalidad, EstadoEvaluacion
from src.telemetry.infrastructure.routers import calidad_router
from test_rf62_dev02_persistencia_aptitud import _escenario


@pytest.fixture
def http(monkeypatch):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(calidad_router.router)
    repo = Mock()
    repo.listar.return_value = ([], 0)
    repo.obtener_por_lectura.return_value = None
    monkeypatch.setattr(calidad_router, 'SqlAlchemyTelemetriaCalidadRepository', lambda db: repo)
    alcance = Mock()
    alcance.listar_ids_fincas_permitidas.return_value = None
    monkeypatch.setattr(calidad_router, 'AlcanceFincaAdapter', lambda db: alcance)
    monkeypatch.setattr(rbac, 'tiene_permiso', lambda *args: True)
    app.dependency_overrides[get_db] = lambda: Mock()
    app.dependency_overrides[get_current_user] = lambda: Mock(id_usuario=7, id_rol=1, id_estado_cuenta=2)

    @app.get('/otro-contrato')
    def otro(pagina: int = Query(ge=1)):
        return pagina

    with TestClient(app) as client:
        yield client, repo, app


@pytest.mark.parametrize('query,campo', [
    ({'clasificacion': 'VALOR_NO_CATALOGADO_ENUM'}, 'clasificacion'),
    ({'clasificacion': ''}, 'clasificacion'),
    ({'estado_evaluacion': 'ACTIVA'}, 'estado_evaluacion'),
    ({'estado_evaluacion': ''}, 'estado_evaluacion'),
    ({'fecha_desde': '2026-04-16T23:59:59Z', 'fecha_hasta': '2026-04-14T00:00:00Z'}, 'fecha_desde'),
    ({'fecha_desde': 'no-es-fecha'}, 'fecha_desde'),
    ({'pagina': 0}, 'pagina'),
    ({'pagina': -1}, 'pagina'),
    ({'pagina': 'abc'}, 'pagina'),
    ({'por_pagina': 0}, 'por_pagina'),
    ({'por_pagina': 201}, 'por_pagina'),
    ({'por_pagina': 'abc'}, 'por_pagina'),
])
def test_query_invalida_es_422_sin_consultar_repositorio(http, query, campo):
    client, repo, _ = http
    respuesta = client.get('/iot/calidad', params=query)
    assert respuesta.status_code == 422, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo['error_code'] == 'VAL_ENTRADA'
    assert campo in {f['field'] for f in cuerpo['fields']}
    assert 'items' not in cuerpo and 'total' not in cuerpo
    repo.listar.assert_not_called()


@pytest.mark.parametrize('clasificacion', list(ClasificacionCalidad))
@pytest.mark.parametrize('estado', list(EstadoEvaluacion))
def test_enums_validos_y_filtros_combinados_conservan_contrato(http, clasificacion, estado):
    client, repo, _ = http
    respuesta = client.get('/iot/calidad', params={
        'clasificacion': clasificacion.value, 'estado_evaluacion': estado.value,
        'id_sensor': 9, 'pagina': 2, 'por_pagina': 200,
    })
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {'items': [], 'total': 0, 'pagina': 2, 'por_pagina': 200}
    filtros = repo.listar.call_args.kwargs
    assert filtros['clasificacion'] == clasificacion.value
    assert filtros['estado_evaluacion'] == estado.value
    assert filtros['id_sensor'] == 9
    assert filtros['pagina'] == 2 and filtros['por_pagina'] == 200


@pytest.mark.parametrize('query', [
    {}, {'por_pagina': 1},
    {'fecha_desde': '2026-04-16T00:00:00Z'},
    {'fecha_hasta': '2026-04-16T00:00:00Z'},
    {'fecha_desde': '2026-04-16T00:00:00Z', 'fecha_hasta': '2026-04-16T00:00:00Z'},
    {'fecha_desde': '2026-04-16T00:00:00-05:00', 'fecha_hasta': '2026-04-16T05:00:00Z'},
    {'fecha_desde': '2026-04-16T00:00:00', 'fecha_hasta': '2026-04-16T05:00:00Z'},
])
def test_defaults_y_limites_temporales_validos(http, query):
    client, repo, _ = http
    respuesta = client.get('/iot/calidad', params=query)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['pagina'] == 1
    repo.listar.assert_called_once()


def test_rango_invertido_no_se_puede_omitir_al_invocar_caso_de_uso():
    repo = Mock()
    with pytest.raises(BusinessRuleError) as error:
        ConsultarCalidadUseCase(repo).listar(
            fecha_desde=datetime(2026, 4, 16, tzinfo=timezone.utc),
            fecha_hasta=datetime(2026, 4, 14, tzinfo=timezone.utc),
        )
    assert error.value.code == 'VAL_ENTRADA' and error.value.status_code == 422
    repo.listar.assert_not_called()


def test_otros_contratos_y_detalle_mantienen_su_validacion_400(http):
    client, repo, _ = http
    assert client.get('/otro-contrato?pagina=0').status_code == 400
    assert client.get('/iot/calidad/no-es-entero').status_code == 400
    assert client.get('/iot/calidad/999').status_code == 404
    repo.listar.assert_not_called()


def test_openapi_publica_enums_rangos_y_error_estandar(http):
    _, _, app = http
    schema = app.openapi()
    operacion = schema['paths']['/iot/calidad']['get']
    parametros = {p['name']: p['schema'] for p in operacion['parameters']}
    for campo, enum in [('clasificacion', ClasificacionCalidad), ('estado_evaluacion', EstadoEvaluacion)]:
        ref = next(s['$ref'] for s in parametros[campo]['anyOf'] if '$ref' in s)
        assert set(schema['components']['schemas'][ref.rsplit('/', 1)[1]]['enum']) == {e.value for e in enum}
    assert parametros['pagina']['minimum'] == 1
    assert parametros['por_pagina']['minimum'] == 1 and parametros['por_pagina']['maximum'] == 200
    assert operacion['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse')


@pytest.mark.parametrize('serie,cambios', [
    ([22, 23] * 10, {}),
    ([22, 23] * 9, {}),
    ([25] * 20, {'valor': Decimal('25')}),
    ([22, 23] * 10, {'estado_calidad_rf53': 'ERROR_CALIBRACION', 'parametros_calibracion': None}),
    ([], {'estado_calidad_rf53': 'FUERA_DE_RANGO'}),
])
def test_todas_las_ramas_guardan_parametros_y_detalle_los_conserva(http, serie, cambios):
    client, repo, _ = http
    caso, db, lecturas, _, datos = _escenario(serie)
    ev = caso.execute(**(datos | cambios))
    assert ev.parametros_aplicados
    if cambios.get('estado_calidad_rf53') == 'FUERA_DE_RANGO':
        assert ev.parametros_aplicados['regla_aplicada'] == 'FUERA_DE_RANGO_RF53'
        assert ev.parametros_aplicados['indice_calidad'] == 0
        caso.parametros_port.obtener_parametros.assert_not_called()
        lecturas.obtener_serie_temporal.assert_not_called()
    else:
        assert {'k', 'M', 'N', 'umbral_drift', 'P', 'frecuencia_muestreo_min'} <= ev.parametros_aplicados.keys()
    db.commit.assert_called_once()
    repo.obtener_por_lectura.return_value = ev
    respuesta = client.get(f'/iot/calidad/{ev.id_telemetria}')
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['parametros_aplicados'] == ev.parametros_aplicados


def test_get_no_inventa_parametros_para_evaluaciones_historicas(http):
    client, repo, _ = http
    caso, _, _, _, datos = _escenario([22, 23] * 10)
    ev = caso.execute(**datos)
    ev.parametros_aplicados = {}
    repo.obtener_por_lectura.return_value = ev
    assert client.get(f'/iot/calidad/{ev.id_telemetria}').json()['parametros_aplicados'] == {}


def test_consulta_conserva_autenticacion_y_rbac(http, monkeypatch):
    client, repo, app = http
    monkeypatch.setattr(rbac, 'tiene_permiso', lambda *args: False)
    assert client.get('/iot/calidad').status_code == 403
    repo.listar.assert_not_called()
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/iot/calidad').status_code == 401
