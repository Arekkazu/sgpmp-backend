# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: aviso E7 en segundo plano y conteo con el semáforo base |
"""INC-M03-177-G57B (RF-58, CA-13): el dashboard no espera al aviso E7 ni repite su consulta."""
from __future__ import annotations

import inspect

from fastapi import BackgroundTasks

from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.domain.entities.monitoreo import SemaforoBaseSensor
from src.telemetry.infrastructure.adapters import aviso_sin_umbral_background_adapter as bg_mod
from src.telemetry.infrastructure.routers import monitoreo_router
from tests.telemetry.test_dev39_rf58_dashboard import _sensor


def test_el_aviso_se_agenda_y_no_corre_dentro_del_request(monkeypatch):
    corridos = []
    monkeypatch.setattr(bg_mod, '_procesar_aviso_sin_umbral', lambda sensores: corridos.append(sensores))
    tareas = BackgroundTasks()
    assert bg_mod.AvisoSinUmbralBackgroundAdapter(tareas).avisar([_sensor(id_sensor=901)]) == 1
    assert corridos == [] and len(tareas.tasks) == 1
    bg_mod._EN_CURSO.discard(901)


def test_un_refresco_no_duplica_el_aviso_en_curso(monkeypatch):
    monkeypatch.setattr(bg_mod, '_EN_CURSO', set())
    primero, segundo = BackgroundTasks(), BackgroundTasks()
    assert bg_mod.AvisoSinUmbralBackgroundAdapter(primero).avisar([_sensor(id_sensor=7)]) == 1
    assert bg_mod.AvisoSinUmbralBackgroundAdapter(segundo).avisar([_sensor(id_sensor=7), _sensor(id_sensor=8)]) == 1
    assert [s.id_sensor for s in segundo.tasks[0].args[0]] == [8]


def test_al_terminar_libera_los_sensores_aunque_falle(monkeypatch):
    monkeypatch.setattr(bg_mod, '_EN_CURSO', {7})
    cerradas = []

    class _Db:
        def close(self):
            cerradas.append(True)

    class _Falla:
        def __init__(self, db): pass
        def avisar(self, sensores): raise RuntimeError('smtp caído')

    monkeypatch.setattr(bg_mod, 'sesion_sistema', _Db)
    monkeypatch.setattr(bg_mod, 'AvisoSinUmbralEmailAdapter', _Falla)
    bg_mod._procesar_aviso_sin_umbral([_sensor(id_sensor=7)])
    assert bg_mod._EN_CURSO == set() and cerradas == [True]


def test_el_router_ya_no_avisa_dentro_del_get():
    fuente = inspect.getsource(monitoreo_router)
    assert 'AvisoSinUmbralEmailAdapter' not in fuente
    assert 'AvisoSinUmbralBackgroundAdapter(background_tasks)' in fuente


def test_el_conteo_no_pide_la_consulta_completa_de_estados():
    class _Repo:
        def obtener_estados_sensores(self, **kw):
            raise AssertionError('el conteo no debe repetir la consulta de estados')

        def obtener_semaforos_sensores(self, id_infraestructura, **kw):
            return [SemaforoBaseSensor('VERDE', False, None, None),
                    SemaforoBaseSensor('VERDE', False, 3, 'MODERADO'),   # CA-4: alerta activa → AMARILLO
                    SemaforoBaseSensor('AMARILLO', False, 4, 'CRITICO'),  # CA-4: crítica → ROJO
                    SemaforoBaseSensor('VERDE', True, None, None),       # CA-5: desactualizado → GRIS
                    SemaforoBaseSensor(None, False, None, None)]         # sin caché → GRIS

    assert ObtenerDashboardUseCase(_Repo()).contar_semaforos(None) == {
        'VERDE': 1, 'AMARILLO': 1, 'ROJO': 1, 'GRIS': 2}
