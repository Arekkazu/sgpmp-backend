"""
TC-M03-G22 - Activacion automatica del buffer local y persistencia ante reinicio del dispositivo.

RF relacionado: RF-54 (CU01). Casos: TC-M03-035 y TC-M03-036 (flujo alterno E2).

Criterios de la ficha:
    TC-M03-035: al perder conectividad el buffer se activa solo y guarda el 100% de las mediciones del
    periodo (estado_buffer=PENDIENTE), sin perder ninguna.
    TC-M03-036: tras un reinicio inesperado el buffer se reconstruye desde almacenamiento no volatil, se
    valida por checksum y se restaura el ultimo indice enviado, sin perdida ni duplicacion.

Alcance de este archivo (decision del 2026-10-19): el proyecto no tiene codigo del nodo Edge ni un
simulador, y el backend no expone el buffer (no existe GET /dispositivos/{id}/buffer). Por eso:
- _NodoEdgeSimulado hace de nodo y es solo el DRIVER de la prueba: captura lecturas, guarda su buffer en
  un archivo (almacenamiento no volatil simulado) con checksum e ultimo indice enviado, y se "reinicia"
  perdiendo todo lo que tenia en memoria.
- Las aserciones son sobre lo que el SISTEMA ve y guarda (backend TEST, endpoints reales):
    * el heartbeat con buffer activo deja al dispositivo en BUFFER_ACTIVO y luego vuelve a ACTIVO (RF-60);
    * la sincronizacion por POST /iot/telemetria/batch (origen BUFFER_LOCAL) entrega el 100% de lo
      capturado durante la desconexion, en orden y sin duplicados (historial RF-59);
    * tras el reinicio, el reenvio desde el ultimo indice persistido (con solapamiento) no duplica ni pierde.
- Lo que ocurre DENTRO del nodo (estado_buffer=PENDIENTE, reconstruccion real desde flash/SD/EEPROM y
  validacion de checksum del firmware) no es verificable sin el nodo o el simulador del equipo de IoT:
  esos tests quedan en SKIP con la razon. Validarlos contra el simulador propio solo probaria el simulador.
- La desconexion de 30 min se comprime: 30 lecturas con timestamps separados 1 min (dentro de la ventana
  de 72 h de BUFFER_LOCAL), sin esperar 30 min reales.

Requisitos: acceso de red a TEST. Variables: BROKER_TOKEN (token de servicio del broker de TEST, DEV-06;
sin el /iot/* responde 401) y BASE_URL (opcional).

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G22 -v \
        --html=reporte-TC-M03-G22.html --self-contained-html
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30

# DEV-06: los endpoints /iot/* de dispositivo exigen el token de servicio del broker (Authorization: Bearer);
# se toma de BROKER_TOKEN y no se versiona. El serial del cuerpo es la identidad del nodo, no una credencial.
BROKER_TOKEN = os.getenv("BROKER_TOKEN", "")
_HEADERS_BROKER = {"Authorization": f"Bearer {BROKER_TOKEN}"}


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    """Nodo Edge minimo: captura, buffer persistido en archivo con checksum, sincronizacion y reinicio."""

    def __init__(self, device_id: int, sensor_id: int, access_key: str, archivo: Path) -> None:
        self.device_id = device_id
        self.sensor_id = sensor_id
        self.access_key = access_key
        self.archivo = archivo
        self.conectado = True
        self.buffer: list[dict] = []
        self.ultimo_indice_enviado = 0
        self._siguiente_indice = 1

    # -- almacenamiento no volatil simulado
    @staticmethod
    def _checksum(registros: list[dict]) -> str:
        return hashlib.sha256(json.dumps(registros, sort_keys=True).encode()).hexdigest()

    def persistir(self) -> None:
        self.archivo.write_text(json.dumps({
            "registros": self.buffer,
            "checksum": self._checksum(self.buffer),
            "ultimo_indice_enviado": self.ultimo_indice_enviado,
            "siguiente_indice": self._siguiente_indice,
        }), encoding="utf-8")

    def reiniciar(self) -> None:
        """Reinicio inesperado: se pierde la memoria y se reconstruye desde el archivo."""
        self.buffer, self.ultimo_indice_enviado, self._siguiente_indice = [], 0, 1
        datos = json.loads(self.archivo.read_text(encoding="utf-8"))
        if self._checksum(datos["registros"]) != datos["checksum"]:
            raise RuntimeError("Buffer corrupto: checksum invalido")
        self.buffer = datos["registros"]
        self.ultimo_indice_enviado = datos["ultimo_indice_enviado"]
        self._siguiente_indice = datos["siguiente_indice"]

    # -- operacion
    def _lectura(self, ts: datetime, valor: float, origen: str) -> dict:
        return {
            "device_id": self.device_id, "sensor_id": self.sensor_id,
            "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": valor, "unidad": "°C",
            "timestamp_captura": ts.isoformat(), "origen": origen, "serial": self.access_key,
        }

    def capturar(self, ts: datetime, valor: float) -> Optional[requests.Response]:
        if self.conectado:
            return requests.post(f"{BASE_URL}/iot/telemetria", json=self._lectura(ts, valor, "TIEMPO_REAL"),
                                 headers=_HEADERS_BROKER, timeout=TIMEOUT)
        self.buffer.append({"indice": self._siguiente_indice, **self._lectura(ts, valor, "BUFFER_LOCAL")})
        self._siguiente_indice += 1
        self.persistir()
        return None

    def pendientes(self) -> list[dict]:
        return [r for r in self.buffer if r["indice"] > self.ultimo_indice_enviado]

    def heartbeat(self) -> requests.Response:
        return requests.post(
            f"{BASE_URL}/iot/heartbeat",
            json={
                # DEV-06: device_id y serial viajan en el cuerpo (antes headers X-Device-Id / X-Device-API-Key).
                "device_id": self.device_id,
                "serial": self.access_key,
                "tipo_mensaje": "HEARTBEAT",
                "estado_local_buffer": "A" if self.pendientes() else "I",
                "datos_pendientes_buffer": len(self.pendientes()),
                "fecha_registro": datetime.now(timezone.utc).isoformat(),
            },
            headers=_HEADERS_BROKER,
            timeout=TIMEOUT,
        )

    def sincronizar(self, desde_indice: Optional[int] = None, hasta_indice: Optional[int] = None,
                    persistir_indice: bool = True) -> requests.Response:
        desde = self.ultimo_indice_enviado if desde_indice is None else desde_indice
        lote = [r for r in self.buffer if desde < r["indice"] <= (hasta_indice or 10**9)]
        r = requests.post(
            f"{BASE_URL}/iot/telemetria/batch",
            json={"registros": [{k: v for k, v in x.items() if k != "indice"} for x in lote]},
            headers=_HEADERS_BROKER,
            timeout=TIMEOUT,
        )
        if r.status_code == 200 and persistir_indice and lote:
            self.ultimo_indice_enviado = lote[-1]["indice"]
            self.persistir()
        return r


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


def _crear(s: requests.Session, ruta: str, cuerpo: dict, campo: str):
    r = s.post(f"{BASE_URL}{ruta}", json=cuerpo, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion {ruta}: HTTP {r.status_code} {r.text}"
    return r.json()[campo]


@pytest.fixture(scope="module")
def area(admin) -> int:
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Buffer Edge {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Buffer Edge {suf}", "descripcion": "Especie de prueba TC-M03-G22",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Buffer Edge {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo(admin, area, tmp_path, etiqueta) -> _NodoEdgeSimulado:
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G22-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G22",
        "id_infraestructura": area, "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensor_id = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                       {"nombre": f"Sensor {etiqueta} {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    return _NodoEdgeSimulado(device_id, sensor_id, serial, tmp_path / f"buffer_{etiqueta}.json")


def _historial(admin, sensor_id: int) -> list[dict]:
    hoy = datetime.now(timezone.utc).date()
    r = admin.get(f"{BASE_URL}/iot/monitoreo/historial", params={
        "fecha_inicio": str(hoy - timedelta(days=1)), "fecha_fin": str(hoy + timedelta(days=1)),
        "sensor_id": sensor_id, "por_pagina": 500, "orden": "ASC"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Historial: HTTP {r.status_code} {r.text}"
    return r.json()["items"]


def _estado(admin, device_id: int) -> str:
    r = admin.get(f"{BASE_URL}/iot/dispositivos/{device_id}/estado", timeout=TIMEOUT)
    assert r.status_code == 200, f"Estado del dispositivo: HTTP {r.status_code} {r.text}"
    return r.json()["estado"]["estado_actual"]


# --------------------------------------------------------------------------- TC-M03-035
@pytest.fixture(scope="module")
def corrida_035(admin, area, tmp_path_factory):
    nodo = _nodo(admin, area, tmp_path_factory.mktemp("g22_035"), "035")
    inicio = datetime.now(timezone.utc) - timedelta(minutes=40)

    assert nodo.heartbeat().status_code == 200, "Heartbeat inicial"
    en_linea = [nodo.capturar(inicio + timedelta(minutes=i), 24.0) for i in range(3)]

    nodo.conectado = False  # se corta la conectividad 30 min
    for i in range(30):
        nodo.capturar(inicio + timedelta(minutes=3 + i), 24.0 + i * 0.1)

    nodo.conectado = True  # vuelve la conectividad
    hb_pendientes = nodo.heartbeat()
    estado_con_buffer = _estado(admin, nodo.device_id)
    sync = nodo.sincronizar()
    hb_vacio = nodo.heartbeat()
    estado_final = _estado(admin, nodo.device_id)
    return {"nodo": nodo, "en_linea": en_linea, "hb_pendientes": hb_pendientes, "estado_con_buffer": estado_con_buffer,
            "sync": sync, "hb_vacio": hb_vacio, "estado_final": estado_final, "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_035_lecturas_en_linea_aceptadas(corrida_035):
    assert [r.status_code for r in corrida_035["en_linea"]] == [201, 201, 201]


def test_tc_m03_035_backend_registra_buffer_activo_al_reconectar(corrida_035):
    assert corrida_035["hb_pendientes"].status_code == 200
    assert corrida_035["estado_con_buffer"] == "BUFFER_ACTIVO", (
        f"Con 30 lecturas pendientes el dispositivo deberia estar BUFFER_ACTIVO, esta {corrida_035['estado_con_buffer']}"
    )


def test_tc_m03_035_sincroniza_el_100_por_ciento_sin_perdidas(corrida_035):
    r = corrida_035["sync"]
    assert r.status_code == 200, f"Sincronizacion: HTTP {r.status_code} {r.text}"
    cuerpo = r.json()
    assert (cuerpo["total"], cuerpo["aceptados"], cuerpo["rechazados"], cuerpo["duplicados"]) == (30, 30, 0, 0), cuerpo

    buffer = [x for x in corrida_035["historial"] if x["origen_dato"] == "BUFFER_LOCAL"]
    assert len(buffer) == 30, f"Se esperaban 30 lecturas BUFFER_LOCAL persistidas, hay {len(buffer)}"
    capturas = [x["timestamp_captura"] for x in buffer]
    assert capturas == sorted(capturas, key=lambda t: datetime.fromisoformat(t.replace("Z", "+00:00")))
    assert len(corrida_035["historial"]) == 33, "3 lecturas en linea + 30 del buffer, sin duplicados"


def test_tc_m03_035_buffer_vacio_y_dispositivo_activo_tras_sincronizar(corrida_035):
    assert corrida_035["hb_vacio"].status_code == 200
    assert corrida_035["estado_final"] == "ACTIVO"


def test_tc_m03_035_estado_buffer_pendiente_en_el_nodo():
    pytest.skip("estado_buffer=PENDIENTE es interno del nodo Edge: requiere el nodo o el simulador del equipo de IoT")


# --------------------------------------------------------------------------- TC-M03-036
@pytest.fixture(scope="module")
def corrida_036(admin, area, tmp_path_factory):
    nodo = _nodo(admin, area, tmp_path_factory.mktemp("g22_036"), "036")
    inicio = datetime.now(timezone.utc) - timedelta(hours=2)
    assert nodo.heartbeat().status_code == 200, "Heartbeat inicial"

    nodo.conectado = False
    for i in range(20):
        nodo.capturar(inicio + timedelta(minutes=i), 22.0 + i * 0.1)
    nodo.conectado = True

    # Se envian las 10 primeras y el indice queda persistido en 10.
    sync_parcial = nodo.sincronizar(hasta_indice=10)
    # Se envian las 5 siguientes pero el nodo se reinicia ANTES de persistir el nuevo indice.
    sync_sin_confirmar = nodo.sincronizar(hasta_indice=15, persistir_indice=False)
    pendientes_antes = [x["indice"] for x in nodo.pendientes()]

    nodo.reiniciar()  # reinicio inesperado
    pendientes_despues = [x["indice"] for x in nodo.pendientes()]
    sync_reanudada = nodo.sincronizar()  # reenvia 11..20: 11..15 ya estaban en el backend
    return {"nodo": nodo, "sync_parcial": sync_parcial, "sync_sin_confirmar": sync_sin_confirmar,
            "pendientes_antes": pendientes_antes, "pendientes_despues": pendientes_despues,
            "sync_reanudada": sync_reanudada, "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_036_pendientes_coinciden_antes_y_despues_del_reinicio(corrida_036):
    # Guarda del driver: si el simulador no restaura su indice, el resto del caso no tiene sentido.
    assert corrida_036["pendientes_antes"] == corrida_036["pendientes_despues"] == list(range(11, 21))


def test_tc_m03_036_reenvio_tras_reinicio_sin_duplicar(corrida_036):
    assert corrida_036["sync_parcial"].json()["aceptados"] == 10
    assert corrida_036["sync_sin_confirmar"].json()["aceptados"] == 5
    r = corrida_036["sync_reanudada"]
    assert r.status_code == 200, f"Sincronizacion tras el reinicio: HTTP {r.status_code} {r.text}"
    cuerpo = r.json()
    assert cuerpo["duplicados"] == 5, f"Las 5 lecturas ya enviadas antes del reinicio deben detectarse como duplicadas: {cuerpo}"
    assert cuerpo["aceptados"] == 5 and cuerpo["rechazados"] == 0, cuerpo


def test_tc_m03_036_sin_perdida_ni_duplicacion_en_el_backend(corrida_036):
    historial = corrida_036["historial"]
    assert len(historial) == 20, f"Se esperaban exactamente 20 lecturas, hay {len(historial)}"
    assert len({x["timestamp_captura"] for x in historial}) == 20, "Hay timestamps repetidos (duplicados)"


def test_tc_m03_036_reconstruccion_desde_memoria_no_volatil_y_checksum_en_el_nodo():
    pytest.skip("La reconstruccion desde flash/SD/EEPROM y la validacion de checksum son del firmware del nodo Edge: "
                "requieren el nodo o el simulador del equipo de IoT")
