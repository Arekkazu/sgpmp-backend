# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: validar migración histórica, deduplicación concurrente, hash e inmutabilidad HTTP en PostgreSQL. |
# | 2026-11-10 | Arekkazu | Lote M05/M06 RLS modulo5: bitácora sin UPDATE/DELETE para la API, identidad RLS y fn_ en la función de hash |
"""Regresión de #964 con rol real de API y restricciones activas."""
from __future__ import annotations

import csv
import importlib
import io
import pkgutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.auditoria_suministro_port import EventoAuditoriaSuministro
from src.supplies.infrastructure.repositories.auditoria_suministro_repository import SqlAlchemyAuditoriaSuministroRepository

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def montar(integration_app):
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.supplies.infrastructure.models'):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + '.'):
            importlib.import_module(item.name)
    from src.supplies.infrastructure.routers.auditoria_suministros_router import router
    if not any(getattr(r, 'path', None) == '/suministros/auditoria' for r in integration_app.routes):
        integration_app.include_router(router)
        integration_app.openapi_schema = None


def emitir(usuario, **cambios):
    return EventoAuditoriaSuministro(**(dict(entidad_afectada='registro_suministro',
        tipo_operacion='REGISTRO_FALLIDO', id_usuario=usuario, resultado='FALLIDO',
        numero_reintentos=0, registro_incompleto=True) | cambios))


def fila(db, identidad):
    return dict(db.execute(text('SELECT * FROM modulo5.auditorias_suministros WHERE id_evento_m05=:i'),
                           {'i': identidad}).mappings().one())


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers, montar):
    usuarios = {rol: crear_usuario_db(id_rol=rol) for rol in (1, 2, 5, 8)}
    headers = {rol: crear_auth_headers(usuario) for rol, usuario in usuarios.items()}
    e = emitir(usuarios[1]['id_usuario'])
    SqlAlchemyAuditoriaSuministroRepository(db_session).registrar(e)
    db_session.commit()
    return dict(usuarios=usuarios, headers=headers, evento=e, fila=fila(db_session, e.id_evento_m05))


@pytest.fixture
def db_migracion(motor_vision_concurrente):
    with Session(motor_vision_concurrente, expire_on_commit=False) as db:
        yield db


def test_migracion_preserva_columnas_originales_y_hash_legado(db_migracion, password_hash):
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory
    db_session = db_migracion
    integration_engine = db_session.get_bind()
    assert integration_engine.url.host in ('127.0.0.1', 'localhost')
    assert integration_engine.url.database.startswith('dev28_concurrency_test_')
    revision = ScriptDirectory.from_config(Config('alembic.ini')).get_revision('d96480a11e01').module
    usuario = {'id_usuario': crear_usuario_efimero(db_session, password_hash)}
    with Operations.context(MigrationContext.configure(db_session.connection())):
        revision.downgrade()
    id_antiguo = db_session.execute(text("""INSERT INTO modulo5.auditorias_suministros(
        entidad_afectada,tipo_operacion,id_usuario,resultado,registro_incompleto)
        VALUES('legado_prueba','REGISTRO_FALLIDO',:u,'FALLIDO',true) RETURNING id_auditoria_suministro"""),
        {'u': usuario['id_usuario']}).scalar_one()
    original = db_session.execute(text('SELECT to_jsonb(a) FROM modulo5.auditorias_suministros a WHERE id_auditoria_suministro=:i'), {'i': id_antiguo}).scalar_one()
    with Operations.context(MigrationContext.configure(db_session.connection())):
        revision.upgrade()
    nuevo = db_session.execute(text('SELECT to_jsonb(a) FROM modulo5.auditorias_suministros a WHERE id_auditoria_suministro=:i'), {'i': id_antiguo}).scalar_one()
    assert nuevo['version_hash_integridad'] == 1 and nuevo['id_evento_m05']
    assert {k: v for k, v in nuevo.items() if k not in ('id_evento_m05', 'version_hash_integridad')} == original
    assert nuevo['detalle_causa'] is None  # No se inventa la evidencia histórica.
    verificado = db_session.execute(text('SELECT hash_integridad=modulo5.fn_hash_evento_auditoria_m05(to_jsonb(a),version_hash_integridad) FROM modulo5.auditorias_suministros a WHERE id_auditoria_suministro=:i'), {'i': id_antiguo}).scalar_one()
    assert verificado
    # Si ya se emitieron registros nuevos, el downgrade debe fallar antes de retirar identidad.
    SqlAlchemyAuditoriaSuministroRepository(db_session).registrar(emitir(usuario['id_usuario']))
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            with Operations.context(MigrationContext.configure(db_session.connection())):
                revision.downgrade()
    assert db_session.execute(text('SELECT count(*) FROM modulo5.auditorias_suministros')).scalar_one() == 2


def test_evento_incompleto_nuevo_se_consulta_con_causa_y_uuid(client, escenario):
    e = escenario
    r = client.get('/suministros/auditoria/' + str(e['fila']['id_auditoria_suministro']), headers=e['headers'][1])
    assert r.status_code == 200, r.text
    item = r.json()
    assert item['id_evento_m05'] == str(e['evento'].id_evento_m05)
    assert item['version_hash_integridad'] == 2 and item['registro_incompleto']
    assert 'Campos faltantes:' in item['detalle_causa']
    assert 'activo biológico' in item['detalle_causa'] and 'ciclo productivo' in item['detalle_causa']
    lista = client.get('/suministros/auditoria', headers=e['headers'][1], params={'id_usuario': e['usuarios'][1]['id_usuario']})
    assert lista.status_code == 200 and lista.json()['items'][0] == item


@pytest.mark.parametrize('metodo', ['PUT', 'PATCH', 'DELETE', 'POST'])
def test_modificar_evento_devuelve_405_y_un_rechazo_sin_alterar_objetivo(client, db_session, escenario, metodo):
    e = escenario
    original = fila(db_session, e['evento'].id_evento_m05)
    r = client.request(metodo, '/suministros/auditoria/' + str(original['id_auditoria_suministro']),
                       headers=e['headers'][1], json={'detalle_causa': 'alteración no permitida', 'secreto': 'NO_REGISTRAR'})
    assert r.status_code == 405 and r.headers['allow'] == 'GET', r.text
    assert fila(db_session, e['evento'].id_evento_m05) == original
    rechazos = client.get('/suministros/auditoria', headers=e['headers'][1],
                           params={'resultado': 'RECHAZADO', 'entidad_afectada': 'auditorias_suministros'})
    assert rechazos.status_code == 200 and rechazos.json()['total'] == 1, rechazos.text
    item, = rechazos.json()['items']
    assert item['id_usuario'] == e['usuarios'][1]['id_usuario']
    assert item['id_evento_m05'] != str(e['evento'].id_evento_m05) and item['fecha_evento']
    assert str(original['id_auditoria_suministro']) in item['detalle_causa']
    assert 'NO_REGISTRAR' not in item['detalle_causa']


def test_inexistente_y_lector_sin_permiso_no_reciben_informacion_del_objetivo(client, escenario):
    e = escenario
    for identificador in (e['fila']['id_auditoria_suministro'], 2147483646):
        r = client.delete('/suministros/auditoria/' + str(identificador), headers=e['headers'][2])
        assert r.status_code == 405, r.text
    lectura = client.get('/suministros/auditoria', headers=e['headers'][2])
    assert lectura.status_code == 403, lectura.text
    autorizada = client.get('/suministros/auditoria', headers=e['headers'][1], params={
        'id_usuario': e['usuarios'][2]['id_usuario'], 'resultado': 'RECHAZADO'})
    assert autorizada.status_code == 200 and autorizada.json()['total'] == 2


def test_guardas_no_publican_superficie_de_escritura_y_conservan_jwt(integration_app, client, escenario):
    e = escenario
    for path, operaciones in integration_app.openapi()['paths'].items():
        if path.startswith('/suministros/auditoria'):
            assert not {'post', 'put', 'patch', 'delete'} & operaciones.keys()
    r = client.delete('/suministros/auditoria/' + str(e['fila']['id_auditoria_suministro']))
    assert r.status_code == 401, r.text


def test_reentrega_del_mismo_uuid_no_duplica_ni_revierte_otras_escrituras(db_session, escenario):
    e = escenario
    original = fila(db_session, e['evento'].id_evento_m05)
    repo = SqlAlchemyAuditoriaSuministroRepository(db_session)
    alimento = db_session.execute(text("INSERT INTO modulo5.tipos_alimentos(nombre,costo_unitario,unidad_medida,estado) VALUES(:n,1,'kg','ACTIVO') RETURNING id_tipo_elemento"), {'n': 'Alimento ' + uuid4().hex}).scalar_one()
    repo.registrar(e['evento'])
    repo.registrar(replace(e['evento'], detalle_causa='Un reintento no sustituye el original.'))
    db_session.commit()
    assert fila(db_session, e['evento'].id_evento_m05) == original
    assert db_session.execute(text('SELECT count(*) FROM modulo5.tipos_alimentos WHERE id_tipo_elemento=:a'), {'a': alimento}).scalar_one() == 1


def test_hash_nuevo_incluye_todas_las_columnas_y_uuid(db_session, escenario):
    e = escenario
    validado = db_session.execute(text("""SELECT a.hash_integridad=encode(public.digest(
        (SELECT string_agg(format('%I=%L',key,value),' & ' ORDER BY key)
         FROM jsonb_each_text(to_jsonb(a)-'hash_integridad')), 'sha256'),'hex')
        FROM modulo5.auditorias_suministros a WHERE id_evento_m05=:i"""), {'i': e['evento'].id_evento_m05}).scalar_one()
    assert validado
    alterado = db_session.execute(text("SELECT modulo5.fn_hash_evento_auditoria_m05(jsonb_set(to_jsonb(a),'{id_evento_m05}',to_jsonb(CAST(:otro AS text))),2)<>hash_integridad FROM modulo5.auditorias_suministros a WHERE id_evento_m05=:i"), {'i': e['evento'].id_evento_m05, 'otro': str(uuid4())}).scalar_one()
    assert alterado


@pytest.mark.parametrize('operacion,rol', [('UPDATE', 'sgpmp_app'), ('DELETE', 'sgpmp_app'), ('DELETE', None)])
def test_sql_bajo_rol_api_no_puede_alterar_la_bitacora(db_session, escenario, operacion, rol):
    e = escenario
    if rol:
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
    try:
        sql = ('UPDATE modulo5.auditorias_suministros SET detalle_causa=detalle_causa '
               if operacion == 'UPDATE' else 'DELETE FROM modulo5.auditorias_suministros ')
        try:
            with db_session.begin_nested():
                afectadas = db_session.execute(text(sql + 'WHERE id_evento_m05=:i'), {'i': e['evento'].id_evento_m05}).rowcount
        except DBAPIError as rechazo:
            if rechazo.orig.pgcode == '42501':
                assert rol == 'sgpmp_app' and operacion == 'DELETE'
                assert not db_session.execute(text("SELECT has_table_privilege('sgpmp_app','modulo5.auditorias_suministros','DELETE')")).scalar_one()
            else:
                assert rechazo.orig.pgcode == '55000'
        else:
            # La RLS de modulo5 no tiene política de UPDATE ni DELETE en la bitácora: para el rol de la API la
            # fila no existe y la sentencia no toca nada (el trigger queda para quien no está sujeto a RLS).
            assert rol == 'sgpmp_app' and afectadas == 0
    finally:
        if rol:
            db_session.execute(text('RESET ROLE'))
    assert fila(db_session, e['evento'].id_evento_m05) == e['fila']


def test_sql_nuevo_incompleto_sin_causa_se_rechaza_sin_desactivar_triggers(db_session, escenario):
    with pytest.raises(DBAPIError) as rechazo:
        with db_session.begin_nested():
            db_session.execute(text("INSERT INTO modulo5.auditorias_suministros(entidad_afectada,tipo_operacion,id_usuario,resultado,registro_incompleto) VALUES('prueba','REGISTRO_FALLIDO',:u,'FALLIDO',true)"), {'u': escenario['usuarios'][1]['id_usuario']})
    assert rechazo.value.orig.pgcode == '23514'


def test_exportacion_y_lectores_autorizados_conservan_uuid(client, escenario):
    e = escenario
    for rol in (5, 8):
        r = client.get('/suministros/auditoria/exportar', headers=e['headers'][rol], params={
            'id_usuario': e['usuarios'][1]['id_usuario'], 'formato': 'csv'})
        assert r.status_code == 200, r.text
        item, = csv.DictReader(io.StringIO(r.text))
        assert item['id_evento_m05'] == str(e['evento'].id_evento_m05) and item['version_hash_integridad'] == '2'


def test_fallo_al_auditar_intento_conserva_405_y_sello(client, db_session, escenario, monkeypatch, caplog):
    from src.shared.errors import ServiceUnavailableError
    def fallar(self, evento):
        raise ServiceUnavailableError(code='NO_DISPONIBLE', message='No disponible')
    monkeypatch.setattr(SqlAlchemyAuditoriaSuministroRepository, 'registrar', fallar)
    e = escenario
    r = client.patch('/suministros/auditoria/' + str(e['fila']['id_auditoria_suministro']), headers=e['headers'][1])
    assert r.status_code == 405 and 'No se pudo auditar' in caplog.text
    assert fila(db_session, e['evento'].id_evento_m05) == e['fila']


def test_commit_de_rechazo_respeta_rollback_exterior(client, db_session, escenario):
    e = escenario
    db_session.commit()
    exterior = db_session.get_bind().begin_nested()
    try:
        assert client.delete('/suministros/auditoria/' + str(e['fila']['id_auditoria_suministro']), headers=e['headers'][1]).status_code == 405
        assert db_session.execute(text("SELECT count(*) FROM modulo5.auditorias_suministros WHERE resultado='RECHAZADO'")).scalar_one() == 1
    finally:
        db_session.close()
        exterior.rollback()
    assert db_session.execute(text("SELECT count(*) FROM modulo5.auditorias_suministros WHERE resultado='RECHAZADO'")).scalar_one() == 0


def test_deduplicacion_concurrente_en_dos_transacciones_reales(motor_vision_concurrente, password_hash):
    integration_engine = motor_vision_concurrente
    assert integration_engine.url.host in ('127.0.0.1', 'localhost')
    assert integration_engine.url.database.startswith('dev28_concurrency_test_')
    with integration_engine.begin() as c:
        c.exec_driver_sql('GRANT USAGE ON SCHEMA modulo5,modulo1,auditoria TO sgpmp_app')
        c.exec_driver_sql('GRANT INSERT,SELECT ON modulo5.auditorias_suministros TO sgpmp_app')
        c.exec_driver_sql('GRANT USAGE,SELECT ON SEQUENCE modulo5.auditorias_suministros_id_auditoria_suministro_seq TO sgpmp_app')
        usuario = crear_usuario_efimero(c, password_hash)

    e = emitir(usuario)
    barrera = Barrier(2)
    def guardar():
        with Session(integration_engine) as db:
            db.execute(text('SET LOCAL ROLE sgpmp_app'))
            db.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(usuario)})
            # Identidad que leen las políticas RLS (la API la declara en cada request).
            db.execute(text("SELECT set_config('app.current_user_id',:u,true)"), {'u': str(usuario)})
            barrera.wait(timeout=10)
            SqlAlchemyAuditoriaSuministroRepository(db).registrar(e)
            db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(guardar) for _ in range(2)]
        for futuro in futuros:
            futuro.result(timeout=20)
    with integration_engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM modulo5.auditorias_suministros WHERE id_evento_m05=:i'), {'i': e.id_evento_m05}).scalar_one() == 1


def nombre(prefijo):
    return prefijo+' '+''.join(chr(97+int(c,16)) for c in uuid4().hex[:12])


def sembrar_activo(db,usuario,tipo='INDIVIDUAL'):
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"),{'u':str(usuario)})
    especie=db.execute(text("INSERT INTO modulo9.especies(nombre,es_activo,fecha_creacion,grupo_manejo,densidad_maxima_por_especie) VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"),{'n':nombre('Especie Suministros')}).scalar_one()
    finca=db.execute(text("INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo) VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"),{'n':nombre('Finca Suministros')}).scalar_one()
    area=db.execute(text("INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo) VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"),{'n':nombre('Corral Suministros'),'f':finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'),{'a':area,'e':especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'),{'u':usuario,'f':finca})
    activo=db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,identificador,fecha_inicio_ciclo,
        id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,id_usuario,fecha_creacion,
        soporte_documental,detalles_procedencia) VALUES(:e,:a,:t,:ident,current_date-30,1,'Fixture de suministros','compra',100,'{}',:u,now()-interval '31 days','doc','') RETURNING id_activo_biologico"""),{'e':especie,'a':area,'t':tipo,'u':usuario,'ident':uuid4().hex[:20] if tipo=='INDIVIDUAL' else None}).scalar_one()
    if tipo=='POBLACIONAL':
        db.execute(text('INSERT INTO modulo2.detalles_activos_biologicos_poblacionales(id_activo_biologico,cantidad_inicial,cantidad_actual,peso_promedio_inicial,densidad) VALUES(:a,10,10,.1,.1)'),{'a':activo})
    else:
        db.execute(text("INSERT INTO modulo2.detalles_activos_individuales(id_activo_biologico,raza,sexo,fecha_nacimeinto,peso_inicial,fecha_creacion,id_usuario) VALUES(:a,'Criolla','Macho',current_date-100,1,now(),:u)"),{'a':activo,'u':usuario})
    biologico=db.execute(text('INSERT INTO modulo9.ciclos_biologicos(nombre,duracion_dias,id_especie) VALUES(:n,365,:e) RETURNING id_ciclo_biologico'),{'n':nombre('Ciclo Biologico'),'e':especie}).scalar_one()
    productivo=db.execute(text('INSERT INTO modulo9.ciclos_productivos(nombre,duracion_dias,id_ciclo_biologico) VALUES(:n,60,:b) RETURNING id_ciclo_productivo'),{'n':nombre('Fase Productiva'),'b':biologico}).scalar_one()
    puente=db.execute(text('INSERT INTO modulo9.ciclos_productivos_biologicos(id_ciclo_productivo,id_ciclo_biologico) VALUES(:p,:b) RETURNING id_ciclos_productivo_biologico'),{'p':productivo,'b':biologico}).scalar_one()
    fase=db.execute(text("INSERT INTO modulo2.gestiones_fases(id_activo_biologico,id_ciclo_productiva,fecha_inicio,es_activa,id_usuario,id_ciclos_productivo_biologico) VALUES(:a,:p,now()-interval '30 days',true,:u,:b) RETURNING id_gestion_fases"),{'a':activo,'p':productivo,'u':usuario,'b':puente}).scalar_one()
    return dict(activo=activo,fase=fase,finca=finca)



def test_rf78_rf79_separan_reporte_pendiente_de_evento_incompleto(client, db_session, escenario, integration_app):
    from src.supplies.infrastructure.routers.costeo_suministros_router import router as costeo
    from src.supplies.infrastructure.routers.provision_nic41_router import router as provision
    e = escenario
    for router, path in ((costeo, '/suministros/costeo-directo'), (provision, '/suministros/nic41/ciclo/{id_gestion_fases}/consolidar')):
        if not any(getattr(r, 'path', None) == path for r in integration_app.routes):
            integration_app.include_router(router)
            integration_app.openapi_schema = None
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    a = sembrar_activo(db_session, e['usuarios'][1]['id_usuario'])
    db_session.commit()
    hoy = db_session.execute(text("SELECT (clock_timestamp() AT TIME ZONE 'UTC')::date")).scalar_one()
    r = client.post('/suministros/costeo-directo', headers=e['headers'][1], json={
        'id_activo_biologico': a['activo'], 'id_idempotencia': str(uuid4()), 'tipo_suministro': 'SERVICIO_VETERINARIO',
        'fecha_aplicacion': hoy.isoformat(), 'cantidad': '2', 'precio_unitario': '500', 'unidad_medida': 'servicio',
        'justificacion_precio': 'Precio documentado con el profesional responsable'})
    assert r.status_code == 200, r.text
    db_session.execute(text("UPDATE modulo5.outbox_provisiones_m06 SET numero_intentos=1,fecha_intentos=ARRAY[now()] WHERE id_gestion_fases=:f"), {'f': a['fase']})
    db_session.execute(text('UPDATE modulo2.gestiones_fases SET es_activa=false,fecha_finalizacion=now() WHERE id_gestion_fases=:f'), {'f': a['fase']})
    db_session.commit()
    r = client.post('/suministros/nic41/ciclo/' + str(a['fase']) + '/consolidar', headers=e['headers'][1])
    assert r.status_code == 201 and r.json()['es_reporte_potencialmente_incompleto'], r.text
    filas = db_session.execute(text("SELECT registro_incompleto,detalle_causa,id_evento_m05,version_hash_integridad FROM modulo5.auditorias_suministros WHERE entidad_afectada='provision_nic41' AND id_activo_biologico=:a"), {'a': a['activo']}).all()
    assert len(filas) == 2
    assert all(not f[0] and 'eventos pendientes de entrega' in f[1] and f[2] and f[3] == 2 for f in filas)


def test_emisor_sql_de_rf75_recibe_uuid_y_hash_sin_pasarlo_por_python(client, db_session, escenario, integration_app):
    from src.supplies.infrastructure.routers.consumo_alimento_router import router
    if not any(getattr(r, 'path', None) == '/suministros/consumo-alimentos' for r in integration_app.routes):
        integration_app.include_router(router)
        integration_app.openapi_schema = None
    e = escenario
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    a = sembrar_activo(db_session, e['usuarios'][1]['id_usuario'])
    alimento = db_session.execute(text("INSERT INTO modulo5.tipos_alimentos(nombre,costo_unitario,unidad_medida,estado) VALUES(:n,100,'kg','ACTIVO') RETURNING id_tipo_elemento"), {'n': nombre('Concentrado')}).scalar_one()
    hoy = db_session.execute(text("SELECT (clock_timestamp() AT TIME ZONE 'UTC')::date")).scalar_one()
    db_session.commit()
    ultimo = db_session.execute(text('SELECT max(id_auditoria_suministro) FROM modulo5.auditorias_suministros')).scalar_one()
    r = client.post('/suministros/consumo-alimentos', headers=e['headers'][1], json={
        'id_activo_biologico': a['activo'], 'id_tipo_alimento': alimento, 'fecha_consumo': hoy.isoformat(),
        'hora_suministro': '08:00', 'cantidad_alimento': '2', 'costo_unitario': '100'})
    assert r.status_code == 201, r.text
    nuevos = db_session.execute(text('SELECT tipo_operacion,id_evento_m05,version_hash_integridad,hash_integridad FROM modulo5.auditorias_suministros WHERE id_auditoria_suministro>:i'), {'i': ultimo}).all()
    assert any(x[0] == 'INSERT' for x in nuevos)
    assert all(x[1] and x[2] == 2 and len(x[3]) == 64 for x in nuevos)


def crear_usuario_efimero(db, password_hash):
    return db.execute(text("""INSERT INTO modulo1.usuarios(tipo_identificacion,numero_identificacion,nombre,
        apellidos,fecha_nacimiento,genero,correo_electronico,contrasena_cifrada,telefono,direccion,id_rol,fecha_registro)
        VALUES('CC',:n,'Prueba','Base efimera','1990-01-01','M',:correo,:clave,'3001234567','Prueba local',1,now())
        RETURNING id_usuario"""), {'n': str(uuid4().int % 10**15).zfill(15),
            'correo': 'inc964-' + uuid4().hex + '@example.com', 'clave': password_hash}).scalar_one()


def test_metodos_no_admitidos_siguen_anunciando_solo_get(client, escenario):
    e = escenario
    r = client.options('/suministros/auditoria/' + str(e['fila']['id_auditoria_suministro']))
    assert r.status_code == 405 and r.headers['allow'] == 'GET', r.text
