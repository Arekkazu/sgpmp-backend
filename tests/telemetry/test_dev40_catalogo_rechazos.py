# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: prueba catalogo y rechazos HTTP     |
# | 2026-10-29 | Arekkazu | INC-M03-134-G03 RF-60/RF-53: mantenimiento desde cualquier estado |
"""Pruebas aisladas de puertos y HTTP; no sustituyen PostgreSQL real."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
import pytest

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AppError, ServiceUnavailableError
from src.shared.middlewares import RequestContextMiddleware
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import IngerirTelemetriaUseCase
from src.telemetry.application.use_cases.ingesta.registrar_rechazo_estructura_use_case import RegistrarRechazoEstructuraUseCase
from src.telemetry.domain.entities.telemetria import ReglaVariableI3P1
from src.telemetry.domain.repositories.ingesta_telemetria_port import ResultadoPersistenciaIngesta
from src.telemetry.infrastructure.adapters.variable_catalogo_m09_adapter import VariableCatalogoM09Adapter
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaDTO
from src.telemetry.infrastructure.routers import telemetria_router, ruta_ingesta_auditada


def payload(**cambios):
    return dict(dict(device_id=3, sensor_id=6, serial='nodo',
        tipo_variable='VARIABLE_NUEVA', valor='22.5', unidad='unidad',
        timestamp_captura=datetime.now(timezone.utc).isoformat()), **cambios)


def regla():
    return ReglaVariableI3P1(831, 'VARIABLE_NUEVA', 'AMBIENTAL', 'unidad', ['unidad'], Decimal('0'), Decimal('100'))


def use_case():
    db, persistencia, identidad, bitacora, catalogo = [Mock() for _ in range(5)]
    catalogo.obtener_regla.return_value = regla()
    identidad.validar_dispositivo_heartbeat.return_value.en_mantenimiento = False
    persistencia.ingerir.return_value = ResultadoPersistenciaIngesta(1, 'ERROR_CALIBRACION', 'OK', datetime.now(timezone.utc))
    return IngerirTelemetriaUseCase(db, persistencia, identidad, bitacora, catalogo)


def fila(**cambios):
    return dict(dict(id_variable_ambiental=831, nombre='Variable Nueva', codigo_telemetria='VARIABLE_NUEVA',
        categoria_variable='AMBIENTAL', unidad='unidad', valor_fisico_min=0, valor_fisico_max=100), **cambios)


def test_variable_sin_id_quemado_llega_a_ingesta_con_metadatos_oficiales():
    uc = use_case()
    assert uc.execute(IngerirTelemetriaDTO(**payload())).id_telemetria == 1
    valores = uc.ingesta_port.ingerir.call_args.args[0]
    assert valores['id_variable'] == 831 and valores['categoria'] == 'AMBIENTAL'


@pytest.mark.parametrize('cambio,codigo', [({'id_variable': 400}, 'VARIABLE_INCOMPATIBLE'),
    ({'categoria_variable': 'ANIMAL'}, 'VARIABLE_INCOMPATIBLE'), ({}, 'VARIABLE_NO_ENCONTRADA')])
def test_referencia_incompatible_o_inexistente_no_es_estructura(cambio, codigo):
    uc = use_case()
    if not cambio:
        uc.catalogo_port.obtener_regla.return_value = None
    with pytest.raises(AppError) as exc:
        uc.execute(IngerirTelemetriaDTO(**payload(**cambio)))
    assert exc.value.code == codigo
    uc.ingesta_port.ingerir.assert_not_called()
    assert uc.bitacora_repo.registrar_error.call_args.kwargs['estado_calidad'] == 'ERROR_SENSOR'
    uc.db.commit.assert_called_once()


def test_fallo_catalogo_no_se_reclasifica_como_rechazo_de_usuario():
    uc = use_case()
    uc.catalogo_port.obtener_regla.side_effect = ServiceUnavailableError('BD_NO_DISPONIBLE', 'No disponible')
    with pytest.raises(ServiceUnavailableError):
        uc.execute(IngerirTelemetriaDTO(**payload()))
    uc.ingesta_port.ingerir.assert_not_called()
    uc.bitacora_repo.registrar_error.assert_not_called()
    uc.db.commit.assert_not_called()
    uc.db.rollback.assert_called_once()


def test_adapter_relee_datos_sin_cache_y_normaliza_nombre():
    db = Mock()
    db.execute.return_value.mappings.return_value.all.side_effect = [
        [fila(nombre='Medición Dinámica', codigo_telemetria='CODIGO_M09')],
        [fila(nombre='Medición Dinámica', codigo_telemetria='CODIGO_M09', unidad='otra')],
    ]
    adapter = VariableCatalogoM09Adapter(db)
    assert adapter.obtener_regla('MEDICION_DINAMICA').unidad_estandar == 'unidad'
    assert adapter.obtener_regla('CODIGO_M09').unidad_estandar == 'otra'
    assert db.execute.call_count == 2


@pytest.mark.parametrize('filas,codigo', [([], None), ([fila(categoria_variable=None)], 'CATALOGO_INCOMPLETO'),
    ([fila(), fila(id_variable_ambiental=832)], 'CATALOGO_AMBIGUO')])
def test_catalogo_ausente_incompleto_o_ambiguo(filas, codigo):
    db = Mock()
    db.execute.return_value.mappings.return_value.all.return_value = filas
    adapter = VariableCatalogoM09Adapter(db)
    if codigo is None:
        assert adapter.obtener_regla('VARIABLE_NUEVA') is None
    else:
        with pytest.raises(ServiceUnavailableError) as exc:
            adapter.obtener_regla('VARIABLE_NUEVA')
        assert exc.value.code == codigo


def test_adapter_traduce_error_real_de_sqlalchemy_sin_exponer_sql():
    db = Mock()
    db.execute.side_effect = OperationalError('select privado', {}, RuntimeError('secreto'))
    with pytest.raises(ServiceUnavailableError) as exc:
        VariableCatalogoM09Adapter(db).obtener_regla('VARIABLE_NUEVA')
    assert exc.value.code == 'BD_NO_DISPONIBLE' and 'privado' not in exc.value.message


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv('BROKER_SERVICE_TOKEN', 'broker-unitario')
    eventos = []
    monkeypatch.setattr(ruta_ingesta_auditada, '_registrar', eventos.append)
    uc = use_case()
    monkeypatch.setattr(telemetria_router, '_build_use_case', lambda db: uc)
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(telemetria_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: Mock()
    with TestClient(app, headers={'Authorization': 'Bearer broker-unitario'}, raise_server_exceptions=False) as client:
        yield client, eventos, uc


@pytest.mark.parametrize('ruta,body', [('/iot/telemetria', {}), ('/iot/telemetria', {'valor': 'credencial-secreta'}),
    ('/iot/telemetria/batch', {}), ('/iot/telemetria/batch', {'registros': [payload(), {}]})])
def test_estructura_individual_y_lote_es_400_con_un_solo_registro(http, ruta, body):
    client, eventos, uc = http
    response = client.post(ruta, json=body)
    assert response.status_code == 400 and response.json()['error_code'] == 'VAL_ENTRADA'
    assert len(eventos) == 1 and eventos[0]['resultado'] == 'RECHAZADO'
    assert eventos[0]['endpoint'] == ruta and eventos[0]['errores']
    assert 'credencial-secreta' not in repr(eventos)
    uc.ingesta_port.ingerir.assert_not_called()


def test_json_malformado_no_guarda_body_ni_cabeceras(http):
    client, eventos, _ = http
    response = client.post('/iot/telemetria', content='{"access_key":"secreto-malformado",',
        headers={'Content-Type': 'application/json', 'X-Request-ID': 'secreto-correlacion', 'X-Gateway-Id': 'secreto-gateway'})
    assert response.status_code == 400 and len(eventos) == 1
    assert not any(valor in repr(eventos) for valor in ['secreto-malformado', 'secreto-correlacion', 'secreto-gateway', 'broker-unitario'])


def test_identificadores_no_convertibles_y_claves_arbitrarias_no_se_guardan(http):
    client, eventos, _ = http
    client.post('/iot/telemetria', json={'device_id': 'password-secreto', 'sensor_id': True})
    assert 'device_id' not in eventos[0] and 'sensor_id' not in eventos[0]
    assert 'password-secreto' not in repr(eventos)


def test_peticion_valida_y_error_negocio_no_generan_error_estructura(http):
    client, eventos, uc = http
    assert client.post('/iot/telemetria', json=payload()).status_code == 201
    uc.catalogo_port.obtener_regla.return_value = None
    assert client.post('/iot/telemetria', json=payload()).status_code == 404
    assert eventos == []


def test_indisponibilidad_catalogo_por_http_no_es_400_ni_se_audita_como_estructura(http):
    client, eventos, uc = http
    uc.catalogo_port.obtener_regla.side_effect = ServiceUnavailableError('BD_NO_DISPONIBLE', 'No disponible')
    response = client.post('/iot/telemetria', json=payload())
    assert response.status_code == 503 and response.json()['error_code'] == 'BD_NO_DISPONIBLE'
    assert eventos == []


def test_auth_y_vision_conservan_su_manejo_sin_bitacora_escalar(http):
    client, eventos, _ = http
    assert client.post('/iot/telemetria', json=payload(), headers={'Authorization': 'Bearer incorrecto'}).status_code == 401
    assert client.post('/iot/telemetria/vision', json={}).status_code == 400
    assert eventos == []


def test_cada_intento_http_genera_una_evidencia_distinta(http):
    client, eventos, _ = http
    for _ in range(2):
        assert client.post('/iot/telemetria', json={}).status_code == 400
    assert len(eventos) == 2 and eventos[0]['id_correlacion'] != eventos[1]['id_correlacion']


@pytest.mark.parametrize('fallo', ['registro', 'commit'])
def test_fallo_bitacora_no_oculta_rechazo_y_revierte_transaccion_exclusiva(fallo, caplog):
    db, repo = Mock(), Mock()
    (repo.registrar_error if fallo == 'registro' else db.commit).side_effect = RuntimeError('secreto')
    RegistrarRechazoEstructuraUseCase(db, repo).execute({'endpoint': '/iot/telemetria'})
    db.rollback.assert_called_once()
    assert 'ERROR_ESTRUCTURA' in caplog.text and 'secreto' not in caplog.text
