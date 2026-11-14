# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: consulta de indicadores del sistema de alertas |
"""Caso de uso: indicadores de estado del sistema de alertas (RF-57, Salida 3).

INC-M03-178-G57B: ``alertas_vencidas_sin_atencion`` no estaba en ninguna ruta; tampoco los
otros cinco indicadores que el RF pide exponer ("el sistema mantiene y expone métricas
actualizadas"). Se calculan al consultar, sobre ``modulo3.alertas``: no hay contadores que
puedan desincronizarse, y una alerta que vence sube el indicador en la siguiente consulta.
"""
from __future__ import annotations

from src.shared.errors import ValidationError
from src.telemetry.domain.entities.indicadores_alertas import FiltroIndicadoresAlertas, IndicadoresAlertas
from src.telemetry.domain.repositories.indicadores_alertas_repository import IndicadoresAlertasRepository


class ConsultarIndicadoresAlertasUseCase:
    def __init__(self, indicadores_repo: IndicadoresAlertasRepository) -> None:
        self.indicadores_repo = indicadores_repo

    def execute(self, filtro: FiltroIndicadoresAlertas) -> IndicadoresAlertas:
        if filtro.fecha_desde and filtro.fecha_hasta and filtro.fecha_desde > filtro.fecha_hasta:
            raise ValidationError(
                code='RANGO_FECHAS_INVALIDO',
                message='fecha_desde no puede ser posterior a fecha_hasta.',
                field='fecha_desde',
            )
        return self.indicadores_repo.calcular(filtro)
