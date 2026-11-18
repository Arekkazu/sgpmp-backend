# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-14 | destroyerban     | INC-M05-353-G37 RF-80: A02c, A02d y A04 contra PostgreSQL real |
"""Regresión HTTP de INC-M05-353-G37 (TC-M05-G37 reintento 1) con triggers y FKs reales.

Reproduce los pasos de QA: suministro directo con fase abierta, historial, rechazo
sin fase, consolidar con el ciclo activo (A02c), historial con fechas invertidas
(A02d) y la revisión de campos mínimos de cada evento (A04).
"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m05_275_g37_auditoria_rechazos_integration import (  # noqa: F401 (fixtures)
    cerrar,
    escenario,
    montar,
    payload,
)

pytestmark = pytest.mark.integration

# Restricción 8 sobre lo que devuelve GET /suministros/auditoria.
_MINIMOS = {
    'SUMINISTRO_REGISTRADO': ('id_registro_suministro', 'id_tipo_suministro', 'costo_afectado', 'origen_precio'),
    'PRECIO_MANUAL_INGRESADO': ('id_registro_suministro', 'origen_precio'),
    'ACUMULADO_ACTUALIZADO': ('id_registro_suministro', 'costo_afectado'),
    'CICLO_CONSOLIDADO': ('costo_afectado',),
    'REPORTE_COSTOS_GENERADO': ('costo_afectado',),
    'REGISTRO_FALLIDO': ('id_tipo_suministro', 'numero_reintentos'),
}


def eventos(client, e, **filtros):
    r = client.get('/suministros/auditoria', headers=e['headers'],
                   params=dict(id_activo_biologico=e['activo'], registros_por_pagina=100) | filtros)
    assert r.status_code == 200, r.text
    return r.json()['items']


def test_a02c_consolidar_con_ciclo_activo_deja_evento_rechazado(client, escenario):
    e = escenario
    inicio = time.perf_counter()
    r = client.post(f"/suministros/nic41/ciclo/{e['fase']}/consolidar", headers=e['headers'])
    assert r.status_code == 409 and r.json()['error_code'] == 'CICLO_ACTIVO', r.text
    nuevos = eventos(client, e, tipo_operacion='CICLO_CONSOLIDADO')
    assert time.perf_counter() - inicio < 2
    evento, = nuevos
    assert evento['resultado'] == 'RECHAZADO' and evento['id_usuario'] == e['usuario']
    assert evento['id_gestion_fases'] == e['fase'] and evento['id_ciclo_productivo'] is not None
    assert evento['registro_incompleto'] and 'costo afectado' in evento['detalle_causa']
    assert len(evento['hash_integridad']) == 64


def test_a02d_historial_con_fechas_invertidas_deja_evento_rechazado(client, escenario):
    e = escenario
    inicio = time.perf_counter()
    r = client.get('/suministros/historial', headers=e['headers'], params={
        'id_activo_biologico': e['activo'], 'fecha_inicio_filtro': e['hoy'].isoformat(),
        'fecha_fin_filtro': (e['hoy'] - timedelta(days=5)).isoformat()})
    assert r.status_code == 422 and r.json()['error_code'] == 'COMBINACION_FILTROS_INVALIDA', r.text
    evento, = eventos(client, e, tipo_operacion='CONSULTA_HISTORIAL_EJECUTADA')
    assert time.perf_counter() - inicio < 2
    assert evento['resultado'] == 'RECHAZADO' and evento['id_usuario'] == e['usuario']
    assert 'fecha final del filtro es anterior' in evento['detalle_causa']
    assert evento['datos_nuevos']['filtros_aplicados']['id_activo_biologico'] == e['activo']


def test_a04_cada_evento_trae_sus_minimos_o_queda_incompleto(client, db_session, escenario):
    e = escenario
    assert client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e)).status_code == 200
    r = client.post('/suministros/costeo-directo', headers=e['headers'], json=payload(e, cantidad='-1'))
    assert r.status_code == 422, r.text
    assert client.get('/suministros/historial', headers=e['headers'],
                      params={'id_activo_biologico': e['activo']}).status_code == 200
    cerrar(db_session, e)
    assert client.post(f"/suministros/nic41/ciclo/{e['fase']}/consolidar", headers=e['headers']).status_code == 201

    vistos = eventos(client, e)
    tipos = {ev['tipo_operacion'] for ev in vistos}
    assert tipos >= {'SUMINISTRO_REGISTRADO', 'PRECIO_MANUAL_INGRESADO', 'ACUMULADO_ACTUALIZADO',
                     'REGISTRO_FALLIDO', 'CONSULTA_HISTORIAL_EJECUTADA', 'CICLO_CONSOLIDADO',
                     'REPORTE_COSTOS_GENERADO'}
    for ev in vistos:
        if ev['tipo_operacion'] in ('INSERT', 'UPDATE', 'DELETE', 'SELECT'):
            continue  # filas de los triggers DML, fuera del catálogo de RF-80
        faltan = [c for c in ('id_activo_biologico', 'id_ciclo_productivo') + _MINIMOS.get(ev['tipo_operacion'], ())
                  if ev[c] is None]
        assert bool(faltan) == bool(ev['registro_incompleto']), ev
        if faltan:
            assert 'Campos faltantes:' in ev['detalle_causa'], ev

    exitosos = {ev['tipo_operacion']: ev for ev in vistos if ev['resultado'] == 'EXITOSO'}
    registro = exitosos['SUMINISTRO_REGISTRADO']
    assert registro['id_tipo_suministro'] == 'SERVICIO_VETERINARIO' and registro['id_registro_suministro']
    assert exitosos['ACUMULADO_ACTUALIZADO']['id_registro_suministro'] == registro['id_registro_suministro']
    assert not registro['registro_incompleto'] and not exitosos['CONSULTA_HISTORIAL_EJECUTADA']['registro_incompleto']
    fallido, = (ev for ev in vistos if ev['tipo_operacion'] == 'REGISTRO_FALLIDO')
    assert fallido['id_tipo_suministro'] == 'SERVICIO_VETERINARIO' and not fallido['registro_incompleto']
