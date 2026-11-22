# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-243-G169 RF-62: ERROR_CALIBRACION corre fases 2, 3 y 5; versión de límites en FUERA_DE_RANGO |
"""INC-M03-243-G169 (#885, TC-M03-321/322) con PostgreSQL real y el router HTTP.

R7 de RF-62: con estado_dato_rf53 = ERROR_CALIBRACION se omite solo la fase 4 (drift);
congelado, outlier y gap corren sobre la serie cruda. Un sensor sin calibración solo
tiene lecturas ERROR_CALIBRACION: tomar únicamente las LECTURA_VALIDA lo dejaba
siempre en serie_insuficiente / INDETERMINADA.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m03_104_g165_motor_calidad import equipo_g165, rutas_g165  # noqa: F401

pytestmark = pytest.mark.integration

_INSERTAR = text('''INSERT INTO modulo3.telemetrias
    (id_sensor,id_variable,id_dispositivo_iot,valor_crudo,valor_ajustado,timestamp_captura,
     timestamp_procesamiento,origen,estado_calidad,calibrado,categoria_variable,unidad_medida,
     valor_agregado,tipo_dato,metadatos,frecuencia_muestreo_min)
    VALUES (:s,9,:d,:v,NULL,:ts,now(),'TIEMPO_REAL',CAST(:estado AS modulo3.enum_telemetria_estado_calidad),
            false,'AMBIENTAL','°C',false,'CRUDO','{}',45)
    RETURNING id_telemetria''')


def _serie_sin_calibracion(db, e):
    captura = db.execute(text("SELECT now() - interval '1 minute'")).scalar_one()
    for i in range(20):
        db.execute(_INSERTAR, {'s': e['sensor'], 'd': e['dispositivo'], 'v': Decimal('21.5') if i % 2 else Decimal('22.5'),
                               'ts': captura - timedelta(minutes=95 + 45 * i), 'estado': 'ERROR_CALIBRACION'})
    evaluada = db.execute(_INSERTAR, {'s': e['sensor'], 'd': e['dispositivo'], 'v': Decimal('25.5'),
                                      'ts': captura, 'estado': 'ERROR_CALIBRACION'}).scalar_one()
    db.commit()
    return evaluada


def test_error_calibracion_con_serie_completa_no_es_indeterminada(client, db_session, equipo_g165):
    e = equipo_g165
    lectura = _serie_sin_calibracion(db_session, e)

    r = client.post(f'/iot/calidad/{lectura}/evaluar', headers=e['headers'])

    assert r.status_code == 201, r.text
    ev = r.json()
    flags = ev['flags_detectados']
    assert 'serie_insuficiente' not in flags
    assert ev['clasificacion_calidad'] != 'INDETERMINADA' and ev['indice_calidad'] is not None
    assert flags['calibracion_no_disponible']['activo'] is True
    assert flags['gap_temporal_anomalo']['activo'] is True      # fase 5: 95 min > 2 × 45 min
    assert 'posible_drift' not in flags                           # fase 4 omitida


def test_fuera_de_rango_persiste_version_de_limites_fisicos(client, db_session, equipo_g165):
    e = equipo_g165
    captura = db_session.execute(text("SELECT now() - interval '1 minute'")).scalar_one()
    lectura = db_session.execute(_INSERTAR, {'s': e['sensor'], 'd': e['dispositivo'], 'v': Decimal('50'),
                                             'ts': captura, 'estado': 'FUERA_DE_RANGO'}).scalar_one()
    db_session.commit()

    r = client.post(f'/iot/calidad/{lectura}/evaluar', headers=e['headers'])

    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev['indice_calidad'] == 0 and ev['clasificacion_calidad'] == 'NO_APTO'
    assert ev['flags_detectados']['fuera_de_rango_rf53']['activo'] is True
    assert ev['version_limites_fisicos_aplicada'] and ev['version_limites_fisicos_aplicada'].startswith('va9:')
    guardada = db_session.execute(text('''SELECT version_limites_fisicos_aplicada FROM modulo3.telemetria_calidad
        WHERE id_telemetria = :t AND estado_evaluacion = 'VIGENTE' '''), {'t': lectura}).scalar_one()
    assert guardada == ev['version_limites_fisicos_aplicada']
