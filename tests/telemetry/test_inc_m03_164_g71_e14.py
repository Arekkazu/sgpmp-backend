# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: variable compañera y reglas como objeto sin BD |
"""INC-M03-164-G71: piezas de dominio de E14 (RF-57)."""
from decimal import Decimal

import pytest

from src.telemetry.domain.entities.reglas_base_rf57 import companera_faltante, regla_compuesta, regla_simple


@pytest.mark.parametrize("variable,correlacion,faltante", [
    ("TEMPERATURA_AMBIENTAL", None, "HUMEDAD_RELATIVA"),
    ("HUMEDAD_RELATIVA", {}, "TEMPERATURA_AMBIENTAL"),
    ("TEMPERATURA_AMBIENTAL", {"humedad_relativa": 70}, None),
    ("TEMPERATURA_AMBIENTAL", {"THI": 75}, None),
    ("OXIGENO_DISUELTO", None, None),  # RIESGO_HIDRICO es de dato puntual: sin búsqueda
])
def test_companera_faltante(variable, correlacion, faltante):
    assert companera_faltante(variable, correlacion) == faltante


def test_regla_simple_lleva_su_banda_y_su_origen():
    assert regla_simple("TEMPERATURA_AMBIENTAL", Decimal("31.0"), 525, 77) == {
        "id": "RF57_BASE_TEMPERATURA_AMBIENTAL", "nombre": "TEMPERATURA_AMBIENTAL_LEVE", "tipo": "REGLA_SIMPLE_RF57",
        "valor": "31.0", "id_sensor": 525, "id_telemetria": 77}
    assert regla_simple("HUMEDAD_RELATIVA", Decimal("60"))["nombre"] == "HUMEDAD_RELATIVA_NORMAL"


def test_regla_compuesta():
    assert regla_compuesta("ESTRES_TERMICO", "83.70") == {
        "id": "RF57_ESTRES_TERMICO", "nombre": "ESTRES_TERMICO", "tipo": "REGLA_COMPUESTA_RF57", "thi": "83.70"}
