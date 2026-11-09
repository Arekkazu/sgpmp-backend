# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-277-G20 RF-77: validar promedio, bajas, snapshot, historial, regeneración y polling con PostgreSQL real. |
"""Regresión de #963 con JWT, rol de API y restricciones activas."""
from __future__ import annotations

import importlib
import pkgutil
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration
CAUSA = 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.'


@pytest.fixture(autouse=True)
def montar(integration_app, monkeypatch):
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.supplies.infrastructure.models'):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + '.'):
            importlib.import_module(item.name)
    from src.supplies.infrastructure.routers.reporte_gastos_router import router as reportes
    from src.supplies.infrastructure.routers.medicamento_router import router as medicamentos
    from src.biological_assets.infrastructure.routers.activo_biologico_router import router as activos
    for router, path in ((reportes, '/suministros/reportes-gastos'),
                         (medicamentos, '/suministros/medicamentos'),
                         (activos, '/activos-biologicos/{id_activo}/eventos/baja')):
        if not any(getattr(r, 'path', None) == path and 'POST' in getattr(r, 'methods', set()) for r in integration_app.routes):
            integration_app.include_router(router)
            integration_app.openapi_schema = None
    monkeypatch.setattr('src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter.send_email', lambda **_: None)


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
        db.execute(text('INSERT INTO modulo2.detalles_activos_biologicos_poblacionales(id_activo_biologico,cantidad_inicial,cantidad_actual,peso_promedio_inicial,densidad) VALUES(:a,50,50,.1,.5)'),{'a':activo})
    else:
        db.execute(text("INSERT INTO modulo2.detalles_activos_individuales(id_activo_biologico,raza,sexo,fecha_nacimeinto,peso_inicial,fecha_creacion,id_usuario) VALUES(:a,'Criolla','Macho',current_date-100,1,now(),:u)"),{'a':activo,'u':usuario})
    biologico=db.execute(text('INSERT INTO modulo9.ciclos_biologicos(nombre,duracion_dias,id_especie) VALUES(:n,365,:e) RETURNING id_ciclo_biologico'),{'n':nombre('Ciclo Biologico'),'e':especie}).scalar_one()
    productivo=db.execute(text('INSERT INTO modulo9.ciclos_productivos(nombre,duracion_dias,id_ciclo_biologico) VALUES(:n,60,:b) RETURNING id_ciclo_productivo'),{'n':nombre('Fase Productiva'),'b':biologico}).scalar_one()
    puente=db.execute(text('INSERT INTO modulo9.ciclos_productivos_biologicos(id_ciclo_productivo,id_ciclo_biologico) VALUES(:p,:b) RETURNING id_ciclos_productivo_biologico'),{'p':productivo,'b':biologico}).scalar_one()
    fase=db.execute(text("INSERT INTO modulo2.gestiones_fases(id_activo_biologico,id_ciclo_productiva,fecha_inicio,es_activa,id_usuario,id_ciclos_productivo_biologico) VALUES(:a,:p,now()-interval '30 days',true,:u,:b) RETURNING id_gestion_fases"),{'a':activo,'p':productivo,'u':usuario,'b':puente}).scalar_one()
    return dict(activo=activo,fase=fase,finca=finca,area=area)


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers, montar):
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO'),(3,'EN_TRATAMIENTO'),(6,'BAJA') ON CONFLICT DO NOTHING"))
    admin = crear_usuario_db(id_rol=1)
    propietario = crear_usuario_db(id_rol=2)
    ajeno = crear_usuario_db(id_rol=2)
    vet = crear_usuario_db(id_rol=3)
    poblacional = sembrar_activo(db_session, propietario['id_usuario'], 'POBLACIONAL')
    individual = sembrar_activo(db_session, propietario['id_usuario'])
    hoy = db_session.execute(text("SELECT (clock_timestamp() AT TIME ZONE 'America/Bogota')::date")).scalar_one()
    headers = {k: crear_auth_headers(u) | {'X-Zona-Horaria': 'America/Bogota'}
               for k, u in dict(admin=admin, propietario=propietario, ajeno=ajeno, vet=vet).items()}
    db_session.commit()
    return dict(**poblacional, individual=individual['activo'], area_individual=individual['area'], usuario=admin['id_usuario'],
                propietario_id=propietario['id_usuario'], headers=headers, hoy=hoy)


def registrar_gasto(client, e, activo=None):
    r = client.post('/suministros/medicamentos', headers=e['headers']['admin'], json=dict(
        id_activo_biologico=activo or e['activo'], nombre_medicamento='Oxitetraciclina',
        fecha_aplicacion=e['hoy'].isoformat(), hora_aplicacion='08:00', via_administracion='ORAL',
        dosis_aplicada='10', unidad_dosis='ml', costo_unitario='5000', periodo_retiro_dias=0,
        motivo_aplicacion='Tratamiento preventivo documentado', nombre_veterinario='Profesional de pruebas'))
    assert r.status_code == 201, r.text


def baja(client, e, cantidad=50):
    r = client.post('/activos-biologicos/' + str(e['activo']) + '/eventos/baja',
                    headers=e['headers']['admin'], json=dict(tipo_baja='muerte',
                    fecha_baja=e['hoy'].isoformat(), motivo_baja='Baja controlada para regresión del reporte',
                    cantidad_afectada=cantidad))
    assert r.status_code == 201, r.text


def cuerpo(e, **cambios):
    return dict(activo_biologico_id=e['activo'], fecha_inicio_reporte=e['hoy'].isoformat(),
                fecha_fin_reporte=e['hoy'].isoformat(), tipo_periodo='CICLO_COMPLETO') | cambios


def generar(client, e, actor='admin', **cambios):
    r = client.post('/suministros/reportes-gastos', headers=e['headers'][actor], json=cuerpo(e, **cambios))
    assert r.status_code == 200, r.text
    return r.json()


def assert_no_calculable(r):
    assert r['gasto_promedio_individuo'] == 'NO_CALCULABLE' and r['causa_no_calculable_promedio'] == CAUSA
    assert Decimal(r['gasto_total_acumulado']) == Decimal('50000')


def test_baja_total_conserva_literal_en_generacion_consulta_historial_y_regeneracion(client, db_session, escenario):
    e = escenario
    registrar_gasto(client, e)
    baja(client, e)
    estado = db_session.execute(text('SELECT ab.id_estado,dp.cantidad_actual FROM modulo2.activos_biologicos ab JOIN modulo2.detalles_activos_biologicos_poblacionales dp USING(id_activo_biologico) WHERE ab.id_activo_biologico=:a'), {'a': e['activo']}).one()
    assert tuple(estado) == (6, 0)
    r = generar(client, e)
    assert_no_calculable(r)
    assert sum(Decimal(x['subtotal']) for x in r['desglose_categorias']) == Decimal('50000')
    rid = r['id_reporte_gasto_acumulado']
    for ruta in ('/' + str(rid), '/' + str(rid) + '/regenerar'):
        consulta = client.get('/suministros/reportes-gastos' + ruta, headers=e['headers']['admin'])
        assert consulta.status_code == 200, consulta.text
        assert_no_calculable(consulta.json())
    historial = client.get('/suministros/reportes-gastos/historial', headers=e['headers']['admin'])
    assert historial.status_code == 200, historial.text
    assert_no_calculable(next(x for x in historial.json()['items'] if x['id_reporte_gasto_acumulado'] == rid))
    almacenado = db_session.execute(text('SELECT json_parametros FROM modulo5.reporte_gastos_acumulados WHERE id_reporte_gasto_acumulado=:r'), {'r': rid}).scalar_one()
    assert almacenado['resumen_promedio']['causa_no_calculable_promedio'] == CAUSA
    assert almacenado['resumen_promedio']['gasto_promedio_individuo'] is None


@pytest.mark.parametrize('restantes', [50, 20])
def test_promedio_calculable_usa_cantidad_actual_y_conserva_decimales(client, escenario, restantes):
    e = escenario
    registrar_gasto(client, e)
    if restantes < 50:
        baja(client, e, 50 - restantes)
    r = generar(client, e)
    assert Decimal(r['gasto_promedio_individuo']) == Decimal('50000') / restantes
    assert r['causa_no_calculable_promedio'] is None
    assert (r['nota_bajas'] is not None) == (restantes < 50)


def test_snapshot_no_cambia_si_el_lote_cambia_despues_de_generar(client, escenario):
    e = escenario
    registrar_gasto(client, e)
    inicial = generar(client, e)
    rid = inicial['id_reporte_gasto_acumulado']
    baja(client, e)
    consulta = client.get('/suministros/reportes-gastos/' + str(rid), headers=e['headers']['admin'])
    assert consulta.status_code == 200 and Decimal(consulta.json()['gasto_promedio_individuo']) == Decimal('1000'), consulta.text
    assert consulta.json()['causa_no_calculable_promedio'] is None
    regenerado = client.get('/suministros/reportes-gastos/' + str(rid) + '/regenerar', headers=e['headers']['admin'])
    assert regenerado.status_code == 200, regenerado.text
    assert_no_calculable(regenerado.json())


def test_individual_y_agregado_conservan_promedio_no_aplicable(client, escenario):
    e = escenario
    registrar_gasto(client, e, e['individual'])
    for filtros in (dict(activo_biologico_id=e['individual']),
                    dict(activo_biologico_id=None, id_infraestructura=e['area_individual'])):
        r = generar(client, e, **filtros)
        assert r['gasto_promedio_individuo'] is None and r['causa_no_calculable_promedio'] is None


@pytest.mark.parametrize('literal', [False, True])
def test_polling_de_resultado_async_persistido_conserva_literal_y_causa(client, db_session, escenario, literal):
    from src.supplies.application.use_cases.reporte_gastos.procesar_cola_reportes_gastos_use_case import _resultado_json
    from src.supplies.domain.entities.trabajo_reporte_gasto import TrabajoReporteGasto, EjecucionReporteGasto
    from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync
    from src.supplies.infrastructure.factories.reporte_gastos_factory import build_generar_reporte_gastos_use_case
    from src.supplies.infrastructure.repositories.reporte_gasto_repository import SqlAlchemyReporteGastoRepository
    from src.supplies.infrastructure.repositories.trabajo_reporte_gasto_repository import SqlAlchemyTrabajoReporteGastoRepository
    e = escenario
    registrar_gasto(client, e)
    baja(client, e)
    generado = generar(client, e)
    snapshot = SqlAlchemyReporteGastoRepository(db_session).obtener(generado['id_reporte_gasto_acumulado'])
    completo = build_generar_reporte_gastos_use_case(db_session).construir_desde_parametros(
        snapshot.parametros, SimpleNamespace(id_usuario=e['usuario'], id_rol=1))
    resultado = _resultado_json(completo)
    if literal:
        resultado['gasto_promedio_individuo'] = 'NO_CALCULABLE'
    repo = SqlAlchemyTrabajoReporteGastoRepository(db_session)
    trabajo = repo.encolar(TrabajoReporteGasto(parametros=snapshot.parametros, id_usuario_solicitante=e['usuario']))
    ejecucion = repo.crear_ejecucion(EjecucionReporteGasto(id_cola=trabajo.id_cola))
    ahora = datetime.now(timezone.utc)
    ejecucion.completar(hora_fin=ahora, id_reporte_resultado=snapshot.id_reporte_gasto_acumulado, resultado_json=resultado)
    repo.guardar_ejecucion(ejecucion)
    repo.marcar_estado(trabajo.id_cola, EstadoTrabajoAsync.COMPLETADO, fecha_procesado=ahora)
    db_session.commit()
    r = client.get('/suministros/reportes-gastos/trabajos/' + str(trabajo.id_cola), headers=e['headers']['admin'])
    assert r.status_code == 200 and r.json()['estado'] == 'COMPLETADO', r.text
    assert_no_calculable(r.json()['reporte'])


@pytest.mark.parametrize('formato', ['CSV', 'PDF'])
def test_exportacion_y_descarga_siguen_funcionando_sin_convertir_el_dominio_a_texto(client, escenario, formato):
    e = escenario
    registrar_gasto(client, e)
    baja(client, e)
    generado = generar(client, e)
    r = client.post('/suministros/reportes-gastos/' + str(generado['id_reporte_gasto_acumulado']) + '/exportacion',
                    headers=e['headers']['admin'], json={'formato_exportacion': formato})
    assert r.status_code == 201, r.text
    descarga = client.get(r.json()['url_descarga'], headers=e['headers']['admin'])
    assert descarga.status_code == 200, descarga.text
    if formato == 'PDF':
        assert descarga.content.startswith(b'%PDF')
    else:
        assert b'monto_cop' in descarga.content


def test_productor_propietario_puede_generar_y_ajeno_no_accede_al_activo(client, escenario):
    e = escenario
    registrar_gasto(client, e)
    baja(client, e)
    assert_no_calculable(generar(client, e, actor='propietario'))
    r = client.post('/suministros/reportes-gastos', headers=e['headers']['ajeno'], json=cuerpo(e))
    assert r.status_code in (403, 404), r.text
    for actor in ('vet',):
        r = client.post('/suministros/reportes-gastos', headers=e['headers'][actor], json=cuerpo(e))
        assert r.status_code == 403, r.text
    assert client.post('/suministros/reportes-gastos', json=cuerpo(e)).status_code == 401


@pytest.mark.parametrize('cantidad', [0, 50])
def test_sin_gastos_distingue_cero_calculable_de_poblacion_cero(client, escenario, cantidad):
    e = escenario
    if cantidad == 0:
        baja(client, e)
    r = generar(client, e)
    assert r['sin_datos'] and Decimal(r['gasto_total_acumulado']) == 0
    if cantidad == 0:
        assert r['gasto_promedio_individuo'] == 'NO_CALCULABLE' and r['causa_no_calculable_promedio'] == CAUSA
    else:
        assert Decimal(r['gasto_promedio_individuo']) == 0 and r['causa_no_calculable_promedio'] is None


def test_fallo_despues_de_flush_revierte_snapshot_y_metadatos(client, db_session, escenario, monkeypatch):
    from src.shared.errors import ServiceUnavailableError
    from src.supplies.infrastructure.repositories.reporte_gasto_repository import SqlAlchemyReporteGastoRepository
    guardar = SqlAlchemyReporteGastoRepository.guardar
    def fallar(self, reporte):
        guardar(self, reporte)
        raise ServiceUnavailableError(code='SERVICIO_NO_DISPONIBLE', message='Fallo controlado tras guardar')
    monkeypatch.setattr(SqlAlchemyReporteGastoRepository, 'guardar', fallar)
    e = escenario
    registrar_gasto(client, e)
    baja(client, e)
    r = client.post('/suministros/reportes-gastos', headers=e['headers']['admin'], json=cuerpo(e))
    assert r.status_code == 503, r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo5.reporte_gastos_acumulados WHERE id_activo_biologico=:a'), {'a': e['activo']}).scalar_one() == 0
    assert db_session.execute(text('SELECT sum(costo_total_medicamento) FROM modulo5.registros_medicamentos WHERE id_activo_biologico=:a'), {'a': e['activo']}).scalar_one() == Decimal('50000')
