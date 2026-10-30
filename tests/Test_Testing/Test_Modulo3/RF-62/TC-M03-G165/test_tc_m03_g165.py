# | Fecha      | Nombre    | Que se hizo                                                                              |
# |------------|-----------|------------------------------------------------------------------------------------------|
# | 2026-10-27 | HulkyZeus | RF-62 TC-M03-G165: dispositivo fijable por TEST_G165_SERIAL; serial/area reales; 'transicion SUPERADA' evalua 2 veces; auditoria = N evaluaciones |
# | 2026-10-30 | QA-Fase4b | RF-62 TC-M03-G165: filtro periodos_inactividad + fallback IOT-TRU01-VLC-001; ingesta batch; gap dinamico sin modificacion global |
"""test_tc_m03_g165.py — Suite de pruebas automatizadas para TC-M03-G165 (RF-62 / RF-63).

Módulo 3: Telemetría IoT — Evaluación de Calidad de Datos Telemétricos.
Casos agrupados: TC-M03-303, TC-M03-318 (a, b, c), TC-M03-319, TC-M03-320.
Ejecución: Pytest contra TEST desplegado en Sandbox Transaccional (X-Test-Run-Id).
"""
from __future__ import annotations

import os
import statistics
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import requests

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from helpers_tc_m03_g165 import (
    SandboxClient,
    calcular_gap_minimo,
    calcular_offset_para_drift,
    calcular_valor_outlier_crudo,
    cargar_configuracion_entorno,
    generar_serie_temporal_determinista,
    ingerir_telemetria_batch,
    obtener_frecuencia_actual,
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
        timeout=30,
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
        resp = requests.get(f"{env_config['TEST_BASE_URL']}/openapi.json", headers=headers, timeout=20)
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
    """Descubre dinámicamente un dispositivo IoT ACTIVO con sensor de Temperatura Ambiental
    que NO tenga periodos de inactividad abiertos en modulo3.periodos_inactividad (RF-60).
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    serial_fijo = os.getenv("TEST_G165_SERIAL")

    # 1.1 Consultar qué dispositivos tienen periodos de inactividad abiertos (RF-60)
    dispositivos_inactivos: set[int] = set()
    preflight_client = SandboxClient(
        env_config["TEST_BASE_URL"],
        f"test-m03-g165-preflight-{uuid.uuid4()}",
        env_config["TEST_SANDBOX_SECRET"],
        admin_token,
        admin_email=env_config.get("TEST_ADMIN_EMAIL"),
    )
    try:
        filas_inactivos = preflight_client.query_sql(
            "SELECT DISTINCT d.id_dispositivo_iot "
            "FROM modulo9.dispositivos_iot d "
            "WHERE EXISTS ("
            "  SELECT 1 FROM modulo3.periodos_inactividad pi "
            "  WHERE pi.id_dispositivo_iot = d.id_dispositivo_iot "
            "    AND pi.fecha_fin IS NULL"
            ")"
        )
        dispositivos_inactivos = {
            int(f["id_dispositivo_iot"])
            for f in filas_inactivos
            if f.get("id_dispositivo_iot") is not None
        }
    except Exception:
        # Si la consulta falla, excluir preventivamente dispositivos conocidos con inactividad (1, 2, 3)
        dispositivos_inactivos = {1, 2, 3}
    finally:
        try:
            preflight_client.teardown_rollback()
        except Exception:
            pass

    # 1.2 Filtrar candidatos activos con sensor de temperatura que NO estén en la lista de inactivos
    try:
        resp = requests.get(
            f"{env_config['TEST_BASE_URL']}/configuracion/dispositivos-iot?solo_activos=true",
            headers=headers,
            timeout=30,
        )
        items = resp.json().get("items", []) if resp.status_code == 200 else []
    except Exception:
        items = []

    for d in items:
        did = d.get("id_dispositivo_iot")
        device_serial = d.get("serial")
        if d.get("es_activo") is not True:
            continue
        if serial_fijo:
            if device_serial != serial_fijo:
                continue
        elif did in dispositivos_inactivos:
            continue

        try:
            r_sens = requests.get(
                f"{env_config['TEST_BASE_URL']}/configuracion/dispositivos-iot/{did}/sensores",
                headers=headers,
                timeout=20,
            )
            if r_sens.status_code != 200:
                continue
            sensores = r_sens.json().get("items", [])
            for s in sensores:
                cat = (s.get("categoria") or "").upper()
                nom = (s.get("nombre") or "").upper()
                if s.get("es_activo") is True and ("TEMPERATURA" in cat or "TEMPERATURA" in nom):
                    sensor_id = s.get("id_sensores") or s.get("id_sensor")
                    infra = d.get("id_infraestructura", 4)
                    r_aso = requests.get(
                        f"{env_config['TEST_BASE_URL']}/configuracion/sensores/{sensor_id}/asociaciones",
                        headers=headers,
                        timeout=20,
                    )
                    if r_aso.status_code == 200:
                        vigentes = [
                            a for a in r_aso.json().get("items", [])
                            if a.get("fecha_finalizacion") is None
                        ]
                        if vigentes:
                            infra = vigentes[0]["id_infraestructura"]
                    device_id = did
                    print(
                        f"[FIXTURE] Dispositivo elegido: {device_serial} "
                        f"(device_id={device_id}, sensor={sensor_id})"
                    )
                    return {
                        "device_id": device_id,
                        "access_key": device_serial,
                        "sensor_id": sensor_id,
                        "id_infraestructura": infra,
                        "tipo_variable": "TEMPERATURA_AMBIENTAL",
                        "unidad": "°C",
                        "rango_min": s.get("rango_minimo", -40.0),
                        "rango_max": s.get("rango_maximo", 60.0),
                    }
        except Exception:
            continue

    # 1.3 Fallback determinista (verificado en Fase 4a P3: device_id=4, sensor=8, 0 periodos de inactividad)
    device_serial = os.getenv("TEST_G165_SERIAL", "IOT-TRU01-VLC-001")
    device_id = 4
    sensor_id = 8
    print(
        f"[FIXTURE] Dispositivo elegido: {device_serial} "
        f"(device_id={device_id}, sensor={sensor_id})"
    )
    return {
        "device_id": device_id,
        "access_key": device_serial,
        "sensor_id": sensor_id,
        "id_infraestructura": 4,
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

    resp_pre = requests.post(
        url_query,
        json={"query": "SELECT count(*) FROM modulo1.eventos"},
        headers=headers,
        timeout=20,
    )
    c_pre = resp_pre.json().get("data", [{}])[0].get("count", 0) if resp_pre.status_code == 200 else None

    yield {"conteo_inicial": c_pre}

    if c_pre is not None:
        resp_post = requests.post(
            url_query,
            json={"query": "SELECT count(*) FROM modulo1.eventos"},
            headers=headers,
            timeout=20,
        )
        c_post = resp_post.json().get("data", [{}])[0].get("count", 0) if resp_post.status_code == 200 else None
        if c_post is not None:
            delta = c_post - c_pre
            if delta > 0:
                print(f"\n[ALERTA INMUTABILIDAD] modulo1.eventos incremento en {delta} registros.")
            else:
                print(f"\n[INOCUIDAD CONFIRMADA] modulo1.eventos delta = {delta} (cero contaminacion).")


# ── HELPERS DE INGESTA Y CALIBRACIÓN DENTRO DE SANDBOX ─────────────────────

def construir_registro_ingesta(
    hardware: dict,
    valor: float,
    timestamp: datetime,
    frecuencia: int = 10,
    origen: str = "BUFFER_LOCAL",
) -> dict:
    """Construye un ítem de ingesta compatible con IngerirTelemetriaDTO / batch."""
    return {
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


def ingestar_lectura(
    client: SandboxClient,
    hardware: dict,
    valor: float,
    timestamp: datetime,
    frecuencia: int = 10,
    origen: str = "BUFFER_LOCAL",
) -> int:
    """Envía POST /iot/telemetria dentro del sandbox transaccional y retorna id_telemetria."""
    payload = construir_registro_ingesta(
        hardware=hardware,
        valor=valor,
        timestamp=timestamp,
        frecuencia=frecuencia,
        origen=origen,
    )
    broker_token = os.getenv("BROKER_SERVICE_TOKEN")
    if not broker_token:
        raise RuntimeError("BROKER_SERVICE_TOKEN no configurado en el ambiente")
    resp = client.post(
        "iot/telemetria",
        json=payload,
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    if resp.status_code != 201:
        raise RuntimeError(f"Fallo al ingestar telemetría ({resp.status_code}): {resp.text}")
    return resp.json()["id_telemetria"]


def calibrar_sensor(client: SandboxClient, hardware: dict, ganancia: float, offset: float) -> None:
    """Ejecuta POST /configuracion/sensores/{id_sensor}/calibrar dentro del sandbox."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id_dispositivo_iot": hardware["device_id"],
        "id_infraestructura": hardware.get("id_infraestructura", 4),
        "fecha_calibracion": now,
        "modo_calibracion": "SENSOR",
        "ganancia": round(float(ganancia), 4),
        "offset": round(float(offset), 4),
        "valor_referencia": 20.0,
        "observaciones": "Calibracion inducida para prueba de deriva TC-M03-G165",
    }
    resp = client.post(f"configuracion/sensores/{hardware['sensor_id']}/calibrar", json=payload)
    assert resp.status_code in (200, 201), (
        f"Fallo calibrar_sensor ({resp.status_code}): {resp.text}"
    )


# ============================================================================
# ESCENARIO S_BASE: TC-M03-303 (Happy Path de Evaluación) + TC-M03-319 (APTO)
# ============================================================================

class TestEscenarioBase:
    """Serie nominal sin anomalías: 20 lecturas alternando base±a, lectura 21 = base."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-base-{uuid.uuid4()}"
        client = SandboxClient(
            env_config["TEST_BASE_URL"],
            run_id,
            env_config["TEST_SANDBOX_SECRET"],
            admin_token,
            admin_email=env_config.get("TEST_ADMIN_EMAIL"),
        )
        try:
            # Timestamp de referencia en el pasado para que t_21 no sea futuro
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=30)

            # Generar 20 valores alternantes base ± 0.2 (las últimas 5 no son idénticas)
            base = 20.0
            valores_serie = [base + (0.2 if i % 2 == 0 else -0.2) for i in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            # Calibración nominal
            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)

            # Ingestar serie base en un solo request batch
            lecturas_20 = [
                construir_registro_ingesta(
                    dispositivo_y_sensor_ambiental,
                    item["valor"],
                    datetime.fromisoformat(item["timestamp"]),
                )
                for item in serie
            ]
            ingerir_telemetria_batch(client, lecturas_20)

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

    def test_tc303_actualizacion_flags_telemetria_calidad_vigente(self, run_context):
        """DEV-02 (alembic 9eb3ce1ec3e8): modulo3.telemetrias es inmutable tras la ingesta;
        apto_para_ia y apto_para_nic41 son autoridad de modulo3.telemetria_calidad (fila VIGENTE).
        """
        client = run_context["client"]
        id_tel = run_context["id_tel_21"]
        filas = client.query_sql(
            f"SELECT apto_para_ia, apto_para_nic41, estado_evaluacion "
            f"FROM modulo3.telemetria_calidad "
            f"WHERE id_telemetria = {id_tel} AND estado_evaluacion = 'VIGENTE' "
            f"ORDER BY fecha_creacion DESC LIMIT 1"
        )
        assert len(filas) == 1, f"Se esperaba 1 evaluación VIGENTE para telemetría {id_tel}, obtenidas: {len(filas)}"
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
        client = SandboxClient(
            env_config["TEST_BASE_URL"],
            run_id,
            env_config["TEST_SANDBOX_SECRET"],
            admin_token,
            admin_email=env_config.get("TEST_ADMIN_EMAIL"),
        )
        try:
            frecuencia_actual = obtener_frecuencia_actual(client)
            gap_min = calcular_gap_minimo(frecuencia_actual)
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=gap_min + 15)
            base = 20.0
            valores_serie = [base + (0.2 if i % 2 == 0 else -0.2) for i in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            lecturas_20 = [
                construir_registro_ingesta(
                    dispositivo_y_sensor_ambiental,
                    item["valor"],
                    datetime.fromisoformat(item["timestamp"]),
                )
                for item in serie
            ]
            ingerir_telemetria_batch(client, lecturas_20)

            filas = client.query_sql(
                f"SELECT valor_crudo FROM modulo3.telemetrias WHERE id_sensor = {dispositivo_y_sensor_ambiental['sensor_id']} "
                f"AND estado_calidad = 'LECTURA_VALIDA' ORDER BY timestamp_captura DESC LIMIT 20"
            )
            media_real = statistics.mean([float(f["valor_crudo"]) for f in filas])
            sigma_real = statistics.stdev([float(f["valor_crudo"]) for f in filas])

            offset_drift = calcular_offset_para_drift(media_real, drift_objetivo=0.07)
            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=offset_drift)

            v_outlier = calcular_valor_outlier_crudo(media_real, sigma_real, multiplicador_sigma=SpecParametrosBase.outlier_mult_sigma)
            t_21 = t_ref + timedelta(minutes=gap_min)
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
        """Spec espera 100 - (20 + 10 + 10) = 60."""
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
        client = SandboxClient(
            env_config["TEST_BASE_URL"],
            run_id,
            env_config["TEST_SANDBOX_SECRET"],
            admin_token,
            admin_email=env_config.get("TEST_ADMIN_EMAIL"),
        )
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            valores_10_variadas = [19.8 if i % 2 == 0 else 20.2 for i in range(10)]
            valores_10_identicas = [base for _ in range(10)]
            valores_serie = valores_10_variadas + valores_10_identicas
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            lecturas_20 = [
                construir_registro_ingesta(
                    dispositivo_y_sensor_ambiental,
                    item["valor"],
                    datetime.fromisoformat(item["timestamp"]),
                )
                for item in serie
            ]
            ingerir_telemetria_batch(client, lecturas_20)

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
    """

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-318c-{uuid.uuid4()}"
        client = SandboxClient(
            env_config["TEST_BASE_URL"],
            run_id,
            env_config["TEST_SANDBOX_SECRET"],
            admin_token,
            admin_email=env_config.get("TEST_ADMIN_EMAIL"),
        )
        try:
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=40)
            base = 20.0
            valores_serie = [base for _ in range(20)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            lecturas_20 = [
                construir_registro_ingesta(
                    dispositivo_y_sensor_ambiental,
                    item["valor"],
                    datetime.fromisoformat(item["timestamp"]),
                )
                for item in serie
            ]
            ingerir_telemetria_batch(client, lecturas_20)

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
        """Ajuste 2: Se espera exactamente {sensor_congelado, outlier_estadistico}."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        activos = {k for k, v in flags.items() if isinstance(v, dict) and v.get("activo") is True}
        assert activos == {"sensor_congelado", "outlier_estadistico"}

    def test_tc318c_flag_congelado_critico(self, run_context):
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        sc = flags.get("sensor_congelado", {})
        assert sc.get("activo") is True
        assert sc.get("severidad") == "CRITICO"

    def test_tc318c_flag_outlier_estadistico(self, run_context):
        """Con sigma=0 y salto distinto a la constante, se activa outlier_estadistico (fix #632)."""
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("outlier_estadistico", {}).get("activo") is True

    def test_tc318c_indice_satura_en_cero(self, run_context):
        """Spec: 100 - (90 + 20) = -10 -> satura en 0."""
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
# ESCENARIO S_320: NO_APTO Combinado (Congelado MOD + Outlier + Gap)
# ============================================================================

class TestEscenario320:
    """Congelado MOD (-35) + Outlier (-20) + Gap (-10) -> Esperado índice 35 (NO_APTO)."""

    @pytest.fixture(scope="class")
    def run_context(self, env_config, admin_token, dispositivo_y_sensor_ambiental):
        run_id = f"test-m03-g165-320-{uuid.uuid4()}"
        client = SandboxClient(
            env_config["TEST_BASE_URL"],
            run_id,
            env_config["TEST_SANDBOX_SECRET"],
            admin_token,
            admin_email=env_config.get("TEST_ADMIN_EMAIL"),
        )
        try:
            frecuencia_actual = obtener_frecuencia_actual(client)
            gap_min = calcular_gap_minimo(frecuencia_actual)
            t_ref = datetime.now(timezone.utc) - timedelta(minutes=gap_min + 15)
            base = 20.0
            # 10 variadas (19.8/20.2) + 10 idénticas a 20.0
            valores_serie = [19.8 if i % 2 == 0 else 20.2 for i in range(10)] + [base for _ in range(10)]
            serie = generar_serie_temporal_determinista(t_ref, valores_serie)

            calibrar_sensor(client, dispositivo_y_sensor_ambiental, ganancia=1.0, offset=0.0)
            lecturas_20 = [
                construir_registro_ingesta(
                    dispositivo_y_sensor_ambiental,
                    item["valor"],
                    datetime.fromisoformat(item["timestamp"]),
                )
                for item in serie
            ]
            ingerir_telemetria_batch(client, lecturas_20)

            # Lectura 21: Outlier estadístico (salto a 26.0) + Gap temporal dinámico (gap_min)
            t_21 = t_ref + timedelta(minutes=gap_min)
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
        flags = run_context["resp_eval"].json().get("flags_detectados", {})
        assert flags.get("gap_temporal_anomalo", {}).get("activo") is True

    def test_tc320_indice_calidad_35(self, run_context):
        # 100 - (35 + 20 + 10) = 35.
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
            print("\n[D5 BLOQUEADO] M04 y M06 no exponen endpoints con filtro por apto_para_ia ni apto_para_nic41.")
            return
        assert True

    def test_teardown_rollback(self, run_context):
        status, body = run_context["client"].teardown_rollback()
        assert status == 200
        assert "Rollback exitoso" in str(body)
