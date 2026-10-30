# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-58/59: combinaciones, variables, E3, series, filtros y 422 |
# | 2026-10-30 | Arekkazu | INC-M04-225-G112 RF-59: categoria_variable, estado_dato y origen_dato solos |
"""RF-59 (INC-M03-180..193): combinaciones de la Restricción 12, varias variables,
estado vacío, series, filtros de área/activo y 422 en parámetros inválidos."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.shared.errors import BusinessRuleError
from src.telemetry.application.use_cases.monitoreo.consultar_historial_use_case import (
    MENSAJE_SIN_RESULTADOS,
    ConsultarHistorialUseCase,
)
from src.telemetry.domain.entities.monitoreo import FiltrosHistorial, LecturaHistorica
from src.telemetry.infrastructure.repositories.historial_telemetria_repository import (
    _COUNT_HISTORIAL,
    _build_query,
)


def _lectura(i, variable='Temperatura Ambiental', valor='20'):
    return LecturaHistorica(
        id_telemetria=i, id_sensor=7, nombre_sensor='S7', id_variable=9, tipo_variable=variable,
        categoria_variable='AMBIENTAL', valor=Decimal(valor), valor_ajustado=None, unidad_medida='°C',
        timestamp_captura=datetime(2026, 10, 20, 10, i, tzinfo=timezone.utc), estado_calidad='LECTURA_VALIDA',
        estado_semaforo_historico='GRIS', origen_dato='TIEMPO_REAL', id_infraestructura=1, infraestructura='A',
        finca='F', id_activo_biologico=None, especie=None, id_especie=None, id_alerta=None,
        nivel_bateria_pct=None, calidad_senal_rssi=None, calidad_senal_snr=None,
    )


class _Repo:
    def __init__(self, lecturas=(), desconocidas=(), alertas=()):
        self.lecturas, self.desconocidas, self.alertas = list(lecturas), list(desconocidas), list(alertas)
        self.consultado = False

    def consultar(self, f):
        self.consultado = True
        return self.lecturas, len(self.lecturas)

    def calcular_estadisticas(self, f):
        return []

    def detectar_vacios(self, f):
        return []

    def alertas_correlacionadas(self, f):
        return self.alertas

    def variables_no_reconocidas(self, tipos):
        return [t for t in tipos if t in self.desconocidas]


class _Umbral:
    def obtener_umbral_vigente(self, **kw):
        return None


def _filtros(**cambios):
    base = dict(fecha_inicio=date(2026, 10, 18), fecha_fin=date(2026, 10, 25))
    base.update(cambios)
    return FiltrosHistorial(**base)


def _ejecutar(repo, **filtros):
    return ConsultarHistorialUseCase(repo, _Umbral()).execute(_filtros(**filtros))


@pytest.mark.parametrize('filtros', [
    dict(), dict(tipo_variable='TEMPERATURA_AMBIENTAL'), dict(sensor_id=1), dict(id_infraestructura=1),
    dict(especie='Tilapia'), dict(tipo_variable='X', id_infraestructura=1), dict(tipo_variable='X', especie='E'),
    dict(sensor_id=1, estado_dato='LECTURA_VALIDA'), dict(categoria_variable='AMBIENTAL', id_infraestructura=1),
    dict(id_activo_biologico=829),
    # INC-M04-225-G112 (#860): filtros opcionales de las Entradas, usados solos.
    dict(categoria_variable='HIDRICA'), dict(estado_dato='FUERA_DE_RANGO'), dict(origen_dato='BUFFER_LOCAL'),
])
def test_combinaciones_de_la_restriccion_12_se_aceptan(filtros):
    _ejecutar(_Repo(), **filtros)


@pytest.mark.parametrize('filtros', [
    dict(categoria_variable='AMBIENTAL', sensor_id=1, estado_dato='LECTURA_VALIDA', id_infraestructura=1),
    dict(origen_dato='TIEMPO_REAL', especie='E'),
    dict(sensor_id=1, id_infraestructura=1),
])
def test_combinacion_no_listada_se_rechaza_con_422_sin_consultar(filtros):
    repo = _Repo()
    with pytest.raises(BusinessRuleError) as exc:
        _ejecutar(repo, **filtros)
    assert exc.value.status_code == 422 and exc.value.code == 'COMBINACION_FILTROS_INVALIDA'
    assert 'Combinaciones permitidas' in exc.value.message and not repo.consultado


def test_variable_desconocida_es_422_y_no_cero_lecturas():
    with pytest.raises(BusinessRuleError) as exc:
        _ejecutar(_Repo(desconocidas=['VARIABLE_X']), tipo_variable='VARIABLE_X')
    assert exc.value.code == 'TIPO_VARIABLE_INVALIDO' and exc.value.status_code == 422


def test_varias_variables_por_coma_o_repetidas_y_una_serie_por_variable():
    assert _filtros(tipo_variable='A, B,A').tipo_variable == ['A', 'B']
    assert _filtros(tipo_variable=['A', 'B,C']).tipo_variable == ['A', 'B', 'C']
    repo = _Repo([_lectura(1), _lectura(2, 'Humedad Relativa', '80'), _lectura(3)])
    _, _, _, meta = _ejecutar(repo, tipo_variable='Temperatura Ambiental,Humedad Relativa')
    series = {s['tipo_variable']: s for s in meta['series']}
    assert set(series) == {'Temperatura Ambiental', 'Humedad Relativa'}
    assert [p['valor'] for p in series['Temperatura Ambiental']['puntos']] == [Decimal('20'), Decimal('20')]


def test_sin_resultados_el_aviso_orienta_al_usuario():
    _, _, _, meta = _ejecutar(_Repo(), sensor_id=1)
    assert meta['aviso'] == MENSAJE_SIN_RESULTADOS
    assert MENSAJE_SIN_RESULTADOS.startswith('No se encontraron registros para los filtros seleccionados')


def test_alertas_correlacionadas_solo_con_incluir_alertas():
    from src.telemetry.domain.entities.monitoreo import AlertaCorrelacionada
    alerta = AlertaCorrelacionada(38, 'ESTRES_TERMICO', 'LEVE', None, 'TEMPERATURA_AMBIENTAL', 'RESUELTA')
    assert _ejecutar(_Repo(alertas=[alerta]), sensor_id=467)[3]['alertas_correlacionadas'] == []
    meta = _ejecutar(_Repo(alertas=[alerta]), sensor_id=467, incluir_alertas=True)[3]
    assert meta['alertas_correlacionadas'][0]['estado_final'] == 'RESUELTA'


def test_filtros_de_area_activo_y_codigo_de_variable_en_sql():
    sql, params = _build_query(
        _filtros(id_infraestructura=389, id_activo_biologico=829, tipo_variable='temperatura_corporal'),
        _COUNT_HISTORIAL,
    )
    assert 'COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura) = :id_infraestructura' in sql
    assert 'vl_lat.id_activo_biologico = :id_activo_biologico' in sql
    assert params['tipos_codigo'] == ['TEMP_CORPORAL']


def test_la_ruta_que_declara_422_lo_responde_y_las_demas_conservan_400():
    from fastapi import FastAPI, Query
    from fastapi.testclient import TestClient

    from src.shared.error_handlers import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)

    @app.get('/con-422', openapi_extra={'x-codigo-validacion': 422})
    def con_422(fecha_fin: date = Query(), por_pagina: int = Query(default=1, le=500)):
        return {}

    @app.get('/sin-422')
    def sin_422(fecha_fin: date = Query()):
        return {}

    cliente = TestClient(app)
    faltante = cliente.get('/con-422')
    assert faltante.status_code == 422 and faltante.json()['error_code'] == 'VAL_ENTRADA'
    assert faltante.json()['fields'][0]['field'] == 'fecha_fin'
    assert cliente.get('/con-422', params={'fecha_fin': '2026-10-20', 'por_pagina': 501}).status_code == 422
    assert cliente.get('/sin-422').status_code == 400


def test_historial_y_auditoria_m04_declaran_422_en_el_contrato():
    import main
    rutas = main.app.openapi()['paths']
    for ruta in ('/iot/monitoreo/historial', '/prediccion/auditoria'):
        operacion = rutas[ruta]['get']
        assert operacion['x-codigo-validacion'] == 422 and '422' in operacion['responses']
    assert 'correlacion_id' in [p['name'] for p in rutas['/prediccion/auditoria']['get']['parameters']]
