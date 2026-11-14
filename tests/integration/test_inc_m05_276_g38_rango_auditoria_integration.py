# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-276-G38 RF-80: verificar rangos, formatos, límites inclusivos y RBAC con PostgreSQL real. |
"""Contrato de auditoría con JWT real, sgpmp_app y timestamps persistidos."""
from __future__ import annotations

import csv
import importlib
import io
import pkgutil
from datetime import datetime, timezone

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
    from src.supplies.infrastructure.routers.auditoria_suministros_router import router
    if not any(getattr(r, 'path', None) == '/suministros/auditoria' for r in integration_app.routes):
        integration_app.include_router(router)
        integration_app.openapi_schema = None


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers, montar, monkeypatch):
    from src.supplies.infrastructure.repositories.auditoria_suministro_read_repository import (
        SqlAlchemyAuditoriaSuministroReadRepository,
    )
    usuarios = {rol: crear_usuario_db(id_rol=rol) for rol in (1, 2, 3, 5, 8)}
    headers = {rol: crear_auth_headers(usuario) for rol, usuario in usuarios.items()}
    ids = []
    for hora in (10, 11, 12):
        ids.append(db_session.execute(text("""
            INSERT INTO modulo5.auditorias_suministros(
                entidad_afectada,tipo_operacion,id_usuario,resultado,fecha_evento,fecha_emision,
                clasificacion_registro,retencion_aplicable,numero_reintentos,detalle_causa)
            VALUES('registro_suministro','REGISTRO_FALLIDO',:u,'RECHAZADO',:f,:f,
                   'TECNICO','1 año',0,'Intento controlado para probar filtros de fechas')
            RETURNING id_auditoria_suministro
        """), {'u': usuarios[1]['id_usuario'], 'f': datetime(2026, 11, 1, hora, tzinfo=timezone.utc)}).scalar_one())
    db_session.commit()
    consultas = []
    consultar = SqlAlchemyAuditoriaSuministroReadRepository.consultar
    def observar(self, filtros):
        consultas.append(filtros)
        return consultar(self, filtros)
    monkeypatch.setattr(SqlAlchemyAuditoriaSuministroReadRepository, 'consultar', observar)
    return dict(headers=headers, usuario=usuarios[1]['id_usuario'], ids=ids, consultas=consultas)


def parametros(e, **cambios):
    return dict(id_usuario=e['usuario'], fecha_desde='2026-11-01T10:00:00Z',
                fecha_hasta='2026-11-01T11:00:00Z') | cambios


@pytest.mark.parametrize('rol', [1, 5, 8])
def test_lector_autorizado_rechaza_rango_invertido_sin_consultar(client, escenario, rol):
    e = escenario
    r = client.get('/suministros/auditoria', headers=e['headers'][rol],
                   params=parametros(e, fecha_desde='2026-11-02T00:00:00Z'))
    assert r.status_code == 400 and r.json()['error_code'] == 'VAL_ENTRADA', r.text
    assert 'Corrige' in r.json()['message'] and r.json()['fields'][0]['field'] == 'fecha_hasta'
    assert e['consultas'] == []


@pytest.mark.parametrize('formato', ['csv', 'xlsx', 'pdf'])
def test_exportacion_rechaza_rango_invertido_antes_de_leer_y_generar_archivo(client, escenario, formato):
    e = escenario
    r = client.get('/suministros/auditoria/exportar', headers=e['headers'][1],
                   params=parametros(e, fecha_desde='2026-11-02T00:00:00Z', formato=formato))
    assert r.status_code == 400 and r.json()['error_code'] == 'VAL_ENTRADA', r.text
    assert 'content-disposition' not in r.headers and e['consultas'] == []


@pytest.mark.parametrize('ruta', ['/suministros/auditoria', '/suministros/auditoria/exportar'])
@pytest.mark.parametrize('campo', ['fecha_desde', 'fecha_hasta'])
def test_fecha_malformada_se_rechaza_separadamente(client, escenario, ruta, campo):
    e = escenario
    r = client.get(ruta, headers=e['headers'][1], params=parametros(e, **{campo: 'no-es-una-fecha'}))
    assert r.status_code == 400 and r.json()['error_code'] == 'VAL_ENTRADA', r.text
    assert e['consultas'] == []


def test_rango_valido_filtra_inclusivamente_y_conserva_paginacion(client, escenario):
    e = escenario
    p = parametros(e, registros_por_pagina=1)
    r = client.get('/suministros/auditoria', headers=e['headers'][1], params=p)
    assert r.status_code == 200, r.text
    assert r.json()['total'] == 2 and r.json()['items'][0]['id_auditoria_suministro'] == e['ids'][1]
    siguiente = client.get('/suministros/auditoria', headers=e['headers'][1], params=p | {'pagina': 2})
    assert siguiente.status_code == 200 and siguiente.json()['items'][0]['id_auditoria_suministro'] == e['ids'][0]


@pytest.mark.parametrize('desde,hasta,ids_indices', [
    ('2026-11-01T10:00:00Z', '2026-11-01T10:00:00Z', [0]),
    ('2026-11-01T05:00:00-05:00', '2026-11-01T11:00:00+01:00', [0]),
    ('2026-11-01T10:00:00', '2026-11-01T10:00:00Z', [0]),
    (None, '2026-11-01T10:00:00Z', [0]),
    ('2026-11-01T12:00:00Z', None, [2]),
    (None, None, [2, 1, 0]),
])
def test_igualdad_zonas_y_extremos_opcionales(client, escenario, desde, hasta, ids_indices):
    e = escenario
    p = {'id_usuario': e['usuario']}
    if desde is not None:
        p['fecha_desde'] = desde
    if hasta is not None:
        p['fecha_hasta'] = hasta
    r = client.get('/suministros/auditoria', headers=e['headers'][1], params=p)
    assert r.status_code == 200, r.text
    assert [x['id_auditoria_suministro'] for x in r.json()['items']] == [e['ids'][i] for i in ids_indices]


def test_desfase_horario_se_compara_por_instante_no_por_hora_escrita(client, escenario):
    e = escenario
    r = client.get('/suministros/auditoria', headers=e['headers'][1], params=parametros(
        e, fecha_desde='2026-11-01T10:00:00-05:00', fecha_hasta='2026-11-01T11:00:00Z'))
    assert r.status_code == 400 and e['consultas'] == [], r.text


@pytest.mark.parametrize('ruta', ['/suministros/auditoria', '/suministros/auditoria/exportar'])
def test_consulta_valida_sin_coincidencias_conserva_200(client, escenario, ruta):
    e = escenario
    r = client.get(ruta, headers=e['headers'][1], params=parametros(
        e, fecha_desde='2026-11-02T00:00:00Z', fecha_hasta='2026-11-03T00:00:00Z'))
    assert r.status_code == 200, r.text
    if ruta.endswith('/exportar'):
        assert list(csv.DictReader(io.StringIO(r.text))) == []
    else:
        assert r.json()['total'] == 0 and r.json()['items'] == []
    assert len(e['consultas']) == 1


def test_csv_y_detalle_conservan_los_eventos_filtrados(client, escenario):
    e = escenario
    r = client.get('/suministros/auditoria/exportar', headers=e['headers'][5], params=parametros(e))
    assert r.status_code == 200 and 'text/csv' in r.headers['content-type'], r.text
    filas = list(csv.DictReader(io.StringIO(r.text)))
    assert [int(x['id_auditoria_suministro']) for x in filas] == e['ids'][1::-1]
    detalle = client.get('/suministros/auditoria/' + str(e['ids'][0]), headers=e['headers'][8])
    assert detalle.status_code == 200 and detalle.json()['id_usuario'] == e['usuario'], detalle.text


@pytest.mark.parametrize('rol', [2, 3])
def test_roles_sin_permiso_siguen_en_403_aun_con_rango_invalido(client, escenario, rol):
    e = escenario
    for ruta in ('/suministros/auditoria', '/suministros/auditoria/exportar'):
        r = client.get(ruta, headers=e['headers'][rol], params=parametros(e, fecha_desde='2026-11-02T00:00:00Z'))
        assert r.status_code == 403, r.text
    assert e['consultas'] == []


def test_jwt_ausente_conserva_401_sin_consultar(client, escenario):
    e = escenario
    r = client.get('/suministros/auditoria', params=parametros(e, fecha_desde='2026-11-02T00:00:00Z'))
    assert r.status_code == 401 and e['consultas'] == [], r.text
