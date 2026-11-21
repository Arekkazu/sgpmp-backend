# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-247-G92 RF-58: el estado general de la unidad no depende de la página |
"""INC-M03-247-G92 (#897, TC-M03-183): una unidad de 60 sensores con el único ROJO en
la posición 55 se veía VERDE en la página 1 y ROJO en la página 2. El estado general
sale de todos los sensores de la unidad; la paginación solo recorta el detalle.
"""
from __future__ import annotations

import pytest

from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.domain.entities.monitoreo import ResumenUnidadProductiva, SemaforoBaseSensor
from tests.telemetry.test_dev39_rf58_dashboard import _sensor

UNIDAD = 697
ID_ROJO = 1196


def _sensores_unidad() -> list:
    sensores = [_sensor(id_sensor=1100 + i, semaforo='VERDE') for i in range(60)]
    sensores[54] = _sensor(id_sensor=ID_ROJO, semaforo='VERDE', id_alerta=9, severidad_alerta='CRITICO')
    for s in sensores:
        s.id_infraestructura = UNIDAD
    return sensores


class _Repo:
    def __init__(self) -> None:
        self.sensores = _sensores_unidad()
        self.consultas_semaforos = 0

    def obtener_estados_sensores(self, *, id_infraestructura, pagina, por_pagina, ids_fincas_permitidas):
        inicio = (pagina - 1) * por_pagina
        return self.sensores[inicio:inicio + por_pagina], len(self.sensores)

    def obtener_semaforos_sensores(self, id_infraestructura, *, ids_fincas_permitidas=None):
        self.consultas_semaforos += 1
        return [SemaforoBaseSensor(s.estado_semaforo, s.dato_desactualizado, s.id_alerta,
                                   s.severidad_alerta, s.id_infraestructura) for s in self.sensores]

    def obtener_resumen_unidades(self, *, ids_fincas_permitidas=None):
        return [ResumenUnidadProductiva(
            id_infraestructura=UNIDAD, nombre_infraestructura='Galpón', id_finca=1, nombre_finca='F',
            total_sensores=60, sensores_online=60, sensores_sin_senal=0, sensores_con_error=0,
            estado_general='VERDE', alertas_activas_count=1, ultimo_dato_recibido=None)]


@pytest.mark.parametrize('pagina,por_pagina,visibles', [(1, 50, 50), (2, 50, 10), (1, 10, 10), (6, 10, 10)])
def test_estado_general_rojo_en_todas_las_paginas(pagina, por_pagina, visibles):
    sensores, resumen, total = ObtenerDashboardUseCase(_Repo()).execute(
        UNIDAD, pagina, por_pagina, ver_datos_tecnicos=True)

    assert total == 60
    assert len(sensores) == visibles
    assert resumen[0].estado_general == 'ROJO'
    assert resumen[0].alertas_activas_count == 1


def test_sensor_rojo_sigue_rojo_en_su_pagina():
    sensores, _, _ = ObtenerDashboardUseCase(_Repo()).execute(UNIDAD, 2, 50, ver_datos_tecnicos=True)

    assert next(s for s in sensores if s.id_sensor == ID_ROJO).estado_semaforo == 'ROJO'


def test_conteo_y_estado_general_comparten_una_sola_consulta():
    repo = _Repo()
    uc = ObtenerDashboardUseCase(repo)

    uc.execute(UNIDAD, 1, 50, ver_datos_tecnicos=True)
    conteo = uc.contar_semaforos(UNIDAD)

    assert conteo == {'VERDE': 59, 'ROJO': 1}
    assert repo.consultas_semaforos == 1
