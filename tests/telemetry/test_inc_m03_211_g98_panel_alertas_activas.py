# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | INC-M03-211-G98 RF-58: panel integrado de alertas activas          |
"""INC-M03-211-G98 (#788): el dashboard trae el total y la lista de alertas ACTIVA (CA-11)."""
from datetime import datetime, timezone
from unittest.mock import Mock

from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.domain.entities.indicadores_alertas import AlertaActivaPanel
from src.telemetry.infrastructure.schema.monitoreo_schema import AlertaActivaPanelSchema, DashboardResponseSchema


def _alerta(id_alerta, severidad):
    return AlertaActivaPanel(id_alerta, 'ESTRES_TERMICO', severidad, 'TEMPERATURA', None, '°C',
                             datetime.now(timezone.utc), 12, 1, 7, 'LOTE-7')


def test_panel_pasa_el_alcance_del_usuario_y_devuelve_total_aparte():
    indicadores = Mock()
    indicadores.listar_activas.return_value = ([_alerta(1, 'CRITICO')], 3)
    alertas, total = ObtenerDashboardUseCase(Mock(), indicadores_alertas=indicadores).panel_alertas_activas(
        5, ids_fincas_permitidas=[2])
    filtro, limite = indicadores.listar_activas.call_args.args
    assert (filtro.id_infraestructura, filtro.ids_fincas_permitidas, limite) == (5, [2], 50)
    assert total == 3 and alertas[0].id_activo_biologico == 7
    assert AlertaActivaPanelSchema.model_validate(alertas[0]).minutos_transcurridos == 12


def test_sin_repositorio_de_alertas_el_panel_queda_vacio():
    assert ObtenerDashboardUseCase(Mock()).panel_alertas_activas(None) == ([], 0)
    assert DashboardResponseSchema(total=4, pagina=1, por_pagina=50, resumen_unidades=[], sensores=[]
                                   ).panel_alertas_activas.total == 0
