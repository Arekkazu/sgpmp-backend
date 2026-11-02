# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 C21.4: exposición a focos vecinos en RF-68 y recálculo de áreas expuestas |
"""RFC-021 C21.4: P = P_base + (1 − P_base)·λ·Fv con Fv = 1 − Π(1 − w·Fs)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.riesgo_contagio.disparar_riesgo_contagio_use_case import (
    DispararRiesgoContagioUseCase,
)
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.domain.entities.riesgo_contagio import (
    DatosContagioError,
    FocoVecino,
    calcular_exposicion,
)
from src.prediction.domain.repositories.contexto_contagio_port import ContextoContagio, SalidaReciente
from tests.prediction.test_rf68_riesgo_contagio import AHORA, _calcular, _dto, _use_case

POTRERO_1 = FocoVecino(id_area=2, via="AGUA", peso=D("0.6"), factor_sanitario=D("1"))
POTRERO_2 = FocoVecino(id_area=4, via="PROXIMIDAD", peso=D("0.4"), factor_sanitario=D("1"))


def test_exposicion_es_la_probabilidad_de_que_llegue_algo_de_algun_foco():
    assert calcular_exposicion([]) == D("0")
    assert calcular_exposicion([POTRERO_1]) == D("0.6")
    # 1 − (1 − 0,6)·(1 − 0,4) = 0,76
    assert calcular_exposicion([POTRERO_1, POTRERO_2]) == D("0.76")
    # Un foco a medias (Fs = 0,5) por una arista de peso 0,6 aporta 0,3.
    assert calcular_exposicion([FocoVecino(2, "AGUA", D("0.6"), D("0.5"))]) == D("0.3")


def test_la_exposicion_se_suma_sobre_la_base_y_sin_focos_nada_cambia():
    base = _calcular()
    assert base.exposicion == {} and base.probabilidad_contagio == D("0.3750")

    expuesto = _calcular(focos_vecinos=[POTRERO_1])
    # 0,375 + (1 − 0,375)·0,5·0,6 = 0,5625 → MEDIO
    assert expuesto.probabilidad_contagio == D("0.5625") and expuesto.nivel_texto == "MEDIO"
    assert expuesto.exposicion["p_base"] == "0.3750" and expuesto.exposicion["fv"] == "0.6000"
    assert expuesto.exposicion["focos"] == [{"id_area": 2, "via": "AGUA", "peso": "0.6", "factor_sanitario": "1"}]


def test_area_expuesta_sin_inferencias_propias_se_calcula_con_fs_ausente():
    with pytest.raises(DatosContagioError):
        _calcular(salidas_rf66=[], total_activos_lote=None)
    r = _calcular(salidas_rf66=[], total_activos_lote=None, exigir_cobertura_rf66=False,
                  focos_vecinos=[POTRERO_1])
    assert r.factor_sanitario is None and "fs" in r.factores_ausentes and r.confianza_baja
    assert r.exposicion["fv"] == "0.6000"


def test_el_caso_de_uso_suma_los_focos_del_puerto_y_cambian_la_huella():
    uc, _, _ = _use_case()
    sin_focos = uc.execute(_dto(), 1, 3)
    uc.exposicion_port = SimpleNamespace(focos_hacia=lambda id_lote, desde: [POTRERO_1])
    con_focos = uc.execute(_dto(), 1, 3)
    assert not con_focos.desde_cache and con_focos.huella_entradas != sin_focos.huella_entradas
    assert con_focos.exposicion["focos"][0]["via"] == "AGUA"


def _resultado():
    return ResultadoInferencia(
        id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=2, tipo_modelo="MODELO_ESPECIES_GRANDES",
        id_version_modelo=1, nivel_riesgo=3, probabilidad_riesgo={"3": 0.98}, probabilidad_enfermedad={"13": 0.98},
        confianza_global=D("0.98"), contexto_incompleto=False, modo_ejecucion="SERVIDOR", modo_sombra=True,
        fecha_inferencia=datetime.now(timezone.utc),
    )


def test_el_foco_recalcula_sus_vecinas_sin_alerta_y_con_su_salida_propia_si_es_reciente():
    propia = SalidaReciente({"3": 0.1}, AHORA, True)
    contexto = SimpleNamespace(
        obtener=lambda id_activo, instante: ContextoContagio(D("0.01"), D("100"), None),
        ultima_salida_rf66=lambda id_activo, desde: propia if id_activo == 3 else None,
    )
    estimar = Mock()
    exposicion = SimpleNamespace(lotes_expuestos=lambda id_lote: [3, 4, 2])
    DispararRiesgoContagioUseCase(contexto_port=contexto, estimar=estimar, exposicion_port=exposicion).execute(
        _resultado())

    llamadas = [(c.args[0].id_lote, len(c.args[0].salidas_rf66), c.kwargs["alertar"],
                 c.kwargs["exigir_cobertura_rf66"]) for c in estimar.execute_sistema.call_args_list]
    # Foco (en sombra: no alerta), Corral 1 con su salida reciente y Potrero 2 sin salida; el foco no se repite.
    assert llamadas == [(2, 1, False, True), (3, 1, False, False), (4, 0, False, False)]
