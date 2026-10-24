"""
TC-M03-G34 - Autenticar y cifrar la sincronizacion diferida (OWASP API2).

RF relacionado: RF-54 (CU01). Caso: TC-M03-057 (complementa TC-M03-010 y TC-M03-031 en datos diferidos).

Criterio de la ficha: la sincronizacion con una access_key revocada y la forzada por un canal sin TLS se
rechazan; los datos quedan en el buffer con estado ERROR y el rechazo queda auditado.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el DRIVER
y el backend es el real (endpoint de sincronizacion diferida: POST /iot/telemetria/batch).
- Credencial revocada: el unico mecanismo de revocacion del sistema es la credencial MQTT (RF-23:
  POST/DELETE /configuracion/dispositivos-iot/{id}/credencial-mqtt). Se emite y se revoca, y el nodo sincroniza
  su buffer (a) con su access_key (el serial, que es lo que la ingesta compara) y (b) con la clave MQTT
  revocada. Ambos lotes deben rechazarse por completo, sin persistir nada, y cada rechazo debe quedar en
  modulo3.bitacora_ingest como ERROR_AUTENTICACION (lectura en BD, usuario QA).
- Canal sin TLS: el mismo lote por HTTP plano (puerto 80) sin seguir redirecciones: conexion rechazada o
  redireccion a https://, sin procesar nada (no aparece en la BD).
- Interno del nodo (SKIP): que los datos queden en el buffer con estado ERROR.

Nota del codigo (igual que TC-M03-010c): la ingesta autentica por el serial del dispositivo, que no se puede
revocar; revocar la credencial MQTT no afecta al canal HTTP.

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, TEST_HOST, TEST_PREFIJO, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G34 -v \
        --html=reporte-TC-M03-G34.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
import requests

HOST = os.getenv("TEST_HOST", "sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io")
PREFIJO = os.getenv("TEST_PREFIJO", "/api-sgpmp-test")
BASE_URL = os.getenv("BASE_URL", f"https://{HOST}{PREFIJO}")
TIMEOUT = 30
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


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


def _consulta_bd(sql: str, params: tuple):
    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]
    finally:
        con.close()


@pytest.fixture(scope="module")
def nodo(admin):
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Sincronizacion Segura {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Sincronizacion Segura {suf}", "descripcion": "Especie de prueba TC-M03-G34",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Sincronizacion Segura {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G34-{suf}", "descripcion": "Gateway Edge TC-M03-G34", "id_infraestructura": area,
        "id_tipo_dispositivo": 4, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensor = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                    {"nombre": f"Sensor sincronizacion {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    return {"device_id": device_id, "serial": serial, "sensor": sensor}


def _buffer(nodo: dict, access_key: str, hace_horas: int, n: int = 6) -> list[dict]:
    inicio = datetime.now(timezone.utc) - timedelta(hours=hace_horas)
    return [{"device_id": nodo["device_id"], "sensor_id": nodo["sensor"], "tipo_variable": "TEMPERATURA_AMBIENTAL",
             "valor": 23.0 + i / 10, "unidad": "°C", "timestamp_captura": (inicio + timedelta(minutes=i)).isoformat(),
             "origen": "BUFFER_LOCAL", "access_key": access_key} for i in range(n)]


@pytest.fixture(scope="module")
def revocada(admin, nodo):
    emitida = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot/{nodo['device_id']}/credencial-mqtt", timeout=TIMEOUT)
    assert emitida.status_code == 201, f"Precondicion: emitir credencial MQTT (RF-23): HTTP {emitida.status_code} {emitida.text}"
    clave_mqtt = emitida.json()["password"]
    revocar = admin.delete(f"{BASE_URL}/configuracion/dispositivos-iot/{nodo['device_id']}/credencial-mqtt", timeout=TIMEOUT)
    assert revocar.status_code == 204, f"Precondicion: revocar credencial MQTT: HTTP {revocar.status_code} {revocar.text}"

    desde = datetime.now(timezone.utc) - timedelta(seconds=5)
    con_serial = requests.post(f"{BASE_URL}/iot/telemetria/batch",
                               json={"registros": _buffer(nodo, nodo["serial"], 5)}, timeout=TIMEOUT)
    con_clave_revocada = requests.post(f"{BASE_URL}/iot/telemetria/batch",
                                       json={"registros": _buffer(nodo, clave_mqtt, 6)}, timeout=TIMEOUT)
    persistidos = _consulta_bd("SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor = %s", (nodo["sensor"],))
    auditados = _consulta_bd(
        "SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_dispositivo_iot = %s "
        "AND estado_calidad = 'ERROR_AUTENTICACION' AND fecha_evento >= %s", (nodo["device_id"], desde))
    return {"con_serial": con_serial, "con_clave_revocada": con_clave_revocada,
            "persistidos": persistidos, "auditados": auditados}


@pytest.mark.parametrize("intento", ["con_serial", "con_clave_revocada"])
def test_tc_m03_057_sincronizacion_con_credencial_revocada_rechazada(intento, revocada):
    r = revocada[intento]
    assert r.status_code in (200, 401, 403), f"HTTP {r.status_code} {r.text}"
    if r.status_code == 200:
        cuerpo = r.json()
        assert cuerpo["aceptados"] == 0 and cuerpo["rechazados"] == cuerpo["total"], (
            f"Tras revocar la credencial el lote ({intento}) no debio aceptarse: {cuerpo}"
        )


def test_tc_m03_057_nada_persistido_con_credencial_revocada(revocada):
    assert revocada["persistidos"] == 0, f"Se persistieron {revocada['persistidos']} lecturas con la credencial revocada"


def test_tc_m03_057_rechazo_auditado(revocada):
    assert revocada["auditados"] >= 12, (
        f"Se esperaban 12 eventos ERROR_AUTENTICACION en modulo3.bitacora_ingest (6 + 6), hay {revocada['auditados']}"
    )


def test_tc_m03_057_sincronizacion_por_canal_sin_tls_no_se_procesa(nodo):
    lote = _buffer(nodo, nodo["serial"], 8)
    try:
        r = requests.post(f"http://{HOST}{PREFIJO}/iot/telemetria/batch", json={"registros": lote},
                          timeout=TIMEOUT, allow_redirects=False)
    except requests.exceptions.ConnectionError:
        r = None  # el puerto 80 no acepta la conexion: rechazado
    if r is not None and r.status_code in (301, 302, 307, 308):
        assert r.headers.get("Location", "").startswith("https://"), f"Redirige pero no a HTTPS: {r.headers.get('Location')}"
    elif r is not None:
        assert "aceptados" not in r.text and r.status_code >= 400, (
            f"El lote se proceso por HTTP plano: HTTP {r.status_code} {r.text[:300]}"
        )
    primer_ts = datetime.fromisoformat(lote[0]["timestamp_captura"])
    en_bd = _consulta_bd("SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor = %s AND timestamp_captura = %s",
                         (nodo["sensor"], primer_ts))
    assert en_bd == 0, "El lote enviado por HTTP plano quedo persistido"


def test_tc_m03_057_datos_en_buffer_con_estado_error_en_el_nodo():
    pytest.skip("Que los datos rechazados queden en el buffer con estado ERROR es interno del nodo Edge: requiere el nodo o "
                "el simulador del equipo de IoT")
