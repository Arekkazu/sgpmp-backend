# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M05-270-G14 RF-76: verificar dosis decimal(10,4) desde HTTP hasta el ledger en PostgreSQL. |
"""Regresión #954 con restricciones activas y transacciones de prueba."""
from __future__ import annotations
import importlib
import pkgutil
import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def montar(integration_app,monkeypatch):
    for paquete in ('src.configuration.infrastructure.models','src.biological_assets.infrastructure.models',
                    'src.supplies.infrastructure.models'):
        modulo=importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__,paquete+'.'):
            importlib.import_module(item.name)
    from src.supplies.infrastructure.routers.medicamento_router import router as medicamento
    from src.supplies.infrastructure.routers.consumo_alimento_router import router as consumo
    for router,path in ((medicamento,'/suministros/medicamentos'),(consumo,'/suministros/consumo-alimentos')):
        if not any(getattr(r,'path',None)==path and 'POST' in getattr(r,'methods',set()) for r in integration_app.routes):
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
    return dict(activo=activo,fase=fase,finca=finca)


@pytest.fixture
def escenario(db_session,crear_usuario_db,crear_auth_headers,montar):
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO'),(3,'EN_TRATAMIENTO') ON CONFLICT DO NOTHING"))
    vet=crear_usuario_db(id_rol=3)
    ajeno=crear_usuario_db(id_rol=3)
    productor=crear_usuario_db(id_rol=2)
    individual=sembrar_activo(db_session,vet['id_usuario'])
    poblacional=sembrar_activo(db_session,vet['id_usuario'],'POBLACIONAL')
    alimento=db_session.execute(text("INSERT INTO modulo5.tipos_alimentos(nombre,costo_unitario,unidad_medida,estado) VALUES(:n,1000,'kg','ACTIVO') RETURNING id_tipo_elemento"),{'n':nombre('Concentrado')}).scalar_one()
    hoy=db_session.execute(text("SELECT (transaction_timestamp() AT TIME ZONE 'America/Bogota')::date")).scalar_one()
    return dict(individual=individual,poblacional=poblacional,alimento=alimento,hoy=hoy,vet_id=vet['id_usuario'],
                vet=crear_auth_headers(vet)|{'X-Zona-Horaria':'America/Bogota'},
                ajeno=crear_auth_headers(ajeno),productor=crear_auth_headers(productor))


def medicamento(e,clase='individual',retiro=7):
    return dict(id_activo_biologico=e[clase]['activo'],nombre_medicamento='Oxitetraciclina',
        fecha_aplicacion=e['hoy'].isoformat(),hora_aplicacion='08:00',via_administracion='INTRAMUSCULAR',
        dosis_aplicada='10',unidad_dosis='ml',costo_unitario='500',periodo_retiro_dias=retiro,
        motivo_aplicacion='Tratamiento de infeccion respiratoria',nombre_veterinario='Dr. Perez')




@pytest.mark.parametrize('dosis',['0.0001','0.0004','0.0005','0.0015','0.001','10'])
def test_dosis_conserva_cuatro_decimales_en_todo_el_flujo(client,db_session,escenario,dosis):
    e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':dosis})
    assert r.status_code==201,r.text
    cantidad=D(dosis)
    costo=cantidad*D('500')
    assert r.json()['medicamento']['estado_registro']=='VALIDADO'
    assert D(r.json()['medicamento']['cantidad'])==cantidad
    assert D(r.json()['medicamento']['costo_total_medicamento'])==costo
    guardado=db_session.execute(text('SELECT cantidad,costo_total_medicamento FROM modulo5.registros_medicamentos WHERE id_activo_biologico=:a'),{'a':e['individual']['activo']}).one()
    ledger=db_session.execute(text('SELECT cantidad,costo_registro FROM modulo5.registro_suministro WHERE id_activo_biologico=:a'),{'a':e['individual']['activo']}).one()
    assert tuple(guardado)==tuple(ledger)==(cantidad,costo)
    assert db_session.execute(text('SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f'),{'f':e['individual']['fase']}).scalar_one()==costo


@pytest.mark.parametrize('dosis',['0.00001','0.00049','0.00151','1.23456','1000000'])
def test_precision_no_representable_rechaza_sin_escribir_y_permite_la_siguiente(client,db_session,escenario,dosis):
    e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':dosis})
    assert r.status_code==400 and r.json()['error_code']=='VAL_ENTRADA',r.text
    for tabla in ('registros_medicamentos','registro_suministro','acumulado_ciclo','auditorias_suministros','outbox_provisiones_m06'):
        assert db_session.execute(text('SELECT count(*) FROM modulo5.'+tabla)).scalar_one()==0,tabla
    siguiente=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':'0.0001'})
    assert siguiente.status_code==201,siguiente.text
    assert D(siguiente.json()['medicamento']['cantidad'])==D('.0001')


@pytest.mark.parametrize('dosis',['0.00010','1.23450','1e-4','999999.9999'])
def test_ceros_finales_exponente_y_maximo_no_alteran_valor(client,escenario,dosis):
    e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':dosis,'costo_unitario':'1'})
    assert r.status_code==201,r.text
    assert D(r.json()['medicamento']['cantidad'])==D(dosis)
    assert D(r.json()['medicamento']['costo_total_medicamento'])==D(dosis)


def test_vista_auditoria_outbox_y_get_conservan_dosis_y_costo(client,db_session,escenario):
    e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':'.0001'})
    assert r.status_code==201,r.text
    a=e['individual']['activo']
    vista=db_session.execute(text('SELECT cantidad_dosis,costo_total_medicamento FROM modulo5.vw_m05_aplicacion_medicamentos WHERE id_activo_biologico=:a'),{'a':a}).one()
    assert tuple(vista)==(D('.0001'),D('.05'))
    audit=db_session.execute(text("SELECT datos_nuevos,hash_integridad FROM modulo5.auditorias_suministros WHERE entidad_afectada='registros_medicamentos'")).one()
    assert D(str(audit[0]['cantidad']))==D('.0001') and len(audit[1])==64
    costo=db_session.execute(text("SELECT costo_afectado FROM modulo5.auditorias_suministros WHERE tipo_operacion='ACUMULADO_ACTUALIZADO' AND id_activo_biologico=:a"),{'a':a}).scalar_one()
    assert costo==D('.05')
    outbox=db_session.execute(text('SELECT costo_registro,json_contenido FROM modulo5.outbox_provisiones_m06 WHERE id_activo_biologico=:a'),{'a':a}).one()
    assert outbox[0]==D('.05')
    assert D(outbox[1]['costo_registro'])==D(outbox[1]['acumulado_total_ciclo'])==D('.05')
    consulta=client.get('/suministros/medicamentos',headers=e['vet'],params={'id_activo_biologico':a})
    assert consulta.status_code==200,consulta.text
    assert D(consulta.json()['items'][0]['cantidad'])==D('.0001')


def test_poblacional_y_retiro_usan_dosis_total_sin_truncar(client,db_session,escenario):
    e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,'poblacional',7)|{'dosis_aplicada':'.0015'})
    assert r.status_code==201,r.text
    m=r.json()['medicamento']
    assert D(m['cantidad'])==D('.0015') and D(m['dosis_por_individuo'])==D('.0002')
    assert D(m['costo_total_medicamento'])==D('.75')
    assert m['fecha_fin_retiro']==(e['hoy']+timedelta(days=7)).isoformat()
    assert db_session.execute(text('SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico=:a'),{'a':e['poblacional']['activo']}).scalar_one()==3


def test_acumulacion_de_varias_dosis_no_pierde_decimales(client,db_session,escenario):
    e=escenario
    dosis=['.0001','.0004','.0005','.0015','.001','10']
    for n,d in enumerate(dosis):
        r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':d,'hora_aplicacion':f'09:{n:02d}'})
        assert r.status_code==201,r.text
    total=sum(D(x) for x in dosis)*500
    assert db_session.execute(text('SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f'),{'f':e['individual']['fase']}).scalar_one()==total
    assert db_session.execute(text('SELECT sum(costo_registro) FROM modulo5.registro_suministro')).scalar_one()==total


@pytest.mark.parametrize('actor,estado',[('ajeno',404),('productor',403)])
def test_precision_no_elude_rbac_ni_finca(client,db_session,escenario,actor,estado):
    e=escenario
    r=client.post('/suministros/medicamentos',headers=e[actor],json=medicamento(e,retiro=0)|{'dosis_aplicada':'.0001'})
    assert r.status_code==estado,r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo5.registros_medicamentos')).scalar_one()==0


def test_rollback_del_outbox_revierte_toda_la_dosis(client,db_session,escenario,monkeypatch):
    from src.shared.errors import ServiceUnavailableError
    from src.supplies.infrastructure.repositories.outbox_provision_m06_repository import SqlAlchemyOutboxProvisionM06Repository as Repo
    e=escenario
    db_session.commit()
    original=Repo.encolar
    def fallar(self,evento):
        original(self,evento)
        raise ServiceUnavailableError('SERVICIO_NO_DISPONIBLE','Fallo de prueba después del outbox.')
    monkeypatch.setattr(Repo,'encolar',fallar)
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e)|{'dosis_aplicada':'.0001'})
    assert r.status_code==503,r.text
    for tabla in ('registros_medicamentos','registro_suministro','acumulado_ciclo','auditorias_suministros','outbox_provisiones_m06'):
        assert db_session.execute(text('SELECT count(*) FROM modulo5.'+tabla)).scalar_one()==0,tabla
    assert db_session.execute(text('SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico=:a'),{'a':e['individual']['activo']}).scalar_one()==1


@pytest.mark.parametrize('cantidad,costo,campo',[(0,500,'dosis_aplicada'),(1,0,'costo_unitario')])
def test_trigger_real_invalido_se_traduce_sin_exponer_sql(db_session,escenario,cantidad,costo,campo):
    from src.shared.db_error_translator import raise_from_db_error
    from src.shared.errors import ValidationError
    e=escenario
    with pytest.raises(ValidationError) as exc:
        with db_session.begin_nested():
            try:
                db_session.execute(text("""INSERT INTO modulo5.registros_medicamentos(id_activo_biologico,nombre_medicamento,
                    descripcion_clinica,unidad_dosis,cantidad,fecha_aplicacion,costo_unitario_medicamento,id_usuario)
                    VALUES(:a,'Medicamento de prueba','Descripcion clinica','ml',:cantidad,:fecha,:costo,:u)"""),
                    {'a':e['individual']['activo'],'cantidad':cantidad,'fecha':e['hoy'],'costo':costo,'u':e['vet_id']})
            except Exception as error:
                raise_from_db_error(error)
    assert exc.value.status_code==400 and exc.value.code=='VAL_ENTRADA' and exc.value.field==campo
    assert 'INSERT' not in exc.value.message and 'P0001' not in exc.value.message
