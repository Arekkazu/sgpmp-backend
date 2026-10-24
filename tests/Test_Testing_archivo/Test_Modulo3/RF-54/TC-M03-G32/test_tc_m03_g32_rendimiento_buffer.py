"""
TC-M03-G32 - Rendimiento del buffer local: latencia de escritura y no bloqueo de la captura durante la
sincronizacion por lotes.

RF relacionado: RF-54 (CU01). Casos: TC-M03-053 (RNF-03) y TC-M03-070 (CA-14).

Criterios de la ficha:
    TC-M03-053: la escritura local en el buffer tarda <= 50 ms por evento durante una rafaga sostenida
    ("se mide en el dispositivo, no en el backend").
    TC-M03-070: mientras se sincroniza un lote grande (ej. 500) se siguen capturando mediciones nuevas sin
    demora perceptible (<= 50 ms), sin perdidas ni bloqueos.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto. La latencia de escritura
local (RNF-03) es una propiedad del hardware/firmware: medirla sobre un simulador en Python no dice nada del
nodo real, asi que TC-M03-053 y la parte local de TC-M03-070 quedan en SKIP.
Lo que si involucra al sistema en TC-M03-070, y se verifica contra el backend real, es que la sincronizacion
de un lote grande no bloquee la recepcion de las mediciones nuevas del mismo dispositivo:
- se envia un lote de 500 lecturas BUFFER_LOCAL (POST /iot/telemetria/batch) y, mientras se procesa, el
  mismo dispositivo envia lecturas TIEMPO_REAL (POST /iot/telemetria) en paralelo;
- todas las lecturas concurrentes se aceptan (201) y quedan persistidas, ademas de las 500 del lote;
- ninguna lectura concurrente queda "detras" del lote: su latencia maxima debe ser una fraccion de la
  duracion del lote (FRACCION_MAX_BLOQUEO) y su p95 no superar LATENCIA_P95_MS (por defecto 500 ms, el umbral
  de disponibilidad de RF-53 usado en TC-M03-027).

Carga: 500 + ~N lecturas contra TEST; coordinar el horario con el equipo.

Requisitos: acceso de red a TEST. Variables opcionales: BASE_URL, LATENCIA_P95_MS, FRACCION_MAX_BLOQUEO.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G32 -v \
        --html=reporte-TC-M03-G32.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import statistics
import string
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
LATENCIA_P95_MS = float(os.getenv("LATENCIA_P95_MS", "500"))
FRACCION_MAX_BLOQUEO = float(os.getenv("FRACCION_MAX_BLOQUEO", "0.25"))
TIMEOUT = 30
TIMEOUT_LOTE = 600
TAMANO_LOTE = 500
PERIODO_CAPTURA_SEG = 0.5  # una medicion nueva cada 0.5 s mientras dura el lote


def _sufijo() -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(8))


@pytest.fixture(scope="module")
def admin() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Login Administrador: HTTP {r.status_code} {r.text}"
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def _crear(s, ruta, cuerpo, campo):
    r = s.post(f"{BASE_URL}{ruta}", json=cuerpo, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion {ruta}: HTTP {r.status_code} {r.text}"
    return r.json()[campo]


@pytest.fixture(scope="module")
def corrida(admin):
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Lote Concurrente {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Lote Concurrente {suf}", "descripcion": "Especie de prueba TC-M03-G32",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Lote Concurrente {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G32-{suf}", "descripcion": "Nodo Edge TC-M03-G32", "id_infraestructura": area,
        "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    s_buffer = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                      {"nombre": f"Sensor buffer {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    s_vivo = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                    {"nombre": f"Sensor en vivo {suf}", "categoria": "TEMPERATURA"}, "id_sensores")

    def lectura(sensor, ts, origen):
        return {"device_id": device_id, "sensor_id": sensor, "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 24.0,
                "unidad": "°C", "timestamp_captura": ts.isoformat(), "origen": origen, "access_key": serial}

    inicio = datetime.now(timezone.utc) - timedelta(hours=10)
    lote = [lectura(s_buffer, inicio + timedelta(minutes=i), "BUFFER_LOCAL") for i in range(TAMANO_LOTE)]

    resultado_lote: dict = {}

    def enviar_lote():
        t0 = time.perf_counter()
        resp = requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": lote}, timeout=TIMEOUT_LOTE)
        resultado_lote.update(respuesta=resp, duracion_s=time.perf_counter() - t0)

    hilo = threading.Thread(target=enviar_lote)
    hilo.start()
    time.sleep(1)  # el lote ya esta en proceso
    concurrentes = []
    while hilo.is_alive():
        t0 = time.perf_counter()
        r = requests.post(f"{BASE_URL}/iot/telemetria",
                          json=lectura(s_vivo, datetime.now(timezone.utc) - timedelta(seconds=1), "TIEMPO_REAL"), timeout=TIMEOUT)
        concurrentes.append((r.status_code, (time.perf_counter() - t0) * 1000))
        time.sleep(PERIODO_CAPTURA_SEG)
    hilo.join()

    hoy = datetime.now(timezone.utc).date()
    totales = {}
    for nombre, sensor in (("buffer", s_buffer), ("vivo", s_vivo)):
        h = admin.get(f"{BASE_URL}/iot/monitoreo/historial", params={
            "fecha_inicio": str(hoy - timedelta(days=1)), "fecha_fin": str(hoy + timedelta(days=1)),
            "sensor_id": sensor, "por_pagina": 1}, timeout=TIMEOUT)
        totales[nombre] = h.json()["total"] if h.status_code == 200 else -1
    return {"lote": resultado_lote, "concurrentes": concurrentes, "totales": totales}


def test_tc_m03_070_el_lote_grande_se_sincroniza_completo(corrida):
    r = corrida["lote"]["respuesta"]
    assert r.status_code == 200, f"Lote de {TAMANO_LOTE}: HTTP {r.status_code} {r.text[:300]}"
    assert r.json()["aceptados"] == TAMANO_LOTE, r.json()
    assert corrida["totales"]["buffer"] == TAMANO_LOTE


def test_tc_m03_070_las_mediciones_nuevas_no_se_pierden_durante_el_lote(corrida):
    concurrentes = corrida["concurrentes"]
    assert concurrentes, "El lote termino antes de poder enviar mediciones concurrentes (lote demasiado rapido)"
    fallidas = [c for c in concurrentes if c[0] != 201]
    assert not fallidas, f"Mediciones concurrentes no aceptadas: {fallidas[:5]}"
    assert corrida["totales"]["vivo"] == len(concurrentes)


def test_tc_m03_070_el_lote_no_bloquea_la_recepcion_concurrente(corrida):
    latencias = [c[1] for c in corrida["concurrentes"]]
    if not latencias:
        pytest.fail("No hubo mediciones concurrentes que medir (el lote termino antes)")
    duracion_lote_ms = corrida["lote"]["duracion_s"] * 1000
    p95 = statistics.quantiles(latencias, n=20)[-1] if len(latencias) >= 2 else latencias[0]
    print(f"Lote: {duracion_lote_ms:.0f} ms; concurrentes: n={len(latencias)}, p95={p95:.0f} ms, max={max(latencias):.0f} ms")
    assert max(latencias) < duracion_lote_ms * FRACCION_MAX_BLOQUEO, (
        f"Una medicion concurrente tardo {max(latencias):.0f} ms, comparable al lote ({duracion_lote_ms:.0f} ms): quedo en cola"
    )
    assert p95 <= LATENCIA_P95_MS, f"p95 de las mediciones concurrentes {p95:.0f} ms > {LATENCIA_P95_MS:.0f} ms"


def test_tc_m03_053_latencia_de_escritura_local_en_el_nodo():
    pytest.skip("RNF-03 (<= 50 ms por escritura en el buffer local) se mide en el dispositivo, no en el backend (lo dice la "
                "ficha): requiere el nodo o el simulador del equipo de IoT")


def test_tc_m03_070_captura_local_no_bloqueada_en_el_nodo():
    pytest.skip("Que la captura local no se demore (<= 50 ms) mientras el nodo transmite el lote es interno del nodo Edge: "
                "requiere el nodo o el simulador del equipo de IoT")
