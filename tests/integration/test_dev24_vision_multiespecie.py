# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-23 | Leandro | DEV-24 RF-24: probar DB-06 real, HTTP, atomicidad, concurrencia y RLS en PostgreSQL. |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016: estado_calibracion con el catálogo de DB-09 |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: observaciones sembradas ya evaluadas |
"""Requiere DB-06 (#613) y nivel_criticidad de DB-07 (#614), sin crear tablas alternativas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib
import json
import pkgutil
from threading import Event
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import (
    CalibrarVisionUseCase, ConsultarCalibracionVisionUseCase,
)
from src.configuration.infrastructure.adapters.observacion_vision_m03_adapter import ObservacionVisionM03Adapter
from src.configuration.infrastructure.dto.calibrar_vision_dto import CalibrarVisionDTO
from src.configuration.infrastructure.repositories.calibracion_vision_repository import (
    SqlAlchemyCalibracionVisionRepository, SqlAlchemyLineaBaseVisionRepository,
)
from src.configuration.infrastructure.repositories.camara_area_repository import SqlAlchemyCamaraAreaRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.routers.calibracion_vision_router import router
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.errors import BusinessRuleError, InfrastructureError
from tests.integration.test_dev07_vision_d4 import hardware

pytestmark = pytest.mark.integration
RUTA = '/configuracion/calibraciones-vision'


@pytest.fixture(autouse=True)
def modelos(integration_engine):
    for nombre in ('configuration', 'biological_assets', 'telemetry', 'identity_access', 'prediction'):
        paquete = importlib.import_module(f'src.{nombre}.infrastructure.models')
        for item in pkgutil.iter_modules(paquete.__path__, paquete.__name__ + '.'):
            importlib.import_module(item.name)
    with integration_engine.connect() as c:
        puente = c.execute(text("SELECT to_regclass('modulo9.infraestructuras_especies')")).scalar()
        criticidad = c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_schema='modulo9' AND table_name='infraestructuras' AND column_name='nivel_criticidad'")).scalar()
    if not puente or not criticidad:
        pytest.skip('Faltan las migraciones oficiales DB-06/DB-07; el test no modifica el esquema.')


def preparar(db, usuario, cantidad=2):
    equipo = hardware(db)
    especies = []
    for _ in range(cantidad):
        nombre = 'Vision ' + ''.join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex)
        especie = db.execute(text('''INSERT INTO modulo9.especies
            (nombre,fecha_creacion,es_activo,grupo_manejo,densidad_maxima_por_especie)
            VALUES (:nombre,now(),true,'AVES',10) RETURNING id_especie'''), {'nombre': nombre}).scalar_one()
        db.execute(text('''INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie)
            VALUES (:area,:especie)'''), {'area': equipo['area'], 'especie': especie})
        especies.append(especie)
    db.execute(text("UPDATE modulo9.infraestructuras SET tipo_modelo_asignado='MODELO_AVES' WHERE id_infraestructura=:area"), equipo)
    inicio = datetime.now(timezone.utc) - timedelta(days=1)
    for i in range(60):
        db.execute(text('''INSERT INTO modulo3.observaciones_vision
            (id_dispositivo_iot,id_infraestructura,fecha_observacion,cobertura_ventana,cantidad_tracks,
             cantidad_tracks_perdidos,fps_efectivo,estado_calibracion,json_vector,indice_calidad_vision,
             clasificacion_calidad,es_apto_para_ia,es_confianza_baja,fecha_evaluacion_calidad)
            VALUES (:device,:area,:fecha,.95,20,0,25,'CALIBRADO',  -- catálogo de DB-09

             CAST(:vector AS jsonb),95,'OPTIMA',true,false,now())'''),  # ya evaluada (RF-62)
            {**equipo, 'fecha': inicio + timedelta(minutes=i),
             'vector': json.dumps({'densidad_actividad': .5, 'dispersion_espacial': 2.4, 'tasa_movimiento': 1.8})})
    db.commit()
    return {**equipo, 'especies': especies, 'usuario': usuario, 'inicio': inicio, 'fin': inicio + timedelta(hours=2)}


@pytest.fixture
def datos(db_session, crear_usuario_db):
    rol = db_session.execute(text('SELECT id_rol FROM modulo1.roles WHERE es_protegido LIMIT 1')).scalar_one()
    usuario = crear_usuario_db(id_rol=rol)
    return preparar(db_session, usuario)


def dto(datos):
    return CalibrarVisionDTO(modo_calibracion='VISION', area_id=datos['area'],
        ventana_observacion={'inicio': datos['inicio'], 'fin': datos['fin']})


def caso(db):
    return CalibrarVisionUseCase(db, SqlAlchemyInfraestructuraRepository(db), SqlAlchemyCamaraAreaRepository(db),
        ObservacionVisionM03Adapter(db), SqlAlchemyCalibracionVisionRepository(db),
        SqlAlchemyLineaBaseVisionRepository(db), SqlAlchemyEventoRepository(db))


def ejecutar(db, datos):
    return caso(db).execute(dto(datos), SimpleNamespace(id_usuario=datos['usuario']['id_usuario']))


def estado(db, area):
    return [tuple(r) for r in db.execute(text('''SELECT id_especie,id_calibracion_vision,json_valor::text
        FROM modulo9.lineas_base_vision WHERE id_infraestructura=:a ORDER BY id_especie'''), {'a': area})]


def historial(db, area):
    return db.execute(text('''SELECT id_especie,estado,json_linea_base FROM modulo9.calibraciones_vision
        WHERE id_infraestructura=:a ORDER BY id_calibracion_vision'''), {'a': area}).all()


def test_dos_especies_persisten_dos_pares_recalibracion_conserva_historial(db_session, datos):
    primero = ejecutar(db_session, datos)
    assert [c.id_especie for c in primero] == datos['especies']
    assert len(estado(db_session, datos['area'])) == 2
    segundo = ejecutar(db_session, datos)
    assert len(historial(db_session, datos['area'])) == 4
    assert {r[1] for r in estado(db_session, datos['area'])} == {c.id_calibracion_vision for c in segundo}
    assert {c.id_calibracion_vision for c in primero}.isdisjoint(c.id_calibracion_vision for c in segundo)
    consulta = ConsultarCalibracionVisionUseCase(caso(db_session).infraestructura_repo,
        caso(db_session).calibracion_repo, caso(db_session).linea_base_repo)
    assert len(consulta.obtener_linea_base_vigente(datos['area'])) == 2
    assert consulta.obtener_linea_base_vigente(datos['area'], especie_id=datos['especies'][1]).id_especie == datos['especies'][1]


def test_regresion_mono_usa_db06_sin_id_especie_en_infraestructura(db_session, crear_usuario_db):
    datos = preparar(db_session, crear_usuario_db(), cantidad=1)
    resultado = ejecutar(db_session, datos)
    assert resultado.id_especie == datos['especies'][0]
    assert len(historial(db_session, datos['area'])) == len(estado(db_session, datos['area'])) == 1


@pytest.mark.parametrize('falla', ['guardar', 'publicar', 'auditar'])
def test_segundo_par_fallido_revierte_todo_y_conserva_ambas_vigentes(db_session, datos, monkeypatch, falla):
    ejecutar(db_session, datos)
    anteriores = estado(db_session, datos['area'])
    db_session.commit()
    repositorio, metodo = {
        'guardar': (SqlAlchemyCalibracionVisionRepository, 'guardar'),
        'publicar': (SqlAlchemyLineaBaseVisionRepository, 'publicar'),
        'auditar': (SqlAlchemyEventoRepository, 'registrar'),
    }[falla]
    original = getattr(repositorio, metodo)
    def fallar(repo, *args, **kw):
        especie = kw['detalle']['id_especie'] if falla == 'auditar' else args[0].id_especie
        if especie == datos['especies'][1]:
            raise RuntimeError('fallo inyectado segundo par')
        return original(repo, *args, **kw)
    monkeypatch.setattr(repositorio, metodo, fallar)
    with pytest.raises((RuntimeError, InfrastructureError)):
        ejecutar(db_session, datos)
    assert estado(db_session, datos['area']) == anteriores
    assert len(historial(db_session, datos['area'])) == 2


def test_datos_insuficientes_conservan_vigentes_y_dejan_dos_fallidas_sql_null(db_session, datos):
    ejecutar(db_session, datos)
    anteriores = estado(db_session, datos['area'])
    solicitud = dto(datos)
    solicitud.ventana_observacion.fin = datos['inicio'] + timedelta(minutes=1)
    with pytest.raises(BusinessRuleError) as exc:
        caso(db_session).execute(solicitud, SimpleNamespace(id_usuario=datos['usuario']['id_usuario']))
    assert exc.value.code == 'LINEA_BASE_NO_CALCULADA'
    assert estado(db_session, datos['area']) == anteriores
    assert [(r.estado, r.json_linea_base) for r in historial(db_session, datos['area'])[2:]] == [('FALLIDA', None)] * 2


def test_observaciones_de_camara_trasladada_no_se_mezclan(db_session, datos):
    otra = hardware(db_session)
    db_session.execute(text('''UPDATE modulo3.observaciones_vision SET id_infraestructura=:otra
        WHERE id_dispositivo_iot=:device'''), {'otra': otra['area'], 'device': datos['device']})
    muestras = ObservacionVisionM03Adapter(db_session).listar([datos['device']], datos['inicio'], datos['fin'],
        id_infraestructura=datos['area'])
    assert muestras == []
    with pytest.raises(BusinessRuleError):
        ejecutar(db_session, datos)
    assert not estado(db_session, datos['area'])


@pytest.fixture
def vision_app(integration_app):
    integration_app.include_router(router)
    return integration_app


@pytest.fixture
def vision_client(vision_app, client):
    return client


def test_http_autenticado_crea_y_consulta_colecciones_y_mantiene_modo_obligatorio(vision_client, crear_auth_headers, datos):
    headers = crear_auth_headers(datos['usuario'])
    body = dto(datos).model_dump(mode='json')
    respuesta = vision_client.post(RUTA, json=body, headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()['total'] == 2
    assert {r['especie_id'] for r in respuesta.json()['items']} == set(datos['especies'])
    lineas = vision_client.get(RUTA + '/linea-base', params={'area_id': datos['area']}, headers=headers)
    assert lineas.status_code == 200 and lineas.json()['total'] == 2, lineas.text
    una = vision_client.get(RUTA + '/linea-base', params={'area_id': datos['area'], 'especie_id': datos['especies'][1]}, headers=headers)
    assert una.status_code == 200 and una.json()['especie_id'] == datos['especies'][1], una.text
    historico = vision_client.get(RUTA, params={'area_id': datos['area']}, headers=headers)
    assert historico.status_code == 200 and historico.json()['total'] == 2
    body.pop('modo_calibracion')
    assert vision_client.post(RUTA, json=body, headers=headers).status_code == 400
    assert vision_client.post(RUTA, json=body).status_code == 401


def test_http_productor_no_puede_calibrar_y_ingeniero_no_ve_finca_ajena(
    vision_client, db_session, crear_usuario_db, crear_auth_headers, datos,
):
    roles = dict(db_session.execute(text('SELECT nombre_rol,id_rol FROM modulo1.roles')).all())
    productor = crear_usuario_db(id_rol=roles['Productor'])
    headers = crear_auth_headers(productor)
    rechazo = vision_client.post(RUTA, json=dto(datos).model_dump(mode='json'), headers=headers)
    assert rechazo.status_code == 403, rechazo.text
    # No se alteran permisos ni se falsifica el resultado de la compuerta RBAC.
    ingeniero = crear_usuario_db(id_rol=roles['Ingeniero de Campo'])
    headers = crear_auth_headers(ingeniero)
    rechazo = vision_client.post(RUTA, json=dto(datos).model_dump(mode='json'), headers=headers)
    assert rechazo.status_code == 404, rechazo.text
    assert not estado(db_session, datos['area'])


def test_http_ingeniero_asignado_calibra_sin_permiso_de_editar_infraestructura(
    vision_client, db_session, crear_usuario_db, crear_auth_headers, datos,
):
    rol = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE lower(nombre_rol)='ingeniero de campo'")).scalar_one()
    ingeniero = crear_usuario_db(id_rol=rol)
    finca = db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'), {'a': datos['area']}).scalar_one()
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca,es_activo) VALUES (:u,:f,true)'),
        {'u': ingeniero['id_usuario'], 'f': finca})
    headers = crear_auth_headers(ingeniero)
    respuesta = vision_client.post(RUTA, json=dto(datos).model_dump(mode='json'), headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()['total'] == 2


def test_historial_sigue_inmutable_y_puente_mantiene_force_rls(db_session, datos):
    ejecutar(db_session, datos)
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text('DELETE FROM modulo9.calibraciones_vision WHERE id_infraestructura=:a'), {'a': datos['area']})
    assert len(historial(db_session, datos['area'])) == 2
    flags = db_session.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='modulo9.infraestructuras_especies'::regclass")).one()
    assert flags == (True, True)
    assert not db_session.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname='sgpmp_app'")).scalar_one()


def test_publicaciones_concurrentes_se_serializan_desde_el_primer_par(integration_engine):
    # Los trabajadores requieren datos confirmados. Solo se permite esta prueba
    # en una base local desechable DEV-24; los demas tests usan rollback exterior.
    if integration_engine.url.host not in {'127.0.0.1', 'localhost'} or integration_engine.url.database != 'sgpmp_dev24_test':
        pytest.skip('Concurrencia requiere la base local desechable sgpmp_dev24_test.')
    with Session(integration_engine) as db:
        uid = db.execute(text("SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico='servicio.sistema@sgpmp.local'")).scalar_one()
        datos = preparar(db, {'id_usuario': uid})
    primero_bloqueado, segundo_iniciado, liberar = Event(), Event(), Event()
    pids = {}
    def primero():
        with Session(integration_engine) as db:
            pids['primero'] = db.execute(text('SELECT pg_backend_pid()')).scalar_one()
            uc = caso(db)
            original = uc.calibracion_repo.guardar
            def guardar(cal):
                primero_bloqueado.set()
                assert liberar.wait(15)
                return original(cal)
            uc.calibracion_repo.guardar = guardar
            return uc.execute(dto(datos), SimpleNamespace(id_usuario=uid))
    def segundo():
        with Session(integration_engine) as db:
            pids['segundo'] = db.execute(text('SELECT pg_backend_pid()')).scalar_one()
            segundo_iniciado.set()
            return ejecutar(db, datos)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(primero)
        assert primero_bloqueado.wait(15)
        f2 = pool.submit(segundo)
        assert segundo_iniciado.wait(15)
        try:
            # Comprueba la espera en PostgreSQL, sin confiar en la velocidad
            # de planificación de los hilos ni en pausas arbitrarias.
            with integration_engine.connect() as c:
                for _ in range(100):
                    bloqueadores = c.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid': pids['segundo']}).scalar_one()
                    if pids['primero'] in bloqueadores:
                        break
                    Event().wait(.05)
            assert pids['primero'] in bloqueadores
        finally:
            liberar.set()
        r1, r2 = f1.result(timeout=20), f2.result(timeout=20)
    with Session(integration_engine) as db:
        assert len(historial(db, datos['area'])) == 4
        assert {r[1] for r in estado(db, datos['area'])} == {c.id_calibracion_vision for c in r2}
        assert {c.id_calibracion_vision for c in r1}.isdisjoint(c.id_calibracion_vision for c in r2)
