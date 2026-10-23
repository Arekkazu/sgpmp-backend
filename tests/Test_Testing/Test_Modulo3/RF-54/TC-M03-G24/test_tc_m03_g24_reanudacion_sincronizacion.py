"""
TC-M03-G24 - Inicio y reanudacion automatica de la sincronizacion ante cambios de conectividad.

RF relacionado: RF-54 (CU01). Casos: TC-M03-038 (CA-5) y TC-M03-041 (flujo alterno E4).

Criterios de la ficha:
    TC-M03-038: al restablecerse la conectividad (ACK exitoso) la sincronizacion arranca sola, sin accion
    manual, dentro del intervalo de monitoreo, y el buffer se drena hasta emitir BUFFER_DRAINED.
    TC-M03-041: un corte a mitad de lote detiene el envio de forma controlada, conserva el estado del lote y
    la sincronizacion se reanuda desde el ultimo checkpoint, sin duplicados ni perdida de orden.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, _NodoEdgeSimulado es el
DRIVER. Tiene un monitor de conectividad (un "tick" = un intervalo de monitoreo) que, si hay pendientes,
envia un heartbeat; si recibe ACK (200) dispara la sincronizacion por su cuenta. El test nunca llama a
sincronizar a mano en 038: solo cambia la conectividad y avanza el monitor.
Las aserciones son sobre el backend real: estado del dispositivo (RF-60: BUFFER_ACTIVO -> ACTIVO), respuesta
de POST /iot/telemetria/batch e historial RF-59.

- El corte de 041 se simula con un timeout de lectura minimo en el cliente: el nodo no recibe la respuesta y
  no avanza su checkpoint, aunque el servidor haya procesado parte o todo el lote (es justo el caso dificil).
  Se espera ESPERA_RECONEXION_SEG (60 s por defecto, como la ficha) antes de reanudar.
- BUFFER_DRAINED: el backend no tiene ese evento; lo observable es el heartbeat con buffer inactivo y 0
  pendientes, que devuelve el dispositivo a ACTIVO. La emision del evento en el nodo y la detencion
  "controlada" del envio son internas del firmware: SKIP.

Requisitos: acceso de red a TEST. Variables opcionales: BASE_URL, ESPERA_RECONEXION_SEG.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G24 -v \
        --html=reporte-TC-M03-G24.html --self-contained-html
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
# Espera entre el corte y la reconexion (la ficha dice 1 minuto); tambien deja terminar al servidor el lote cortado.
ESPERA_RECONEXION_SEG = float(os.getenv("ESPERA_RECONEXION_SEG", "60"))


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    def __init__(self, device_id: int, sensor_id: int, access_key: str) -> None:
        self.device_id, self.sensor_id, self.access_key = device_id, sensor_id, access_key
        self.conectado = True
        self.buffer: list[dict] = []
        self.checkpoint = 0  # ultimo indice confirmado por el backend
        self.sincronizaciones: list[dict] = []
        self.heartbeats: list[int] = []

    def capturar_offline(self, ts: datetime, valor: float) -> None:
        self.buffer.append({
            "indice": len(self.buffer) + 1, "device_id": self.device_id, "sensor_id": self.sensor_id,
            "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": valor, "unidad": "°C",
            "timestamp_captura": ts.isoformat(), "origen": "BUFFER_LOCAL", "access_key": self.access_key,
        })

    def pendientes(self) -> list[dict]:
        return [r for r in self.buffer if r["indice"] > self.checkpoint]

    def _heartbeat(self) -> int:
        pendientes = len(self.pendientes())
        r = requests.post(
            f"{BASE_URL}/iot/heartbeat",
            json={"tipo_mensaje": "HEARTBEAT", "estado_local_buffer": "A" if pendientes else "I",
                  "datos_pendientes_buffer": pendientes, "fecha_registro": datetime.now(timezone.utc).isoformat()},
            headers={"X-Device-Id": str(self.device_id), "X-Device-API-Key": self.access_key}, timeout=TIMEOUT,
        )
        self.heartbeats.append(r.status_code)
        return r.status_code

    def enviar_lote(self, lote: list[dict], timeout=TIMEOUT) -> dict:
        """Envia un lote; solo avanza el checkpoint si recibe la confirmacion del backend."""
        cuerpo = {"registros": [{k: v for k, v in x.items() if k != "indice"} for x in lote]}
        try:
            r = requests.post(f"{BASE_URL}/iot/telemetria/batch", json=cuerpo, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            resultado = {"confirmado": False, "error": type(exc).__name__}
        else:
            resultado = {"confirmado": r.status_code == 200, "status": r.status_code,
                         "cuerpo": r.json() if r.status_code == 200 else r.text}
            if resultado["confirmado"]:
                self.checkpoint = lote[-1]["indice"]
        self.sincronizaciones.append(resultado)
        return resultado

    def tick_monitor(self, tamano_lote: int = 10) -> None:
        """Un intervalo de monitoreo: si hay red y pendientes, ACK por heartbeat y sincroniza solo."""
        if not self.conectado:
            return
        if self._heartbeat() != 200:
            return
        while self.pendientes():
            if not self.enviar_lote(self.pendientes()[:tamano_lote])["confirmado"]:
                return
        self._heartbeat()  # buffer drenado: informa 'I' y 0 pendientes


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
        "nombre": f"Finca Reanudacion Buffer {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Reanudacion {suf}", "descripcion": "Especie de prueba TC-M03-G24",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Reanudacion {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo(admin, area, etiqueta) -> _NodoEdgeSimulado:
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G24-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G24",
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


def _estado(admin, device_id: int) -> str:
    r = admin.get(f"{BASE_URL}/iot/dispositivos/{device_id}/estado", timeout=TIMEOUT)
    assert r.status_code == 200, f"Estado del dispositivo: HTTP {r.status_code} {r.text}"
    return r.json()["estado"]["estado_actual"]


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# --------------------------------------------------------------------------- TC-M03-038
@pytest.fixture(scope="module")
def corrida_038(admin, area):
    nodo = _nodo(admin, area, "038")
    nodo.tick_monitor()  # en linea y sin pendientes: solo heartbeat (inicializa el estado RF-60)
    inicio = datetime.now(timezone.utc) - timedelta(hours=1)

    nodo.conectado = False
    for i in range(25):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 21.0 + i * 0.1)
    nodo.tick_monitor()  # sin red: el monitor no puede hacer nada
    sincronizaciones_sin_red = len(nodo.sincronizaciones)

    nodo.conectado = True  # vuelve la red; ninguna accion manual
    nodo.tick_monitor()    # primer intervalo de monitoreo tras la reconexion
    return {"nodo": nodo, "sin_red": sincronizaciones_sin_red, "estado": _estado(admin, nodo.device_id),
            "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_038_sin_red_no_se_intenta_sincronizar(corrida_038):
    assert corrida_038["sin_red"] == 0


def test_tc_m03_038_la_sincronizacion_arranca_sola_en_el_primer_intervalo(corrida_038):
    nodo = corrida_038["nodo"]
    assert nodo.heartbeats and all(c == 200 for c in nodo.heartbeats), f"ACK de heartbeat: {nodo.heartbeats}"
    assert nodo.sincronizaciones, "El monitor no disparo ninguna sincronizacion al reconectar"
    assert all(s["confirmado"] for s in nodo.sincronizaciones), nodo.sincronizaciones


def test_tc_m03_038_el_buffer_se_drena_completo(corrida_038):
    nodo = corrida_038["nodo"]
    assert nodo.pendientes() == []
    aceptados = sum(s["cuerpo"]["aceptados"] for s in nodo.sincronizaciones)
    assert aceptados == 25
    assert len(corrida_038["historial"]) == 25


def test_tc_m03_038_backend_ve_el_buffer_drenado(corrida_038):
    assert corrida_038["estado"] == "ACTIVO", (
        f"Tras drenar el buffer (heartbeat 'I', 0 pendientes) el dispositivo deberia estar ACTIVO: {corrida_038['estado']}"
    )


def test_tc_m03_038_evento_buffer_drained():
    pytest.skip("BUFFER_DRAINED lo emite el nodo y el backend no tiene ese evento: requiere el nodo o el simulador del "
                "equipo de IoT (en el backend se observa como heartbeat 'I' con 0 pendientes)")


# --------------------------------------------------------------------------- TC-M03-041
@pytest.fixture(scope="module")
def corrida_041(admin, area):
    nodo = _nodo(admin, area, "041")
    inicio = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(30):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 19.0 + i * 0.1)

    primer = nodo.enviar_lote(nodo.pendientes()[:10])   # lote 1 completo: checkpoint = 10
    checkpoint_antes_del_corte = nodo.checkpoint
    # Lote 2 (11..20): la red se cae mientras se transmite; el nodo no recibe la confirmacion.
    cortado = nodo.enviar_lote(nodo.pendientes()[:10], timeout=(5, 0.001))
    checkpoint_tras_el_corte = nodo.checkpoint
    time.sleep(ESPERA_RECONEXION_SEG)
    # Se restablece la red: se reanuda desde el checkpoint (11..30).
    reanudado = nodo.enviar_lote(nodo.pendientes())
    return {"nodo": nodo, "primer": primer, "cortado": cortado, "checkpoint_antes": checkpoint_antes_del_corte,
            "checkpoint_despues": checkpoint_tras_el_corte, "reanudado": reanudado,
            "historial": _historial(admin, nodo.sensor_id)}


def test_tc_m03_041_el_corte_no_avanza_el_checkpoint(corrida_041):
    assert corrida_041["primer"]["confirmado"]
    assert not corrida_041["cortado"]["confirmado"], "La simulacion del corte no interrumpio la respuesta"
    assert corrida_041["checkpoint_antes"] == corrida_041["checkpoint_despues"] == 10


def test_tc_m03_041_la_reanudacion_desde_el_checkpoint_no_duplica(corrida_041):
    r = corrida_041["reanudado"]
    assert r["confirmado"], f"Reanudacion: {r}"
    cuerpo = r["cuerpo"]
    # Lo que el backend alcanzo a guardar del lote cortado debe volver como duplicado, nunca como registro nuevo.
    assert cuerpo["total"] == 20 and cuerpo["rechazados"] == 0, cuerpo
    assert cuerpo["aceptados"] + cuerpo["duplicados"] == 20, cuerpo


def test_tc_m03_041_sin_perdida_ni_duplicados_y_en_orden(corrida_041):
    historial = corrida_041["historial"]
    capturas = [_ts(x["timestamp_captura"]) for x in historial]
    assert len(historial) == 30, f"Se esperaban 30 lecturas, hay {len(historial)}"
    assert len(set(capturas)) == 30, "Hay lecturas duplicadas"
    assert capturas == sorted(capturas)
    ids = [x["id_telemetria"] for x in historial]
    assert ids == sorted(ids), "El orden de insercion no sigue el orden cronologico"


def test_tc_m03_041_detencion_controlada_y_estado_del_lote_en_el_nodo():
    pytest.skip("Detener el envio de forma controlada y conservar el estado del lote en curso es interno del firmware "
                "del nodo Edge: requiere el nodo o el simulador del equipo de IoT")
