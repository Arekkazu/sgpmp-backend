# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-53/62: conserva pruebas explicitas del contrato legado |
"""D4 con token de servicio → PostgreSQL DB-03 → consumidor RF-24 existente.

Sin broker ni motor IA real. El cálculo RF-62 comprobado es el heredado; las
diferencias con AIOT-SPEC-01 se documentan, no se simulan como resueltas.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import importlib
import pkgutil
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import telemetria_router
from src.telemetry.application.use_cases.ingesta.ingerir_observaciones_vision_use_case import IngerirObservacionesVisionUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.dto.observacion_vision_d4_dto import ObservacionVisionD4LegadoDTO as ObservacionVisionD4DTO
from src.telemetry.infrastructure.repositories.observacion_vision_repository import SqlAlchemyObservacionVisionRepository
from src.configuration.infrastructure.adapters.observacion_vision_m03_adapter import ObservacionVisionM03Adapter

pytestmark=pytest.mark.integration
TOKEN='token-solo-prueba-dev07'


@pytest.fixture(autouse=True)
def modelos(integration_engine):
    for paquete in ('src.configuration.infrastructure.models','src.biological_assets.infrastructure.models',
                    'src.telemetry.infrastructure.models','src.identity_access.infrastructure.models','src.prediction.infrastructure.models'):
        mod=importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__,paquete+'.'):importlib.import_module(item.name)
    with integration_engine.connect() as c:
        campos=set(c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='modulo3' AND table_name='observaciones_vision'")).scalars())
    if not {'fecha_inicio_ventana','json_version_cascada'}<=campos:
        pytest.skip('La base aislada debe incluir DB-03 65541db23c71; las pruebas no alteran el esquema.')


def hardware(db):
    tag=uuid.uuid4().hex[:12]
    nombre='Vision '+''.join(chr(97+int(c,16)) for c in tag)
    area=db.execute(text('''WITH finca AS (INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
        VALUES (:n,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :n,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura'''),{'n':nombre}).scalar_one()
    tipo=db.execute(text("SELECT id_tipo_dispositivo FROM modulo9.tipos_dispositivo_iot WHERE categoria='CAMARA' ORDER BY id_tipo_dispositivo LIMIT 1")).scalar_one()
    device=db.execute(text('''INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,
        id_infraestructura,id_tipo_dispositivo,resolucion,fps,area_cobertura_m2)
        VALUES (:s,'DEV-07',true,now(),:a,:t,'1280x720',25,100) RETURNING id_dispositivo_iot'''),{'s':tag,'a':area,'t':tipo}).scalar_one()
    db.commit()
    return dict(serial=tag,device=device,area=area)


@pytest.fixture
def equipo(db_session):return hardware(db_session)


@pytest.fixture
def client(db_session,monkeypatch):
    monkeypatch.setenv('BROKER_SERVICE_TOKEN',TOKEN)
    app=FastAPI();register_error_handlers(app);app.include_router(telemetria_router.router)
    app.dependency_overrides[get_db_sistema]=lambda:db_session
    with TestClient(app,raise_server_exceptions=False) as c:yield c


def sobre(equipo,**cambios):
    fin=datetime.now(timezone.utc)-timedelta(minutes=1)
    return dict(serial=equipo['serial'],area_id=equipo['area'],
        ventana_inicio=(fin-timedelta(minutes=1)).isoformat(),ventana_fin=fin.isoformat(),
        componentes={'densidad_actividad':.65,'dispersion_espacial':2.4,'tasa_movimiento':1.8},
        calidad={'cobertura_ventana':.95,'n_tracks':19,'n_tracks_perdidos':1,'fps_efectivo':24,'estado_calibracion':'CALIBRADA'},
        version_cascada={'detector':'det-1','seguimiento':'seg-2','metricas':'met-3','anomalias':'ano-4'})|cambios


def enviar(client,datos,token=TOKEN):
    return client.post('/iot/telemetria/vision',json=datos,headers={'Authorization':'Bearer '+token} if token else {})


def filas(db,equipo):
    return db.execute(text('SELECT * FROM modulo3.observaciones_vision WHERE id_dispositivo_iot=:id ORDER BY id_observacion_vision'),{'id':equipo['device']}).mappings().all()


def test_http_persiste_sobre_d4_con_ventana_y_versiones(client,db_session,equipo):
    datos=sobre(equipo)
    r=enviar(client,datos)
    assert r.status_code==201,r.text
    fila=filas(db_session,equipo)[0]
    assert fila['fecha_inicio_ventana']==datetime.fromisoformat(datos['ventana_inicio'])
    assert fila['fecha_observacion']==datetime.fromisoformat(datos['ventana_fin'])
    assert fila['json_version_cascada']==datos['version_cascada']
    assert fila['json_vector']==datos['componentes']
    assert fila['indice_calidad']==97 and fila['es_apto_para_ia']
    assert r.json()['observaciones'][0]['apto_para_nic41'] is False
    assert r.json()['observaciones'][0]['version_cascada']==datos['version_cascada']


@pytest.mark.parametrize('token',[None,'incorrecto'])
def test_serial_no_autentica_sin_token_valido(client,db_session,equipo,token):
    r=enviar(client,sobre(equipo),token)
    assert r.status_code==401,r.text
    assert not filas(db_session,equipo)


def test_token_no_configurado_no_simula_disponibilidad(client,db_session,equipo,monkeypatch):
    monkeypatch.delenv('BROKER_SERVICE_TOKEN')
    r=enviar(client,sobre(equipo))
    assert r.status_code==503,r.text
    assert not filas(db_session,equipo)


@pytest.mark.parametrize('cambio,codigo',[({'serial':'NO-REGISTRADA'},'ERROR_AUTENTICACION'),
    ({'area_id':999999},'AREA_NO_COINCIDE')])
def test_identidad_y_area_validas_requeridas(client,db_session,equipo,cambio,codigo):
    r=enviar(client,sobre(equipo,**cambio))
    assert r.status_code in (401,422),r.text
    assert r.json()['error_code']==codigo
    assert not filas(db_session,equipo)


@pytest.mark.parametrize('campo',['apto_para_ia','es_apto_para_ia','indice_calidad'])
def test_decision_del_cliente_se_rechaza(client,db_session,equipo,campo):
    r=enviar(client,sobre(equipo,**{campo:True}))
    assert r.status_code==400,r.text
    assert not filas(db_session,equipo)


def test_calidad_baja_calculada_no_es_apta(client,db_session,equipo):
    datos=sobre(equipo)
    datos['calidad'].update(cobertura_ventana=0,n_tracks=0,n_tracks_perdidos=5,fps_efectivo=0,estado_calibracion='SIN_DETECCION')
    r=enviar(client,datos)
    assert r.status_code==201,r.text
    assert r.json()['observaciones'][0]['apto_para_ia'] is False
    assert filas(db_session,equipo)[0]['es_apto_para_ia'] is False


def test_reenvio_preserva_fila_original_y_deduplica_por_instante(client,db_session,equipo):
    datos=sobre(equipo);r=enviar(client,datos)
    assert r.status_code==201,r.text
    original=dict(filas(db_session,equipo)[0])
    fecha=datetime.fromisoformat(datos['ventana_fin']).astimezone(timezone(timedelta(hours=-5)))
    datos['ventana_fin']=fecha.isoformat();datos['version_cascada']['detector']='otro'
    segundo=enviar(client,datos)
    assert segundo.status_code==201,segundo.text
    assert segundo.json()['duplicadas']==1 and segundo.json()['aceptadas']==0
    assert dict(filas(db_session,equipo)[0])==original


def test_lote_heredado_con_token_se_conserva(client,db_session,equipo):
    datos=sobre(equipo)
    viejo=dict(device_id=equipo['device'],serial=equipo['serial'],area_id=equipo['area'],observaciones=[
        dict(timestamp_captura=datos['ventana_fin'],vector=datos['componentes'],**datos['calidad'])])
    r=enviar(client,viejo)
    assert r.status_code==201,r.text
    fila=filas(db_session,equipo)[0]
    assert fila['fecha_inicio_ventana'] is None and fila['json_version_cascada'] is None
    assert fila['indice_calidad']==97


def test_error_tras_insert_revierte_todo_el_lote(client,db_session,equipo,monkeypatch):
    original=SqlAlchemyObservacionVisionRepository.guardar
    def fallar(repo,obs):
        original(repo,obs)
        raise RuntimeError('fallo simulado despues de insertar')
    monkeypatch.setattr(SqlAlchemyObservacionVisionRepository,'guardar',fallar)
    r=enviar(client,sobre(equipo))
    assert r.status_code==500
    assert not filas(db_session,equipo)


def test_concurrencia_no_crea_dos_observaciones(motor_vision_concurrente):
    integration_engine=motor_vision_concurrente
    with Session(integration_engine) as db:equipo=hardware(db)
    datos=sobre(equipo)
    def procesar():
        with Session(integration_engine) as db:
            repo=SqlAlchemyObservacionVisionRepository(db)
            # Fuerza a comprobar la carrera del INSERT, no solo el precheck.
            repo.fechas_existentes=lambda *args:set()
            return IngerirObservacionesVisionUseCase(db,repo,DispositivoM09Adapter(db)).execute(ObservacionVisionD4DTO(**datos))
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:resultados=list(executor.map(lambda _:procesar(),range(2)))
        assert sum(len(r.observaciones) for r in resultados)==1
        assert sum(r.duplicados for r in resultados)==1
        with Session(integration_engine) as db:assert len(filas(db,equipo))==1
    finally:
        with integration_engine.begin() as c:c.execute(text('UPDATE modulo9.dispositivos_iot SET es_activo=false WHERE id_dispositivo_iot=:id'),{'id':equipo['device']})


def test_rf24_consume_observaciones_d4_persistidas_para_linea_base(client,db_session,equipo):
    from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import CalibrarVisionUseCase
    from src.configuration.infrastructure.dto.calibrar_vision_dto import CalibrarVisionDTO
    fin=datetime.now(timezone.utc)-timedelta(minutes=2)
    for i in range(40):
        datos=sobre(equipo,ventana_inicio=(fin-timedelta(minutes=60-i)).isoformat(),ventana_fin=(fin-timedelta(minutes=59-i)).isoformat())
        datos['componentes']['densidad_actividad']=.6+(i%3)*.01
        r=enviar(client,datos);assert r.status_code==201,r.text
    adapter=ObservacionVisionM03Adapter(db_session)
    inicio=fin-timedelta(hours=2)
    assert len(adapter.listar([equipo['device']],inicio,fin))==40
    infra,camaras,cal,lb,eventos=Mock(),Mock(),Mock(),Mock(),Mock()
    infra.obtener_por_id.return_value=SimpleNamespace(id_infraestructura=equipo['area'],id_especie=4,tipo_modelo_asignado='MODELO_AVES')
    camaras.listar_por_area.return_value=[SimpleNamespace(id_dispositivo_iot=equipo['device'],es_activo=True)]
    cal.guardar.side_effect=lambda c:c
    uc=CalibrarVisionUseCase(Mock(),infra,camaras,adapter,cal,lb,eventos)
    dto=CalibrarVisionDTO(modo_calibracion='VISION',area_id=equipo['area'],ventana_observacion={'inicio':inicio,'fin':fin})
    resultado=uc.execute(dto,SimpleNamespace(id_usuario=7))
    assert resultado.estado.value=='EXITOSA'
    assert set(resultado.linea_base['valores'])=={'densidad_actividad','dispersion_espacial','tasa_movimiento'}
    lb.publicar.assert_called_once()
