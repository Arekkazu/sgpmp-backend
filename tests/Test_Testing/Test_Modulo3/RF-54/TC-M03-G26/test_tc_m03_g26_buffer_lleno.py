# | Fecha      | Nombre      | Que se hizo                                                                  |
# |------------|-------------|------------------------------------------------------------------------------|
# | 2026-10-26 | Juan Manuel | M03 RF-54: asociar/calibrar sensores y fecha_fin=hoy (DB-10)                 |
"""
TC-M03-G26 - Comportamiento del buffer al alcanzar capacidad critica: politicas de rechazo, sobrescritura
y priorizacion de eventos Edge.

RF relacionado: RF-54 (CU01). Casos: TC-M03-043 (CA-10), TC-M03-044 y TC-M03-056 (flujo alterno E7).

Criterios de la ficha:
    TC-M03-043: con POLITICA_RECHAZO y el buffer lleno, los nuevos datos se descartan, se emite
    BUFFER_OVERFLOW y la bitacora local registra timestamp, % de ocupacion y el nombre literal de la politica;
    los datos previos quedan intactos.
    TC-M03-044: con POLITICA_SOBRESCRITURA se reemplazan los mas antiguos o de menor criticidad (segun
    categoria_variable), con BUFFER_OVERFLOW y la politica en la bitacora local.
    TC-M03-056: bajo presion, agregacion en Edge y prioridad de EVENTO_EDGE sobre CRUDO.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el
DRIVER. Casi todo el caso ocurre dentro del nodo (que descartar, que sobrescribir, que priorizar,
BUFFER_OVERFLOW, bitacora local): eso queda en SKIP. Lo verificable en el backend real es:
- Configuracion de la politica: la ficha dice "configurar POLITICA_RECHAZO / POLITICA_SOBRESCRITURA". El
  canal de configuracion del nodo desde el sistema es RF-23 (POST /configuracion/dispositivos-iot/{id}/configurar);
  se comprueba si acepta y conserva la politica. (modulo3.buffers, que tenia el enum
  POLITICA_RECHAZO/POLITICA_SOBRESCRITURA, se retiro en DB-03: el buffer vive en el Edge.)
- Buffer lleno visto por el backend: heartbeat con estado_local_buffer='L' (lleno). El dispositivo no
  deberia quedar como un ACTIVO normal y el administrador deberia enterarse (alerta tecnica).
- Integridad al sincronizar: lo que el nodo conservo llega completo e inalterado (historial RF-59).
- 056: los EVENTO_EDGE guardados en el buffer se aceptan al sincronizar (POST /iot/eventos-edge con
  origen BUFFER_LOCAL) y los datos agregados en Edge se guardan como EDGE_AGREGADO.

Requisitos: acceso de red a TEST. Variables: BROKER_TOKEN (token de servicio del broker de TEST, DEV-06;
sin el /iot/* responde 401) y BASE_URL (opcional).

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G26 -v \
        --html=reporte-TC-M03-G26.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30

# DEV-06: los endpoints /iot/* de dispositivo exigen el token de servicio del broker (Authorization: Bearer);
# se toma de BROKER_TOKEN y no se versiona. El serial del cuerpo es la identidad del nodo, no una credencial.
BROKER_TOKEN = os.getenv("BROKER_TOKEN", "")
_HEADERS_BROKER = {"Authorization": f"Bearer {BROKER_TOKEN}"}
CAPACIDAD = 20


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    """Buffer de capacidad fija con politica configurable (solo para conducir la prueba)."""

    def __init__(self, device_id: int, access_key: str, politica: str) -> None:
        self.device_id, self.access_key, self.politica = device_id, access_key, politica
        self.buffer: list[dict] = []

    def capturar_offline(self, sensor_id: int, tipo: str, unidad: str, valor, ts: datetime) -> None:
        registro = {"device_id": self.device_id, "sensor_id": sensor_id, "tipo_variable": tipo, "valor": valor,
                    "unidad": unidad, "timestamp_captura": ts.isoformat(), "origen": "BUFFER_LOCAL",
                    "serial": self.access_key}
        if len(self.buffer) < CAPACIDAD:
            self.buffer.append(registro)
        elif self.politica == "POLITICA_SOBRESCRITURA":
            self.buffer.pop(0)  # reemplaza el mas antiguo
            self.buffer.append(registro)
        # POLITICA_RECHAZO: el nuevo dato se descarta

    def heartbeat(self) -> requests.Response:
        return requests.post(
            f"{BASE_URL}/iot/heartbeat",
            json={
                "device_id": self.device_id, "serial": self.access_key, "tipo_mensaje": "HEARTBEAT", "estado_local_buffer": "L" if len(self.buffer) >= CAPACIDAD else "A",
                  "datos_pendientes_buffer": len(self.buffer), "fecha_registro": datetime.now(timezone.utc).isoformat()},
            headers=_HEADERS_BROKER, timeout=TIMEOUT,
        )

    def sincronizar(self) -> requests.Response:
        return requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": self.buffer}, headers=_HEADERS_BROKER, timeout=TIMEOUT)


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
        "nombre": f"Finca Buffer Lleno {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Buffer Lleno {suf}", "descripcion": "Especie de prueba TC-M03-G26",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Buffer Lleno {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _dispositivo(admin, area, etiqueta, categorias):
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G26-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G26",
        "id_infraestructura": area, "id_tipo_dispositivo": 1, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensores = [_crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                       {"nombre": f"Sensor {etiqueta} {i + 1} {suf}", "categoria": c}, "id_sensores")
                for i, c in enumerate(categorias)]
    return device_id, serial, sensores


def _historial(admin, sensor_id: int) -> list[dict]:
    hoy = datetime.now(timezone.utc).date()
    r = admin.get(f"{BASE_URL}/iot/monitoreo/historial", params={
        "fecha_inicio": str(hoy - timedelta(days=1)), "fecha_fin": str(hoy),
        "sensor_id": sensor_id, "por_pagina": 500, "orden": "ASC"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Historial: HTTP {r.status_code} {r.text}"
    return r.json()["items"]


def _estado(admin, device_id: int) -> str:
    r = admin.get(f"{BASE_URL}/iot/dispositivos/{device_id}/estado", timeout=TIMEOUT)
    assert r.status_code == 200, f"Estado del dispositivo: HTTP {r.status_code} {r.text}"
    return r.json()["estado"]["estado_actual"]


def _alertas_tecnicas(admin, device_id: int, desde: datetime) -> list[dict]:
    r = admin.get(f"{BASE_URL}/iot/alertas-tecnicas", params={
        "fecha_desde": desde.isoformat(), "fecha_hasta": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "por_pagina": 200}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Alertas tecnicas: HTTP {r.status_code} {r.text}"
    return [a for a in r.json()["items"] if a.get("id_dispositivo_ioit") == device_id]


# --------------------------------------------------------------------------- configuracion de la politica (043 / 044)
@pytest.mark.parametrize("politica", ["POLITICA_RECHAZO", "POLITICA_SOBRESCRITURA"])
def test_tc_m03_043_044_la_politica_de_buffer_lleno_se_configura_desde_el_sistema(politica, admin, area):
    device_id, _, _ = _dispositivo(admin, area, politica[9:12], ["TEMPERATURA"])
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot/{device_id}/configurar",
                   json={"frecuencia_captura": 15, "politica_buffer": politica}, timeout=TIMEOUT)
    assert r.status_code in (200, 201, 202), f"Configuracion remota (RF-23): HTTP {r.status_code} {r.text}"
    configuraciones = admin.get(f"{BASE_URL}/configuracion/dispositivos-iot/{device_id}/configuraciones", timeout=TIMEOUT)
    assert configuraciones.status_code == 200, configuraciones.text
    assert politica in r.text or politica in configuraciones.text, (
        f"La configuracion remota no acepta ni conserva la politica {politica} (RF-23 solo admite "
        "frecuencia_captura, intervalo_transmision y fps)"
    )


# --------------------------------------------------------------------------- TC-M03-043
@pytest.fixture(scope="module")
def corrida_043(admin, area):
    device_id, serial, (sensor,) = _dispositivo(admin, area, "043", ["TEMPERATURA"])
    nodo = _NodoEdgeSimulado(device_id, serial, "POLITICA_RECHAZO")
    desde = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert nodo.heartbeat().status_code == 200, "Heartbeat inicial"
    inicio = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(CAPACIDAD + 10):  # 10 lecturas mas de las que caben
        nodo.capturar_offline(sensor, "TEMPERATURA_AMBIENTAL", "°C", round(20 + i * 0.1, 1), inicio + timedelta(minutes=i))
    conservados = [dict(x) for x in nodo.buffer]
    hb_lleno = nodo.heartbeat()
    estado_lleno = _estado(admin, device_id)
    alertas = _alertas_tecnicas(admin, device_id, desde)
    sync = nodo.sincronizar()
    return {"sensor": sensor, "conservados": conservados, "hb_lleno": hb_lleno, "estado_lleno": estado_lleno,
            "alertas": alertas, "sync": sync, "historial": _historial(admin, sensor)}


def test_tc_m03_043_backend_reconoce_el_buffer_lleno(corrida_043):
    assert corrida_043["hb_lleno"].status_code == 200
    assert corrida_043["estado_lleno"] != "ACTIVO", (
        "Con el buffer lleno (heartbeat 'L') el dispositivo queda como ACTIVO, igual que uno sin buffer"
    )


def test_tc_m03_043_el_administrador_se_entera_del_desborde(corrida_043):
    assert corrida_043["alertas"], "Ninguna alerta tecnica del dispositivo con el buffer lleno"


def test_tc_m03_043_los_datos_previos_llegan_intactos(corrida_043):
    r = corrida_043["sync"]
    assert r.status_code == 200 and r.json()["aceptados"] == CAPACIDAD, r.text
    persistidos = {(_ts(x["timestamp_captura"]), Decimal(str(x["valor"]))) for x in corrida_043["historial"]}
    esperados = {(_ts(x["timestamp_captura"]), Decimal(str(x["valor"]))) for x in corrida_043["conservados"]}
    assert persistidos == esperados


def test_tc_m03_043_descarte_buffer_overflow_y_bitacora_local_en_el_nodo():
    pytest.skip("El descarte, el evento BUFFER_OVERFLOW y la bitacora local (timestamp, % ocupacion, politica literal) "
                "son internos del nodo Edge: requieren el nodo o el simulador del equipo de IoT")


# --------------------------------------------------------------------------- TC-M03-044
@pytest.fixture(scope="module")
def corrida_044(admin, area):
    device_id, serial, sensores = _dispositivo(admin, area, "044", ["TEMPERATURA", "PH", None])
    nodo = _NodoEdgeSimulado(device_id, serial, "POLITICA_SOBRESCRITURA")
    series = [(sensores[0], "TEMPERATURA_AMBIENTAL", "°C", 20.0), (sensores[1], "PH_AGUA", "pH", 7.0),
              (sensores[2], "FRECUENCIA_CARDIACA", "bpm", 70)]
    inicio = datetime.now(timezone.utc) - timedelta(hours=3)
    for i in range(CAPACIDAD + 12):
        sensor, tipo, unidad, base = series[i % 3]
        nodo.capturar_offline(sensor, tipo, unidad, base + i / 10, inicio + timedelta(minutes=i))
    conservados = [dict(x) for x in nodo.buffer]
    sync = nodo.sincronizar()
    historial = [x for s in sensores for x in _historial(admin, s)]
    return {"conservados": conservados, "sync": sync, "historial": historial}


def test_tc_m03_044_lo_conservado_tras_sobrescribir_llega_completo(corrida_044):
    r = corrida_044["sync"]
    assert r.status_code == 200 and r.json()["aceptados"] == CAPACIDAD, r.text
    persistidos = sorted(_ts(x["timestamp_captura"]) for x in corrida_044["historial"])
    esperados = sorted(_ts(x["timestamp_captura"]) for x in corrida_044["conservados"])
    assert persistidos == esperados


def test_tc_m03_044_criterio_de_sobrescritura_y_bitacora_local_en_el_nodo():
    pytest.skip("Que se reemplacen los mas antiguos o los de menor criticidad (categoria_variable), BUFFER_OVERFLOW y la "
                "politica en la bitacora local son internos del nodo Edge: requieren el nodo o el simulador de IoT")


# --------------------------------------------------------------------------- TC-M03-056
@pytest.fixture(scope="module")
def corrida_056(admin, area):
    device_id, serial, (sensor,) = _dispositivo(admin, area, "056", ["TEMPERATURA"])
    inicio = datetime.now(timezone.utc) - timedelta(hours=4)
    # El nodo, bajo presion, guardo: 6 promedios de ventana de 5 min (EDGE_AGREGADO) y 2 EVENTO_EDGE.
    agregados = [{
        "device_id": device_id, "sensor_id": sensor, "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 24.0 + i / 10,
        "unidad": "°C", "timestamp_captura": (inicio + timedelta(minutes=5 * i)).isoformat(), "origen": "EDGE_AGREGADO",
        "valor_agregado": True, "ventana_agregacion": 5, "serial": serial,
    } for i in range(6)]
    sync = requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": agregados}, headers=_HEADERS_BROKER, timeout=TIMEOUT)
    eventos = []
    for i in range(2):
        ts = inicio + timedelta(minutes=7 + i * 10)
        eventos.append(requests.post(f"{BASE_URL}/iot/eventos-edge", json={
            "device_id": device_id, "sensor_id": sensor, "serial": serial,
            "clasificacion_rf55": "DESVIACION_SIMPLE", "severidad": "MODERADO",
            "variables_involucradas": [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 34.5, "unidad": "°C",
                                        "timestamp_captura": ts.isoformat()}],
            "timestamp_captura": ts.isoformat(), "timestamp_procesamiento_edge": (ts + timedelta(seconds=2)).isoformat(),
            "origen": "BUFFER_LOCAL", "estado_conectividad": False,
        }, headers=_HEADERS_BROKER, timeout=TIMEOUT))
    return {"sync": sync, "eventos": eventos, "historial": _historial(admin, sensor)}


def test_tc_m03_056_los_evento_edge_del_buffer_se_aceptan_al_sincronizar(corrida_056):
    for i, r in enumerate(corrida_056["eventos"], start=1):
        assert r.status_code == 201, f"EVENTO_EDGE {i} (origen BUFFER_LOCAL): HTTP {r.status_code} {r.text}"


def test_tc_m03_056_los_datos_agregados_en_edge_se_guardan_como_tales(corrida_056):
    r = corrida_056["sync"]
    assert r.status_code == 200 and r.json()["aceptados"] == 6, r.text
    agregados = [x for x in corrida_056["historial"] if x["origen_dato"] == "EDGE_AGREGADO"]
    assert len(agregados) == 6


def test_tc_m03_056_activacion_de_agregacion_y_prioridad_evento_edge_en_el_nodo():
    pytest.skip("Activar la agregacion bajo presion y priorizar EVENTO_EDGE sobre CRUDO al guardar en el buffer es "
                "interno del nodo Edge (la ficha pide confirmar si esta en el MVP): requiere el nodo o el simulador de IoT")
