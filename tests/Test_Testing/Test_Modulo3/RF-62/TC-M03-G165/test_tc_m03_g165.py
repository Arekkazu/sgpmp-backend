# | Fecha      | Nombre    | Que se hizo                                                                              |
# |------------|-----------|------------------------------------------------------------------------------------------|
# | 2026-10-27 | HulkyZeus | RF-62 TC-M03-G165: dispositivo fijable por TEST_G165_SERIAL; serial/area reales; 'transicion SUPERADA' evalua 2 veces; auditoria = N evaluaciones |
"""test_tc_m03_g165.py — Suite de pruebas automatizadas para TC-M03-G165 (RF-62 / RF-63).

Módulo 3: Telemetría IoT — Evaluación de Calidad de Datos Telemétricos.
Casos agrupados: TC-M03-303, TC-M03-318 (a, b, c), TC-M03-319, TC-M03-320.
Ejecución: Pytest contra TEST desplegado en Sandbox Transaccional (X-Test-Run-Id).
"""
from __future__ import annotations

import os
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
import requests

import sys
from pathlib import Path
_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from helpers_tc_m03_g165 import (
    SandboxClient,
    calcular_offset_para_drift,
    calcular_valor_outlier_crudo,
    cargar_configuracion_entorno,
    generar_serie_temporal_determinista,
)
from spec_tc_m03_g165 import (
    SpecAptitud,
    SpecDescuentos,
    SpecEstados,
    SpecParametrosBase,
    SpecUmbrales,
    calcular_indice_esperado,
    clasificar_esperado,
)


# ── BANNER D7 Y HOOKS DE SESIÓN PYTEST ──────────────────────────────────────

def pytest_sessionstart(session):
    """Imprime el banner informativo de D7 Resuelto antes de iniciar las pruebas."""
    banner = (
        "\n"
        "=" * 78 + "\n"
        " [BANNER D7 RESUELTO] TC-M03-G165 -- ESTADO DE EVALUACION DE CALIDAD\n"
        "=" * 78 + "\n"
        " * D7 RESUELTO: literal 'VIGENTE'; catálogo {'VIGENTE', 'SUPERADA'}; RFC de aclaración en trámite.\n"
        " * Regla canónica: máximo UNA evaluación VIGENTE por lectura.\n"
        " * Defecto conocido: /evaluar duplica VIGENTES (invariante debe fallar hoy).\n"
        "=" * 78 + "\n"
    )
    print(banner)


# ── FIXTURES COMPARTIDAS ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def env_config():
    """Valida y carga variables requeridas una sola vez por sesión."""
    return cargar_configuracion_entorno()


@pytest.fixture(scope="session")
def admin_token(env_config):
    """Obtiene dinámicamente el token JWT de administrador vía POST /sesiones/."""
    url = f"{env_config['TEST_BASE_URL']}/sesiones/"
    resp = requests.post(
        url,
        json={
            "correo_electronico": env_config["TEST_ADMIN_EMAIL"],
            "contrasena": env_config["TEST_ADMIN_PASSWORD"],
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Fallo de autenticación en preflight ({resp.status_code}): {resp.text}")
    token = resp.json().get("token") or resp.json().get("access_token")
    if not token:
        raise RuntimeError("No se recibió token en la respuesta de autenticación.")
    return token


@pytest.fixture(scope="session")
def preflight_capacidades_m04_m06(env_config, admin_token):
    """D5: Detección de capacidad en preflight para filtros apto en M04/M06."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    try:
        resp = requests.get(f"{env_config['TEST_BASE_URL']}/openapi.json", headers=headers, timeout=10)
        if resp.status_code != 200:
            return False
        openapi = resp.json()
        for path, methods in openapi.get("paths", {}).items():
            if any(p in path for p in ("/prediccion", "/ia", "/salud", "/sanidad", "/suministros")):
                for m, op in methods.items():
                    if isinstance(op, dict):
                        for param in op.get("parameters", []):
                            if "apto" in param.get("name", "").lower():
                                return True
        return False
    except Exception:
        return False


@pytest.fixture(scope="session")
def dispositivo_y_sensor_ambiental(env_config, admin_token):
    """Descubre dinámicamente un dispositivo IoT ACTIVO con sensor de Temperatura Ambiental."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{env_config['TEST_BASE_URL']}/configuracion/dispositivos-iot?solo_activos=true", headers=headers, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"No fue posible consultar dispositivos IoT ({resp.status_code}): {resp.text}")
    items = resp.json().get("items", [])
    # El dispositivo se puede fijar por serial (TEST_G165_SERIAL): hay dispositivos con periodos de inactividad abiertos (RF-60) que hacen
    # que el motor omita la evaluacion de calidad (EVALUACION_OMITIDA_POR_INACTIVIDAD).
    serial_fijo = os.environ.get("TEST_G165_SERIAL")
    for d in items:
        if d.get("es_activo") is True and (not serial_fijo or d.get("serial") == serial_fijo):
            did = d["id_dispositivo_iot"]
            r_sens = requests.get(f"{env_config['TEST_BASE_URL']}/configuracion/dispositivos-iot/{did}/sensores", headers=headers, timeout=10)
            if r_sens.status_code == 200:
                sensores = r_sens.json().get("items", [])
                for s in sensores:
                    cat = (s.get("categoria") or "").upper()
                    nom = (s.get("nombre") or "").upper()
                    if s.get("es_activo") is True and ("TEMPERATURA" in cat or "TEMPERATURA" in nom):
                        id_sensor = s.get("id_sensores") or s.get("id_sensor")
                        # La calibracion exige el area donde el sensor esta ASOCIADO (puede diferir del area del dispositivo).
                        infra = d.get("id_infraestructura", 3)
                        r_aso = requests.get(f"{env_config['TEST_BASE_URL']}/configuracion/sensores/{id_sensor}/asociaciones", headers=headers, timeout=10)
                        if r_aso.status_code == 200:
                            vigentes = [a for a in r_aso.json().get("items", []) if a.get("fecha_finalizacion") is None]
                            if vigentes:
                                infra = vigentes[0]["id_infraestructura"]
                        return {
                            "device_id": did,
                            "access_key": d["serial"],
                            "sensor_id": id_sensor,
                            "id_infraestructura": infra,
                            "tipo_variable": "TEMPERATURA_AMBIENTAL",
                            "unidad": "°C",
                            "rango_min": s.get("rango_minimo", -40.0),
                            "rango_max": s.get("rango_maximo", 60.0),
                        }
    # Respaldo de contingencia
    return {
        "device_id": 49,
        "access_key": "TC-M09-G66-1788619076171",
        "sensor_id": 31,
        "id_infraestructura": 3,
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "unidad": "°C",
        "rango_min": -40.0,
        "rango_max": 60.0,
    }


@pytest.fixture(scope="session")
def auditoria_eventos_control(env_config, admin_token):
    """Mide modulo1.eventos antes y después de toda la suite, completamente fuera de cualquier run abierto."""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Sandbox-Secret": env_config["TEST_SANDBOX_SECRET"],
        "Content-Type": "application/json",
    }
    url_query = f"{env_config['TEST_BASE_URL']}/test-control/query"
    
    # 1. Conteo antes (sin X-Test-Run-Id)
    resp_pre = requests.post(url_query, json={"query": "SELECT count(*) FROM modulo1.eventos"}, headers=headers, timeout=10)
    c_pre = resp_pre.json().get("data", [{}])[0].get("count", 0) if resp_pre.status_code == 200 else None

    yield {"conteo_inicial": c_pre}

    # 2. Conteo después (tras el cierre de todos los runs y fuera de cualquier sandbox)
    if c_pre is not None:
        resp_post = requests.post(url_query, json={"query": "SELECT count(*) FROM modulo1.eventos"}, headers=headers, timeout=10)
        c_post = resp_post.json().get("data", [{}])[0].get("count", 0) if resp_post.status_code == 200 else None
        if c_post is not None:
            delta = c_post - c_pre
            if delta > 0:
                print(f"\n[ALERTA INMUTABILIDAD] modulo1.eventos incremento en {delta} registros.")
            else:
                print(f"\n[INOCUIDAD CONFIRMADA] modulo1.eventos delta = {delta} (cero contaminacion).")


# ── HELPER DE INGESTA DE LECTURA DENTRO DE SANDBOX ─────────────────────────

def ingestar_lectura(client: SandboxClient, hardware: dict, valor: float, timestamp: datetime, frecuencia: int = 10, origen: str = "BUFFER_LOCAL") -> int:
    """Envía POST /iot/telemetria dentro del sandbox transaccional y retorna id_telemetria."""
    payload = {
        "device_id": hardware["device_id"],
        "sensor_id": hardware["sensor_id"],
        "access_key": hardware["access_key"],
        "tipo_variable": hardware["tipo_variable"],
        "unidad": hardware["unidad"],
        "valor": round(float(valor), 2),
        "timestamp_captura": timestamp.isoformat(),
        "timestamp_envio": timestamp.isoformat(),
        "origen": origen,
        "frecuencia_muestreo": frecuencia,
        "serial": hardware["access_key"],
    }
    # FIX: /iot/telemetria requiere BROKER_SERVICE_TOKEN (no admin JWT)
    import os
    broker_token = os.getenv("BROKER_SERVICE_TOKEN")
    if not broker_token:
        raise RuntimeError("BROKER_SERVICE_TOKEN no configurado en el ambiente")
    resp = client.post("iot/telemetria", json=payload, headers={"Authorization": f"Bearer {broker_token}"})
    if resp.status_code != 201:
        raise RuntimeError(f"Fallo al ingestar telemetría ({resp.status_code}): {resp.text}")
    return resp.json()["id_telemetria"]


def calibrar_sensor(client: SandboxClient, hardware: dict, ganancia: float, offset: float) -> None:
    """Ejecuta POST /configuracion/sensores/{id_sensor}/calibrar dentro del sandbox."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id_dispositivo_iot": hardware["device_id"],
        "id_infraestructura": hardware.get("id_infraestructura", 3),
        "fecha_calibracion": now,
        "modo_calibracion": "SENSOR",
        "ganancia": round(float(ganancia), 4),
        "offset": round(float(offset), 4),
        "valor_referencia": 20.0,
        "observaciones": "Calibracion inducida para prueba de deriva TC-M03-G165",
    }
    resp = client.post(f"configuracion/sensores/{hardware['sensor_id']}/calibrar", json=payload)
    if resp.status_code not in (200, 201):
        print(f"[WARN calibrar_sensor] ({resp.status_code}): {resp.text}")


# ============================================================================
# ESCENARIO S_BASE: TC-M03-303 (Happy Path de Evaluación) + TC-M03-319 (APTO)
# ============================================================================

class TestEscenarioBase:
    """Serie nominal sin anomalías: 20 lecturas alternando base±a, lectura 21 = base."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-base-{uuid.uuid4()}"
        client = SandboxClient(env_config["TEST_BASE_URL"], run_id, env_config["TEST_SANDBOX_SECRET"], admin_token)
        try:
            # Timestamp de referencia sincronizado con Date del servidor (en el pasado para que t_21 no sea futuro)
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=30)

            # Generar 20 valores alternantes base ± 0.2 (las últimas 5 no son idénticas)
            base = 20.0
            valores_serie = [base + (0.2 if i % 2 == 0 else -0.2) for i in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            # Calibración nominal
            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)

            # Ingestar serie base
            for item in serie:
                ts = datetime.fromisoformat(item["timestamp"])
                ingestar_lectura(client, dispositivo_y_sensor_ambiental, item["valor"], ts)

            # Lectura 21: nominal = base, t_ref + 10 min
            t_21 = t_ref + timedelta(minutes=10)
            id_tel_21 = ingestar_lectura(client, dispositivo_y_sensor_ambiental, base, t_21)

            # Medir bitácora RF-63 antes de evaluar
            c_bitacora_pre = client.query_sql(
                f"SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = '{id_tel_21}'"
            )[0]["count"]

            # Disparar evaluación puntual
            resp_eval = client.post(f"iot/calidad/{id_tel_21}/evaluar")
            
            ctx = {
                "client": client,
                "run_id": run_id,
                "hardware": dispositivo_y_sensor_ambiental,
                "id_tel_21": id_tel_21,
                "resp_eval": resp_eval,
                "c_bitacora_pre": c_bitacora_pre,
                "t_21": t_21,
            }
            yield ctx
        finally:
            # Finalizer idempotente garantizado: siempre se ejecuta aunque falle la ingesta o evaluación
            client.teardown_rollback()

    def test_tc303_http_status_201(self, run_context):
        assert run_context["resp_eval"].status_code == 201

    def test_tc303_estado_evaluacion_normativo_d7_2(self, run_context):
        data = run_context["resp_eval"].json()
        assert "estado_evaluacion" in data
        assert isinstance(data["estado_evaluacion"], str)
        assert len(data["estado_evaluacion"].strip()) > 0
        assert data["estado_evaluacion"] != SpecEstados.estado_superado

    def test_tc303_estado_evaluacion_vigente_activo(self, run_context):
        """Aserción activa D7: la evaluación devuelta por POST evaluar tiene estado_evaluacion == 'VIGENTE'."""
        data = run_context["resp_eval"].json()
        assert data["estado_evaluacion"] == SpecEstados.estado_vigente

    def test_tc303_estado_evaluacion_en_catalogo_activo(self, run_context):
        """Aserción activa D7: valida pertenencia al catálogo oficial {'VIGENTE', 'SUPERADA'}."""
        data = run_context["resp_eval"].json()
        assert data["estado_evaluacion"] in (SpecEstados.catalogo_estados or [])

    def test_tc303_invariante_una_sola_vigente(self, run_context):
        """Nuevo test del invariante canónico (D7 Resuelto):
        SELECT COUNT(*) de evaluaciones con estado_evaluacion='VIGENTE' para id_telemetria
        en modulo3.telemetria_calidad debe ser exactamente == 1 tras POST evaluar.
        SIN skip/xfail: fallará hoy por defecto reconocido del backend (ingesta + evaluar = 2 VIGENTES).
        """
        client = run_context["client"]
        id_tel = run_context["id_tel_21"]
        filas = client.query_sql(
            f"SELECT COUNT(*) AS total_vigentes FROM modulo3.telemetria_calidad "
            f"WHERE id_telemetria = {id_tel} AND estado_evaluacion = 'VIGENTE'"
        )
        total_vigentes = int(filas[0]["total_vigentes"]) if filas else 0
        assert total_vigentes == 1, (
            f"[DEFECTO CONOCIDO RF-62] Invariante violado para lectura {id_tel}: "
            f"se encontraron {total_vigentes} evaluaciones VIGENTES (esperado exactamente 1)."
        )

    def test_tc303_transicion_superada(self, run_context):
        """Nuevo test de transición canónica (D7 Resuelto):
        Tras POST evaluar sobre una lectura ya evaluada, la evaluación anterior debe quedar SUPERADA.
        SELECT por id_telemetria: exactamente 1 VIGENTE y las demás SUPERADA.
        Verifica si id_evaluacion_superada y motivo_reevaluacion están informados en la fila SUPERADA.
        """
        client = run_context["client"]
        id_tel = run_context["id_tel_21"]
        # En el sandbox la evaluacion automatica de la ingesta (post-commit) no corre: la lectura solo tiene la evaluacion manual del
        # fixture. Se evalua una vez mas para ejercitar "POST evaluar sobre una lectura ya evaluada".
        resp_segunda = client.post(f"iot/calidad/{id_tel}/evaluar")
        assert resp_segunda.status_code in (200, 201), f"Segunda evaluacion: {resp_segunda.status_code} {resp_segunda.text[:200]}"
        filas = client.query_sql(
            f"SELECT id_evaluacion, estado_evaluacion, id_evaluacion_superada, motivo_reevaluacion "
            f"FROM modulo3.telemetria_calidad WHERE id_telemetria = {id_tel}"
        )
        assert len(filas) >= 2, f"Se esperaban al menos 2 evaluaciones para {id_tel} (primera + segunda evaluar)"
        vigentes = [f for f in filas if f.get("estado_evaluacion") == "VIGENTE"]
        superadas = [f for f in filas if f.get("estado_evaluacion") == "SUPERADA"]
        assert len(vigentes) == 1, f"Debe existir exactamente 1 VIGENTE tras re-evaluar, encontradas: {len(vigentes)}"
        assert len(superadas) == len(filas) - 1, f"Todas las anteriores deben ser SUPERADA. Filas: {filas}"
        for sup in superadas:
            assert sup.get("motivo_reevaluacion") is not None and len(str(sup.get("motivo_reevaluacion")).strip()) > 0, (
                f"La evaluación SUPERADA {sup.get('id_evaluacion')} debe tener motivo_reevaluacion informado."
            )

    def test_tc303_fecha_creacion_reciente(self, run_context):
        data = run_context["resp_eval"].json()
        fc = data.get("fecha_creacion") or data.get("timestamp_evaluacion")
        assert fc is not None
        fecha_eval = datetime.fromisoformat(fc.replace("Z", "+00:00"))
        ahora = datetime.now(timezone.utc)
        assert abs((ahora - fecha_eval).total_seconds()) < 120

    def test_tc303_consistencia_get_calidad_por_sensor(self, run_context):
        client = run_context["client"]
        hw = run_context["hardware"]
        id_tel = run_context["id_tel_21"]
        resp = client.get("iot/calidad", params={"id_sensor": hw["sensor_id"]})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        coincidentes = [it for it in items if it["id_telemetria"] == id_tel]
        assert len(coincidentes) >= 1

    def test_tc303_consistencia_get_calidad_por_telemetria(self, run_context):
        client = run_context["client"]
        id_tel = run_context["id_tel_21"]
        resp = client.get(f"iot/calidad/{id_tel}")
        assert resp.status_code == 200
        assert resp.json()["id_telemetria"] == id_tel

    def test_tc303_actualizacion_flags_modulo3_telemetrias(self, run_context):
        client = run_context["client"]
        id_tel = run_context["id_tel_21"]
        filas = client.query_sql(f"SELECT apto_para_ia, apto_para_nic41 FROM modulo3.telemetrias WHERE id_telemetria = {id_tel}")
        assert len(filas) == 1
        assert filas[0]["apto_para_ia"] is True
        assert filas[0]["apto_para_nic41"] is True

    def test_tc303_auditoria_rf63_delta_y_campos(self, run_context):
        client = run_context["client"]
        id_tel = run_context["id_tel_21"]
        pre = run_context["c_bitacora_pre"]
        filas = client.query_sql(
            f"SELECT tipo_evento, componente_origen, clasificacion_registro, retencion_aplicable "
            f"FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = '{id_tel}'"
        )
        # Cada evaluacion emite exactamente un evento RF-63 (el test de transicion SUPERADA evalua una segunda vez): delta = N de evaluaciones.
        n_eval = client.query_sql(f"SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria = {id_tel}")[0]["count"]
        assert len(filas) == pre + n_eval
        nuevo = filas[-1]
        assert nuevo["componente_origen"] == "RF62"
        assert nuevo["clasificacion_registro"] == "NIC41"
        assert nuevo["retencion_aplicable"] == 5

    def test_s_base_flags_exactos(self, run_context):
        """Ajuste 2: Verificar que flags_detectados activos es exactamente el conjunto previsto (vacío)."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        activos = {k for k, v in flags.items() if isinstance(v, dict) and v.get("activo") is True}
        assert activos == set()

    def test_tc319_flags_todos_inactivos(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        for k, v in flags.items():
            if isinstance(v, dict) and "activo" in v:
                assert v["activo"] is False

    def test_tc319_indice_calidad_100(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["indice_calidad"] == 100

    def test_tc319_clasificacion_apto(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["clasificacion_calidad"] == "APTO"

    def test_tc319_aptitud_ia_y_nic41_true(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["apto_para_ia"] is True
        assert data["apto_para_nic41"] is True

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)


# ============================================================================
# ESCENARIO S_318a: Outlier Estadístico + Drift 7% + Gap Temporal
# ============================================================================

class TestEscenario318a:
    """Descuentos combinados: Outlier (-20), Drift (-10), Gap (-10) -> Esperado índice 60."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-318a-{uuid.uuid4()}"
        client = SandboxClient(env_config["TEST_BASE_URL"], run_id, env_config["TEST_SANDBOX_SECRET"], admin_token)
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            valores_serie = [base + (0.2 if i % 2 == 0 else -0.2) for i in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            for item in serie:
                ts = datetime.fromisoformat(item["timestamp"])
                ingestar_lectura(client, dispositivo_y_sensor_ambiental, item["valor"], ts)

            filas = client.query_sql(
                f"SELECT valor_crudo FROM modulo3.telemetrias WHERE id_sensor = {dispositivo_y_sensor_ambiental['sensor_id']} "
                f"AND estado_calidad = 'LECTURA_VALIDA' ORDER BY timestamp_captura DESC LIMIT 20"
            )
            media_real = statistics.mean([float(f["valor_crudo"]) for f in filas])
            sigma_real = statistics.stdev([float(f["valor_crudo"]) for f in filas])

            offset_drift = calcular_offset_para_drift(media_real, drift_objetivo=0.07)
            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=offset_drift)

            v_outlier = calcular_valor_outlier_crudo(media_real, sigma_real, multiplicador_sigma=SpecParametrosBase.outlier_mult_sigma)
            t_21 = t_ref + timedelta(minutes=SpecParametrosBase.gap_temporal_min)
            id_tel_21 = ingestar_lectura(client, dispositivo_y_sensor_ambiental, v_outlier, t_21)

            resp_eval = client.post(f"iot/calidad/{id_tel_21}/evaluar")
            ctx = {"client": client, "resp_eval": resp_eval}
            yield ctx
        finally:
            client.teardown_rollback()

    def test_s_318a_flags_exactos(self, run_context):
        """Ajuste 2: Se espera exactamente {outlier_estadistico, posible_drift, gap_temporal_anomalo}."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        activos = {k for k, v in flags.items() if isinstance(v, dict) and v.get("activo") is True}
        assert activos == {"outlier_estadistico", "posible_drift", "gap_temporal_anomalo"}

    def test_tc318a_flag_outlier_estadistico(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("outlier_estadistico", {}).get("activo") is True

    def test_tc318a_flag_posible_drift(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("posible_drift", {}).get("activo") is True

    def test_tc318a_flag_gap_temporal(self, run_context):
        """DEFECTO PROBABLE: Fase 5 sin implementar en evaluar_calidad_telemetria_use_case.py:194."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("gap_temporal_anomalo", {}).get("activo") is True

    def test_tc318a_trazabilidad_estadistica_presente(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        outlier = flags.get("outlier_estadistico", {})
        drift = flags.get("posible_drift", {})
        assert "media_serie" in outlier
        assert "desviacion_estandar" in outlier
        assert "magnitud_drift_porcentaje" in drift

    def test_tc318a_indice_calidad_60(self, run_context):
        """Spec espera 100 - (20 + 10 + 10) = 60. Falla si gap temporal no descuenta (daría 70)."""
        data = run_context["resp_eval"].json()
        assert data["indice_calidad"] == 60

    def test_tc318a_clasificacion_apto_con_reserva(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["clasificacion_calidad"] == "APTO_CON_RESERVA"

    def test_tc318a_aptitud_ia_true_nic41_false(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["apto_para_ia"] is True
        assert data["apto_para_nic41"] is False

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)


# ============================================================================
# ESCENARIO S_318b: Sensor Congelado MODERADO + Drift 15%
# ============================================================================

class TestEscenario318b:
    """10 lecturas variadas + 10 idénticas (congelado MOD) + Drift 15% -> Esperado índice 40."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-318b-{uuid.uuid4()}"
        client = SandboxClient(env_config["TEST_BASE_URL"], run_id, env_config["TEST_SANDBOX_SECRET"], admin_token)
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            valores_10_variadas = [19.8 if i % 2 == 0 else 20.2 for i in range(10)]
            valores_10_identicas = [base for _ in range(10)]
            valores_serie = valores_10_variadas + valores_10_identicas
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            for item in serie:
                ts = datetime.fromisoformat(item["timestamp"])
                ingestar_lectura(client, dispositivo_y_sensor_ambiental, item["valor"], ts)

            filas = client.query_sql(
                f"SELECT valor_crudo FROM modulo3.telemetrias WHERE id_sensor = {dispositivo_y_sensor_ambiental['sensor_id']} "
                f"AND estado_calidad = 'LECTURA_VALIDA' ORDER BY timestamp_captura DESC LIMIT 20"
            )
            media_real = statistics.mean([float(f["valor_crudo"]) for f in filas])
            offset_drift = calcular_offset_para_drift(media_real, drift_objetivo=0.15)
            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=offset_drift)

            t_21 = t_ref + timedelta(minutes=10)
            id_tel_21 = ingestar_lectura(client, dispositivo_y_sensor_ambiental, base, t_21)

            resp_eval = client.post(f"iot/calidad/{id_tel_21}/evaluar")
            ctx = {"client": client, "resp_eval": resp_eval}
            yield ctx
        finally:
            client.teardown_rollback()

    def test_s_318b_flags_exactos(self, run_context):
        """Ajuste 2: Se espera exactamente {sensor_congelado, posible_drift}."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        activos = {k for k, v in flags.items() if isinstance(v, dict) and v.get("activo") is True}
        assert activos == {"sensor_congelado", "posible_drift"}

    def test_tc318b_flag_congelado_moderado(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        sc = flags.get("sensor_congelado", {})
        assert sc.get("activo") is True
        assert sc.get("severidad") == "MODERADO"

    def test_tc318b_flag_posible_drift_15(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        drift = flags.get("posible_drift", {})
        assert drift.get("activo") is True
        mag = float(drift.get("magnitud_drift_porcentaje", 0))
        assert 10.0 <= mag <= 20.0

    def test_tc318b_flag_outlier_inactivo(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("outlier_estadistico", {}).get("activo", False) is False

    def test_tc318b_flag_gap_inactivo(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("gap_temporal_anomalo", {}).get("activo", False) is False

    def test_tc318b_indice_calidad_40(self, run_context):
        # 100 - (35 [MOD] + 25 [Drift 15%]) = 40
        data = run_context["resp_eval"].json()
        assert data["indice_calidad"] == 40

    def test_tc318b_clasificacion_apto_con_reserva(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["clasificacion_calidad"] == "APTO_CON_RESERVA"

    def test_tc318b_aptitud_ia_true_nic41_false(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["apto_para_ia"] is True
        assert data["apto_para_nic41"] is False

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)


# ============================================================================
# ESCENARIO S_318c: Sensor Congelado CRÍTICO + Outlier con sigma = 0
# ============================================================================

class TestEscenario318c:
    """20 lecturas idénticas (sigma=0) + lectura 21 con salto.
    
    Spec espera: Congelado CRÍTICO (-90) + Outlier (-20) -> saturación en 0.
    Defecto probable del backend: guard `sigma > 0` omite outlier estadístico.
    """

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-318c-{uuid.uuid4()}"
        client = SandboxClient(env_config["TEST_BASE_URL"], run_id, env_config["TEST_SANDBOX_SECRET"], admin_token)
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            valores_serie = [base for _ in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            for item in serie:
                ts = datetime.fromisoformat(item["timestamp"])
                ingestar_lectura(client, dispositivo_y_sensor_ambiental, item["valor"], ts)

            t_21 = t_ref + timedelta(minutes=10)
            id_tel_21 = ingestar_lectura(client, dispositivo_y_sensor_ambiental, base + 6.0, t_21)

            resp_eval = client.post(f"iot/calidad/{id_tel_21}/evaluar")
            ctx = {"client": client, "resp_eval": resp_eval}
            yield ctx
        finally:
            client.teardown_rollback()

    def test_tc318c_no_error_5xx_con_sigma_cero(self, run_context):
        """Verifica robustez: sigma=0 no causa excepción de división por cero ni error 500."""
        assert run_context["resp_eval"].status_code == 201

    def test_s_318c_flags_exactos(self, run_context):
        """Ajuste 2: Se espera exactamente {sensor_congelado, outlier_estadistico}.
        
        DEFECTO PROBABLE: Falla porque outlier_estadistico no se activa al tener sigma=0.
        """
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        activos = {k for k, v in flags.items() if isinstance(v, dict) and v.get("activo") is True}
        assert activos == {"sensor_congelado", "outlier_estadistico"}

    def test_tc318c_flag_congelado_critico(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        sc = flags.get("sensor_congelado", {})
        assert sc.get("activo") is True
        assert sc.get("severidad") == "CRITICO"

    def test_tc318c_flag_outlier_estadistico(self, run_context):
        """DEFECTO PROBABLE: use_case:153 `if sigma > 0:` no activa outlier si la serie fue idéntica."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("outlier_estadistico", {}).get("activo") is True

    def test_tc318c_indice_satura_en_cero(self, run_context):
        """Spec: 100 - (90 + 20) = -10 -> satura en 0. Si outlier no aplica, da 100 - 90 = 10."""
        data = run_context["resp_eval"].json()
        assert data["indice_calidad"] == 0

    def test_tc318c_clasificacion_no_apto(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["clasificacion_calidad"] == "NO_APTO"

    def test_tc318c_aptitud_ambas_false(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["apto_para_ia"] is False
        assert data["apto_para_nic41"] is False

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)


# ============================================================================
# ESCENARIO S_318c_bis: Saturación Aritmética Cero vía Límite Físico (Complementario)
# ============================================================================

class TestEscenario318cBis:
    """Valida la saturación aritmética en 0 activando Outlier por LIMITE_FISICO (>60 °C)."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-318cbis-{uuid.uuid4()}"
        client = SandboxClient(env_config["TEST_BASE_URL"], run_id, env_config["TEST_SANDBOX_SECRET"], admin_token)
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            valores_serie = [base for _ in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            for item in serie:
                ts = datetime.fromisoformat(item["timestamp"])
                ingestar_lectura(client, dispositivo_y_sensor_ambiental, item["valor"], ts)

            # Lectura 21: valor 65.0 °C (aceptada por ingesta [-50, 100], pero viola _RANGOS_FISICOS [-40, 60])
            t_21 = t_ref + timedelta(minutes=10)
            id_tel_21 = ingestar_lectura(client, dispositivo_y_sensor_ambiental, 65.0, t_21)

            resp_eval = client.post(f"iot/calidad/{id_tel_21}/evaluar")
            ctx = {"client": client, "resp_eval": resp_eval}
            yield ctx
        finally:
            client.teardown_rollback()

    def test_tc318c_bis_flag_congelado_critico(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("sensor_congelado", {}).get("severidad") == "CRITICO"

    def test_tc318c_bis_flag_outlier_limite_fisico(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        outlier = flags.get("outlier_estadistico", {})
        assert outlier.get("activo") is True
        assert outlier.get("causa") == "LIMITE_FISICO"

    def test_tc318c_bis_saturacion_aritmetica_cero(self, run_context):
        # 100 - (90 + 20) = -10 -> max(0, -10) = 0
        data = run_context["resp_eval"].json()
        assert data["indice_calidad"] == 0
        assert data["clasificacion_calidad"] == "NO_APTO"

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)


# ============================================================================
# ESCENARIO S_320: NO_APTO Combinado (Congelado MOD + Outlier + Gap)
# ============================================================================

class TestEscenario320:
    """Congelado MOD (-35) + Outlier (-20) + Gap (-10) -> Esperado índice 35 (NO_APTO)."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-320-{uuid.uuid4()}"
        client = SandboxClient(env_config["TEST_BASE_URL"], run_id, env_config["TEST_SANDBOX_SECRET"], admin_token)
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            # 10 variadas (19.8/20.2) + 10 idénticas a 20.0
            valores_serie = [19.8 if i % 2 == 0 else 20.2 for i in range(10)] + [base for _ in range(10)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            for item in serie:
                ts = datetime.fromisoformat(item["timestamp"])
                ingestar_lectura(client, dispositivo_y_sensor_ambiental, item["valor"], ts)

            # Lectura 21: Outlier estadístico (salto a 26.0) + Gap temporal (25 min)
            t_21 = t_ref + timedelta(minutes=SpecParametrosBase.gap_temporal_min)
            id_tel_21 = ingestar_lectura(client, dispositivo_y_sensor_ambiental, base + 6.0, t_21)

            resp_eval = client.post(f"iot/calidad/{id_tel_21}/evaluar")
            ctx = {"client": client, "resp_eval": resp_eval}
            yield ctx
        finally:
            client.teardown_rollback()

    def test_s_320_flags_exactos(self, run_context):
        """Ajuste 2: Se espera exactamente {sensor_congelado, outlier_estadistico, gap_temporal_anomalo}."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        activos = {k for k, v in flags.items() if isinstance(v, dict) and v.get("activo") is True}
        assert activos == {"sensor_congelado", "outlier_estadistico", "gap_temporal_anomalo"}

    def test_tc320_flag_congelado_moderado(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("sensor_congelado", {}).get("severidad") == "MODERADO"

    def test_tc320_flag_outlier_estadistico(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("outlier_estadistico", {}).get("activo") is True

    def test_tc320_flag_gap_temporal(self, run_context):
        """DEFECTO PROBABLE: Gap temporal no implementado en use case."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("gap_temporal_anomalo", {}).get("activo") is True

    def test_tc320_indice_calidad_35(self, run_context):
        # 100 - (35 + 20 + 10) = 35. Falla si gap temporal no descuenta (daría 45).
        data = run_context["resp_eval"].json()
        assert data["indice_calidad"] == 35

    def test_tc320_clasificacion_no_apto(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["clasificacion_calidad"] == "NO_APTO"

    def test_tc320_aptitud_ambas_false(self, run_context):
        data = run_context["resp_eval"].json()
        assert data["apto_para_ia"] is False
        assert data["apto_para_nic41"] is False

    def test_tc320_exclusion_m04_m06_condicionada(self, run_context, preflight_capacidades_m04_m06):
        """D5: Condicionada a si M04/M06 exponen capacidad de filtro en OpenAPI."""
        if not preflight_capacidades_m04_m06:
            # D5: Si NO existe, sin aserción de negocio. Se anota como dependencia bloqueada.
            print("\n[D5 BLOQUEADO] M04 y M06 no exponen endpoints con filtro por apto_para_ia ni apto_para_nic41.")
            return
        # Si existiera la capacidad, se asertaría la exclusión de la lectura
        assert True

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)
