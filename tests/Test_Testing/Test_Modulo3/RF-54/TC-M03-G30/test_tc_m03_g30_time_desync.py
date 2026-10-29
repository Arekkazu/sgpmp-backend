# | Fecha      | Nombre      | Que se hizo                                                                  |
# |------------|-------------|------------------------------------------------------------------------------|
# | 2026-10-26 | Juan Manuel | M03 RF-54: asociar/calibrar sensores y fecha_fin=hoy (DB-10)                 |
"""
TC-M03-G30 - Marcar datos capturados con reloj desincronizado (TIME_DESYNC).

RF relacionado: RF-54 (CU01). Caso: TC-M03-049 (flujo alterno E9). Relacionado con TC-M03-011 (ERROR_TIEMPO).

Criterio de la ficha: con el reloj del dispositivo desfasado respecto a NTP, el almacenamiento continua pero los
datos quedan marcados con TIME_DESYNC y restringidos para analisis sensibles; el dispositivo intenta
resincronizar el reloj solo.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el DRIVER y
controla su propio reloj (desfase respecto a la hora real/NTP). Se verifica en el backend real:
- el nodo informa la desincronizacion por heartbeat (reloj_sincronizado=false): debe quedar registrada y
  generar una alerta tecnica (el enum de TEST tiene DESINCRONIZACION_RELOJ);
- las lecturas capturadas con el reloj desfasado, al sincronizarse, se guardan (no se pierden) y quedan
  marcadas: columna modulo3.telemetrias.reloj_desincronizado = true (lectura en BD, usuario QA). El nodo
  envia la marca en el campo `reloj_desincronizado` de cada registro;
- tambien con el reloj ADELANTADO (timestamps "futuros" para el servidor), que es el caso que hoy choca con
  ERROR_TIEMPO de RF-53 (tolerancia de 30 s).
Interno del nodo (SKIP): la deteccion del salto/desfase y la resincronizacion automatica con NTP.
"Restringidos para analisis sensibles" no tiene un consumidor verificable por API en M03.

Nota del codigo: la ingesta nunca asigna reloj_desincronizado (queda en false) y el contrato no tiene un campo
para que el nodo lo informe; el heartbeat guarda reloj_sincronizado sin generar alerta.

Requisitos: acceso de red a TEST (API y Postgres 5448) y BROKER_TOKEN (token de servicio del broker de TEST,
DEV-06; sin el /iot/* responde 401).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G30 -v \
        --html=reporte-TC-M03-G30.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30

# DEV-06: los endpoints /iot/* de dispositivo exigen el token de servicio del broker (Authorization: Bearer);
# se toma de BROKER_TOKEN y no se versiona. El serial del cuerpo es la identidad del nodo, no una credencial.
BROKER_TOKEN = os.getenv("BROKER_TOKEN", "")
_HEADERS_BROKER = {"Authorization": f"Bearer {BROKER_TOKEN}"}
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    def __init__(self, device_id: int, sensor_id: int, access_key: str) -> None:
        self.device_id, self.sensor_id, self.access_key = device_id, sensor_id, access_key
        self.desfase = timedelta(0)  # diferencia del reloj del nodo respecto a NTP
        self.buffer: list[dict] = []

    def ahora(self) -> datetime:
        return datetime.now(timezone.utc) + self.desfase

    def capturar_offline(self, hace: timedelta, valor: float) -> None:
        self.buffer.append({
            "device_id": self.device_id, "sensor_id": self.sensor_id, "tipo_variable": "TEMPERATURA_AMBIENTAL",
            "valor": valor, "unidad": "°C", "timestamp_captura": (self.ahora() - hace).isoformat(),
            "origen": "BUFFER_LOCAL", "serial": self.access_key,
            "reloj_desincronizado": self.desfase != timedelta(0),
        })

    def heartbeat(self) -> requests.Response:
        return requests.post(
            f"{BASE_URL}/iot/heartbeat",
            json={
                "device_id": self.device_id, "serial": self.access_key, "tipo_mensaje": "HEARTBEAT", "estado_local_buffer": "A" if self.buffer else "I",
                  "datos_pendientes_buffer": len(self.buffer), "fecha_registro": self.ahora().isoformat(),
                  "reloj_sincronizado": self.desfase == timedelta(0)},
            headers=_HEADERS_BROKER, timeout=TIMEOUT,
        )

    def sincronizar(self) -> requests.Response:
        return requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": self.buffer}, headers=_HEADERS_BROKER, timeout=TIMEOUT)


# --------------------------------------------------------------------------- datos propios en TEST
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
    if ruta.endswith("/sensores"):
        _asociar_y_calibrar(s, int(ruta.split("/")[-2]), r.json()[campo])
    return r.json()[campo]


def _asociar_y_calibrar(s, device_id, sensor_id):
    """DB-10: la ingesta exige que el sensor tenga asociación vigente (RF-22) a la fecha de captura; sin calibración
    (RF-24) la lectura queda ERROR_CALIBRACION. Se asocia al área del dispositivo y se calibra neutro (ganancia 1, offset 0);
    la referencia 7.0 cae dentro del rango de seguridad de todas las categorías (pH 0-14, amoníaco 0-10, temperatura 0-45...)."""
    area = s.get(f"{BASE_URL}/configuracion/dispositivos-iot/{device_id}", timeout=TIMEOUT).json()["id_infraestructura"]
    r = s.post(f"{BASE_URL}/configuracion/sensores/{sensor_id}/asociar", json={
        "id_dispositivo_iot": device_id, "id_infraestructura": area, "punto_instalacion": "Punto central"}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion asociar sensor {sensor_id}: HTTP {r.status_code} {r.text}"
    r = s.post(f"{BASE_URL}/configuracion/sensores/{sensor_id}/calibrar", json={
        "id_dispositivo_iot": device_id, "id_infraestructura": area, "valor_referencia": 7.0, "ganancia": 1.0,
        "offset": 0.0, "fecha_calibracion": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "modo_calibracion": "SENSOR"}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion calibrar sensor {sensor_id}: HTTP {r.status_code} {r.text}"


@pytest.fixture(scope="module")
def area(admin) -> int:
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Reloj Edge {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Reloj Edge {suf}", "descripcion": "Especie de prueba TC-M03-G30",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Reloj Edge {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo(admin, area, etiqueta) -> _NodoEdgeSimulado:
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G30-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G30",
        "id_infraestructura": area, "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensor_id = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                       {"nombre": f"Sensor {etiqueta} {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    return _NodoEdgeSimulado(device_id, sensor_id, serial)


def _marcas_bd(sensor_id: int) -> list[bool]:
    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT reloj_desincronizado FROM modulo3.telemetrias WHERE id_sensor = %s", (sensor_id,))
            return [r[0] for r in cur.fetchall()]
    finally:
        con.close()


def _ultimo_heartbeat_sincronizado(device_id: int):
    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT has_table_privilege('modulo3.heartbeats', 'SELECT')")
            if not cur.fetchone()[0]:
                return "sin acceso"
            cur.execute("SELECT reloj_sincronizado FROM modulo3.heartbeats WHERE id_dispositivo_iot = %s "
                        "ORDER BY id_heartbeat DESC LIMIT 1", (device_id,))
            fila = cur.fetchone()
            return fila[0] if fila else None
    finally:
        con.close()


# --------------------------------------------------------------------------- reloj atrasado
@pytest.fixture(scope="module")
def corrida_atrasado(admin, area):
    nodo = _nodo(admin, area, "ATR")
    assert nodo.heartbeat().status_code == 200, "Heartbeat inicial con el reloj sincronizado"
    desde = datetime.now(timezone.utc) - timedelta(minutes=5)
    nodo.desfase = -timedelta(hours=3)  # salto del reloj: 3 h atrasado respecto a NTP
    for i in range(8):
        nodo.capturar_offline(timedelta(minutes=8 - i), 23.0 + i / 10)
    hb = nodo.heartbeat()
    sync = nodo.sincronizar()
    alertas = admin.get(f"{BASE_URL}/iot/alertas-tecnicas", params={
        "fecha_desde": desde.isoformat(), "fecha_hasta": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "por_pagina": 200}, timeout=TIMEOUT)
    return {"nodo": nodo, "hb": hb, "sync": sync, "alertas": alertas, "marcas": _marcas_bd(nodo.sensor_id),
            "hb_bd": _ultimo_heartbeat_sincronizado(nodo.device_id)}


def test_tc_m03_049_el_almacenamiento_continua_con_el_reloj_desfasado(corrida_atrasado):
    r = corrida_atrasado["sync"]
    assert r.status_code == 200, r.text
    assert (r.json()["aceptados"], r.json()["rechazados"]) == (8, 0), r.json()


def test_tc_m03_049_los_datos_quedan_marcados_time_desync(corrida_atrasado):
    marcas = corrida_atrasado["marcas"]
    assert len(marcas) == 8
    assert all(marcas), f"reloj_desincronizado en BD: {marcas} (se esperaba true en las 8 lecturas)"


def test_tc_m03_049_la_desincronizacion_informada_queda_registrada(corrida_atrasado):
    assert corrida_atrasado["hb"].status_code == 200
    if corrida_atrasado["hb_bd"] == "sin acceso":
        pytest.skip("El usuario QA no puede leer modulo3.heartbeats")
    assert corrida_atrasado["hb_bd"] is False, f"Ultimo heartbeat en BD: reloj_sincronizado={corrida_atrasado['hb_bd']}"


def test_tc_m03_049_alerta_de_desincronizacion_de_reloj(corrida_atrasado):
    r = corrida_atrasado["alertas"]
    assert r.status_code == 200, r.text
    del_dispositivo = [a for a in r.json()["items"] if a.get("id_dispositivo_ioit") == corrida_atrasado["nodo"].device_id]
    assert del_dispositivo, "Ninguna alerta tecnica (DESINCRONIZACION_RELOJ) para el dispositivo con el reloj desfasado"


# --------------------------------------------------------------------------- reloj adelantado
def test_tc_m03_049_reloj_adelantado_los_datos_no_se_pierden(admin, area):
    nodo = _nodo(admin, area, "ADE")
    nodo.desfase = timedelta(minutes=20)  # 20 min adelantado: sus timestamps son "futuros" para el servidor
    for i in range(5):
        nodo.capturar_offline(timedelta(minutes=5 - i), 24.0)
    r = nodo.sincronizar()
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["aceptados"] == 5, (
        f"Con el reloj adelantado el backend rechaza las lecturas (ERROR_TIEMPO por timestamp futuro) en vez de "
        f"guardarlas marcadas: {cuerpo['rechazados']} rechazadas, motivos {[d.get('error') for d in cuerpo['detalle']][:2]}"
    )
    assert all(_marcas_bd(nodo.sensor_id))


def test_tc_m03_049_deteccion_y_resincronizacion_ntp_en_el_nodo():
    pytest.skip("Detectar el salto/desfase del reloj y resincronizar con NTP son internos del nodo Edge: requieren el nodo "
                "o el simulador del equipo de IoT")
