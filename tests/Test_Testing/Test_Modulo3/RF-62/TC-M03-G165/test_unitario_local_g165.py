"""test_unitario_local_g165.py — Pruebas unitarias puramente locales en memoria.

Valida:
1. Oráculo independiente contra la spec (casos 60, 40, 0, 100, 35 y saturación).
2. Helpers de serie determinista y cálculo de offset para drift desde media real.
3. Helpers de cálculo de valor outlier con y sin offset.
4. Validación estricta de que la falta de variables de entorno lanza excepción clara sin filtrar secretos.
"""
from __future__ import annotations

import os
import pytest
from datetime import datetime, timezone

import sys
from pathlib import Path
_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from spec_tc_m03_g165 import (
    SpecAptitud,
    SpecDescuentos,
    SpecEstados,
    SpecParametrosBase,
    SpecUmbrales,
    calcular_indice_esperado,
    clasificar_esperado,
)
from helpers_tc_m03_g165 import (
    SandboxConfigError,
    calcular_offset_para_drift,
    calcular_valor_outlier_crudo,
    cargar_configuracion_entorno,
    generar_serie_temporal_determinista,
)


class TestOraculoNormativo:
    """Valida los cálculos del oráculo independiente puro contra la especificación."""

    def test_oraculo_s_base_nominal_indice_100(self):
        flags = {}
        idx = calcular_indice_esperado(flags)
        clase = clasificar_esperado(idx)
        ia, nic41 = SpecAptitud.derivar(clase)
        assert idx == 100
        assert clase == "APTO"
        assert ia is True and nic41 is True

    def test_oraculo_s_318a_outlier_drift_gap_indice_60(self):
        flags = {
            "outlier_estadistico": True,       # -20
            "posible_drift": 7.0,              # < 10% -> -10
            "gap_temporal_anomalo": True,      # -10
        }
        idx = calcular_indice_esperado(flags)
        clase = clasificar_esperado(idx)
        ia, nic41 = SpecAptitud.derivar(clase)
        assert idx == 60
        assert clase == "APTO_CON_RESERVA"
        assert ia is True and nic41 is False

    def test_oraculo_s_318b_congelado_moderado_drift_15_indice_40(self):
        flags = {
            "sensor_congelado": "MODERADO",    # -35
            "posible_drift": 15.0,             # 10%-20% -> -25
        }
        idx = calcular_indice_esperado(flags)
        clase = clasificar_esperado(idx)
        ia, nic41 = SpecAptitud.derivar(clase)
        assert idx == 40
        assert clase == "APTO_CON_RESERVA"
        assert ia is True and nic41 is False

    def test_oraculo_s_318c_saturacion_en_cero(self):
        flags = {
            "sensor_congelado": "CRITICO",     # -90
            "outlier_estadistico": True,       # -20
        }
        idx = calcular_indice_esperado(flags)
        clase = clasificar_esperado(idx)
        ia, nic41 = SpecAptitud.derivar(clase)
        # 100 - (90 + 20) = -10 -> max(0, -10) = 0
        assert idx == 0
        assert clase == "NO_APTO"
        assert ia is False and nic41 is False

    def test_oraculo_s_320_no_apto_combinado_indice_35(self):
        flags = {
            "sensor_congelado": "MODERADO",    # -35
            "outlier_estadistico": True,       # -20
            "gap_temporal_anomalo": True,      # -10
        }
        idx = calcular_indice_esperado(flags)
        clase = clasificar_esperado(idx)
        ia, nic41 = SpecAptitud.derivar(clase)
        assert idx == 35
        assert clase == "NO_APTO"
        assert ia is False and nic41 is False


class TestHelpersMatematicosLocales:
    """Valida los algoritmos de series y offsets en memoria con datos simulados."""

    def test_generar_serie_temporal_determinista(self):
        t_ref = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
        valores = [20.0, 20.2, 19.8]
        serie = generar_serie_temporal_determinista(t_ref, valores, intervalo_min=10)
        assert len(serie) == 3
        # El último elemento es en t_ref
        assert serie[-1]["timestamp"] == t_ref.isoformat()
        assert serie[-1]["valor"] == 19.8
        # El primero es 20 min antes
        assert serie[0]["timestamp"] == (t_ref - pytest.importorskip("datetime").timedelta(minutes=20)).isoformat()
        assert serie[0]["valor"] == 20.0

    def test_calcular_offset_para_drift_7_pct(self):
        media_serie = 20.0
        drift = 0.07
        offset = calcular_offset_para_drift(media_serie, drift)
        # val_cal_esperado = media_serie + offset = 20.0 - 1.3084 = 18.6916
        # drift_rel = |20.0 - 18.6916| / 18.6916 = 1.3084 / 18.6916 = 7.00%
        val_cal = media_serie + offset
        drift_rel = abs(media_serie - val_cal) / val_cal
        assert abs(drift_rel - 0.07) < 0.001

    def test_calcular_offset_para_drift_15_pct(self):
        media_serie = 20.0
        drift = 0.15
        offset = calcular_offset_para_drift(media_serie, drift)
        val_cal = media_serie + offset
        drift_rel = abs(media_serie - val_cal) / val_cal
        assert abs(drift_rel - 0.15) < 0.001

    def test_calcular_valor_outlier_crudo_con_sigma_normal(self):
        media = 20.0
        sigma = 0.5
        v = calcular_valor_outlier_crudo(media, sigma, multiplicador_sigma=6.0)
        # 20.0 + 6 * 0.5 = 23.0
        assert v == 23.0

    def test_calcular_valor_outlier_crudo_con_sigma_cero(self):
        media = 20.0
        sigma = 0.0
        v = calcular_valor_outlier_crudo(media, sigma)
        assert v > media
        assert v == 26.0


class TestValidacionSeguridadConfiguracion:
    """Valida que la falta de variables lance error claro sin exponer credenciales."""

    def test_falla_sin_variables_de_entorno(self, monkeypatch):
        # Desactivar variables para probar la excepción
        for k in ("TEST_BASE_URL", "ENABLE_TEST_SANDBOX", "TEST_SANDBOX_SECRET", "TEST_ADMIN_PASSWORD"):
            monkeypatch.setenv(k, "")
        
        # Simular lectura sin .env.test accesible
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        with pytest.raises(SandboxConfigError) as exc_info:
            cargar_configuracion_entorno()
        msg = str(exc_info.value)
        assert "Faltan variables requeridas de testing" in msg
        # Verificar que no contenga valores de contraseñas ni secretos si estuvieran en entorno
        dummy_pass = os.environ.get("TEST_ADMIN_PASSWORD")
        if dummy_pass:
            assert dummy_pass not in msg
        dummy_sec = os.environ.get("TEST_SANDBOX_SECRET")
        if dummy_sec:
            assert dummy_sec not in msg
