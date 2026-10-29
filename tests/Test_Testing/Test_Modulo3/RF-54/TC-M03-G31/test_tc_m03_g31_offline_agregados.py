"""
TC-M03-G31 - Procesamiento Edge en operacion totalmente offline y sincronizacion de datos agregados con trazabilidad.

RF relacionado: RF-54 (CU01). Casos: TC-M03-051 (CA-13) y TC-M03-052 (CA-16).

Criterios de la ficha:
    TC-M03-051: sin conectividad el nodo sigue capturando, evalua reglas locales (RF-55) y guarda CRUDO,
    AGREGADO y EVENTO_EDGE; genera BACKEND_UNAVAILABLE.
    TC-M03-052: los agregados llegan al backend como tipo_dato=AGREGADO con su ventana y trazabilidad completa,
    y el backend los procesa como EDGE_AGREGADO.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el DRIVER
(arma en su buffer lecturas crudas, promedios por ventana de 5 min y eventos de desviacion). Se verifica en el
backend real:
- 051: al reconectar se aceptan los tres tipos guardados offline: CRUDO (BUFFER_LOCAL) y AGREGADO
  (EDGE_AGREGADO) por POST /iot/telemetria/batch, y EVENTO_EDGE por POST /iot/eventos-edge con origen
  BUFFER_LOCAL.
- 052: en modulo3.telemetrias (lectura en BD, usuario QA; el historial RF-59 no expone estos campos):
  agregados con tipo_dato=AGREGADO, origen=EDGE_AGREGADO, ventana_agregacion_min=5, valor_agregado y
  dato_agredado_edge en true; crudos con tipo_dato=CRUDO y origen=BUFFER_LOCAL; y cada agregado conserva el
  valor promedio calculado en Edge.
- Interno del nodo (SKIP): la operacion autonoma, la evaluacion de reglas RF-55 y BACKEND_UNAVAILABLE.

Requisitos: acceso de red a TEST (API y Postgres 5448) y BROKER_TOKEN (token de servicio del broker de TEST,
DEV-06; sin el /iot/* responde 401).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G31 -v \
        --html=reporte-TC-M03-G31.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import statistics
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30

# DEV-06: los endpoints /iot/* de dispositivo exigen el token de servicio del broker (Authorization: Bearer);
# se toma de BROKER_TOKEN y no se versiona. El serial del cuerpo es la identidad del nodo, no una credencial.
BROKER_TOKEN = os.getenv("BROKER_TOKEN", "")
_HEADERS_BROKER = {"Authorization": f"Bearer {BROKER_TOKEN}"}
VENTANA_MIN = 5
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    """Captura offline cada minuto, agrega por ventana y registra eventos cuando el valor supera 30 °C."""

    def __init__(self, device_id: int, sensor_crudo: int, sensor_agregado: int, access_key: str) -> None:
        self.device_id, self.access_key = device_id, access_key
        self.sensor_crudo, self.sensor_agregado = sensor_crudo, sensor_agregado
        self.crudos: list[dict] = []
        self.agregados: list[dict] = []
        self.eventos: list[dict] = []

    def _base(self, sensor_id, valor, ts: datetime, origen: str) -> dict:
        return {"device_id": self.device_id, "sensor_id": sensor_id, "tipo_variable": "TEMPERATURA_AMBIENTAL",
                "valor": valor, "unidad": "°C", "timestamp_captura": ts.isoformat(), "origen": origen,
                "serial": self.access_key}

    def operar_offline(self, inicio: datetime, minutos: int) -> None:
        ventana: list[float] = []
        for m in range(minutos):
            ts = inicio + timedelta(minutes=m)
            valor = round(26 + 6 * ((m % 15) / 15), 2)  # sube hasta ~31.6 °C cada 15 min
            self.crudos.append(self._base(self.sensor_crudo, valor, ts, "BUFFER_LOCAL"))
            ventana.append(valor)
            if valor > 30 and not any(e["timestamp_captura"] == ts.isoformat() for e in self.eventos):
                self.eventos.append({
                    "device_id": self.device_id, "sensor_id": self.sensor_crudo, "serial": self.access_key,
                    "clasificacion_rf55": "DESVIACION_SIMPLE", "severidad": "MODERADO",
                    "variables_involucradas": [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": valor,
                                                "unidad": "°C", "timestamp_captura": ts.isoformat()}],
                    "timestamp_captura": ts.isoformat(),
                    "timestamp_procesamiento_edge": (ts + timedelta(seconds=1)).isoformat(),
                    "origen": "BUFFER_LOCAL", "estado_conectividad": False,
                })
            if len(ventana) == VENTANA_MIN:
                agregado = self._base(self.sensor_agregado, round(statistics.mean(ventana), 2),
                                      ts - timedelta(minutes=VENTANA_MIN - 1), "EDGE_AGREGADO")
                agregado.update({"valor_agregado": True, "ventana_agregacion": VENTANA_MIN})
                self.agregados.append(agregado)
                ventana = []


# --------------------------------------------------------------------------- datos propios en TEST
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
        "nombre": f"Finca Offline Edge {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Offline Edge {suf}", "descripcion": "Especie de prueba TC-M03-G31",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Offline Edge {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G31-{suf}", "descripcion": "Nodo Edge TC-M03-G31", "id_infraestructura": area,
        "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    # Un sensor para la serie cruda y otro (mismo punto, canal agregado) para no chocar claves con los crudos.
    s_crudo = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                     {"nombre": f"Sensor crudo {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    s_agregado = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                        {"nombre": f"Sensor agregado {suf}", "categoria": "TEMPERATURA"}, "id_sensores")

    nodo = _NodoEdgeSimulado(device_id, s_crudo, s_agregado, serial)
    nodo.operar_offline(datetime.now(timezone.utc) - timedelta(hours=1), 30)

    sync_crudos = requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": nodo.crudos}, headers=_HEADERS_BROKER, timeout=TIMEOUT)
    sync_agregados = requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": nodo.agregados}, headers=_HEADERS_BROKER, timeout=TIMEOUT)
    eventos = [requests.post(f"{BASE_URL}/iot/eventos-edge", json=e, headers=_HEADERS_BROKER, timeout=TIMEOUT) for e in nodo.eventos]

    con = psycopg2.connect(**DB)
    try:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id_sensor, timestamp_captura, valor_crudo, tipo_dato::text AS tipo_dato, origen::text AS origen, "
                "       ventana_agregacion_min, valor_agregado, dato_agredado_edge "
                "FROM modulo3.telemetrias WHERE id_sensor IN (%s, %s)", (s_crudo, s_agregado))
            filas = list(cur.fetchall())
    finally:
        con.close()
    return {"nodo": nodo, "sync_crudos": sync_crudos, "sync_agregados": sync_agregados, "eventos": eventos,
            "crudos_bd": [f for f in filas if f["id_sensor"] == s_crudo],
            "agregados_bd": [f for f in filas if f["id_sensor"] == s_agregado]}


# --------------------------------------------------------------------------- TC-M03-051
def test_tc_m03_051_el_nodo_genero_los_tres_tipos_offline(corrida):
    nodo = corrida["nodo"]
    assert len(nodo.crudos) == 30 and len(nodo.agregados) == 6 and nodo.eventos, "Guarda del driver"


def test_tc_m03_051_al_reconectar_se_aceptan_crudos_agregados_y_eventos(corrida):
    for nombre, r, n in [("CRUDO", corrida["sync_crudos"], 30), ("AGREGADO", corrida["sync_agregados"], 6)]:
        assert r.status_code == 200, f"{nombre}: HTTP {r.status_code} {r.text}"
        assert (r.json()["aceptados"], r.json()["rechazados"]) == (n, 0), f"{nombre}: {r.json()}"
    for i, r in enumerate(corrida["eventos"], start=1):
        assert r.status_code == 201, f"EVENTO_EDGE {i}: HTTP {r.status_code} {r.text}"


def test_tc_m03_051_operacion_autonoma_rf55_y_backend_unavailable_en_el_nodo():
    pytest.skip("La operacion autonoma, la evaluacion de reglas locales RF-55 y BACKEND_UNAVAILABLE son internas del nodo "
                "Edge: requieren el nodo o el simulador del equipo de IoT")


# --------------------------------------------------------------------------- TC-M03-052
def test_tc_m03_052_agregados_conservan_su_trazabilidad(corrida):
    agregados = corrida["agregados_bd"]
    assert len(agregados) == 6
    problemas = [
        (f["timestamp_captura"].isoformat(), f["tipo_dato"], f["origen"], f["ventana_agregacion_min"],
         f["valor_agregado"], f["dato_agredado_edge"])
        for f in agregados
        if not (f["tipo_dato"] == "AGREGADO" and f["origen"] == "EDGE_AGREGADO" and f["ventana_agregacion_min"] == VENTANA_MIN
                and f["valor_agregado"] is True and f["dato_agredado_edge"] is True)
    ]
    assert not problemas, f"Agregados sin trazabilidad completa (ts, tipo_dato, origen, ventana, valor_agregado, dato_agregado_edge): {problemas}"


def test_tc_m03_052_el_valor_promedio_de_edge_se_conserva(corrida):
    enviados = {_ts(a["timestamp_captura"]): Decimal(str(a["valor"])) for a in corrida["nodo"].agregados}
    guardados = {f["timestamp_captura"]: f["valor_crudo"] for f in corrida["agregados_bd"]}
    assert guardados == enviados


def test_tc_m03_052_los_crudos_quedan_como_crudos(corrida):
    crudos = corrida["crudos_bd"]
    assert len(crudos) == 30
    assert {(f["tipo_dato"], f["origen"]) for f in crudos} == {("CRUDO", "BUFFER_LOCAL")}
