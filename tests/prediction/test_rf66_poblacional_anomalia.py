# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: puntaje de anomalía, resultado y RF-68        |
"""RF-66 POBLACIONAL: vector D4 de la cámara contra la línea base RF-24 del área."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.poblacional.evaluar_anomalia_poblacional_use_case import (
    EvaluarAnomaliaPoblacionalUseCase,
)
from src.prediction.domain.entities.anomalia_poblacional import nivel_poblacional, score_anomalia
from src.prediction.domain.repositories.observacion_poblacional_port import LotePoblacional, ObservacionPoblacional
from tests.prediction.test_rf68_disparo_automatico import _contexto, _disparo, _resultado

# Medidas de la cascada sobre los videos de prueba (cerdos moviéndose y cerdos echados).
BASE = {"densidad_actividad": 0.95, "dispersion_espacial": 0.25, "tasa_movimiento": 0.13}
NORMAL = {"densidad_actividad": 0.96, "dispersion_espacial": 0.249, "tasa_movimiento": 0.1323}
ECHADOS = {"densidad_actividad": 0.35, "dispersion_espacial": 0.14, "tasa_movimiento": 0.024}
FIN = datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)


def test_puntaje_y_nivel():
    assert score_anomalia(NORMAL, BASE) < D("0.02")
    # (0,6316 + 0,44 + 0,8154) / 3
    assert score_anomalia(ECHADOS, BASE) == D("0.6290")
    assert score_anomalia({"otra": 1}, BASE) is None
    assert score_anomalia({"tasa_movimiento": 5}, {"tasa_movimiento": 0.1}) == 1  # acotado
    assert [nivel_poblacional(D(s), D("0.5")) for s in ("0.2", "0.5", "0.74", "0.75")] == [0, 2, 2, 3]
    assert nivel_poblacional(D("0.9"), None) == 0  # sin umbral no se clasifica


def _uc(vector=ECHADOS, *, apto=True, base=BASE, ya=False, version=True, umbral=D("0.5")):
    obs = ObservacionPoblacional(9, 7, vector, apto, True, FIN - timedelta(minutes=1), FIN)
    port = SimpleNamespace(
        obtener=lambda i: obs, lotes=lambda a: [LotePoblacional(30, 4, "MODELO_PORCINOS")],
        linea_base=lambda a, e: base, ya_evaluado=lambda *a: ya,
    )
    versiones = Mock()
    versiones.obtener_activo_por_tipo.side_effect = lambda tipo, componente, estado: (
        SimpleNamespace(id_version_modelo=5, estado_version="SOMBRA")
        if version and (componente, estado) == ("DETECTOR", "SOMBRA") else None)
    config = SimpleNamespace(obtener_por_tipo=lambda t: SimpleNamespace(es_activa=True, umbral_score_anomalia=umbral))
    repo, db, disparar = Mock(), Mock(), Mock()
    repo.guardar.side_effect = lambda r: r
    uc = EvaluarAnomaliaPoblacionalUseCase(db=db, observacion_port=port, config_repo=config,
                                           version_repo=versiones, resultado_repo=repo, disparar=disparar)
    return uc, repo, db, disparar


def test_observacion_apta_deja_resultado_en_sombra_con_la_forma_del_front_y_dispara_rf68():
    uc, repo, db, disparar = _uc()
    [r] = uc.execute(9)
    assert (r.id_activo_biologico, r.tipo_modelo, r.id_version_modelo, r.id_especie) == (30, "MODELO_PORCINOS", 5, 4)
    assert r.probabilidad_riesgo == {"score_anomalia": 0.629, "umbral_score_anomalia": 0.5}
    assert (r.nivel_riesgo, r.modo_sombra, r.probabilidad_enfermedad, r.fecha_fin_ventana) == (2, True, {}, FIN)
    assert r.confianza_global == D("0.5") and r.contexto_incompleto  # calidad DEGRADADA
    db.commit.assert_called_once()
    disparar.assert_called_once_with(r)


@pytest.mark.parametrize("cambios", [dict(apto=False), dict(base=None), dict(ya=True), dict(version=False)])
def test_no_deja_resultado_sin_aptitud_linea_base_version_o_si_ya_existe(cambios):
    uc, repo, _, disparar = _uc(**cambios)
    assert uc.execute(9) == []
    repo.guardar.assert_not_called()
    disparar.assert_not_called()


def test_si_rf68_falla_el_resultado_queda():
    uc, repo, db, disparar = _uc()
    disparar.side_effect = RuntimeError("caída")
    assert len(uc.execute(9)) == 1
    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_rf68_recibe_el_puntaje_como_fs_poblacional():
    uc, estimar = _disparo(_contexto())
    resultado = _resultado()
    resultado.probabilidad_riesgo = {"score_anomalia": 0.629, "umbral_score_anomalia": 0.5}
    uc.execute(resultado)
    dto = estimar.execute_sistema.call_args.args[0]
    assert dto.score_anomalia == D("0.629") and dto.salidas_rf66 == []
