# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: listado de observaciones de visión evaluadas (el panel mostraba datos de ejemplo) |
"""RF-62: el panel de calidad de visión pintaba calidadVisionMock.ts; ahora lee GET /iot/calidad/vision.

La consulta se verificó contra PostgreSQL 16 con el esquema completo y observaciones evaluadas,
sin evaluar y fuera del rango; aquí van la validación, los valores por defecto, la política sin
inventar valores y el orden de la ruta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.calidad.consultar_calidad_vision_use_case import (
    ConsultarCalidadVisionUseCase,
)
from src.telemetry.domain.entities.calidad_vision_listado import ObservacionVisionEvaluada
from src.telemetry.infrastructure.adapters.politica_vision_mlops_adapter import PoliticaVisionMLOpsAdapter

AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
OBS = ObservacionVisionEvaluada(
    id_observacion_vision=1, id_dispositivo_iot=9, serial_camara="CAM-GALPON-A-01", id_infraestructura=4,
    nombre_area="Galpón A", fecha_inicio_ventana=AHORA - timedelta(minutes=5), fecha_observacion=AHORA,
    n_individuos_observados=42, cobertura_ventana=Decimal("0.96"), fps_efectivo=Decimal("11.6"),
    cantidad_tracks_perdidos=2, estado_calibracion="CALIBRADO", indice_calidad_vision=Decimal("93.75"),
    clasificacion_calidad="OPTIMA", es_apto_para_ia=True, es_confianza_baja=False,
    flags_detectados={"fps_insuficiente": {"activo": True, "fps_configurado": "12"}},
    fecha_evaluacion_calidad=AHORA,
)


class _Repo:
    def __init__(self):
        self.filtros = None

    def listar(self, filtros):
        self.filtros = filtros
        return [OBS], 1


class _Parametros:
    def __init__(self, valores):
        self.valores = valores

    def obtener(self, nombres):
        return {n: SimpleNamespace(valor=v, minimo=None, maximo=None) for n, v in self.valores.items() if n in nombres}


POLITICA = {"w1": Decimal("0.40"), "w2": Decimal("0.35"), "w3": Decimal("0.25"), "tracks_perdidos_tolerables": 5,
            "umbral_optima": 80, "umbral_degradada": 40, "factor_en_calibracion": Decimal("0.70")}


def _uc(repo=None, politica=POLITICA):
    return ConsultarCalidadVisionUseCase(repo or _Repo(), PoliticaVisionMLOpsAdapter(_Parametros(politica)))


def test_sin_fechas_son_las_ultimas_24_horas_y_trae_la_politica():
    repo = _Repo()
    r = _uc(repo).execute(ids_fincas=[1], ahora=AHORA)
    assert repo.filtros.hasta == AHORA and repo.filtros.desde == AHORA - timedelta(hours=24)
    assert r.total == 1 and r.politica.w1 == Decimal("0.40") and r.politica.tracks_perdidos_tolerables == 5
    assert r.politica_motivo is None


def test_politica_incompleta_no_se_inventa():
    sin_w3 = {k: v for k, v in POLITICA.items() if k != "w3"}
    r = _uc(politica=sin_w3).execute(ids_fincas=None, ahora=AHORA)
    assert r.politica is None and "w3" in r.politica_motivo
    r = _uc(politica={**POLITICA, "w1": Decimal("0.50")}).execute(ids_fincas=None, ahora=AHORA)
    assert r.politica is None and "sumar" in r.politica_motivo


@pytest.mark.parametrize(("kw", "codigo"), [
    ({"clasificacion": "APTO"}, "CLASIFICACION_INVALIDA"),
    ({"pagina": 0}, "PAGINA_INVALIDA"),
    ({"por_pagina": 201}, "POR_PAGINA_INVALIDO"),
    ({"desde": AHORA, "hasta": AHORA - timedelta(hours=1)}, "RANGO_FECHAS_INVALIDO"),
    ({"desde": AHORA - timedelta(days=40), "hasta": AHORA}, "RANGO_FECHAS_EXCESIVO"),
])
def test_parametros_invalidos_son_400(kw, codigo):
    with pytest.raises(ValidationError) as exc:
        _uc().execute(ids_fincas=None, ahora=AHORA, **kw)
    assert exc.value.code == codigo


def test_sin_evaluar_es_un_filtro_valido():
    repo = _Repo()
    _uc(repo).execute(ids_fincas=None, clasificacion="SIN_EVALUAR", ahora=AHORA)
    assert repo.filtros.clasificacion == "SIN_EVALUAR"


def test_ruta_vision_va_antes_de_id_telemetria(monkeypatch):
    """Si GET /{id_telemetria} va primero, «vision» se toma como id y la ruta responde 422."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.identity_access.infrastructure.dependencies import get_current_user
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.telemetry.infrastructure.routers import calidad_router as router_mod

    rutas = [r.path for r in router_mod.router.routes]
    assert rutas.index("/iot/calidad/vision") < rutas.index("/iot/calidad/{id_telemetria}")

    repo = _Repo()
    cerradas = []
    monkeypatch.setattr(router_mod, "SqlAlchemyCalidadVisionRepository", lambda db: repo)
    monkeypatch.setattr(router_mod, "SqlAlchemyParametrosMLOpsRepository", lambda db: _Parametros(POLITICA))
    monkeypatch.setattr(router_mod, "sesion_sistema", lambda: SimpleNamespace(close=lambda: cerradas.append(True)))
    monkeypatch.setattr(router_mod, "AlcanceFincaAdapter",
                        lambda db: SimpleNamespace(listar_ids_fincas_permitidas=lambda u, r: [3]))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id_usuario=5, id_rol=4)
    for ruta in app.routes:
        if getattr(ruta, "path", "") == "/iot/calidad/vision":
            for dep in ruta.dependencies:
                app.dependency_overrides[dep.dependency] = lambda: None
    r = TestClient(app).get("/iot/calidad/vision", params={"clasificacion": "OPTIMA"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["items"][0]["serial_camara"] == "CAM-GALPON-A-01" and cuerpo["items"][0]["apto_para_nic41"] is False
    assert cuerpo["politica"]["umbral_optima"] == "80" and repo.filtros.ids_fincas == [3]
    assert cerradas == [True]  # la sesión de sistema se cierra
