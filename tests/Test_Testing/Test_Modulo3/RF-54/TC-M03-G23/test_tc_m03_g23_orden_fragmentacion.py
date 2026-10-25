"""
TC-M03-G23 - Integridad de orden y fragmentacion de lotes durante la captura y sincronizacion del buffer.

RF relacionado: RF-54 (CU01). Casos: TC-M03-037, TC-M03-050 (CA-3) y TC-M03-071 (Fase 6).

Criterios de la ficha:
    TC-M03-037: 50 mediciones de varios sensores llegan al backend en orden cronologico estricto
    (timestamp_captura) y conservan el buffer_sequence_id asignado en el nodo. Verificar en la BD.
    TC-M03-050: sensores a 5, 10, 15 y 30 min en modo offline: todas las variables se guardan, sin perdida
    y sin mezclar el orden entre series.
    TC-M03-071: si lo pendiente supera el tamano maximo de payload, se fragmenta en varios lotes sin perder ni
    corromper registros y respetando el orden FIFO entre lotes.

Alcance (mismo criterio que TC-M03-G22): no hay nodo Edge ni simulador en el proyecto. El simulador de este
archivo es solo el DRIVER (arma el buffer, asigna buffer_sequence_id y fragmenta los lotes); las aserciones
son sobre el backend real: respuesta de POST /iot/telemetria/batch y, como pide la ficha, el orden final
leido en la BD (modulo3.telemetrias, solo lectura con el usuario QA).

- El limite de payload LoRaWAN es binario y del firmware; aqui se usa un tope de bytes del JSON por lote
  (LIMITE_BYTES_LOTE, por defecto 4096) solo para forzar varios lotes. Que el NODO respete el limite real
  queda en SKIP (requiere hardware).
- buffer_sequence_id: el contrato de ingesta no lo incluye y modulo3.telemetrias no tiene la columna. Existe
  modulo3.buffers con buffer_sequence_id, pero ningun codigo del backend la escribe. El test busca el id en
  esa tabla para el dispositivo de la prueba.

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, LIMITE_BYTES_LOTE, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G23 -v \
        --html=reporte-TC-M03-G23.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
LIMITE_BYTES_LOTE = int(os.getenv("LIMITE_BYTES_LOTE", "4096"))
TIMEOUT = 30
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    def __init__(self, device_id: int, access_key: str) -> None:
        self.device_id = device_id
        self.access_key = access_key
        self.buffer: list[dict] = []
        self._secuencia = 0

    def capturar_offline(self, sensor_id: int, tipo: str, unidad: str, valor, ts: datetime) -> None:
        self._secuencia += 1
        self.buffer.append({
            "buffer_sequence_id": self._secuencia,
            "device_id": self.device_id, "sensor_id": sensor_id, "tipo_variable": tipo, "valor": valor,
            "unidad": unidad, "timestamp_captura": ts.isoformat(), "origen": "BUFFER_LOCAL",
            "access_key": self.access_key,
        })

    def lotes_fifo(self, limite_bytes: int | None = None) -> list[list[dict]]:
        """Drena en orden FIFO (buffer_sequence_id); si hay limite, corta en lotes que no lo superen."""
        cola = sorted(self.buffer, key=lambda r: r["buffer_sequence_id"])
        if limite_bytes is None:
            return [cola]
        lotes, actual = [], []
        for registro in cola:
            if actual and len(json.dumps({"registros": actual + [registro]}).encode()) > limite_bytes:
                lotes.append(actual)
                actual = []
            actual.append(registro)
        return lotes + ([actual] if actual else [])

    def sincronizar(self, limite_bytes: int | None = None) -> list[requests.Response]:
        return [requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": lote}, timeout=TIMEOUT)
                for lote in self.lotes_fifo(limite_bytes)]


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
    return r.json()[campo]


@pytest.fixture(scope="module")
def area(admin) -> int:
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Orden Buffer {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Orden Buffer {suf}", "descripcion": "Especie de prueba TC-M03-G23",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Orden Buffer {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo_con_sensores(admin, area, etiqueta, categorias) -> tuple[_NodoEdgeSimulado, list[int]]:
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G23-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G23",
        "id_infraestructura": area, "id_tipo_dispositivo": 1, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    nodo = _NodoEdgeSimulado(r.json()["id_dispositivo_iot"], r.json()["serial"])
    sensores = [_crear(admin, f"/configuracion/dispositivos-iot/{nodo.device_id}/sensores",
                       {"nombre": f"Sensor {etiqueta} {i + 1} {suf}", "categoria": c}, "id_sensores")
                for i, c in enumerate(categorias)]
    return nodo, sensores


def _filas_bd(sensores: list[int]) -> list[dict]:
    """Lecturas persistidas en el orden en que se insertaron (id_telemetria)."""
    con = psycopg2.connect(**DB)
    try:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT t.id_telemetria, t.id_sensor, t.valor_crudo, t.timestamp_captura, t.origen::text AS origen, "
                "       va.nombre AS variable "
                "FROM modulo3.telemetrias t JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable "
                "WHERE t.id_sensor = ANY(%s) ORDER BY t.id_telemetria",
                (sensores,),
            )
            return list(cur.fetchall())
    finally:
        con.close()


def _secuencias_en_buffers(device_id: int) -> list[int]:
    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT buffer_sequence_id FROM modulo3.buffers WHERE id_dispositivo_iot = %s "
                        "ORDER BY buffer_sequence_id", (device_id,))
            return [r[0] for r in cur.fetchall()]
    finally:
        con.close()


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# --------------------------------------------------------------------------- TC-M03-037
@pytest.fixture(scope="module")
def corrida_037(admin, area):
    nodo, sensores = _nodo_con_sensores(admin, area, "037", ["TEMPERATURA"] * 5)
    inicio = datetime.now(timezone.utc) - timedelta(hours=3)
    # 50 mediciones de 5 sensores intercaladas; el buffer se drena en FIFO por buffer_sequence_id.
    for i in range(50):
        nodo.capturar_offline(sensores[i % 5], "TEMPERATURA_AMBIENTAL", "°C", round(20 + i * 0.1, 2),
                              inicio + timedelta(minutes=i))
    respuestas = nodo.sincronizar()
    return {"nodo": nodo, "sensores": sensores, "respuestas": respuestas, "filas": _filas_bd(sensores)}


def test_tc_m03_037_las_50_mediciones_se_sincronizan(corrida_037):
    r = corrida_037["respuestas"][0]
    assert r.status_code == 200, f"HTTP {r.status_code} {r.text}"
    assert (r.json()["aceptados"], r.json()["rechazados"], r.json()["duplicados"]) == (50, 0, 0), r.json()
    assert len(corrida_037["filas"]) == 50


def test_tc_m03_037_orden_cronologico_estricto_en_la_bd(corrida_037):
    capturas = [f["timestamp_captura"] for f in corrida_037["filas"]]
    assert capturas == sorted(capturas), "El orden de insercion (id_telemetria) no sigue timestamp_captura"
    assert len(set(capturas)) == 50


def test_tc_m03_037_se_conserva_el_buffer_sequence_id_del_nodo(corrida_037):
    secuencias = _secuencias_en_buffers(corrida_037["nodo"].device_id)
    assert secuencias == list(range(1, 51)), (
        f"El backend no conserva el buffer_sequence_id asignado en el nodo (modulo3.buffers tiene {secuencias or 'nada'} "
        "para el dispositivo; el contrato de ingesta no incluye el campo y modulo3.telemetrias no lo guarda)"
    )


# --------------------------------------------------------------------------- TC-M03-050
_SERIES = [  # (categoria del sensor, tipo_variable, unidad, minutos entre muestras, valor base)
    ("TEMPERATURA", "TEMPERATURA_AMBIENTAL", "°C", 5, 20.0),
    ("PH", "PH_AGUA", "pH", 10, 7.0),
    (None, "FRECUENCIA_CARDIACA", "bpm", 15, 70),
    ("HUMEDAD", "HUMEDAD_RELATIVA", "%", 30, 60.0),
]
_VENTANA_MIN = 120


@pytest.fixture(scope="module")
def corrida_050(admin, area):
    nodo, sensores = _nodo_con_sensores(admin, area, "050", [s[0] for s in _SERIES])
    inicio = datetime.now(timezone.utc) - timedelta(hours=4)
    # Captura offline simultanea: en cada minuto, cada sensor muestrea si le toca segun su frecuencia.
    for minuto in range(_VENTANA_MIN):
        for sensor_id, (_, tipo, unidad, cada, base) in zip(sensores, _SERIES):
            if minuto % cada == 0:
                nodo.capturar_offline(sensor_id, tipo, unidad, base + minuto / 100, inicio + timedelta(minutes=minuto))
    respuestas = nodo.sincronizar()
    return {"sensores": sensores, "respuestas": respuestas, "filas": _filas_bd(sensores)}


def test_tc_m03_050_todas_las_series_se_guardan_sin_perdida(corrida_050):
    r = corrida_050["respuestas"][0]
    assert r.status_code == 200, f"HTTP {r.status_code} {r.text}"
    esperado = {s: _VENTANA_MIN // cada for s, (_, _, _, cada, _) in zip(corrida_050["sensores"], _SERIES)}
    obtenido = {s: sum(1 for f in corrida_050["filas"] if f["id_sensor"] == s) for s in corrida_050["sensores"]}
    assert obtenido == esperado, f"Lecturas por sensor (5/10/15/30 min): esperado {esperado}, obtenido {obtenido}"


def test_tc_m03_050_cada_serie_conserva_su_orden_y_su_variable(corrida_050):
    for sensor_id, (_, tipo, _, _, _) in zip(corrida_050["sensores"], _SERIES):
        serie = [f for f in corrida_050["filas"] if f["id_sensor"] == sensor_id]
        capturas = [f["timestamp_captura"] for f in serie]
        assert capturas == sorted(capturas), f"La serie {tipo} quedo desordenada"
        variables = {f["variable"] for f in serie}
        assert len(variables) == 1, f"La serie del sensor {sensor_id} mezcla variables: {variables}"


# --------------------------------------------------------------------------- TC-M03-071
@pytest.fixture(scope="module")
def corrida_071(admin, area):
    nodo, sensores = _nodo_con_sensores(admin, area, "071", ["TEMPERATURA", "TEMPERATURA"])
    inicio = datetime.now(timezone.utc) - timedelta(hours=6)
    valores = {}
    for i in range(120):
        valor = round(15 + i * 0.05, 2)
        ts = inicio + timedelta(minutes=i)
        nodo.capturar_offline(sensores[i % 2], "TEMPERATURA_AMBIENTAL", "°C", valor, ts)
        valores[(sensores[i % 2], ts)] = Decimal(str(valor))
    lotes = nodo.lotes_fifo(LIMITE_BYTES_LOTE)
    respuestas = nodo.sincronizar(LIMITE_BYTES_LOTE)
    return {"sensores": sensores, "lotes": lotes, "respuestas": respuestas, "valores": valores,
            "filas": _filas_bd(sensores)}


def test_tc_m03_071_el_volumen_requiere_varios_lotes(corrida_071):
    assert len(corrida_071["lotes"]) > 1, "El volumen de prueba debe superar el limite de un lote"


def test_tc_m03_071_todos_los_lotes_aceptados_sin_perdida(corrida_071):
    for i, r in enumerate(corrida_071["respuestas"], start=1):
        assert r.status_code == 200, f"Lote {i}: HTTP {r.status_code} {r.text}"
        cuerpo = r.json()
        assert cuerpo["rechazados"] == 0 and cuerpo["duplicados"] == 0, f"Lote {i}: {cuerpo}"
    assert len(corrida_071["filas"]) == 120


def test_tc_m03_071_registros_sin_corrupcion(corrida_071):
    for f in corrida_071["filas"]:
        esperado = corrida_071["valores"].get((f["id_sensor"], f["timestamp_captura"]))
        assert esperado is not None and f["valor_crudo"] == esperado, (
            f"Registro alterado: sensor {f['id_sensor']} {f['timestamp_captura']} valor {f['valor_crudo']} (esperado {esperado})"
        )


def test_tc_m03_071_orden_fifo_entre_lotes(corrida_071):
    capturas = [f["timestamp_captura"] for f in corrida_071["filas"]]
    assert capturas == sorted(capturas), "Un lote posterior quedo insertado antes que uno anterior"


def test_tc_m03_071_el_nodo_respeta_el_limite_real_de_payload_lorawan():
    pytest.skip("El tamano maximo de payload LoRaWAN (binario, por data rate) lo aplica el firmware del nodo: "
                "requiere el nodo o el simulador del equipo de IoT")
