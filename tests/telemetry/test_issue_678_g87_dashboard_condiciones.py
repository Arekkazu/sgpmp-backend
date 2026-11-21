# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | ISSUE-678 G87 RF-58: separar referencia válida, condición posterior y detalle por permiso. |
"""Reglas de presentación; las secuencias de ingesta se prueban con PostgreSQL."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from tests.telemetry.test_dev39_rf58_dashboard import _dashboard, _sensor


@pytest.mark.parametrize("tecnico", [False, True])
def test_fuera_de_rango_posterior_no_sustituye_la_referencia_valida(tecnico):
    sensor = _sensor(calidad="FUERA_DE_RANGO", ultimo_valor=Decimal("25"),
                     estado_calidad_valor_operativo="LECTURA_VALIDA")
    [resultado] = _dashboard([sensor], ver_datos_tecnicos=tecnico)
    assert resultado.ultimo_valor == Decimal("25")
    assert resultado.es_valor_operativo is True
    assert resultado.indicador_anomalia is True
    assert resultado.estado_calidad == "FUERA_DE_RANGO"
    assert resultado.etiqueta_estado == "Lectura fuera de rango"


def test_ingeniero_distingue_condicion_actual_y_ultima_lectura_valida():
    sensor = _sensor(calidad="ERROR_CALIBRACION", ultimo_valor=Decimal("25"),
                     estado_calidad_valor_operativo="LECTURA_VALIDA",
                     timestamp_estado_actual=datetime(2026, 10, 26, 15, tzinfo=timezone.utc))
    [resultado] = _dashboard([sensor], ver_datos_tecnicos=True)
    assert resultado.ultimo_valor == Decimal("25") and resultado.es_valor_operativo
    assert resultado.estado_calidad == "ERROR_CALIBRACION"
    assert resultado.etiqueta_estado == "Requiere calibración"
    assert resultado.indicador_anomalia
    assert resultado.nivel_bateria_pct == Decimal("80")
    assert resultado.timestamp_estado_actual == sensor.timestamp_estado_actual


def test_productor_conserva_referencia_sin_recibir_el_error_tecnico():
    sensor = _sensor(calidad="ERROR_CALIBRACION", ultimo_valor=Decimal("25"),
                     estado_calidad_valor_operativo="LECTURA_VALIDA")
    [resultado] = _dashboard([sensor], ver_datos_tecnicos=False)
    assert resultado.ultimo_valor == Decimal("25") and resultado.es_valor_operativo
    assert resultado.estado_calidad is None
    assert resultado.indicador_anomalia and resultado.etiqueta_estado == "En revisión técnica"
    assert resultado.nivel_bateria_pct is None
    assert resultado.calidad_senal_rssi is None and resultado.calidad_senal_snr is None
    assert resultado.id_alerta is None


@pytest.mark.parametrize("tecnico", [False, True])
def test_sin_lectura_valida_no_se_inventa_un_valor_operativo(tecnico):
    sensor = _sensor(calidad="ERROR_CALIBRACION", ultimo_valor=None,
                     estado_calidad_valor_operativo=None)
    [resultado] = _dashboard([sensor], ver_datos_tecnicos=tecnico)
    assert resultado.ultimo_valor is None and resultado.es_valor_operativo is False
    assert resultado.indicador_anomalia


def test_lectura_valida_posterior_limpia_indicador_de_la_vista():
    sensor = _sensor(ultimo_valor=Decimal("26"), estado_calidad_valor_operativo="LECTURA_VALIDA")
    [resultado] = _dashboard([sensor], ver_datos_tecnicos=True)
    assert resultado.ultimo_valor == Decimal("26")
    assert not resultado.indicador_anomalia and resultado.etiqueta_estado is None
