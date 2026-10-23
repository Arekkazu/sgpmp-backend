"""
TC-M03-G25 - Confirmacion por ACK, manejo de fallos parciales y agotamiento de reintentos con backoff.

RF relacionado: RF-54 (CU01). Casos: TC-M03-039 (CA-6), TC-M03-040 (flujo alterno E3) y TC-M03-048 (Fase 10).

Criterios de la ficha:
    TC-M03-039: sin ACK del backend un dato no se elimina del buffer; solo lo confirmado pasa a CONFIRMADO.
    TC-M03-040: lote de 20 (15 validos, 5 rechazados): los 15 se confirman, los 5 quedan en ERROR, se
    registra SYNC_PARTIAL_FAILURE y se reintenta solo sobre los fallidos.
    TC-M03-048: con el backend rechazando todo, reintentos con backoff exponencial hasta un limite; al
    agotarse se registra SYNC_FAILURE, el dato queda en buffer (ERROR) y se notifica al administrador.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, _NodoEdgeSimulado es el
DRIVER y el backend es el real (no un mock): lo que se verifica es el contrato que el nodo necesita para no
perder datos.
- ACK por registro: POST /iot/telemetria/batch devuelve en `detalle` un item por registro (estado,
  id_telemetria o error). Un ACK con id_telemetria debe corresponder a una lectura realmente persistida, y un
  rechazo a una que no lo esta (historial RF-59).
- 039: el "ACK que no llega" se simula descartando en el driver parte del detalle recibido; el nodo reenvia
  esos registros y el backend debe responderlos como duplicados (ya confirmados), sin crear registros nuevos.
- 040: el backend debe aceptar el lote parcialmente (HTTP 200, 15/5), identificar cada rechazo y no guardar
  nada de los 5; el reintento sobre los fallidos no debe duplicar los 15.
- 048: se desactiva el dispositivo (RF-21) para que el backend rechace todo de forma sostenida; cada
  reintento debe rechazarse sin persistir nada, y al final debe existir una notificacion al administrador
  (alerta tecnica del dispositivo, RF-60).
- Interno del nodo (SKIP): estado CONFIRMADO/ERROR por registro, borrado local, SYNC_PARTIAL_FAILURE,
  SYNC_FAILURE, intentos_envio y los intervalos del backoff. Medirlos sobre este simulador solo probaria el
  simulador.

Requisitos: acceso de red a TEST. Variables opcionales: BASE_URL.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G25 -v \
        --html=reporte-TC-M03-G25.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30
REINTENTOS_MAX = 5
BACKOFF_BASE_SEG = 0.5


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    def __init__(self, device_id: int, sensor_id: int, access_key: str) -> None:
        self.device_id, self.sensor_id, self.access_key = device_id, sensor_id, access_key
        self.buffer: dict[str, dict] = {}  # clave = timestamp_captura

    def capturar_offline(self, ts: datetime, valor: float, unidad: str = "°C") -> None:
        clave = ts.isoformat()
        self.buffer[clave] = {
            "device_id": self.device_id, "sensor_id": self.sensor_id, "tipo_variable": "TEMPERATURA_AMBIENTAL",
            "valor": valor, "unidad": unidad, "timestamp_captura": clave, "origen": "BUFFER_LOCAL",
            "access_key": self.access_key,
        }

    def enviar(self, registros: list[dict]) -> requests.Response:
        return requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": registros}, timeout=TIMEOUT)

    def borrar_confirmados(self, detalle: list[dict]) -> None:
        """Solo borra lo que el backend confirmo: aceptado (id_telemetria) o ya existente (duplicado)."""
        for item in detalle:
            if item.get("id_telemetria") or item["estado"] == "ERROR_DUPLICADO":
                for clave in list(self.buffer):
                    if datetime.fromisoformat(clave) == _ts(item["timestamp_captura"]):
                        del self.buffer[clave]


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
def area(admin) -> int:
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Ack Buffer {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Ack Buffer {suf}", "descripcion": "Especie de prueba TC-M03-G25",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Ack Buffer {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo(admin, area, etiqueta) -> _NodoEdgeSimulado:
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G25-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G25",
        "id_infraestructura": area, "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensor_id = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                       {"nombre": f"Sensor {etiqueta} {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    return _NodoEdgeSimulado(device_id, sensor_id, serial)


def _historial(admin, sensor_id: int) -> list[dict]:
    hoy = datetime.now(timezone.utc).date()
    r = admin.get(f"{BASE_URL}/iot/monitoreo/historial", params={
        "fecha_inicio": str(hoy - timedelta(days=1)), "fecha_fin": str(hoy + timedelta(days=1)),
        "sensor_id": sensor_id, "por_pagina": 500, "orden": "ASC"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Historial: HTTP {r.status_code} {r.text}"
    return r.json()["items"]


# --------------------------------------------------------------------------- TC-M03-039
@pytest.fixture(scope="module")
def corrida_039(admin, area):
    nodo = _nodo(admin, area, "039")
    inicio = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(20):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 20.0 + i * 0.1)
    enviados = list(nodo.buffer.values())

    primera = nodo.enviar(enviados)
    detalle = primera.json()["detalle"] if primera.status_code == 200 else []
    # El ACK de los ultimos 8 registros "no llega" al nodo (se pierde en la red).
    nodo.borrar_confirmados(detalle[:12])
    en_buffer_tras_ack_parcial = len(nodo.buffer)

    reenvio = nodo.enviar(list(nodo.buffer.values()))
    if reenvio.status_code == 200:
        nodo.borrar_confirmados(reenvio.json()["detalle"])
    return {"nodo": nodo, "primera": primera, "detalle": detalle, "en_buffer": en_buffer_tras_ack_parcial,
            "reenvio": reenvio, "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_039_ack_individual_por_cada_registro(corrida_039):
    assert corrida_039["primera"].status_code == 200, corrida_039["primera"].text
    detalle = corrida_039["detalle"]
    assert len(detalle) == 20, f"El backend debe responder un ACK por registro, devolvio {len(detalle)}"
    assert all(d["id_telemetria"] for d in detalle), detalle


def test_tc_m03_039_cada_ack_corresponde_a_una_lectura_persistida(corrida_039):
    persistidos = {x["id_telemetria"] for x in corrida_039["historial"]}
    confirmados = {d["id_telemetria"] for d in corrida_039["detalle"]}
    assert confirmados <= persistidos, f"ACK de lecturas que no estan en el historial: {confirmados - persistidos}"


def test_tc_m03_039_reenvio_de_lo_no_confirmado_no_duplica(corrida_039):
    assert corrida_039["en_buffer"] == 8
    r = corrida_039["reenvio"]
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["aceptados"], cuerpo["duplicados"], cuerpo["rechazados"]) == (0, 8, 0), (
        f"Lo ya persistido pero sin ACK debe volver como duplicado (confirmado), no como registro nuevo: {cuerpo}"
    )
    assert len(corrida_039["historial"]) == 20
    assert corrida_039["nodo"].buffer == {}, "Tras el reenvio el nodo debe poder confirmar todo"


# --------------------------------------------------------------------------- TC-M03-040
@pytest.fixture(scope="module")
def corrida_040(admin, area):
    nodo = _nodo(admin, area, "040")
    inicio = datetime.now(timezone.utc) - timedelta(hours=2)
    invalidos = set()
    for i in range(20):
        ts = inicio + timedelta(minutes=i)
        if i % 4 == 3:  # 5 de 20 con unidad inconsistente: el backend los rechaza (ERROR_UNIDAD)
            nodo.capturar_offline(ts, 25.0, unidad="%")
            invalidos.add(ts)
        else:
            nodo.capturar_offline(ts, 25.0)
    lote = nodo.enviar(list(nodo.buffer.values()))
    if lote.status_code == 200:
        nodo.borrar_confirmados(lote.json()["detalle"])
    reintento = nodo.enviar(list(nodo.buffer.values()))  # solo los fallidos
    return {"nodo": nodo, "invalidos": invalidos, "lote": lote, "reintento": reintento,
            "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_040_lote_aceptado_parcialmente(corrida_040):
    r = corrida_040["lote"]
    assert r.status_code == 200, f"Un fallo parcial no debe tumbar el lote completo: HTTP {r.status_code} {r.text}"
    cuerpo = r.json()
    assert (cuerpo["total"], cuerpo["aceptados"], cuerpo["rechazados"]) == (20, 15, 5), cuerpo


def test_tc_m03_040_cada_rechazo_identificado(corrida_040):
    rechazados = [d for d in corrida_040["lote"].json()["detalle"] if not d["id_telemetria"]]
    assert {_ts(d["timestamp_captura"]) for d in rechazados} == corrida_040["invalidos"]
    assert all(d["error"] for d in rechazados), "Cada rechazo debe traer el motivo"


def test_tc_m03_040_solo_los_15_validos_persistidos_y_el_reintento_no_duplica(corrida_040):
    assert len(corrida_040["nodo"].buffer) == 5, "Los 5 fallidos deben quedar en el buffer"
    r = corrida_040["reintento"]
    assert r.status_code == 200 and r.json()["total"] == 5 and r.json()["aceptados"] == 0, r.text
    historial = corrida_040["historial"]
    assert len(historial) == 15
    assert not ({_ts(x["timestamp_captura"]) for x in historial} & corrida_040["invalidos"])


def test_tc_m03_040_sync_partial_failure_y_checkpoint_en_el_nodo():
    pytest.skip("Estado ERROR por registro, SYNC_PARTIAL_FAILURE y checkpoint del ultimo lote exitoso son internos del "
                "nodo Edge: requieren el nodo o el simulador del equipo de IoT")


# --------------------------------------------------------------------------- TC-M03-048
@pytest.fixture(scope="module")
def corrida_048(admin, area):
    nodo = _nodo(admin, area, "048")
    inicio = datetime.now(timezone.utc) - timedelta(hours=3)
    for i in range(10):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 22.0)
    desde = datetime.now(timezone.utc) - timedelta(minutes=5)

    r = admin.patch(f"{BASE_URL}/configuracion/dispositivos-iot/{nodo.device_id}/desactivar", timeout=TIMEOUT)
    assert r.status_code == 200, f"Precondicion: desactivar el dispositivo para forzar el rechazo: HTTP {r.status_code} {r.text}"

    intentos = []
    for n in range(REINTENTOS_MAX):
        resp = nodo.enviar(list(nodo.buffer.values()))
        intentos.append(resp)
        if resp.status_code == 200:
            nodo.borrar_confirmados(resp.json()["detalle"])
        if not nodo.buffer:
            break
        time.sleep(BACKOFF_BASE_SEG * (2 ** n))

    alertas = admin.get(f"{BASE_URL}/iot/alertas-tecnicas", params={
        "fecha_desde": desde.isoformat(), "fecha_hasta": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "por_pagina": 200}, timeout=TIMEOUT)
    return {"nodo": nodo, "intentos": intentos, "alertas": alertas, "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_048_cada_reintento_se_rechaza_sin_persistir(corrida_048):
    assert len(corrida_048["intentos"]) == REINTENTOS_MAX
    for n, r in enumerate(corrida_048["intentos"], start=1):
        assert r.status_code == 200, f"Intento {n}: HTTP {r.status_code} {r.text}"
        assert r.json()["rechazados"] == 10 and r.json()["aceptados"] == 0, f"Intento {n}: {r.json()}"
    assert corrida_048["historial"] == []


def test_tc_m03_048_el_dato_nunca_se_descarta(corrida_048):
    assert len(corrida_048["nodo"].buffer) == 10, "Tras agotar los reintentos los 10 datos siguen en el buffer"


def test_tc_m03_048_se_notifica_al_administrador(corrida_048):
    r = corrida_048["alertas"]
    assert r.status_code == 200, f"Alertas tecnicas: HTTP {r.status_code} {r.text}"
    del_dispositivo = [a for a in r.json()["items"] if a.get("id_dispositivo_ioit") == corrida_048["nodo"].device_id]
    assert del_dispositivo, (
        "No hay ninguna alerta tecnica para el dispositivo tras agotar los reintentos (la ficha exige notificar al "
        "administrador; el enum tiene BUFFER_PROLONGADO pero ningun codigo lo genera)"
    )


def test_tc_m03_048_backoff_intentos_envio_y_sync_failure_en_el_nodo():
    pytest.skip("Intervalos de backoff exponencial, contador intentos_envio y SYNC_FAILURE son internos del nodo Edge: "
                "requieren el nodo o el simulador del equipo de IoT")
