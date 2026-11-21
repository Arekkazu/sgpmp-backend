# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M06-273-G67-01 RF-82: verificar migración y reconocimiento por costo mediante HTTP con restricciones activas. |
# | 2026-11-10 | Arekkazu | Lote M05/M06 RF-82: la donación se asienta con RECONOCIMIENTO_DONACION (#1036) |
"""Diagnóstico local de #957; no realiza operaciones en bases compartidas."""
from __future__ import annotations
import importlib
import pkgutil
import uuid
from decimal import Decimal as D
import pytest
from sqlalchemy import text

pytestmark=pytest.mark.integration

@pytest.fixture(autouse=True)
def montar(integration_app):
    for paquete in ('src.configuration.infrastructure.models','src.biological_assets.infrastructure.models'):
        modulo=importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__,paquete+'.'):
            importlib.import_module(item.name)
    from src.financial_valuation.infrastructure.routers.m06_router import router
    if not any(getattr(r,'path',None)=='/finanzas/reconocimientos/{id_activo_biologico}' for r in integration_app.routes):
        integration_app.include_router(router)
        integration_app.openapi_schema=None

def nombre(prefijo):
    return prefijo+' '+''.join(chr(97+int(c,16)) for c in uuid.uuid4().hex[:12])


def sembrar_activo(db,usuario,tipo='INDIVIDUAL',origen='compra'):
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"),{'u':str(usuario)})
    especie=db.execute(text("INSERT INTO modulo9.especies(nombre,es_activo,fecha_creacion,grupo_manejo,densidad_maxima_por_especie) VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"),{'n':nombre('Especie Suministros')}).scalar_one()
    finca=db.execute(text("INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo) VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"),{'n':nombre('Finca Suministros')}).scalar_one()
    area=db.execute(text("INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo) VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"),{'n':nombre('Corral Suministros'),'f':finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'),{'a':area,'e':especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'),{'u':usuario,'f':finca})
    activo=db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,identificador,fecha_inicio_ciclo,
        id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,id_usuario,fecha_creacion,
        soporte_documental,detalles_procedencia) VALUES(:e,:a,:t,:ident,current_date-30,1,'Fixture de suministros',:origen,100,'{}',:u,now()-interval '31 days','doc','') RETURNING id_activo_biologico"""),{'e':especie,'a':area,'t':tipo,'u':usuario,'origen':origen,'ident':uuid.uuid4().hex[:20] if tipo=='INDIVIDUAL' else None}).scalar_one()
    if tipo=='POBLACIONAL':
        db.execute(text('INSERT INTO modulo2.detalles_activos_biologicos_poblacionales(id_activo_biologico,cantidad_inicial,cantidad_actual,peso_promedio_inicial,densidad) VALUES(:a,10,10,.1,.1)'),{'a':activo})
    else:
        db.execute(text("INSERT INTO modulo2.detalles_activos_individuales(id_activo_biologico,raza,sexo,fecha_nacimeinto,peso_inicial,fecha_creacion,id_usuario) VALUES(:a,'Criolla','Macho',current_date-100,1,now(),:u)"),{'a':activo,'u':usuario})
    db.execute(text("UPDATE modulo9.fincas SET tipo_id_tributaria='NIT',numero_id_tributaria='900123456',dv='8',razon_social='Pruebas Contables SAS' WHERE id_finca=:f"),{'f':finca})
    return dict(activo=activo,finca=finca,especie=especie)

@pytest.fixture
def escenario(request,db_session,crear_usuario_db,crear_auth_headers,client):
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    contador=crear_usuario_db(id_rol=5)
    vet=crear_usuario_db(id_rol=3)
    e=sembrar_activo(db_session,contador['id_usuario'],origen=getattr(request,'param','compra'))
    e['uid']=contador['id_usuario']
    e['headers']=crear_auth_headers(contador)|{'X-Zona-Horaria':'America/Bogota'}
    e['vet']=crear_auth_headers(vet)
    r=client.put('/finanzas/configuracion/especies/'+str(e['especie']),headers=e['headers'],json={'clasificacion':'CONSUMO','categoria_precio':'POR_CABEZA','vida_util_meses':24})
    assert r.status_code==200,r.text
    return e

def post(client,e):
    return client.post('/finanzas/reconocimientos/'+str(e['activo']),headers=e['headers'],json={})

def cuenta(db,tabla):
    return db.execute(text('SELECT count(*) FROM modulo6.'+tabla)).scalar_one()

def test_migracion_crea_las_cinco_estructuras(db_session):
    for t in ('configuraciones_contables','parametros_contables_especies','asignaciones_cuentas_contables','comprobantes_nic41','lineas_asiento_nic41'):
        assert db_session.execute(text('SELECT to_regclass(:t)'),{'t':'modulo6.'+t}).scalar_one() is not None,t
        assert db_session.execute(text("SELECT has_table_privilege('sgpmp_app',:t,'SELECT')"),{'t':'modulo6.'+t}).scalar_one(),t
    assert cuenta(db_session,'configuraciones_contables')==1
    assert db_session.execute(text("SELECT has_schema_privilege('sgpmp_app','modulo6','USAGE')")).scalar_one()

def test_compra_por_costo_crea_reconocimiento_valoracion_y_auditoria(client,db_session,escenario):
    e=escenario
    r=post(client,e)
    assert r.status_code==201,r.text
    b=r.json()
    assert b['indicador_valoracion']=='VALORACION_POR_COSTO' and D(str(b['valor_inicial']))==D('100')
    assert b['lineas']==[] # RFC-018: compra por factura; diferencia de valoración cero.
    assert cuenta(db_session,'reconocimientos_iniciales')==1
    v=db_session.execute(text('SELECT escenario_activacion,valor_contable_por_costo FROM modulo6.valoraciones_por_costos WHERE id_activo_biologico=:a'),{'a':e['activo']}).one()
    assert v[0]=='INICIAL_RF82' and v[1]==D('100')
    assert cuenta(db_session,'auditorias_financieras')>=1
    assert cuenta(db_session,'periodos_contables')==1

@pytest.mark.parametrize('escenario',['donacion'],indirect=True)
def test_costo_con_hecho_contable_resuelve_matriz_y_persiste_linea(client,db_session,escenario):
    e=escenario
    r=client.post('/finanzas/configuracion/matriz',headers=e['headers'],json={'tipo_hecho':'RECONOCIMIENTO_DONACION','sentido':'UNICO','id_especie':e['especie'],'cuenta_debito':'1586','cuenta_credito':'4251'})
    assert r.status_code==201,r.text
    r=post(client,e)
    assert r.status_code==201,r.text
    ln,=r.json()['lineas']
    assert (ln['cuenta_debito'],ln['cuenta_credito'],ln['estado'])==('1586','4251','REGISTRADA')
    assert D(str(ln['valor']))==D('100')
    assert cuenta(db_session,'lineas_asiento_nic41')==1

def test_segunda_confirmacion_no_duplica(client,db_session,escenario):
    e=escenario
    assert post(client,e).status_code==201
    r=post(client,e)
    assert r.status_code==409 and r.json()['error_code']=='RECONOCIMIENTO_EXISTENTE',r.text
    assert cuenta(db_session,'reconocimientos_iniciales')==1 and cuenta(db_session,'valoraciones_por_costos')==1

def test_jwt_y_rol_se_conservan(client,db_session,escenario):
    e=escenario
    path='/finanzas/reconocimientos/'+str(e['activo'])
    assert client.post(path,json={}).status_code==401
    r=client.post(path,headers=e['vet'],json={})
    assert r.status_code==403,r.text
    assert cuenta(db_session,'reconocimientos_iniciales')==0

def test_fallo_tardio_revierte_reconocimiento_y_valoracion(client,db_session,escenario,monkeypatch):
    from src.financial_valuation.application.services.contabilizador import Contabilizador
    from src.shared.errors import ServiceUnavailableError
    e=escenario
    db_session.commit()
    original=Contabilizador.auditar
    def fallar(self,evento):
        original(self,evento)
        if evento.tipo_evento=='RECONOCIMIENTO_INICIAL':
            raise ServiceUnavailableError('SERVICIO_NO_DISPONIBLE','Fallo controlado local de auditoría')
    monkeypatch.setattr(Contabilizador,'auditar',fallar)
    r=post(client,e)
    assert r.status_code==503,r.text
    for tabla in ('reconocimientos_iniciales','valoraciones_por_costos','periodos_contables','lineas_asiento_nic41'):
        assert cuenta(db_session,tabla)==0,tabla


def test_migracion_recupera_acl_e_idempotencia(client,db_session,escenario,integration_engine,caplog):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    assert integration_engine.url.host in ('127.0.0.1','localhost','::1')
    assert integration_engine.url.database=='sgpmp_inc957_test'
    e=escenario
    db_session.execute(text('REVOKE USAGE ON SCHEMA modulo6 FROM sgpmp_app'))
    db_session.execute(text('REVOKE SELECT,INSERT ON modulo6.reconocimientos_iniciales FROM sgpmp_app'))
    assert not db_session.execute(text("SELECT has_schema_privilege('sgpmp_app','modulo6','USAGE')")).scalar_one()
    db_session.commit()
    fallo=post(client,e)
    assert fallo.status_code==500 and fallo.json()['error_code']=='ERROR_INTERNO',fallo.text
    assert 'permission denied for schema modulo6' in caplog.text
    revision=ScriptDirectory.from_config(Config('alembic.ini')).get_revision('e957a82c1107').module
    with Operations.context(MigrationContext.configure(db_session.connection())):
        revision.upgrade()
        revision.upgrade() # Repetir los GRANT conserva datos y permisos existentes.
        revision.downgrade() # Downgrade conservador, sin revocar ACL previas del ambiente.
    db_session.commit()
    correcto=post(client,e)
    assert correcto.status_code==201,correcto.text
    assert cuenta(db_session,'reconocimientos_iniciales')==1
    assert not db_session.execute(text("SELECT has_schema_privilege('sgpmp_app','modulo6','CREATE')")).scalar_one()
    assert not db_session.execute(text("SELECT has_table_privilege('sgpmp_app','modulo6.reconocimientos_iniciales','DELETE')")).scalar_one()


def test_valor_razonable_con_mercado_conserva_el_otro_camino(client,db_session,escenario):
    from datetime import timedelta
    from src.shared.fechas import hoy_usuario
    from src.financial_valuation.infrastructure.factories.m06_factory import M06
    from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import SolicitudPrecio
    e=escenario
    # Preparación autorizada con conexión administradora local; el reconocimiento usa sgpmp_app.
    m=M06(db_session)
    from types import SimpleNamespace
    m.__dict__["notificador"]=SimpleNamespace(a_contadores=lambda *args,**kwargs:None)
    m.guardar_costos_venta().execute(e['especie'],D('.05'),D('0'),D('0'),e['uid'])
    m.registrar_precio().execute(SolicitudPrecio(id_especie=e['especie'],categoria='POR_CABEZA',precio_unitario=D('150'),fecha_vigencia=hoy_usuario()-timedelta(days=60),fuente='MERCADO_ACTIVO',evidencia_documental='Boletin local para prueba',confirmar_desviacion=True),e['uid'])
    r=client.post('/finanzas/configuracion/matriz',headers=e['headers'],json={'tipo_hecho':'RECONOCIMIENTO_DIFERENCIA','sentido':'GANANCIA','id_especie':e['especie'],'cuenta_debito':'1586','cuenta_credito':'4250'})
    assert r.status_code==201,r.text
    r=post(client,e)
    assert r.status_code==201,r.text
    b=r.json()
    assert b['indicador_valoracion']=='VALOR_RAZONABLE' and D(str(b['valor_inicial']))==D('142.5')
    ln,=b['lineas']
    assert D(str(ln['valor']))==D('42.5') and ln['estado']=='REGISTRADA'
    assert cuenta(db_session,'calculos_valor_razonable')==1 and cuenta(db_session,'valoraciones_por_costos')==0


def test_contador_sin_finca_no_puede_reconocer(client,db_session,escenario,crear_usuario_db,crear_auth_headers):
    e=escenario
    ajeno=crear_usuario_db(id_rol=5)
    r=client.post('/finanzas/reconocimientos/'+str(e['activo']),headers=crear_auth_headers(ajeno),json={})
    assert r.status_code==404,r.text
    assert cuenta(db_session,'reconocimientos_iniciales')==0
