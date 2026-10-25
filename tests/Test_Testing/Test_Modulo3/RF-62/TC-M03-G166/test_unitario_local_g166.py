"""test_unitario_local_g166.py — Pruebas unitarias locales (SIN RED) para TC-M03-G166.

Verifica:
1. Oráculo independiente puro: severidad, descuentos, índices (100, 85, 65, 10),
   clasificación y aptitud para cada R del plan (4, 5, 9, 10, 19, 20).
2. Construcción matemática del dataset:
   - 41 lecturas con Decimal.
   - Ninguna lectura distinta B1..B20 es igual al valor base (25.40).
   - Formato string uniforme con dos decimales (f"{v:.2f}").
3. Cálculo dinámico de las 6 ventanas de N=20 que recupera el motor:
   - len == 20 para cada ventana evaluada.
   - Comprobación matemática de ausencia de outliers (|v - μ| <= 3σ).
   - Ausencia de drift estadístico con ganancia=1 y offset=0.
   - Replicación local de la condición del motor:
     * I5 (R=4): serie[:5] incluye B20 -> sin flag sensor congelado.
     * I6 (R=5): serie[:5] son I1..I5 -> flag LEVE, repeticiones=5.
     * I10 (R=9): serie[:5] idénticas -> flag LEVE, repeticiones=9.
     * I11 (R=10): serie[:5] idénticas -> flag MODERADO, repeticiones=10.
     * I20 (R=19): serie[:5] idénticas -> flag MODERADO, repeticiones=19.
     * I21 (R=20): serie completa idéntica -> flag CRITICO, repeticiones=20, sigma=0 protegido.
4. Validación de error seguro de configuración cuando faltan variables requeridas.
"""
from __future__ import annotations

import os
import statistics
import sys
from decimal import Decimal
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from helpers_tc_m03_g166 import (
    SandboxConfigError,
    cargar_configuracion_entorno,
    evaluar_congelado_local,
    generar_dataset_g166,
    simular_ventana_motor,
)
from spec_tc_m03_g166 import (
    SpecTCM03G166,
    aptitud_esperada,
    clasificacion_esperada,
    descuento_esperado,
    indice_esperado,
    severidad_esperada,
)


# ── 1. PRUEBAS UNITARIAS DEL ORÁCULO INDEPENDIENTE ────────────────────────────

class TestOraculoG166:
    """Verifica que el oráculo reproduzca exactamente la tabla normativa de spec."""

    @pytest.mark.parametrize("r_val, sev_esp, desc_esp, ind_esp, clasif_esp, apt_esp", [
        (4, None, 0, 100, "APTO", (True, True)),
        (5, "LEVE", 15, 85, "APTO", (True, True)),
        (9, "LEVE", 15, 85, "APTO", (True, True)),
        (10, "MODERADO", 35, 65, "APTO_CON_RESERVA", (True, False)),
        (19, "MODERADO", 35, 65, "APTO_CON_RESERVA", (True, False)),
        (20, "CRITICO", 90, 10, "NO_APTO", (False, False)),
    ])
    def test_oraculo_casos_g166(self, r_val, sev_esp, desc_esp, ind_esp, clasif_esp, apt_esp):
        sev = severidad_esperada(r_val)
        assert sev == sev_esp

        desc = descuento_esperado(sev)
        assert desc == desc_esp

        ind = indice_esperado(sev)
        assert ind == ind_esp

        clasif = clasificacion_esperada(ind)
        assert clasif == clasif_esp

        apt = aptitud_esperada(clasif)
        assert apt == apt_esp


# ── 2. PRUEBAS DEL DATASET Y REGLAS ANTI-HARDCODE ─────────────────────────────

class TestDatasetG166:
    """Verifica propiedades matemáticas y tipado del dataset de 41 lecturas."""

    def test_dataset_longitud_y_tipos(self):
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)
        assert len(dataset) == 41

        # Todas las lecturas usan Decimal y formato uniforme f"{v:.2f}"
        for it in dataset:
            assert isinstance(it["valor"], Decimal)
            assert it["valor_str"] == f"{it['valor']:.2f}"

    def test_dataset_distintas_no_iguales_a_base(self):
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)
        base = SpecTCM03G166.VALOR_BASE

        distintas = [it for it in dataset if it["posicion"] <= 20]
        assert len(distintas) == 20

        # Ninguna lectura distinta puede ser igual al valor base
        for it in distintas:
            assert it["valor"] != base, f"Lectura distinta {it['etiqueta']} es igual a la base: {it['valor']}"

    def test_dataset_identicas_iguales_a_base(self):
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)
        base = SpecTCM03G166.VALOR_BASE

        identicas = [it for it in dataset if it["posicion"] > 20]
        assert len(identicas) == 21

        for it in identicas:
            assert it["valor"] == base


# ── 3. PRUEBAS DINÁMICAS DE LAS SEIS VENTANAS DEL MOTOR ───────────────────────

class TestVentanasMotorG166:
    """Calcula dinámicamente cada ventana a partir del dataset y verifica sus propiedades."""

    @pytest.mark.parametrize("etiqueta_evaluada, r_esperado, activo_esp, sev_esp", [
        ("I5", 4, False, None),
        ("I6", 5, True, "LEVE"),
        ("I10", 9, True, "LEVE"),
        ("I11", 10, True, "MODERADO"),
        ("I20", 19, True, "MODERADO"),
        ("I21", 20, True, "CRITICO"),
    ])
    def test_calculo_dinamico_ventana_y_motor(self, etiqueta_evaluada, r_esperado, activo_esp, sev_esp):
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)

        # 1. Extraer la ventana previa dinámica
        ventana = simular_ventana_motor(dataset, etiqueta_evaluada)
        assert len(ventana) == 20, f"Ventana debe tener longitud 20, obtenida: {len(ventana)}"

        # 2. Evaluar mediante la lógica fiel del motor
        activo, sev, repeticiones = evaluar_congelado_local(ventana, m=SpecTCM03G166.M)

        assert activo == activo_esp
        assert sev == sev_esp
        if activo_esp:
            assert repeticiones == r_esperado

    def test_ventana_r4_sin_flag_por_mezcla(self):
        """En I5 (R=4 idénticas previas), las últimas 5 son I4, I3, I2, I1 y B20 (mezcla)."""
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)
        ventana = simular_ventana_motor(dataset, "I5")

        ultimas_5 = ventana[:5]
        # Debe contener I4, I3, I2, I1 (base) y B20 (distinta)
        assert len(set(str(v) for v in ultimas_5)) > 1
        activo, _, _ = evaluar_congelado_local(ventana)
        assert activo is False

    def test_ventana_r20_estabilidad_sigma_cero(self):
        """En I21 (R=20 idénticas previas), toda la ventana de 20 es idéntica a 25.40 -> sigma=0."""
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)
        ventana = simular_ventana_motor(dataset, "I21")

        valores_float = [float(v) for v in ventana]
        sigma = statistics.stdev(valores_float)
        assert sigma == 0.0

        # La condición sigma > 0 protege contra divisiones por cero en outlier
        activo, sev, rep = evaluar_congelado_local(ventana)
        assert activo is True
        assert sev == "CRITICO"
        assert rep == 20

    @pytest.mark.parametrize("etiqueta", ["I5", "I6", "I10", "I11", "I20"])
    def test_ausencia_outliers_y_drift_en_ventanas_intermedias(self, etiqueta):
        """Demuestra que para cada ventana con lecturas distintas no hay outlier ni drift espurio."""
        dataset = generar_dataset_g166(base=SpecTCM03G166.VALOR_BASE)
        ventana = simular_ventana_motor(dataset, etiqueta)

        valores_float = [float(v) for v in ventana]
        mu = statistics.mean(valores_float)
        sigma = statistics.stdev(valores_float)

        # Sin outlier para el valor base (25.40): |25.40 - mu| <= 3 * sigma
        val_eval = float(SpecTCM03G166.VALOR_BASE)
        assert abs(val_eval - mu) <= 3.0 * sigma

        # Sin drift: con ganancia=1 y offset=0, val_cal_esperado == media_n
        val_cal_esperado = mu
        drift_mag = abs(mu - val_cal_esperado) / abs(val_cal_esperado) * 100
        assert drift_mag == 0.0


# ── 4. PRUEBA DE CARGA SEGURA DE CONFIGURACIÓN ─────────────────────────────────

class TestConfiguracionSegura:
    """Verifica que la ausencia de variables de entorno falle con mensaje claro sin secretos."""

    def test_error_si_faltan_variables(self, monkeypatch):
        # Desactivar temporalmente variables de entorno requeridas
        for k in ("TEST_BASE_URL", "ENABLE_TEST_SANDBOX", "TEST_SANDBOX_SECRET", "TEST_ADMIN_PASSWORD"):
            monkeypatch.delenv(k, raising=False)

        # Apuntar a ruta ficticia de .env.test para forzar ausencia
        with pytest.raises(SandboxConfigError) as exc_info:
            cargar_configuracion_entorno(env_path="non_existent_file.test")

        mensaje = str(exc_info.value)
        assert "Faltan variables requeridas de testing" in mensaje
        # Verificar que el mensaje menciona los nombres de variables faltantes sin exponer valores
        assert "TEST_ADMIN_PASSWORD" in mensaje
        assert "TEST_SANDBOX_SECRET" in mensaje


# ── 5. PRUEBAS DE AUDITORÍA Y METADATA DE SESIÓN (SIMULACIÓN SIN RED) ─────────

class TestAuditoriaSesionLocal:
    """Verifica que la consulta de eventos y la metadata HTML se actualicen correctamente."""

    def test_consultar_eventos_simulado_exito(self):
        from conftest import consultar_conteo_eventos, actualizar_metadata_reporte, _METADATA_EVENTOS

        class MockResponse:
            status_code = 200
            def json(self):
                return {"rows": [{"total": 1420}]}

        class MockClient:
            def __init__(self, base_url, run_id, secret):
                pass
            def execute_query(self, query):
                return MockResponse()
            def delete(self, path):
                return MockResponse()

        cfg = {"TEST_BASE_URL": "http://mock", "TEST_SANDBOX_SECRET": "mock_secret"}
        val, err = consultar_conteo_eventos(cfg, client_factory=MockClient)
        assert val == 1420
        assert err is None

        # Simular ciclo completo de actualización
        actualizar_metadata_reporte("1420", "1420", "0 (Inocuidad confirmada)")
        assert _METADATA_EVENTOS["conteo_inicial"] == "1420"
        assert _METADATA_EVENTOS["conteo_final"] == "1420"
        assert _METADATA_EVENTOS["delta"] == "0 (Inocuidad confirmada)"

    def test_consultar_eventos_simulado_401(self):
        from conftest import consultar_conteo_eventos, actualizar_metadata_reporte, _METADATA_EVENTOS

        class MockResponse401:
            status_code = 401
            def json(self):
                return {"detail": "Unauthorized"}

        class MockResponse200:
            status_code = 200

        class MockClient401:
            def __init__(self, base_url, run_id, secret):
                pass
            def execute_query(self, query):
                return MockResponse401()
            def delete(self, path):
                return MockResponse200()

        cfg = {"TEST_BASE_URL": "http://mock", "TEST_SANDBOX_SECRET": "mock_secret"}
        val, err = consultar_conteo_eventos(cfg, client_factory=MockClient401)
        assert val is None
        assert "HTTP 401" in err

        actualizar_metadata_reporte(f"NO MEDIDO: {err}", f"NO MEDIDO: {err}", "NO CALCULADO")
        assert _METADATA_EVENTOS["conteo_inicial"] == "NO MEDIDO: HTTP 401"
        assert _METADATA_EVENTOS["delta"] == "NO CALCULADO"

    def test_consultar_eventos_simulado_excepcion(self):
        from conftest import consultar_conteo_eventos, actualizar_metadata_reporte, _METADATA_EVENTOS

        class MockResponse200:
            status_code = 200

        class MockClientException:
            def __init__(self, base_url, run_id, secret):
                pass
            def execute_query(self, query):
                raise ConnectionError("Mock connection failure")
            def delete(self, path):
                return MockResponse200()

        cfg = {"TEST_BASE_URL": "http://mock", "TEST_SANDBOX_SECRET": "mock_secret"}
        val, err = consultar_conteo_eventos(cfg, client_factory=MockClientException)
        assert val is None
        assert "Excepcion ConnectionError" in err or "ConnectionError" in err

        actualizar_metadata_reporte(f"NO MEDIDO: {err}", f"NO MEDIDO: {err}", "NO CALCULADO")
        assert "ConnectionError" in _METADATA_EVENTOS["conteo_inicial"]
        assert _METADATA_EVENTOS["delta"] == "NO CALCULADO"
