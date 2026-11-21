# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | RFC-012 RF-53/58: ingesta y caché del dashboard con un área de varias especies |
"""RFC-012 (N:M) en la BD: con varias especies en el área, fn_ingesta_telemetria (DB-06)
evalúa FUERA_DE_RANGO contra el umbral más restrictivo y el caché del dashboard (DB-12)
solo pone GRIS si ninguna especie del área tiene umbral para la variable."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import uuid

import pytest
from sqlalchemy import text

from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository

pytestmark = pytest.mark.integration

_spec = importlib.util.spec_from_file_location('dev41_nm', Path(__file__).with_name('test_dev41_alertas_telemetria.py'))
d41 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d41)


def _segunda_especie(db, ctx, *, valor_min, valor_max):
    """Otra especie del mismo grupo en la misma área, con su propio umbral para la variable."""
    usuario = db.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    especie = db.execute(text('''INSERT INTO modulo9.especies(nombre,descripcion,fecha_creacion,es_activo)
        VALUES(:n,'RFC-012 N:M',now(),true) RETURNING id_especie'''), {'n': 'NM ' + uuid.uuid4().hex[:10]}).scalar_one()
    if valor_min is not None:
        db.execute(text('''INSERT INTO modulo9.umbrales_ambientales
            (id_especie,id_variable_ambiental,unidad_medida,valor_min,valor_max,es_activo,fecha_actualizacion,id_usuario)
            VALUES(:e,:v,:u,:a,:b,true,now(),:uid)'''),
            {'e': especie, 'v': ctx['variable'], 'u': ctx['unidad'], 'a': valor_min, 'b': valor_max, 'uid': usuario})
    for e in (ctx['especie'], especie):
        db.execute(text('''INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie)
            VALUES(:a,:e) ON CONFLICT DO NOTHING'''), {'a': ctx['area'], 'e': e})
    db.commit()
    return especie


def _ingresar(db, ctx, valor, minutos):
    return d41.ingresar(db, ctx, valor, datetime.now(timezone.utc) - timedelta(minutes=minutos))


def test_fuera_de_rango_contra_el_umbral_mas_restrictivo(db_session):
    ctx = d41.preparar(db_session)  # especie A: 20-50
    _segunda_especie(db_session, ctx, valor_min=25, valor_max=40)  # especie B: 25-40
    assert _ingresar(db_session, ctx, 30, 3).estado_calidad == 'LECTURA_VALIDA'
    # 45 vale para A pero no para B: con las dos en el área, sale fuera de rango.
    assert _ingresar(db_session, ctx, 45, 2).estado_calidad == 'FUERA_DE_RANGO'
    assert _ingresar(db_session, ctx, 22, 1).estado_calidad == 'FUERA_DE_RANGO'


def test_especie_sin_umbral_no_restringe_y_el_cache_no_queda_gris(db_session):
    ctx = d41.preparar(db_session)
    _segunda_especie(db_session, ctx, valor_min=None, valor_max=None)  # B sin umbral
    assert _ingresar(db_session, ctx, 45, 1).estado_calidad == 'LECTURA_VALIDA'
    semaforo = db_session.execute(text(
        'SELECT estado_semaforo FROM modulo3.estados_actuales_sensores WHERE id_sensor=:s'), {'s': ctx['sensor']}).scalar_one()
    assert semaforo != 'GRIS'  # A tiene umbral para la variable


def test_area_sin_umbral_para_la_variable_queda_gris(db_session):
    ctx = d41.preparar(db_session)
    db_session.execute(text('UPDATE modulo9.umbrales_ambientales SET es_activo=false WHERE id_umbral_ambiental=:u'),
                       {'u': ctx['umbral']})
    _segunda_especie(db_session, ctx, valor_min=None, valor_max=None)
    assert _ingresar(db_session, ctx, 30, 1).estado_calidad == 'LECTURA_VALIDA'
    semaforo = db_session.execute(text(
        'SELECT estado_semaforo FROM modulo3.estados_actuales_sensores WHERE id_sensor=:s'), {'s': ctx['sensor']}).scalar_one()
    assert semaforo == 'GRIS'
