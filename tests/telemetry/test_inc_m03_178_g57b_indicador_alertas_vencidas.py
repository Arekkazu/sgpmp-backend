# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: indicadores del sistema de alertas y vencidas en el dashboard |
"""INC-M03-178-G57B (RF-57 Salida 3): indicadores consultables, sin BD."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.alertas.consultar_indicadores_alertas_use_case import (
    ConsultarIndicadoresAlertasUseCase,
)
from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.domain.entities.indicadores_alertas import FiltroIndicadoresAlertas, IndicadoresAlertas
from src.telemetry.infrastructure.routers import alerta_router
from src.telemetry.infrastructure.schema.alerta_schema import IndicadoresAlertasSchema
from src.telemetry.infrastructure.schema.monitoreo_schema import DashboardResponseSchema


class _Repo:
    def __init__(self):
        self.filtros = []

    def calcular(self, filtro):
        self.filtros.append(filtro)
        return IndicadoresAlertas(alertas_vencidas_sin_atencion=2)

    def contar_vencidas_sin_atencion(self, filtro):
        self.filtros.append(filtro)
        return 2


def test_el_contrato_expone_los_seis_indicadores_del_rf():
    campos = IndicadoresAlertasSchema.model_fields
    for nombre in ('alertas_activas_total', 'alertas_criticas_activas', 'alertas_por_tipo',
                   'alertas_vencidas_sin_atencion', 'tiempo_promedio_resolucion_min', 'tasa_falsos_positivos'):
        assert nombre in campos
    assert 'alertas_vencidas_sin_atencion' in DashboardResponseSchema.model_fields


def test_la_ruta_de_indicadores_va_antes_del_detalle_por_id():
    rutas = [r.path for r in alerta_router.router.routes]
    assert rutas.index('/iot/alertas/indicadores') < rutas.index('/iot/alertas/{id_alerta}')


def test_el_use_case_pasa_el_alcance_y_el_rango():
    repo = _Repo()
    filtro = FiltroIndicadoresAlertas(id_infraestructura=4, ids_fincas_permitidas=[1],
                                      fecha_desde=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert ConsultarIndicadoresAlertasUseCase(repo).execute(filtro).alertas_vencidas_sin_atencion == 2
    assert repo.filtros == [filtro]


def test_rango_invertido_es_400():
    filtro = FiltroIndicadoresAlertas(fecha_desde=datetime(2026, 10, 2, tzinfo=timezone.utc),
                                      fecha_hasta=datetime(2026, 10, 1, tzinfo=timezone.utc))
    with pytest.raises(ValidationError) as exc:
        ConsultarIndicadoresAlertasUseCase(_Repo()).execute(filtro)
    assert exc.value.code == 'RANGO_FECHAS_INVALIDO'


@pytest.mark.parametrize('descartadas, resueltas, esperado', [(3, 1, 0.75), (0, 4, 0.0), (0, 0, None)])
def test_tasa_de_falsos_positivos(descartadas, resueltas, esperado):
    assert IndicadoresAlertas.tasa(descartadas, resueltas) == esperado


def test_el_dashboard_cuenta_las_vencidas_del_mismo_alcance():
    repo = _Repo()
    caso = ObtenerDashboardUseCase(monitoreo_repo=None, indicadores_alertas=repo)
    assert caso.contar_alertas_vencidas_sin_atencion(7, ids_fincas_permitidas=[3]) == 2
    assert repo.filtros == [FiltroIndicadoresAlertas(id_infraestructura=7, ids_fincas_permitidas=[3])]
    assert ObtenerDashboardUseCase(monitoreo_repo=None).contar_alertas_vencidas_sin_atencion(None) == 0
