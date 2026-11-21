# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M05-272-G25 RF-77: validar auditoria visible, transacciones y roles con PostgreSQL y HTTP reales. |
# | 2026-11-10 | Arekkazu | Lote M05/M06 RLS modulo5: el archivo de otro usuario responde 404 bajo RLS (403 sin ella) |
"""Regresión #958 en una base exclusiva con restricciones y triggers activos."""
from __future__ import annotations
import importlib
import pkgutil
import uuid
from dataclasses import replace
from decimal import Decimal as D
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark=pytest.mark.integration


@pytest.fixture(autouse=True)
def montar(integration_app,monkeypatch):
    for paquete in ('src.configuration.infrastructure.models','src.biological_assets.infrastructure.models','src.supplies.infrastructure.models'):
        modulo=importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__,paquete+'.'):
            importlib.import_module(item.name)
    from src.supplies.infrastructure.routers.reporte_gastos_router import router as reportes
    from src.supplies.infrastructure.routers.auditoria_suministros_router import router as auditoria
    from src.supplies.infrastructure.routers.medicamento_router import router as medicamentos
    for router,path in ((reportes,'/suministros/reportes-gastos'),(auditoria,'/suministros/auditoria'),(medicamentos,'/suministros/medicamentos')):
        if not any(getattr(r,'path',None)==path for r in integration_app.routes):
            integration_app.include_router(router)
            integration_app.openapi_schema=None
    monkeypatch.setattr('src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter.send_email',lambda **_:None)


def nombre(prefijo):
    return prefijo+' '+''.join(chr(97+int(c,16)) for c in uuid.uuid4().hex[:12])


def sembrar_activo(db,usuario,tipo='INDIVIDUAL'):
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"),{'u':str(usuario)})
    especie=db.execute(text("INSERT INTO modulo9.especies(nombre,es_activo,fecha_creacion,grupo_manejo,densidad_maxima_por_especie) VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"),{'n':nombre('Especie Suministros')}).scalar_one()
    finca=db.execute(text("INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo) VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"),{'n':nombre('Finca Suministros')}).scalar_one()
    area=db.execute(text("INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo) VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"),{'n':nombre('Corral Suministros'),'f':finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'),{'a':area,'e':especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'),{'u':usuario,'f':finca})
    activo=db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,identificador,fecha_inicio_ciclo,
        id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,id_usuario,fecha_creacion,
        soporte_documental,detalles_procedencia) VALUES(:e,:a,:t,:ident,current_date-30,1,'Fixture de suministros','compra',100,'{}',:u,now()-interval '31 days','doc','') RETURNING id_activo_biologico"""),{'e':especie,'a':area,'t':tipo,'u':usuario,'ident':uuid.uuid4().hex[:20] if tipo=='INDIVIDUAL' else None}).scalar_one()
    if tipo=='POBLACIONAL':
        db.execute(text('INSERT INTO modulo2.detalles_activos_biologicos_poblacionales(id_activo_biologico,cantidad_inicial,cantidad_actual,peso_promedio_inicial,densidad) VALUES(:a,10,10,.1,.1)'),{'a':activo})
    else:
        db.execute(text("INSERT INTO modulo2.detalles_activos_individuales(id_activo_biologico,raza,sexo,fecha_nacimeinto,peso_inicial,fecha_creacion,id_usuario) VALUES(:a,'Criolla','Macho',current_date-100,1,now(),:u)"),{'a':activo,'u':usuario})
    biologico=db.execute(text('INSERT INTO modulo9.ciclos_biologicos(nombre,duracion_dias,id_especie) VALUES(:n,365,:e) RETURNING id_ciclo_biologico'),{'n':nombre('Ciclo Biologico'),'e':especie}).scalar_one()
    productivo=db.execute(text('INSERT INTO modulo9.ciclos_productivos(nombre,duracion_dias,id_ciclo_biologico) VALUES(:n,60,:b) RETURNING id_ciclo_productivo'),{'n':nombre('Fase Productiva'),'b':biologico}).scalar_one()
    puente=db.execute(text('INSERT INTO modulo9.ciclos_productivos_biologicos(id_ciclo_productivo,id_ciclo_biologico) VALUES(:p,:b) RETURNING id_ciclos_productivo_biologico'),{'p':productivo,'b':biologico}).scalar_one()
    fase=db.execute(text("INSERT INTO modulo2.gestiones_fases(id_activo_biologico,id_ciclo_productiva,fecha_inicio,es_activa,id_usuario,id_ciclos_productivo_biologico) VALUES(:a,:p,now()-interval '30 days',true,:u,:b) RETURNING id_gestion_fases"),{'a':activo,'p':productivo,'u':usuario,'b':puente}).scalar_one()
    return dict(activo=activo,fase=fase,finca=finca,area=area,especie=especie)


@pytest.fixture
def escenario(db_session,crear_usuario_db,crear_auth_headers,client):
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    productor=crear_usuario_db(id_rol=2)
    admin=crear_usuario_db(id_rol=1)
    vet=crear_usuario_db(id_rol=3)
    e=sembrar_activo(db_session,productor['id_usuario'])
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'),{'u':vet['id_usuario'],'f':e['finca']})
    e['hoy']=db_session.execute(text("SELECT (now() AT TIME ZONE 'America/Bogota')::date")).scalar_one()
    for nombre_actor,actor in (('productor',productor),('admin',admin),('vet',vet)):
        e[nombre_actor]=crear_auth_headers(actor)|{'X-Zona-Horaria':'America/Bogota'}
        e[nombre_actor+'_id']=actor['id_usuario']
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=dict(id_activo_biologico=e['activo'],nombre_medicamento='Oxitetraciclina',fecha_aplicacion=e['hoy'].isoformat(),hora_aplicacion='08:00',via_administracion='INTRAMUSCULAR',dosis_aplicada='10',unidad_dosis='ml',costo_unitario='500',periodo_retiro_dias=0,motivo_aplicacion='Tratamiento de infeccion respiratoria',nombre_veterinario='Dr. Perez'))
    assert r.status_code==201,r.text
    return e


def cuerpo(e):
    return dict(activo_biologico_id=e['activo'],fecha_inicio_reporte=(e['hoy']-timedelta(days=1)).isoformat(),fecha_fin_reporte=e['hoy'].isoformat())


def generar(client,e,actor='productor',**extra):
    r=client.post('/suministros/reportes-gastos',headers=e[actor],json=cuerpo(e)|extra)
    assert r.status_code==200,r.text
    return r.json()


def eventos(client,e,entidad,actor='productor'):
    r=client.get('/suministros/auditoria',headers=e['admin'],params={'entidad_afectada':entidad,'id_usuario':e[actor+'_id']})
    assert r.status_code==200,r.text
    return r.json()['items']


def contar(db,tabla):
    return db.execute(text('SELECT count(*) FROM modulo5.'+tabla)).scalar_one()


@pytest.mark.parametrize('actor',['productor','admin'])
@pytest.mark.parametrize('formato',['CSV','PDF'])
def test_generacion_exportacion_y_descarga_quedan_auditadas(client,db_session,escenario,actor,formato):
    e=escenario
    antes=datetime.now(timezone.utc)
    reporte=generar(client,e,actor)
    rid=reporte['id_reporte_gasto_acumulado']
    r=client.post('/suministros/reportes-gastos/'+str(rid)+'/exportacion',headers=e[actor],json={'formato_exportacion':formato})
    assert r.status_code==201,r.text
    archivo=r.json()
    ev_gen,=eventos(client,e,'reporte_gastos_acumulados',actor)
    ev_exp,=eventos(client,e,'archivos_exportacion_suministros',actor)
    for ev in (ev_gen,ev_exp):
        assert ev['id_usuario']==e[actor+'_id'] and ev['resultado']=='EXITOSO'
        assert ev['fecha_evento'] and len(ev['hash_integridad'])==64
        assert ev['clasificacion_registro']=='NIC41' and ev['retencion_aplicable']=='5 años'
        assert datetime.fromisoformat(ev['fecha_emision'].replace('Z','+00:00'))>=antes
        assert ev['datos_nuevos']['id_reporte_gasto_acumulado']==rid
    assert ev_gen['datos_nuevos']['accion']=='GENERACION'
    assert D(ev_gen['datos_nuevos']['gasto_total_acumulado'])==D('5000')
    assert ev_exp['datos_nuevos']['formato']==formato
    aid=ev_exp['datos_nuevos']['id_archivo']
    descarga=client.get('/suministros/reportes-gastos/exportaciones/'+aid,headers=e[actor])
    assert descarga.status_code==200,descarga.text
    assert descarga.content.startswith(b'%PDF') if formato=='PDF' else b'monto_cop' in descarga.content
    assert len(eventos(client,e,'archivos_exportacion_suministros',actor))==1
    assert contar(db_session,'reporte_gastos_acumulados')==1 and contar(db_session,'archivos_exportacion_suministros')==1


@pytest.mark.parametrize('formato',['CSV','PDF'])
def test_exportacion_incluida_en_generacion_no_duplica_eventos(client,db_session,escenario,formato):
    e=escenario
    r=generar(client,e,formato_exportacion=formato)
    assert r['archivo']
    assert len(eventos(client,e,'reporte_gastos_acumulados'))==1
    assert len(eventos(client,e,'archivos_exportacion_suministros'))==1
    assert contar(db_session,'reporte_gastos_acumulados')==1


def test_regeneracion_audita_sin_modificar_el_reporte_original(client,db_session,escenario):
    e=escenario
    rid=generar(client,e)['id_reporte_gasto_acumulado']
    original=db_session.execute(text('SELECT row_to_json(r) FROM modulo5.reporte_gastos_acumulados r WHERE id_reporte_gasto_acumulado=:r'),{'r':rid}).scalar_one()
    r=client.get('/suministros/reportes-gastos/'+str(rid)+'/regenerar',headers=e['productor'])
    assert r.status_code==200 and r.json()['advertencia'],r.text
    ev=eventos(client,e,'reporte_gastos_acumulados')
    assert sorted(x['datos_nuevos']['accion'] for x in ev)==['GENERACION','REGENERACION']
    assert next(x for x in ev if x['tipo_operacion']=='SELECT')['datos_nuevos']['id_reporte_gasto_acumulado']==rid
    assert contar(db_session,'reporte_gastos_acumulados')==1
    actual=db_session.execute(text('SELECT row_to_json(r) FROM modulo5.reporte_gastos_acumulados r WHERE id_reporte_gasto_acumulado=:r'),{'r':rid}).scalar_one()
    assert actual==original
    assert client.get('/suministros/reportes-gastos/'+str(rid),headers=e['productor']).status_code==200
    assert len(eventos(client,e,'reporte_gastos_acumulados'))==2


@pytest.mark.parametrize('fase',['generacion','exportacion','regeneracion'])
def test_fallo_de_auditoria_revierte_la_accion(client,db_session,escenario,monkeypatch,fase):
    from src.supplies.infrastructure.repositories.auditoria_suministro_repository import SqlAlchemyAuditoriaSuministroRepository as Repo
    from src.shared.errors import ServiceUnavailableError
    e=escenario
    rid=None if fase=='generacion' else generar(client,e)['id_reporte_gasto_acumulado']
    db_session.commit()
    accion={'generacion':'GENERACION','exportacion':'EXPORTACION','regeneracion':'REGENERACION'}[fase]
    original=Repo.registrar
    def fallar(self,evento):
        original(self,evento)
        if evento.datos_nuevos and evento.datos_nuevos.get('accion')==accion:
            raise ServiceUnavailableError('SERVICIO_NO_DISPONIBLE','Fallo local controlado después de insertar auditoría.')
    monkeypatch.setattr(Repo,'registrar',fallar)
    if fase=='generacion':
        r=client.post('/suministros/reportes-gastos',headers=e['productor'],json=cuerpo(e))
    elif fase=='exportacion':
        r=client.post('/suministros/reportes-gastos/'+str(rid)+'/exportacion',headers=e['productor'],json={'formato_exportacion':'CSV'})
    else:
        r=client.get('/suministros/reportes-gastos/'+str(rid)+'/regenerar',headers=e['productor'])
    assert r.status_code==503,r.text
    assert contar(db_session,'reporte_gastos_acumulados')==(0 if fase=='generacion' else 1)
    assert contar(db_session,'archivos_exportacion_suministros')==0
    assert len(eventos(client,e,'reporte_gastos_acumulados'))==(0 if fase=='generacion' else 1)
    assert eventos(client,e,'archivos_exportacion_suministros')==[]
    assert contar(db_session,'registros_medicamentos')==1


def test_fallo_pdf_conserva_reporte_y_evento_fallido(client,db_session,escenario,monkeypatch):
    e=escenario
    rid=generar(client,e)['id_reporte_gasto_acumulado']
    def fallo(*args,**kwargs):
        raise RuntimeError('Fallo local controlado del motor PDF')
    monkeypatch.setattr('src.supplies.application.use_cases.reporte_gastos.exportar_reporte_gastos_use_case.generar_pdf',fallo)
    r=client.post('/suministros/reportes-gastos/'+str(rid)+'/exportacion',headers=e['productor'],json={'formato_exportacion':'PDF'})
    assert r.status_code==500 and r.json()['error_code']=='ERROR_GENERACION_PDF',r.text
    fallo_ev,=eventos(client,e,'exportacion_reporte_gastos')
    assert fallo_ev['resultado']=='FALLIDO' and fallo_ev['tipo_operacion']=='REGISTRO_FALLIDO'
    assert eventos(client,e,'archivos_exportacion_suministros')==[]
    assert contar(db_session,'archivos_exportacion_suministros')==0
    assert client.get('/suministros/reportes-gastos/'+str(rid),headers=e['productor']).status_code==200


def test_rbac_historial_y_archivos_privados(client,db_session,escenario,crear_usuario_db,crear_auth_headers):
    e=escenario
    propio=generar(client,e)
    ajeno=generar(client,e,'admin',formato_exportacion='CSV')
    hist=client.get('/suministros/reportes-gastos/historial',headers=e['productor'])
    assert hist.status_code==200,hist.text
    assert [x['id_reporte_gasto_acumulado'] for x in hist.json()['items']]==[propio['id_reporte_gasto_acumulado']]
    archivo_admin,=eventos(client,e,'archivos_exportacion_suministros','admin')
    r=client.get('/suministros/reportes-gastos/exportaciones/'+archivo_admin['datos_nuevos']['id_archivo'],headers=e['productor'])
    # Sin RLS el caso de uso responde 403 (archivo de otro usuario); con la RLS de modulo5 la fila ajena no es
    # visible para el rol de la API y responde como inexistente, sin revelar que existe.
    assert (r.status_code,r.json()['error_code']) in ((403,'ARCHIVO_DE_OTRO_USUARIO'),(404,'ARCHIVO_NO_ENCONTRADO')),r.text
    assert client.get('/suministros/auditoria',headers=e['productor']).status_code==403
    antes=len(eventos(client,e,'reporte_gastos_acumulados'))
    assert client.post('/suministros/reportes-gastos',json=cuerpo(e)).status_code==401
    contador=crear_usuario_db(id_rol=5)
    assert client.post('/suministros/reportes-gastos',headers=crear_auth_headers(contador),json=cuerpo(e)).status_code==403
    assert len(eventos(client,e,'reporte_gastos_acumulados'))==antes


def test_actor_sin_finca_no_genera_reporte_ni_auditoria(client,db_session,escenario,crear_usuario_db,crear_auth_headers):
    e=escenario
    ajeno=crear_usuario_db(id_rol=2)
    r=client.post('/suministros/reportes-gastos',headers=crear_auth_headers(ajeno),json=cuerpo(e))
    assert r.status_code in (403,404),r.text
    assert contar(db_session,'reporte_gastos_acumulados')==0
    assert eventos(client,e,'reporte_gastos_acumulados')==[]


def test_rollback_exterior_revierte_reportes_archivos_y_auditoria(client,db_session,escenario):
    e=escenario
    db_session.commit()
    exterior=db_session.get_bind().begin_nested()
    generar(client,e,formato_exportacion='CSV')
    assert contar(db_session,'archivos_exportacion_suministros')==1
    db_session.close()
    exterior.rollback()
    assert contar(db_session,'reporte_gastos_acumulados')==0
    assert contar(db_session,'archivos_exportacion_suministros')==0
    assert db_session.execute(text("SELECT count(*) FROM modulo5.auditorias_suministros WHERE entidad_afectada IN ('reporte_gastos_acumulados','archivos_exportacion_suministros')")).scalar_one()==0
    assert contar(db_session,'registros_medicamentos')==1


def test_cola_audita_cuando_se_completa_con_identidad_de_servicio(client,db_session,escenario,monkeypatch):
    from sqlalchemy import event
    from src.shared import database
    from src.supplies.infrastructure.factories.reporte_gastos_factory import build_procesar_cola_reportes_gastos_use_case
    e=escenario
    payload=dict(id_infraestructura=e['area'],fecha_inicio_reporte=(e['hoy']-timedelta(days=184)).isoformat(),fecha_fin_reporte=e['hoy'].isoformat(),formato_exportacion='CSV')
    r=client.post('/suministros/reportes-gastos',headers=e['productor'],json=payload)
    assert r.status_code==202,r.text
    assert contar(db_session,'reporte_gastos_acumulados')==0
    assert eventos(client,e,'reporte_gastos_acumulados')==[]
    qid=db_session.execute(text('SELECT id_cola FROM modulo5.cola_generacion_reportes_gastos')).scalar_one()
    db_session.commit()
    conexion=db_session.get_bind()
    def session_local():
        sesion=Session(bind=conexion,expire_on_commit=False,join_transaction_mode='create_savepoint')
        @event.listens_for(sesion,'after_begin')
        def rol(session,transaction,conn):
            conn.exec_driver_sql('SET LOCAL ROLE sgpmp_app')
        return sesion
    # Mantiene declarar_identidad_sistema de producción y ejecuta el worker secuencialmente
    # dentro de la transacción exterior de pruebas; no demuestra concurrencia de procesos.
    monkeypatch.setattr(database,'SessionLocal',session_local)
    monkeypatch.setattr('src.supplies.infrastructure.adapters.notificacion_suministros_m01_adapter.NotificacionSuministrosM01Adapter.a_usuarios',lambda *args,**kwargs:None)
    worker=build_procesar_cola_reportes_gastos_use_case(db_session)
    config=replace(worker.config_repo.obtener(),max_reintentos=1,backoff_minutos=[0])
    worker._procesar(qid,config)
    conexion.exec_driver_sql('RESET ROLE')
    estado=db_session.execute(text('SELECT estado::text FROM modulo5.cola_generacion_reportes_gastos WHERE id_cola=:q'),{'q':qid}).scalar_one()
    assert estado=='COMPLETADO',estado
    gen,=eventos(client,e,'reporte_gastos_acumulados')
    exp,=eventos(client,e,'archivos_exportacion_suministros')
    assert gen['id_usuario']==e['productor_id'] and exp['id_usuario']==e['productor_id']
    assert gen['datos_nuevos']['id_reporte_gasto_acumulado']==exp['datos_nuevos']['id_reporte_gasto_acumulado']
