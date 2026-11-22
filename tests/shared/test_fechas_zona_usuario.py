# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Regla de fechas: entra en UTC y el día calendario es el de la zona del usuario."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

import src.shared.fechas as fechas
from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc
from src.shared.middlewares import RequestContextMiddleware


class _Dto(BaseDTO):
    fecha: FechaHoraUtc


def test_con_zona_se_convierte_a_utc():
    assert _Dto(fecha='2026-10-23T22:00:00-05:00').fecha == datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc)
    assert _Dto(fecha='2026-10-23T22:00:00+02:00').fecha.utcoffset() == timedelta(0)


def test_sin_zona_se_toma_como_utc():
    assert _Dto(fecha='2026-10-23T22:00:00').fecha == datetime(2026, 10, 23, 22, 0, tzinfo=timezone.utc)


def test_zona_invalida_o_ausente_es_utc():
    assert fechas.zona_desde_nombre(None) is timezone.utc
    assert fechas.zona_desde_nombre('Marte/Olympus') is timezone.utc
    assert fechas.zona_desde_nombre('../../etc/passwd') is timezone.utc


def test_el_dia_depende_de_la_zona(monkeypatch, en_colombia):
    instante = datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc)  # 23-oct 22:00 en Bogotá
    assert fechas.fecha_usuario(instante).day == 23
    token = fechas.establecer_zona_usuario('Asia/Tokyo')
    try:
        assert fechas.fecha_usuario(instante).day == 24
    finally:
        fechas._zona.reset(token)


def test_la_cabecera_llega_al_endpoint_y_la_query_queda_en_utc():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get('/x')
    def x(desde: Optional[FechaHoraUtc] = Query(default=None)):  # síncrono: corre en el threadpool
        return {'zona': str(fechas.zona_usuario()), 'desde': desde.isoformat() if desde else None}

    cliente = TestClient(app)
    r = cliente.get('/x', params={'desde': '2026-10-23T22:00:00-05:00'}, headers={'X-Zona-Horaria': 'America/Bogota'})
    assert r.json() == {'zona': 'America/Bogota', 'desde': '2026-10-24T03:00:00+00:00'}
    assert cliente.get('/x').json()['zona'] == 'UTC'


def test_limites_del_dia_en_la_zona_del_usuario(en_colombia):
    from datetime import date
    assert fechas.inicio_dia_usuario(date(2026, 10, 23)) == datetime(2026, 10, 23, 5, 0, tzinfo=timezone.utc)
    assert fechas.fin_dia_usuario(date(2026, 10, 23)) == datetime(2026, 10, 24, 4, 59, 59, 999999, tzinfo=timezone.utc)
    assert fechas.nombre_zona_usuario() == 'America/Bogota'


def test_sin_zona_los_limites_y_la_etiqueta_son_utc():
    from datetime import date
    assert fechas.inicio_dia_usuario(date(2026, 10, 23)) == datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)
    assert fechas.nombre_zona_usuario() == 'UTC'
    assert fechas.etiqueta_zona(fechas.en_zona_usuario(datetime(2026, 1, 1, tzinfo=timezone.utc))) == 'UTC'


def test_etiqueta_con_desfase(en_colombia):
    assert fechas.etiqueta_zona(fechas.en_zona_usuario(datetime(2026, 1, 1, tzinfo=timezone.utc))) == 'UTC-05:00'
