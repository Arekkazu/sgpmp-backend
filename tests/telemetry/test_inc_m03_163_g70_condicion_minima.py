# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-163-G70 RF-57: condición mínima de compuestas y THI NRC sin BD |
"""INC-M03-163-G70: condición mínima de ESTRES_TERMICO y RIESGO_HIDRICO (RF-57 Fase 5)."""
from decimal import Decimal

import pytest

from src.telemetry.domain.entities.reglas_base_rf57 import (
    calcular_thi,
    compuestas_declaradas,
    condicion_minima,
    evaluar_evento,
)


@pytest.mark.parametrize("t,hr,thi", [("24.4", "60", "71.98"), ("31", "75", "83.70"), ("31", "2", "71.74")])
def test_thi_nrc(t, hr, thi):
    assert calcular_thi(Decimal(t), Decimal(hr)) == Decimal(thi)


@pytest.mark.parametrize("variable,valor,correlacion,cumple", [
    ("TEMPERATURA_AMBIENTAL", "31", None, False),
    ("TEMPERATURA_AMBIENTAL", "31", {"humedad_relativa": 75}, True),
    ("HUMEDAD_RELATIVA", "75", {"TEMPERATURA_AMBIENTAL": 31}, True),
    ("HUMEDAD_RELATIVA", "75", None, False),
    ("TEMPERATURA_AMBIENTAL", "31", {"THI": 71.99}, False),
    ("TEMPERATURA_AMBIENTAL", "31", {"THI": 72}, True),
    ("TEMPERATURA_AMBIENTAL", "24.4", {"HUMEDAD_RELATIVA": 60}, False),
])
def test_condicion_minima_estres_termico(variable, valor, correlacion, cumple):
    assert (condicion_minima("ESTRES_TERMICO", variable, Decimal(valor), correlacion) is None) is cumple


@pytest.mark.parametrize("variable,valor,correlacion,cumple", [
    ("OXIGENO_DISUELTO", "4.0", None, False),
    ("OXIGENO_DISUELTO", "4.0", {"PH_AGUA": 7}, False),       # pH normal
    ("OXIGENO_DISUELTO", "4.0", {"PH_AGUA": 6.4}, True),
    ("OXIGENO_DISUELTO", "4.0", {"TDS": 1001}, True),
    ("OXIGENO_DISUELTO", "4.0", {"TDS": 1000}, False),        # TDS normal
    ("PH_AGUA", "6.4", None, True),
    ("PH_AGUA", "8.6", None, True),
    ("TDS", "1500", None, True),
])
def test_condicion_minima_riesgo_hidrico(variable, valor, correlacion, cumple):
    assert (condicion_minima("RIESGO_HIDRICO", variable, Decimal(valor), correlacion) is None) is cumple


def test_compuestas_no_validadas_no_se_bloquean():
    assert condicion_minima("SINDROME_RESPIRATORIO", "NH3", Decimal("30")) is None


@pytest.mark.parametrize("reglas,esperadas", [
    (["ESTRES_TERMICO"], ["ESTRES_TERMICO"]),
    ([{"id": 4, "nombre": "REGLA_RIESGO_HIDRICO"}], ["RIESGO_HIDRICO"]),
    (["DESVIACION_SIMPLE", {"id": 1, "nombre": "UMBRAL_TEMPERATURA_AMBIENTAL_ROJO"}], []),
    ([], []), (None, []),
])
def test_compuestas_declaradas(reglas, esperadas):
    assert compuestas_declaradas(reglas) == esperadas


def test_thi_calculado_desde_la_humedad_eleva_la_severidad():
    evaluacion = evaluar_evento("TEMPERATURA_AMBIENTAL", Decimal("31"), {"HUMEDAD_RELATIVA": 75})
    assert evaluacion.severidad == "MODERADO" and evaluacion.detalle["thi"] == "83.70"
