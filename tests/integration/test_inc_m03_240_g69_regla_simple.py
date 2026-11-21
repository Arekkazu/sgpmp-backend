# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-240-G69 RF-57: lectura aislada fuera de NORMAL genera alerta REGLA_SIMPLE |
"""INC-M03-240-G69 (#881, TC-M03-G69): cada lectura aislada se clasifica en la severidad de su
banda (RF-57 Fase 5, CA-1) y genera su alerta; solo la banda NORMAL no alerta.

Router real, adaptadores de M09 y PostgreSQL real; fixtures de G68/G70.
"""
import pytest
from sqlalchemy import text

from tests.integration.test_inc_m03_162_g68_severidad_alertas_rf57 import (  # noqa: F401
    _UNIDAD, _alerta, _lectura, http, modelos, nuevo_sensor,
)
from tests.integration.test_inc_m03_163_g70_condicion_minima_compuestas import _post

pytestmark = pytest.mark.integration

_CASOS = [
    ('TEMPERATURA_AMBIENTAL', v, s) for v, s in [
        ('30.1', 'LEVE'), ('33.0', 'LEVE'), ('33.1', 'MODERADO'), ('36.0', 'MODERADO'), ('36.1', 'CRITICO'),
        ('19.9', 'LEVE'), ('17.0', 'LEVE'), ('16.9', 'MODERADO'), ('14.0', 'MODERADO'), ('13.9', 'CRITICO')]
] + [
    ('HUMEDAD_RELATIVA', v, s) for v, s in [
        ('70.1', 'LEVE'), ('80.0', 'LEVE'), ('80.1', 'MODERADO'), ('90.0', 'MODERADO'), ('90.1', 'CRITICO'),
        ('49.9', 'LEVE'), ('40.0', 'LEVE'), ('39.9', 'MODERADO'), ('30.0', 'MODERADO'), ('29.9', 'CRITICO')]
] + [
    ('OXIGENO_DISUELTO', v, s) for v, s in [
        ('4.9', 'LEVE'), ('3.0', 'LEVE'), ('2.9', 'MODERADO'), ('2.0', 'MODERADO'), ('1.9', 'CRITICO')]
]


@pytest.mark.parametrize('variable,valor,severidad', _CASOS)
def test_lectura_aislada_genera_alerta_con_la_severidad_de_su_banda(db_session, http, nuevo_sensor,
                                                                    variable, valor, severidad):
    hw = nuevo_sensor()
    # La severidad declarada no manda (Restricción 7): se envía LEVE en todos los casos.
    r = _post(http, hw, variable, valor, 'LEVE')

    assert r.status_code == 201, r.text
    assert (r.json()['tipo_alerta'], r.json()['severidad']) == ('REGLA_SIMPLE', severidad)
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s AND estado_alerta=\'ACTIVA\''),
                              {'s': hw['sensor']}).scalar_one() == 1


@pytest.mark.parametrize('variable,valor', [('TEMPERATURA_AMBIENTAL', '25.0'), ('HUMEDAD_RELATIVA', '60'),
                                            ('OXIGENO_DISUELTO', '6.0')])
def test_banda_normal_no_genera_alerta(db_session, http, nuevo_sensor, variable, valor):
    hw = nuevo_sensor()
    r = _post(http, hw, variable, valor, 'LEVE')

    assert r.status_code == 201 and r.json()['id_alerta'] is None, r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s'),
                              {'s': hw['sensor']}).scalar_one() == 0
