# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-275-G37 RF-80: validar rechazo auditable, atomicidad, JWT, RBAC y finca con PostgreSQL real. |
# | 2026-11-10 | Arekkazu | Lote M05/M06 RNF-05: el rechazo por activo de otra finca lo prueba un Gestor de Granja (Productor ya no crea) |
"""Regresión HTTP de #960 con el rol real de API y restricciones activas."""
from __future__ import annotations

import importlib
import pkgutil
import time
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def montar(integration_app):
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.supplies.infrastructure.models'):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + '.'):
            importlib.import_module(item.name)
    from src.supplies.infrastructure.routers.costeo_suministros_router import router as costeo
    from src.supplies.infrastructure.routers.auditoria_suministros_router import router as auditoria
    from src.supplies.infrastructure.routers.provision_nic41_router import router as provision
    from src.supplies.infrastructure.routers.historial_suministros_router import router as historial
    for router, path in ((costeo, '/suministros/costeo-directo'), (auditoria, '/suministros/auditoria'),
                         (provision, '/suministros/nic41/ciclo/{id_gestion_fases}/consolidar'),
                         (historial, '/suministros/historial')):
        if not any(getattr(r, 'path', None) == path
                   for r in integration_app.routes):
            integration_app.include_router(router)
            integration_app.openapi_schema = None


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
def escenario(db_session, crear_usuario_db, crear_auth_headers, montar):
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    admin = crear_usuario_db(id_rol=1)
    productor = crear_usuario_db(id_rol=2)
    fiscal = crear_usuario_db(id_rol=8)
    # Registra costeo directo pero solo en sus fincas (Productor y Veterinario ya no crean: RNF-05).
    gestor = crear_usuario_db(id_rol=7)
    activo = sembrar_activo(db_session, admin['id_usuario'], 'POBLACIONAL')
    headers = crear_auth_headers(admin) | {'X-Zona-Horaria': 'America/Bogota'}
    hp = crear_auth_headers(productor)
    hf = crear_auth_headers(fiscal)
    hg = crear_auth_headers(gestor)
    hoy = db_session.execute(text("SELECT (clock_timestamp() AT TIME ZONE 'America/Bogota')::date")).scalar_one()
    db_session.commit()  # El rollback del rechazo debe conservar las precondiciones del fixture.
    return dict(**activo, usuario=admin['id_usuario'], headers=headers, productor=hp, fiscal=hf, gestor=hg, hoy=hoy)


def payload(e, **cambios):
    return dict(id_activo_biologico=e['activo'], tipo_suministro='SERVICIO_VETERINARIO',
                id_idempotencia=str(uuid.uuid4()), cantidad='2', precio_unitario='500',
                unidad_medida='servicio', fecha_aplicacion=e['hoy'].isoformat(),
                justificacion_precio='Precio acordado y documentado con el profesional') | cambios


def cerrar(db, e):
    db.execute(text("UPDATE modulo2.gestiones_fases SET es_activa=false,fecha_finalizacion=now() WHERE id_gestion_fases=:f"), {'f': e['fase']})
    db.commit()


def contar(db, e):
    return tuple(db.execute(text('SELECT count(*) FROM modulo5.' + tabla + ' WHERE id_activo_biologico=:a'),
                            {'a': e['activo']}).scalar_one()
                 for tabla in ('registro_suministro', 'acumulado_ciclo', 'outbox_provisiones_m06'))


def rechazos(client, e, **filtros):
    r = client.get('/suministros/auditoria', headers=e['headers'],
                   params=dict(id_activo_biologico=e['activo'], resultado='RECHAZADO') | filtros)
    assert r.status_code == 200, r.text
    return r.json()


def test_ciclo_cerrado_conserva_409_y_publica_rechazo_por_lista_y_detalle(client, db_session, escenario, record_property):
    e = escenario
    primero = payload(e)
    ok = client.post('/suministros/costeo-directo', headers=e['headers'], json=primero)
    assert ok.status_code == 200, ok.text
    antes = contar(db_session, e)
    acumulado = db_session.execute(text('SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f'), {'f': e['fase']}).scalar_one()
    cerrar(db_session, e)
    intento = payload(e)
    inicio = time.perf_counter()
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=intento)
    assert r.status_code == 409 and r.json()['error_code'] == 'CICLO_NO_ACTIVO', r.text
    pagina = rechazos(client, e, tipo_operacion='REGISTRO_FALLIDO', id_usuario=e['usuario'])
    lapso = time.perf_counter() - inicio
    record_property('segundos_post_y_lectura', lapso)
    assert lapso < 2
    assert pagina['total'] == 1
    evento, = pagina['items']
    assert evento['id_usuario'] == e['usuario'] and evento['numero_reintentos'] == 0
    assert str(intento['id_idempotencia']) in evento['detalle_causa']
    assert 'ciclo productivo abierto' in evento['detalle_causa']
    assert evento['fecha_evento'] and evento['fecha_emision'] and len(evento['hash_integridad']) == 64
    assert evento['id_gestion_fases'] is None and evento['registro_incompleto']
    detalle = client.get('/suministros/auditoria/' + str(evento['id_auditoria_suministro']), headers=e['headers'])
    assert detalle.status_code == 200 and detalle.json() == evento
    assert contar(db_session, e) == antes
    assert db_session.execute(text('SELECT acumulado_total_ciclo FROM modulo5.acumulado_ciclo WHERE id_gestion_fases=:f'), {'f': e['fase']}).scalar_one() == acumulado
    # Repetir una operación ya procesada mantiene su idempotencia incluso tras el cierre.
    repetido = client.post('/suministros/costeo-directo', headers=e['headers'], json=primero)
    assert repetido.status_code == 200 and repetido.json()['estado'] == 'YA_PROCESADO', repetido.text
    assert rechazos(client, e)['total'] == 1


@pytest.mark.parametrize('cambios,codigo', [
    ({'justificacion_precio': None}, 'JUSTIFICACION_PRECIO_REQUERIDA'),
    ({'cantidad': '0'}, 'COSTO_REGISTRO_INVALIDO'),
    ({'tipo_suministro': 'DESCONOCIDO'}, 'TIPO_SUMINISTRO_NO_CONFIGURADO'),
    ({'tipo_suministro': 'MEDICAMENTO'}, 'REGISTRO_RF76_INVALIDO'),
])
def test_validaciones_422_sin_costos_parciales(client, db_session, escenario, cambios, codigo):
    e = escenario
    antes = contar(db_session, e)
    cuerpo = payload(e, **cambios)
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=cuerpo)
    assert r.status_code == 422 and r.json()['error_code'] == codigo, r.text
    assert rechazos(client, e)['total'] == 1
    assert contar(db_session, e) == antes


def test_duplicado_409_y_uuid_rechazado_no_reservado(client, db_session, escenario):
    e = escenario
    original = payload(e)
    assert client.post('/suministros/costeo-directo', headers=e['headers'], json=original).status_code == 200
    nuevo = payload(e)
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=nuevo)
    assert r.status_code == 409 and r.json()['error_code'] == 'SUMINISTRO_DUPLICADO', r.text
    assert rechazos(client, e)['total'] == 1
    nuevo['cantidad'] = '3'
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=nuevo)
    assert r.status_code == 200, r.text
    assert contar(db_session, e) == (2, 1, 2)
    assert rechazos(client, e)['total'] == 1


def test_conflicto_tardio_revierte_ledger_outbox_y_exitos_antes_del_rechazo(client, db_session, escenario, monkeypatch):
    from src.shared.errors import ConflictError
    from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
    registrar = RegistradorMovimientoLedger.registrar
    def fallar(self, *args, **kwargs):
        registrar(self, *args, **kwargs)
        raise ConflictError(code='CONFLICTO_PRUEBA', message='Conflicto controlado')
    monkeypatch.setattr(RegistradorMovimientoLedger, 'registrar', fallar)
    e = escenario
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e))
    assert r.status_code == 409 and r.json()['error_code'] == 'CONFLICTO_PRUEBA', r.text
    assert contar(db_session, e) == (0, 0, 0)
    fila, = db_session.execute(text('SELECT resultado,id_gestion_fases FROM modulo5.auditorias_suministros WHERE id_activo_biologico=:a'), {'a': e['activo']}).all()
    assert tuple(fila) == ('RECHAZADO', e['fase'])
    assert rechazos(client, e)['total'] == 1


@pytest.mark.parametrize('oculto', [False, True])
def test_objetivo_inexistente_o_de_otra_finca_no_se_vincula(client, db_session, escenario, oculto):
    e = escenario
    cuerpo = payload(e) if oculto else payload(e, id_activo_biologico=2147483646)
    headers = e['gestor'] if oculto else e['headers']
    r = client.post('/suministros/costeo-directo', headers=headers, json=cuerpo)
    assert r.status_code == 409 and r.json()['error_code'] == 'CICLO_NO_ACTIVO', r.text
    fila, = db_session.execute(text("SELECT id_activo_biologico,id_ciclo_productivo,id_gestion_fases,registro_incompleto FROM modulo5.auditorias_suministros WHERE resultado='RECHAZADO'")).all()
    assert tuple(fila) == (None, None, None, True)
    assert contar(db_session, e) == (0, 0, 0)


def test_fallo_de_auditoria_preserva_409_y_no_deja_fila_incompleta(client, db_session, escenario, monkeypatch, caplog):
    from src.shared.errors import ServiceUnavailableError
    from src.supplies.infrastructure.repositories.auditoria_suministro_repository import SqlAlchemyAuditoriaSuministroRepository
    registrar = SqlAlchemyAuditoriaSuministroRepository.registrar
    def fallar(self, evento):
        registrar(self, evento)
        if evento.resultado == 'RECHAZADO':
            raise ServiceUnavailableError(code='SERVICIO_NO_DISPONIBLE', message='Fallo controlado después del flush')
    monkeypatch.setattr(SqlAlchemyAuditoriaSuministroRepository, 'registrar', fallar)
    e = escenario
    cerrar(db_session, e)
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e))
    assert r.status_code == 409 and r.json()['error_code'] == 'CICLO_NO_ACTIVO', r.text
    assert rechazos(client, e)['total'] == 0
    assert 'No se pudo auditar' in caplog.text
    assert contar(db_session, e) == (0, 0, 0)


def test_jwt_rbac_y_dto_previos_no_generan_rechazo_de_negocio(client, db_session, escenario):
    e = escenario
    r = client.post('/suministros/costeo-directo', json=payload(e))
    assert r.status_code == 401
    r = client.post('/suministros/costeo-directo', headers=e['fiscal'], json=payload(e))
    assert r.status_code == 403, r.text
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e, id_activo_biologico=0))
    assert r.status_code in (400, 422), r.text
    assert rechazos(client, e)['total'] == 0
    r = client.get('/suministros/auditoria', headers=e['productor'])
    assert r.status_code == 403, r.text


def test_commit_del_rechazo_respeta_rollback_exterior_del_sandbox(client, db_session, escenario):
    e = escenario
    cerrar(db_session, e)
    db_session.commit()
    exterior = db_session.get_bind().begin_nested()
    try:
        r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e))
        assert r.status_code == 409, r.text
        assert rechazos(client, e)['total'] == 1
    finally:
        db_session.close()
        exterior.rollback()
    assert rechazos(client, e)['total'] == 0


def test_cierre_consolidado_e_historial_conservan_exitos_tras_rechazo(client, db_session, escenario):
    e = escenario
    assert client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e)).status_code == 200
    cerrar(db_session, e)
    url = '/suministros/nic41/ciclo/' + str(e['fase']) + '/consolidar'
    consolidado = client.post(url, headers=e['headers'])
    assert consolidado.status_code == 201, consolidado.text
    historial = client.get('/suministros/historial', headers=e['headers'], params={'id_activo_biologico': e['activo']})
    assert historial.status_code == 200, historial.text
    # El consolidado y el costo no deben modificarse por un nuevo intento rechazado.
    antes = contar(db_session, e)
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e))
    assert r.status_code == 409 and r.json()['error_code'] == 'CICLO_NO_ACTIVO', r.text
    assert contar(db_session, e) == antes
    eventos = db_session.execute(text('SELECT tipo_operacion,resultado FROM modulo5.auditorias_suministros WHERE id_activo_biologico=:a'), {'a': e['activo']}).all()
    assert {tipo for tipo, resultado in eventos if resultado == 'EXITOSO'} >= {
        'SUMINISTRO_REGISTRADO', 'PRECIO_MANUAL_INGRESADO', 'ACUMULADO_ACTUALIZADO',
        'CICLO_CONSOLIDADO', 'REPORTE_COSTOS_GENERADO', 'CONSULTA_HISTORIAL_EJECUTADA'}
    assert sum(resultado == 'RECHAZADO' for _, resultado in eventos) == 1
    id_provision = consolidado.json()['id_provision']
    posterior = client.get('/suministros/nic41/' + str(id_provision), headers=e['headers'])
    assert posterior.status_code == 200 and posterior.json() == consolidado.json(), posterior.text


def test_conflicto_de_constraint_real_se_audita_tras_rollback(client, db_session, escenario, monkeypatch):
    from src.supplies.infrastructure.repositories.registro_suministro_repository import SqlAlchemyRegistroSuministroRepository
    e = escenario
    assert client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e)).status_code == 200
    antes = contar(db_session, e)
    # Omite solo la preconsulta para alcanzar la restricción UNIQUE real; no desactiva constraints.
    monkeypatch.setattr(SqlAlchemyRegistroSuministroRepository, 'existe_duplicado_contenido', lambda *a, **kw: False)
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e))
    assert r.status_code == 409, r.text
    assert rechazos(client, e)['total'] == 1
    assert contar(db_session, e) == antes
