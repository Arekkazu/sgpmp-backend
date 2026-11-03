# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
"""RF-72: la pantalla de retroalimentación pintaba retroMock.ts; ahora lee GET /bandeja.

La consulta se verificó contra PostgreSQL 16 con el esquema completo (baseline + migraciones) y un
escenario de episodios, ventana, ampliación, evaluación propia y activo en BAJA; aquí van la
validación, los valores por defecto, ``puede_evaluar`` y la ruta con un repositorio en memoria.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.configuration.domain.entities.parametro_mlops import RF72_VENTANA
from src.prediction.application.use_cases.retroalimentacion.consultar_bandeja_retroalimentacion_use_case import (
    ConsultarBandejaRetroalimentacionUseCase,
)
from src.prediction.domain.entities.bandeja_retroalimentacion import (
    IndicadoresBandejaRetroalimentacion,
    InferenciaPorEvaluar,
)
from src.shared.errors import ValidationError

AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)

ITEM = InferenciaPorEvaluar(
    id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=4, identificador_activo="BOV-003",
    especie="Bovino", nombre_finca="Finca", nombre_area="Corral", nivel_riesgo=3, id_patologia=6,
    nombre_patologia="Septicemia", confianza_global=Decimal("0.91"), fecha_inferencia=AHORA,
    fecha_inicio_ventana=None, fecha_fin_ventana=None, tiene_alerta_generada=False, modo_sombra=True,
    estado_evaluacion="PENDIENTE", en_ventana=True, fecha_limite=AHORA + timedelta(days=90),
    numero_evaluaciones=0, evaluada_por_mi=False, activo_en_baja=False,
)


class _Repo:
    def __init__(self, items=(ITEM,)):
        self.items = list(items)
        self.filtros = None

    def listar(self, filtros):
        self.filtros = filtros
        return self.items, len(self.items)

    def indicadores(self, filtros):
        return IndicadoresBandejaRetroalimentacion(pendientes=1, evaluadas=2, vencidas=3)


class _Parametros:
    def __init__(self, ventana=90):
        self.ventana = ventana

    def obtener(self, nombres):
        return {RF72_VENTANA: SimpleNamespace(valor=self.ventana, minimo=None, maximo=None)}


def _uc(repo=None, ventana=90):
    return ConsultarBandejaRetroalimentacionUseCase(repo or _Repo(), _Parametros(ventana))


def test_sin_fechas_mira_la_ventana_mas_un_mes():
    repo = _Repo()
    r = _uc(repo, ventana=60).execute(ids_fincas=[1], id_usuario=7, ahora=AHORA)
    assert repo.filtros.hasta == AHORA and repo.filtros.desde == AHORA - timedelta(days=90)
    assert repo.filtros.ventana_dias == 60 and repo.filtros.id_usuario == 7 and repo.filtros.ahora == AHORA
    assert r.ventana_dias == 60 and r.total == 1 and r.indicadores.vencidas == 3


@pytest.mark.parametrize(("kw", "codigo"), [
    ({"estado_evaluacion": "OTRO"}, "ESTADO_EVALUACION_INVALIDO"),
    ({"nivel_riesgo": 4}, "NIVEL_RIESGO_INVALIDO"),
    ({"pagina": 0}, "PAGINA_INVALIDA"),
    ({"por_pagina": 101}, "POR_PAGINA_INVALIDO"),
    ({"desde": AHORA, "hasta": AHORA - timedelta(days=1)}, "RANGO_FECHAS_INVALIDO"),
    ({"desde": AHORA - timedelta(days=400), "hasta": AHORA}, "RANGO_FECHAS_EXCESIVO"),
])
def test_parametros_invalidos_son_400(kw, codigo):
    with pytest.raises(ValidationError) as exc:
        _uc().execute(ids_fincas=None, id_usuario=1, ahora=AHORA, **kw)
    assert exc.value.code == codigo


@pytest.mark.parametrize(("cambios", "puede"), [
    ({}, True),
    ({"en_ventana": False}, False),                      # FUERA_DE_VENTANA_TEMPORAL
    ({"evaluada_por_mi": True}, False),                  # RETROALIMENTACION_DUPLICADA
    ({"activo_en_baja": True}, False),                   # ACTIVO_EN_BAJA
    ({"numero_evaluaciones": 1, "estado_evaluacion": "EVALUADO"}, True),  # otro veterinario sí
])
def test_puede_evaluar_sigue_las_reglas_del_registro(cambios, puede):
    assert replace(ITEM, **cambios).puede_evaluar is puede


@pytest.mark.parametrize("columna", ["estado_retroalimentacion", "tipo_modelo", "estado_version"])
def test_no_compara_enum_con_texto(columna):
    """El 500 de la ingesta en DEV: un ENUM comparado con un parámetro text. La bandeja no lo hace."""
    from src.prediction.infrastructure.repositories import bandeja_retroalimentacion_repository as repo

    for sql in (repo._SQL_LISTAR.text, repo._SQL_INDICADORES.text):
        assert not re.search(columna + r"\s*(=|<>|LIKE)\s*(CAST|:)", sql)


def test_ruta_bandeja(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.identity_access.infrastructure.dependencies import get_current_user
    from src.prediction.infrastructure.routers import retroalimentacion_clinica_router as router_mod
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    repo = _Repo()
    monkeypatch.setattr(router_mod, "SqlAlchemyBandejaRetroalimentacionRepository", lambda db: repo)
    monkeypatch.setattr(router_mod, "SqlAlchemyParametrosMLOpsRepository", lambda db: _Parametros())
    monkeypatch.setattr(router_mod, "AlcanceFincaAdapter",
                        lambda db: SimpleNamespace(listar_ids_fincas_permitidas=lambda u, r: [9]))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id_usuario=5, id_rol=3)
    for ruta in app.routes:  # 45·R lo prueba require_permission en sus propias pruebas
        if getattr(ruta, "path", "") == "/prediccion/retroalimentacion/bandeja":
            for dep in ruta.dependencies:
                app.dependency_overrides[dep.dependency] = lambda: None
    r = TestClient(app).get("/prediccion/retroalimentacion/bandeja",
                            params={"estado_evaluacion": "PENDIENTE", "nivel_riesgo": 3, "desde": "2026-10-01T00:00:00"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["indicadores"] == {"pendientes": 1, "evaluadas": 2, "vencidas": 3} and cuerpo["ventana_dias"] == 90
    assert cuerpo["items"][0]["puede_evaluar"] is True and cuerpo["items"][0]["identificador_activo"] == "BOV-003"
    assert repo.filtros.ids_fincas == [9] and repo.filtros.estado_evaluacion == "PENDIENTE"
    assert repo.filtros.desde == datetime(2026, 10, 1, tzinfo=timezone.utc)  # sin zona: UTC
