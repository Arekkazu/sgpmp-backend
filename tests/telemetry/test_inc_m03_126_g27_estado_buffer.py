# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: validar consulta protegida, clasificación, datos desconocidos y contrato opcional del heartbeat. |
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import NotFoundError, InfrastructureError
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.telemetry.domain.entities.estado_buffer import MetricasBuffer, EstadoBufferReportado, PoliticaBuffer
from src.telemetry.application.use_cases.infraestructura.consultar_estado_buffer_use_case import ConsultarEstadoBufferUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import RecibirHeartbeatUseCase
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO
from src.telemetry.infrastructure.dto.metricas_buffer_dto import MetricasBufferDTO
from src.telemetry.infrastructure.repositories.estado_buffer_repository import SqlAlchemyEstadoBufferRepository
from src.telemetry.infrastructure.schema.estado_buffer_schema import EstadoBufferSchema
from src.telemetry.infrastructure.routers import infraestructura_iot_router as rutas


FECHA = datetime(2026,10,27,1,0,tzinfo=timezone.utc)


def metricas(**cambios):
    return dict(capacidad_total=1000,capacidad_utilizada=800,
                ultimo_timestamp_pendiente=FECHA.isoformat(),
                politica_buffer_activa='POLITICA_RECHAZO') | cambios


def heartbeat(**cambios):
    return dict(device_id=3,serial='G27-TEST',tipo_mensaje='HEARTBEAT',fecha_registro=FECHA,
                datos_pendientes_buffer=7) | cambios


def app_prueba(db):
    app=FastAPI()
    register_error_handlers(app)
    app.include_router(rutas.router)
    app.dependency_overrides[get_db]=lambda:db
    return app


def test_consulta_buffer_existe_y_exige_autenticacion():
    with TestClient(app_prueba(Mock()),raise_server_exceptions=False) as client:
        respuesta=client.get('/iot/dispositivos/1/buffer')
    assert respuesta.status_code==401,respuesta.text


@pytest.mark.parametrize('usada,estado',[(0,'NORMAL'),('799.999','NORMAL'),(800,'WARNING'),
    ('949.999','WARNING'),(950,'CRITICO'),(1000,'CRITICO')])
def test_limites_normativos_sin_redondear_antes_de_clasificar(usada,estado):
    m=MetricasBufferDTO(**metricas(capacidad_utilizada=usada)).a_dominio()
    assert m.estado_buffer.value==estado
    assert m.porcentaje_ocupacion==Decimal(str(usada))/10


@pytest.mark.parametrize('cambios',[{'capacidad_total':0},{'capacidad_total':-1},
    {'capacidad_total':'NaN'},{'capacidad_total':'Infinity'},{'capacidad_utilizada':-1},
    {'capacidad_utilizada':1001},{'capacidad_utilizada':True},
    {'politica_buffer_activa':'RECHAZAR'},{'ultimo_timestamp_pendiente':'no-es-fecha'},
    {'campo_inventado':1}])
def test_reporte_invalido_no_se_acepta(cambios):
    with pytest.raises(ValidationError):HeartbeatDTO(**heartbeat(metricas_buffer=metricas(**cambios)))


def test_timestamp_normaliza_la_zona_y_no_se_reconstruye():
    dto=MetricasBufferDTO(**metricas(ultimo_timestamp_pendiente='2026-10-26T20:00:00-05:00'))
    assert dto.ultimo_timestamp_pendiente==FECHA


@pytest.mark.parametrize('cambios',[{}, {'metricas_buffer':None}])
def test_heartbeat_anterior_sigue_siendo_valido(cambios):
    assert HeartbeatDTO(**heartbeat(**cambios)).metricas_buffer is None


def test_snapshot_y_heartbeat_se_entregan_en_la_misma_transaccion():
    db,dispositivos,repo=Mock(),Mock(),Mock()
    dispositivos.validar_dispositivo_heartbeat.return_value=SimpleNamespace(es_activo=True)
    repo.guardar.side_effect=lambda h:h
    resultado=RecibirHeartbeatUseCase(db,dispositivos,repo).execute(
        HeartbeatDTO(**heartbeat(metricas_buffer=metricas())))
    assert resultado.metricas_buffer['capacidad_total']=='1000'
    assert resultado.metricas_buffer['ultimo_timestamp_pendiente']==FECHA.isoformat().replace('+00:00','Z')
    assert resultado.datos_pendientes_buffer==7
    db.commit.assert_called_once()


def test_fallo_commit_revierte_el_heartbeat_y_el_snapshot():
    db,dispositivos,repo=Mock(),Mock(),Mock()
    dispositivos.validar_dispositivo_heartbeat.return_value=SimpleNamespace(es_activo=True)
    db.commit.side_effect=RuntimeError('caída simulada')
    with pytest.raises(RuntimeError):
        RecibirHeartbeatUseCase(db,dispositivos,repo).execute(HeartbeatDTO(**heartbeat(metricas_buffer=metricas())))
    db.rollback.assert_called_once()


@pytest.mark.parametrize('reporte',[EstadoBufferReportado(3),
    EstadoBufferReportado(3,id_heartbeat=7,datos_pendientes=12,estado_local_buffer='A')])
def test_ausencia_de_metricas_no_inventa_buffer_vacio_o_normal(reporte):
    datos=EstadoBufferSchema.desde_reporte(reporte)
    assert datos.datos_pendientes==reporte.datos_pendientes
    assert not datos.metricas_disponibles
    assert datos.capacidad_total is datos.capacidad_utilizada is datos.estado_buffer is None
    assert datos.porcentaje_ocupacion is datos.politica_buffer_activa is None


def test_consulta_propaga_alcance_y_no_confirma_transacciones():
    repo=Mock()
    repo.obtener.return_value=EstadoBufferReportado(3)
    assert ConsultarEstadoBufferUseCase(repo).execute(3,[9]).id_dispositivo_iot==3
    repo.obtener.assert_called_once_with(3,[9])


def test_inexistente_y_fuera_de_alcance_comparten_error_publico():
    repo=Mock();repo.obtener.return_value=None
    with pytest.raises(NotFoundError) as fallo:ConsultarEstadoBufferUseCase(repo).execute(3,[])
    assert fallo.value.code=='DISPOSITIVO_NO_ENCONTRADO'


@pytest.fixture
def cliente(monkeypatch):
    db=Mock()
    db.query.return_value.filter.return_value.first.return_value=object()
    repo=Mock()
    repo.obtener.return_value=EstadoBufferReportado(3,id_heartbeat=11,fecha_reporte=FECHA,
        fecha_recepcion=FECHA,datos_pendientes=7,metricas=MetricasBufferDTO(**metricas()).a_dominio())
    alcance=Mock();alcance.listar_ids_fincas_permitidas.return_value=[8]
    monkeypatch.setattr(rutas,'SqlAlchemyEstadoBufferRepository',lambda _:repo)
    monkeypatch.setattr(rutas,'AlcanceFincaAdapter',lambda _:alcance)
    app=app_prueba(db)
    app.dependency_overrides[get_current_user]=lambda:UsuarioActual(1,1,4,2)
    with TestClient(app,raise_server_exceptions=False) as c:
        yield c,db,repo,alcance


def test_respuesta_http_expone_siete_metricas_y_fuente(cliente):
    c,db,repo,alcance=cliente
    r=c.get('/iot/dispositivos/3/buffer')
    assert r.status_code==200,r.text
    d=r.json()
    assert Decimal(d['capacidad_total'])==1000 and Decimal(d['capacidad_utilizada'])==800
    assert Decimal(d['porcentaje_ocupacion'])==80 and d['datos_pendientes']==7
    assert d['estado_buffer']=='WARNING' and d['politica_buffer_activa']=='POLITICA_RECHAZO'
    assert datetime.fromisoformat(d['ultimo_timestamp_pendiente'])==FECHA
    assert d['id_heartbeat']==11 and d['metricas_disponibles']
    repo.obtener.assert_called_once_with(3,[8])
    db.commit.assert_not_called()


def test_rbac_sin_permiso_no_consulta_metricas(cliente):
    c,db,repo,_=cliente
    db.query.return_value.filter.return_value.first.return_value=None
    assert c.get('/iot/dispositivos/3/buffer').status_code==403
    repo.obtener.assert_not_called()


@pytest.mark.parametrize('identificador',['0','-1','abc'])
def test_identificador_invalido_se_rechaza(cliente,identificador):
    c,_,repo,_=cliente
    r=c.get('/iot/dispositivos/'+identificador+'/buffer')
    assert r.status_code==400,r.text
    assert r.json()['error_code']=='VAL_ENTRADA'
    repo.obtener.assert_not_called()


def test_http_fuera_de_alcance_es_404(cliente):
    c,_,repo,_=cliente
    repo.obtener.return_value=None
    r=c.get('/iot/dispositivos/3/buffer')
    assert r.status_code==404 and r.json()['error_code']=='DISPOSITIVO_NO_ENCONTRADO'


def test_json_directo_invalido_no_se_presenta_como_normal():
    db=Mock()
    db.execute.return_value.mappings.return_value.one_or_none.return_value=dict(
        id_dispositivo_iot=3,id_heartbeat=1,fecha_reporte=FECHA,fecha_recepcion=FECHA,
        estado_local_buffer='A',datos_pendientes=7,json_metricas_buffer=metricas(capacidad_total=0))
    with pytest.raises(InfrastructureError) as fallo:SqlAlchemyEstadoBufferRepository(db).obtener(3,[8])
    assert fallo.value.code=='REPORTE_BUFFER_INVALIDO'


def test_openapi_declara_consulta_y_ampliacion_opcional():
    schema=app_prueba(Mock()).openapi()
    assert '/iot/dispositivos/{id_dispositivo_iot}/buffer' in schema['paths']
    heartbeat_schema=schema['components']['schemas']['HeartbeatDTO']
    assert 'metricas_buffer' in heartbeat_schema['properties']
    assert 'metricas_buffer' not in heartbeat_schema.get('required',[])
    respuesta=schema['components']['schemas']['EstadoBufferSchema']['properties']
    assert {'capacidad_total','capacidad_utilizada','porcentaje_ocupacion','datos_pendientes',
            'ultimo_timestamp_pendiente','estado_buffer','politica_buffer_activa'} <= respuesta.keys()
