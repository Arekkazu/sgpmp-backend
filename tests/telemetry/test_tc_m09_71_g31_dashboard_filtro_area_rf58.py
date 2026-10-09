"""TC-M09-71-G31 (frontend #317): al filtrar el dashboard por área, los KPIs
salían bien pero `resumen_unidades` llegaba vacío y el cliente no pintaba
ninguna tarjeta. El resumen debe traer la unidad filtrada, y solo esa.
"""
from __future__ import annotations

from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import (
    ObtenerDashboardUseCase,
)
from src.telemetry.domain.entities.monitoreo import EstadoSensorActual, ResumenUnidadProductiva


def _sensor(id_infraestructura: int) -> EstadoSensorActual:
    return EstadoSensorActual(
        id_sensor=1, id_dispositivo_iot=1, nombre_sensor='T1', tipo_variable='TEMPERATURA',
        categoria_variable='AMBIENTAL', ultimo_valor=None, ultima_unidad=None,
        ultimo_timestamp_captura=None, estado_semaforo='ROJO', estado_calidad=None,
        estado_desviacion=None, estado_conectividad='ACTIVO', tiempo_sin_reporte_min=0,
        dato_desactualizado=False, id_alerta=None, severidad_alerta=None, tendencia=None,
        id_infraestructura=id_infraestructura, nombre_infraestructura='Galpón', id_finca=1,
        nombre_finca='F', nivel_bateria_pct=None, calidad_senal_rssi=None, calidad_senal_snr=None,
    )


def _unidad(id_infraestructura: int) -> ResumenUnidadProductiva:
    return ResumenUnidadProductiva(
        id_infraestructura=id_infraestructura, nombre_infraestructura=f'U{id_infraestructura}',
        id_finca=1, nombre_finca='F', total_sensores=1, sensores_online=1, sensores_sin_senal=0,
        sensores_con_error=0, estado_general='VERDE', alertas_activas_count=0,
        ultimo_dato_recibido=None,
    )


class _RepoFake:
    def obtener_estados_sensores(self, *, id_infraestructura, pagina, por_pagina, ids_fincas_permitidas):
        return [_sensor(id_infraestructura or 7)], 1

    def obtener_resumen_unidades(self, *, ids_fincas_permitidas=None):
        return [_unidad(7), _unidad(8)]


def test_filtro_por_area_devuelve_solo_su_unidad_con_semaforo_recalculado():
    _, resumen, _ = ObtenerDashboardUseCase(_RepoFake()).execute(7, 1, 50, id_rol_usuario=1)

    assert [u.id_infraestructura for u in resumen] == [7]
    assert resumen[0].estado_general == 'ROJO'


def test_sin_filtro_devuelve_todas_las_unidades():
    _, resumen, _ = ObtenerDashboardUseCase(_RepoFake()).execute(None, 1, 50, id_rol_usuario=1)

    assert [u.id_infraestructura for u in resumen] == [7, 8]
