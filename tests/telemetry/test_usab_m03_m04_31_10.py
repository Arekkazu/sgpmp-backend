# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 lote 31-10: acción sugerida, rango de 90 días, contagio y vinculaciones |
"""Lógica nueva del lote de usabilidad/accesibilidad M03-M04 del 31-10."""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.prediction.infrastructure.repositories.monitor_prediccion_repository import _normalizar_contagio
from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.infraestructura.listar_vinculaciones_use_case import ListarVinculacionesUseCase
from src.telemetry.domain.entities.alerta import accion_sugerida_ambiental
from src.telemetry.domain.entities.monitoreo import FiltrosHistorial

_NIVELES = [{'nivel': 'normal', 'limite_inferior': '20', 'limite_superior': '30'}]


@pytest.mark.parametrize('valor,esperada', [
    (Decimal('35'), 'Activar ventilación forzada'),
    (Decimal('12'), 'Encender la calefacción'),
])
def test_m3_06_accion_segun_la_direccion_del_valor(valor, esperada):
    assert accion_sugerida_ambiental('TEMPERATURA_AMBIENTAL', valor, _NIVELES).startswith(esperada)


def test_m3_06_sin_banda_o_variable_desconocida_hay_accion():
    assert accion_sugerida_ambiental('NH3', Decimal('80'), None).startswith('Ventilar')
    assert accion_sugerida_ambiental('OTRA', Decimal('1'), _NIVELES).startswith('Revisar el área')


@pytest.mark.parametrize('filtros,extendido', [
    ({}, False),
    ({'id_infraestructura': 347}, False),  # TC-DIS-160: el área sola no habilita >90 días
    ({'sensor_id': 4}, True),
    ({'tipo_variable': 'NH3'}, True),
    ({'especie': 'Porcinos'}, True),
])
def test_tc_dis_160_rango_extendido_solo_con_variable_sensor_o_especie(filtros, extendido):
    f = FiltrosHistorial(fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 10, 1), **filtros)
    assert f.tiene_filtro_adicional() is extendido


def test_n_04_contagio_tolera_jsonb_con_otra_forma():
    fila = _normalizar_contagio({'factores_ausentes': {'FA': 'sin sensores'}, 'detalle_calculo': ['x']})
    assert fila == {'factores_ausentes': ['FA'], 'detalle_calculo': {'valor': ['x']}}
    assert _normalizar_contagio({'factores_ausentes': 'FD', 'detalle_calculo': None})['factores_ausentes'] == ['FD']


def test_cp84_vinculaciones_con_rango_invertido_es_400():
    repo = Mock()
    with pytest.raises(ValidationError) as e:
        ListarVinculacionesUseCase(db=Mock(), vinculacion_repo=repo).execute(
            fecha_desde=datetime(2026, 10, 30, tzinfo=timezone.utc), fecha_hasta=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert e.value.code == 'RANGO_FECHAS_INVALIDO'
    repo.listar.assert_not_called()
