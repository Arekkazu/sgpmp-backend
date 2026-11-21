# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: bordes de las bandas base, THI y rango físico |
"""INC-M03-162-G68: reglas base de RF-57 Fase 5 sin BD (bordes exactos del RF)."""
from decimal import Decimal

import pytest

from src.telemetry.domain.entities.reglas_base_rf57 import evaluar_evento, fuera_de_rango_fisico


@pytest.mark.parametrize("variable,valor,esperada", [
    # Temperatura ambiental: LEVE >30 o <20, MODERADO >33 o <17, CRITICO >36 o <14.
    ("TEMPERATURA_AMBIENTAL", "30", None), ("TEMPERATURA_AMBIENTAL", "30.01", "LEVE"),
    ("TEMPERATURA_AMBIENTAL", "33", "LEVE"), ("TEMPERATURA_AMBIENTAL", "33.1", "MODERADO"),
    ("TEMPERATURA_AMBIENTAL", "36", "MODERADO"), ("TEMPERATURA_AMBIENTAL", "36.1", "CRITICO"),
    ("TEMPERATURA_AMBIENTAL", "20", None), ("TEMPERATURA_AMBIENTAL", "19.9", "LEVE"),
    ("TEMPERATURA_AMBIENTAL", "16.9", "MODERADO"), ("TEMPERATURA_AMBIENTAL", "13.9", "CRITICO"),
    # Humedad: LEVE <50 o >70, MODERADO <40 o >80, CRITICO <30 o >90.
    ("HUMEDAD_RELATIVA", "60", None), ("HUMEDAD_RELATIVA", "70.5", "LEVE"),
    ("HUMEDAD_RELATIVA", "85", "MODERADO"), ("HUMEDAD_RELATIVA", "29", "CRITICO"),
    # pH: LEVE <6.5 o >8.5, MODERADO <6.0 o >9.0, CRITICO <5.5 o >9.5.
    ("PH_AGUA", "7", None), ("PH_AGUA", "6.4", "LEVE"), ("PH_AGUA", "9.1", "MODERADO"), ("PH_AGUA", "5.4", "CRITICO"),
    # NH3: 25–34 LEVE, 35–44 MODERADO, ≥45 CRITICO.
    ("NH3", "24", None), ("NH3", "25", "LEVE"), ("NH3", "35", "MODERADO"), ("NH3", "45", "CRITICO"),
    # CO2: 3000 LEVE, 3500 MODERADO, ≥4000 CRITICO.
    ("CO2", "2999", None), ("CO2", "3000", "LEVE"), ("CO2", "3500", "MODERADO"), ("CO2", "4000", "CRITICO"),
    # Temperatura corporal: LEVE >40.0 o <36.5, MODERADO >40.5 o <36.0, CRITICO >41.0 o <35.5.
    ("TEMPERATURA_CORPORAL", "38.5", None), ("TEMP_CORPORAL", "40.1", "LEVE"),
    ("TEMPERATURA_CORPORAL", "40.6", "MODERADO"), ("TEMPERATURA_CORPORAL", "35.4", "CRITICO"),
    # Frecuencia cardíaca: LEVE >100 o <45, MODERADO >110 o <42, CRITICO >120 o <40.
    ("FRECUENCIA_CARDIACA", "70", None), ("FRECUENCIA_CARDIACA", "101", "LEVE"),
    ("FRECUENCIA_CARDIACA", "41", "MODERADO"), ("FRECUENCIA_CARDIACA", "121", "CRITICO"),
    # Oxígeno disuelto: NORMAL 5–12, LEVE 3–4.9, MODERADO 2–2.9, CRITICO <2.
    ("OXIGENO_DISUELTO", "8", None), ("OXIGENO_DISUELTO", "5", None), ("OXIGENO_DISUELTO", "4.9", "LEVE"),
    ("OXIGENO_DISUELTO", "2.9", "MODERADO"), ("OXIGENO_DISUELTO", "1.9", "CRITICO"),
    # TDS: 0–1000 NORMAL, 1001–1500 LEVE, 1501–1999 MODERADO, ≥2000 CRITICO.
    ("TDS", "1000", None), ("TDS", "1001", "LEVE"), ("TDS", "1501", "MODERADO"), ("TDS", "2000", "CRITICO"),
])
def test_bandas_base(variable, valor, esperada):
    evaluacion = evaluar_evento(variable, Decimal(valor))
    assert evaluacion.evaluable and evaluacion.severidad == esperada


@pytest.mark.parametrize("variable", ["FRECUENCIA_RESPIRATORIA", "ACTIVIDAD"])
def test_bandas_por_especie_o_media_movil_no_se_evaluan(variable):
    assert not evaluar_evento(variable, Decimal("50")).evaluable


@pytest.mark.parametrize("correlacion,esperada", [
    ({"THI": 71.9}, "LEVE"),                                    # THI NORMAL: queda la banda simple
    ({"THI": 72.12, "temperatura_corporal": 40.5}, "MODERADO"),
    ({"thi": {"valor": "79.14"}, "TEMP_CORPORAL": 40.01}, "CRITICO"),
    ({"THI": 72.12, "FRECUENCIA_RESPIRATORIA": {"nivel": "critico"}}, "MODERADO"),
    ({"THI": 72.12, "FRECUENCIA_RESPIRATORIA": {"severidad": "LEVE"}}, "LEVE"),
    ({"THI": 72.12, "temperatura_corporal": 40}, "LEVE"),       # > 40, no ≥
    ({"THI": "no-numero", "temperatura_corporal": 41}, "LEVE"),  # THI ilegible: sin escalada
    ({"THI": 71.9, "temperatura_corporal": 41}, "LEVE"),         # sin THI ≥ LEVE no escala
])
def test_estres_termico_thi_y_escalada(correlacion, esperada):
    assert evaluar_evento("TEMPERATURA_AMBIENTAL", Decimal("30.5"), correlacion).severidad == esperada


def test_thi_eleva_una_banda_simple_normal():
    evaluacion = evaluar_evento("HUMEDAD_RELATIVA", Decimal("60"), {"THI": 80})
    assert evaluacion.severidad == "MODERADO" and evaluacion.detalle["severidad_por_valor"] is None


@pytest.mark.parametrize("valor,fuera", [("-50", False), ("100", False), ("100.1", True), ("-50.1", True)])
def test_rango_fisico(valor, fuera):
    assert fuera_de_rango_fisico(Decimal(valor), Decimal("-50"), Decimal("100")) is fuera


def test_rango_fisico_sin_limites_no_dispara():
    assert not fuera_de_rango_fisico(Decimal("1e9"), None, None)
