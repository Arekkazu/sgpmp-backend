# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-176-G57A RF-57: ventana de deduplicación y SLA configurables sin BD |
"""INC-M03-176-G57A: ventana de deduplicación (E4) y plazos SLA por severidad, configurables."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.configuration.domain.entities.parametro_mlops import ParametroMLOps
from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO

AHORA = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _adaptador(**valores):
    repo = Mock()
    parametros = {n: ParametroMLOps(n, v, Decimal(1), None) for n, v in valores.items()}
    repo.obtener.side_effect = lambda nombres: {n: p for n, p in parametros.items() if n in nombres}
    return ParametrosAlertasMLOpsAdapter(repo)


def test_sin_configurar_rigen_los_valores_base_del_rf():
    a = _adaptador()
    assert a.obtener_ventana_deduplicacion_min() == 30
    assert a.obtener_sla_minutos() == {"CRITICO": 5, "MODERADO": 30, "LEVE": 120}


def test_configurados_prevalecen():
    a = _adaptador(rf57_ventana_deduplicacion_min=10, rf57_sla_critico_min=2, rf57_sla_leve_min=60)
    assert a.obtener_ventana_deduplicacion_min() == 10
    assert a.obtener_sla_minutos() == {"CRITICO": 2, "MODERADO": 30, "LEVE": 60}


@pytest.mark.parametrize("valor", [0, 1.5, "x"])
def test_configurado_invalido_falla(valor):
    with pytest.raises(ServiceUnavailableError):
        _adaptador(rf57_sla_critico_min=valor).obtener_sla_minutos()


def _alerta(severidad):
    return Alerta(tipo_alerta="ESTRES_TERMICO", severidad=severidad, estado_alerta="ACTIVA", origen_evento="EDGE",
                  tipo_variable="TEMPERATURA_AMBIENTAL", fecha_evento=AHORA, fecha_generacion=AHORA)


@pytest.mark.parametrize("severidad,sla,minutos", [
    ("CRITICO", None, 5), ("MODERADO", None, 30), ("LEVE", None, 120),
    ("CRITICO", {"CRITICO": 2, "MODERADO": 15, "LEVE": 60}, 2),
    ("LEVE", {"CRITICO": 2, "MODERADO": 15, "LEVE": 60}, 60),
])
def test_vencimiento_usa_el_sla_dado_o_el_base(severidad, sla, minutos):
    assert _alerta(severidad).calcular_fecha_vencimiento(sla) - AHORA == timedelta(minutes=minutos)


def test_el_caso_de_uso_usa_la_ventana_y_el_sla_del_puerto():
    repo = Mock()
    repo.buscar_activa_duplicada.return_value = None
    repo.guardar.side_effect = lambda a: a
    parametros = Mock()
    parametros.obtener_ventana_deduplicacion_min.return_value = 7
    parametros.obtener_sla_minutos.return_value = {"CRITICO": 2, "MODERADO": 15, "LEVE": 45}
    dto = ProcesarEventoAlertaDTO(device_id=1, sensor_id=2, serial="S", tipo_variable="TEMPERATURA_AMBIENTAL",
                                  valor=Decimal("31"), unidad="°C", timestamp_evento=AHORA, estado_dato="LECTURA_VALIDA",
                                  severidad_edge="LEVE", origen_evento="EDGE", id_telemetria=1)
    GenararAlertaUseCase(Mock(), repo, Mock(), Mock(), parametros).execute(dto)
    assert repo.buscar_activa_duplicada.call_args.kwargs["ventana_min"] == 7
    alerta = repo.guardar.call_args.args[0]
    assert alerta.fecha_vencimiento - alerta.fecha_generacion == timedelta(minutes=45)
