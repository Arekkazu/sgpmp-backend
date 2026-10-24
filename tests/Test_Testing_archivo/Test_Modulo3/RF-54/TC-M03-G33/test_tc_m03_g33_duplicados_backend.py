"""
TC-M03-G33 - Tratar los duplicados informados por el backend.

RF relacionado: RF-54 (CU01). Caso: TC-M03-042 (cierra el ciclo de idempotencia con TC-M03-021 de RF-53).

Criterio de la ficha: al reenviar datos ya persistidos, el backend responde con un indicador de duplicidad
(HTTP 409 o flag); el dispositivo los marca CONFIRMADO y los elimina del buffer, registra DUPLICATE_DETECTED y no
se crean registros nuevos en el backend.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el DRIVER.
Se verifica el contrato del backend real del que depende el nodo:
- reenvio individual (POST /iot/telemetria): 409 con error_code ERROR_DUPLICADO;
- reenvio en lote (POST /iot/telemetria/batch): cada registro repetido viene marcado en `detalle`
  (estado ERROR_DUPLICADO) y se cuenta en `duplicados`, NUNCA en `rechazados` (si no, el nodo lo reintentaria
  para siempre); mezclado con datos nuevos, los nuevos se aceptan igual;
- no se crea ningun registro nuevo y el valor original no se sobrescribe aunque el reenvio traiga otro valor;
- cada duplicado queda en la bitacora tecnica del backend (modulo3.bitacora_ingest, estado ERROR_DUPLICADO,
  lectura en BD con el usuario QA).
Interno del nodo (SKIP): marcar CONFIRMADO, borrar del buffer y DUPLICATE_DETECTED.

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G33 -v \
        --html=reporte-TC-M03-G33.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


def _sufijo() -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(8))


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


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
        "nombre": f"Finca Duplicados Edge {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Duplicados Edge {suf}", "descripcion": "Especie de prueba TC-M03-G33",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Duplicados Edge {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G33-{suf}", "descripcion": "Nodo Edge TC-M03-G33", "id_infraestructura": area,
        "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensor = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                    {"nombre": f"Sensor duplicados {suf}", "categoria": "TEMPERATURA"}, "id_sensores")

    def lectura(ts: datetime, valor: float) -> dict:
        return {"device_id": device_id, "sensor_id": sensor, "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": valor,
                "unidad": "°C", "timestamp_captura": ts.isoformat(), "origen": "BUFFER_LOCAL", "access_key": serial}

    desde = datetime.now(timezone.utc) - timedelta(seconds=5)
    inicio = datetime.now(timezone.utc) - timedelta(hours=1)
    originales = [lectura(inicio + timedelta(minutes=i), 20.0 + i) for i in range(10)]
    primera = requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": originales}, timeout=TIMEOUT)

    # Reenvio individual de uno ya persistido.
    individual = requests.post(f"{BASE_URL}/iot/telemetria", json=originales[0], timeout=TIMEOUT)
    # Reenvio en lote: 5 ya persistidos (dos con otro valor, misma clave) + 3 nuevos.
    repetidos = [dict(x) for x in originales[1:6]]
    repetidos[0]["valor"] = 99.0
    repetidos[1]["valor"] = 98.0
    nuevos = [lectura(inicio + timedelta(minutes=30 + i), 40.0 + i) for i in range(3)]
    lote = requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": repetidos + nuevos}, timeout=TIMEOUT)

    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT timestamp_captura, valor_crudo FROM modulo3.telemetrias WHERE id_sensor = %s", (sensor,))
            persistidos = dict(cur.fetchall())
            cur.execute("SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_dispositivo_iot = %s "
                        "AND estado_calidad = 'ERROR_DUPLICADO' AND fecha_evento >= %s", (device_id, desde))
            duplicados_bitacora = cur.fetchone()[0]
    finally:
        con.close()
    return {"originales": originales, "nuevos": nuevos, "primera": primera, "individual": individual, "lote": lote,
            "persistidos": persistidos, "duplicados_bitacora": duplicados_bitacora}


def test_tc_m03_042_carga_inicial(corrida):
    r = corrida["primera"]
    assert r.status_code == 200 and r.json()["aceptados"] == 10, r.text


def test_tc_m03_042_reenvio_individual_responde_409_duplicado(corrida):
    r = corrida["individual"]
    assert r.status_code == 409, f"HTTP {r.status_code} {r.text}"
    assert r.json().get("error_code") == "ERROR_DUPLICADO"


def test_tc_m03_042_reenvio_en_lote_indica_duplicidad_por_registro(corrida):
    r = corrida["lote"]
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["total"], cuerpo["aceptados"], cuerpo["duplicados"], cuerpo["rechazados"]) == (8, 3, 5, 0), (
        f"Los repetidos deben contarse como duplicados (no como rechazados) y los nuevos aceptarse: {cuerpo}"
    )
    repetidos = {_ts(x["timestamp_captura"]) for x in corrida["originales"][1:6]}
    marcados = {_ts(d["timestamp_captura"]) for d in cuerpo["detalle"] if d["estado"] == "ERROR_DUPLICADO"}
    assert marcados == repetidos, "Cada registro repetido debe venir marcado como duplicado en el detalle"


def test_tc_m03_042_no_se_crean_registros_ni_se_sobrescriben_valores(corrida):
    persistidos = corrida["persistidos"]
    assert len(persistidos) == 13, f"10 originales + 3 nuevos; hay {len(persistidos)}"
    for x in corrida["originales"]:
        assert persistidos[_ts(x["timestamp_captura"])] == Decimal(str(x["valor"])), (
            f"El duplicado sobrescribio el valor original de {x['timestamp_captura']}"
        )


def test_tc_m03_042_cada_duplicado_queda_en_la_bitacora_del_backend(corrida):
    assert corrida["duplicados_bitacora"] == 6, (
        f"Se esperaban 6 eventos ERROR_DUPLICADO en modulo3.bitacora_ingest (1 individual + 5 del lote), hay "
        f"{corrida['duplicados_bitacora']}"
    )


def test_tc_m03_042_confirmado_borrado_y_duplicate_detected_en_el_nodo():
    pytest.skip("Marcar los datos CONFIRMADO, borrarlos del buffer y registrar DUPLICATE_DETECTED son internos del nodo Edge: "
                "requieren el nodo o el simulador del equipo de IoT")
