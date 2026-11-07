# | Fecha      | Nombre      | Que se hizo                                                                  |
# |------------|-------------|------------------------------------------------------------------------------|
# | 2026-10-26 | Juan Manuel | M03 RF-54: asociar/calibrar sensores y fecha_fin=hoy (DB-10)                 |
# | 2026-10-29 | Juan Manuel | TC-M03-G23 RF-54: buffer_sequence_id en metadatos (INC-M03-131), capturas recientes 037/071 |
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
- buffer_sequence_id (INC-M03-131, 9a0aa196): campo opcional de /iot/telemetria/batch que se conserva tal cual
  en modulo3.telemetrias.metadatos.buffer_sequence_id. Por MQTT el broker (BROKER-MQTT-SGPMP) solo lo pasa si el
  nodo lo manda dentro de `metadatos`; eso es del lado IoT y no se prueba aqui.
- DB-10 (15cb081c4835): la ingesta exige asociacion vigente del sensor a la fecha de CAPTURA. Como los sensores
  se crean en la corrida, 037 y 071 capturan despues de la asociacion (segundos, no horas): lo que prueban
  (orden, secuencia, fragmentacion) no depende de la antiguedad. 050 necesita series de 2 h hacia atras y queda
  bloqueado por DB-10 (INC-M03-133).

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables: BROKER_TOKEN (token de servicio del broker de TEST, DEV-06; sin el /iot/* responde 401).
Opcionales: BASE_URL, LIMITE_BYTES_LOTE, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G23 -v \
        --html=reporte-TC-M03-G23.html --self-contained-html
"""
from __future__ import annotations

import json
import os
import random
import string
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
LIMITE_BYTES_LOTE = int(os.getenv("LIMITE_BYTES_LOTE", "4096"))
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

_BLOQUEO_RLS = (
    "BLOQUEADO: el usuario QA ({usuario}) no puede leer modulo3.telemetrias desde la RLS de modulo3 (migracion "
    "0784d8c03206, 2026-10-28): 'permission denied for function fn_es_usuario_servicio'. El dato se persiste "
    "(la API respondio 201) pero no se puede verificar en BD. Error: {error}"
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
            "serial": self.access_key,
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
        return [requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": lote},
                              headers=_HEADERS_BROKER, timeout=TIMEOUT)
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
            try:
                cur.execute(
                "SELECT t.id_telemetria, t.id_sensor, t.valor_crudo, t.timestamp_captura, t.origen::text AS origen, "
                "       va.nombre AS variable, (t.metadatos ->> 'buffer_sequence_id')::bigint AS buffer_sequence_id "
                "FROM modulo3.telemetrias t JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable "
                "WHERE t.id_sensor = ANY(%s) ORDER BY t.id_telemetria",
                (sensores,),
            )
            except psycopg2.errors.InsufficientPrivilege as exc:
                pytest.fail(_BLOQUEO_RLS.format(usuario=DB["user"], error=str(exc).splitlines()[0]))
            return list(cur.fetchall())
    finally:
        con.close()


def _ventana_reciente(n: int, paso: timedelta) -> datetime:
    """Inicio de n capturas separadas por `paso`, todas posteriores a la asociacion (DB-10) y ya pasadas al enviar."""
    inicio = datetime.now(timezone.utc) + timedelta(seconds=1)
    time.sleep((paso * n).total_seconds() + 3)
    return inicio


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# --------------------------------------------------------------------------- TC-M03-037
@pytest.fixture(scope="module")
def corrida_037(admin, area):
    nodo, sensores = _nodo_con_sensores(admin, area, "037", ["TEMPERATURA"] * 5)
    paso = timedelta(milliseconds=200)
    inicio = _ventana_reciente(50, paso)
    # 50 mediciones de 5 sensores intercaladas; el buffer se drena en FIFO por buffer_sequence_id.
    for i in range(50):
        nodo.capturar_offline(sensores[i % 5], "TEMPERATURA_AMBIENTAL", "°C", round(20 + i * 0.1, 2),
                              inicio + paso * i)
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
    enviado = {(r["sensor_id"], _ts(r["timestamp_captura"])): r["buffer_sequence_id"] for r in corrida_037["nodo"].buffer}
    guardado = {(f["id_sensor"], f["timestamp_captura"]): f["buffer_sequence_id"] for f in corrida_037["filas"]}
    assert guardado == enviado, "telemetrias.metadatos.buffer_sequence_id no coincide con la secuencia asignada en el nodo"
    secuencias = [f["buffer_sequence_id"] for f in corrida_037["filas"]]
    assert secuencias == sorted(secuencias), "El orden de persistencia no sigue la secuencia FIFO del buffer"


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
    paso = timedelta(milliseconds=200)
    inicio = _ventana_reciente(120, paso)
    valores = {}
    for i in range(120):
        valor = round(15 + i * 0.05, 2)
        ts = inicio + paso * i
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
