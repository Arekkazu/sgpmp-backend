"""
TC-M03-G28 - Continuidad operativa durante indisponibilidad prolongada del backend: 72 h y reanudacion completa.

RF relacionado: RF-54 (CU01). Casos: TC-M03-046 (CA-9) y TC-M03-055 (flujo alterno E8).

Criterios de la ficha:
    TC-M03-046: 72 h sin conectividad con todas las variables activas a sus frecuencias: el buffer guarda todo
    el periodo sin perdida y sin aplicar la politica de buffer lleno antes de las 72 h.
    TC-M03-055: con el backend caido varias horas el nodo sigue capturando en modo offline, monitorea la
    disponibilidad, aplica la politica de retencion y genera BACKEND_UNAVAILABLE; al volver el servicio
    sincroniza todo lo pendiente.

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el DRIVER;
el tiempo se acelera (los datos se generan con timestamps del periodo, sin esperar horas reales). Se verifica
en el backend real:
- 046: el volumen completo de 72 h (6 variables, ~3.200 lecturas) se acepta al reconectar, en lotes de hasta
  500 (limite de POST /iot/telemetria/batch), sin perdida, y lo mas antiguo del periodo no se rechaza por
  antiguedad. RIESGO detectado en el codigo: la ingesta rechaza BUFFER_LOCAL con mas de 72 h al momento de
  procesar (ERROR_TIEMPO); si el nodo reconecta justo al cumplirse las 72 h, lo primero del buffer llega
  vencido. Por eso el periodo arranca MARGEN_MIN minutos dentro de la ventana; con MARGEN_MIN=0 se prueba el
  borde exacto.
- 055: "backend caido" se simula desde el nodo con una URL inalcanzable (no se apaga el TEST compartido).
  Durante la caida el nodo monitorea en cada intervalo sin exito; al restablecerse, el heartbeat lleva al
  dispositivo a BUFFER_ACTIVO, se sincroniza todo y vuelve a ACTIVO, con todo lo pendiente persistido.
- Interno del nodo (SKIP): no aplicar la politica de buffer lleno antes de 72 h, la politica de retencion y
  el evento BACKEND_UNAVAILABLE.

Carga: 046 envia ~3.200 lecturas a TEST; coordinar el horario con el equipo.

Requisitos: acceso de red a TEST y BROKER_TOKEN (token de servicio del broker de TEST, DEV-06; sin el
/iot/* responde 401). Variables opcionales: BASE_URL, MARGEN_MIN, TIMEOUT_LOTE.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G28 -v \
        --html=reporte-TC-M03-G28.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
URL_CAIDA = "http://127.0.0.1:9"  # backend inalcanzable desde el punto de vista del nodo
MARGEN_MIN = int(os.getenv("MARGEN_MIN", "2"))
TIMEOUT = 60

# DEV-06: los endpoints /iot/* de dispositivo exigen el token de servicio del broker (Authorization: Bearer);
# se toma de BROKER_TOKEN y no se versiona. El serial del cuerpo es la identidad del nodo, no una credencial.
BROKER_TOKEN = os.getenv("BROKER_TOKEN", "")
_HEADERS_BROKER = {"Authorization": f"Bearer {BROKER_TOKEN}"}
LOTE_MAX = 500
# Un lote de 500 pasa registro por registro por todo el pipeline de ingesta (vinculacion, calidad): margen amplio.
TIMEOUT_LOTE = int(os.getenv("TIMEOUT_LOTE", "600"))

# (categoria del sensor, tipo_variable, unidad, minutos entre muestras, valor base)
VARIABLES = [
    ("TEMPERATURA", "TEMPERATURA_AMBIENTAL", "°C", 5, 22.0),
    ("HUMEDAD", "HUMEDAD_RELATIVA", "%", 10, 65.0),
    ("PH", "PH_AGUA", "pH", 15, 7.1),
    ("OXIGENO", "OXIGENO_DISUELTO", "mg/L", 15, 6.5),
    (None, "FRECUENCIA_CARDIACA", "bpm", 5, 75),
    (None, "FRECUENCIA_RESPIRATORIA", "rpm", 10, 20),
]


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    def __init__(self, device_id: int, access_key: str) -> None:
        self.device_id, self.access_key = device_id, access_key
        self.url = BASE_URL
        self.buffer: list[dict] = []
        self.monitoreos: list[bool] = []

    def capturar_offline(self, sensor_id, tipo, unidad, valor, ts: datetime) -> None:
        self.buffer.append({"device_id": self.device_id, "sensor_id": sensor_id, "tipo_variable": tipo, "valor": valor,
                            "unidad": unidad, "timestamp_captura": ts.isoformat(), "origen": "BUFFER_LOCAL",
                            "serial": self.access_key})

    def monitorear(self) -> bool:
        """Un intervalo de monitoreo de disponibilidad: heartbeat al backend configurado."""
        try:
            r = requests.post(
                f"{self.url}/iot/heartbeat",
                json={
                "device_id": self.device_id, "serial": self.access_key, "tipo_mensaje": "HEARTBEAT", "estado_local_buffer": "A" if self.buffer else "I",
                      "datos_pendientes_buffer": len(self.buffer), "fecha_registro": datetime.now(timezone.utc).isoformat()},
                headers=_HEADERS_BROKER, timeout=5,
            )
            ok = r.status_code == 200
        except requests.exceptions.RequestException:
            ok = False
        self.monitoreos.append(ok)
        return ok

    def sincronizar_todo(self) -> list[requests.Response]:
        respuestas = []
        cola = sorted(self.buffer, key=lambda r: r["timestamp_captura"])
        for i in range(0, len(cola), LOTE_MAX):
            respuestas.append(requests.post(f"{self.url}/iot/telemetria/batch",
                                            json={"registros": cola[i:i + LOTE_MAX]}, headers=_HEADERS_BROKER, timeout=TIMEOUT_LOTE))
        if all(r.status_code == 200 for r in respuestas):
            self.buffer = []
        return respuestas


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
        "nombre": f"Finca Setenta Horas {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Setenta Horas {suf}", "descripcion": "Especie de prueba TC-M03-G28",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Setenta Horas {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo(admin, area, etiqueta, variables):
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G28-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G28",
        "id_infraestructura": area, "id_tipo_dispositivo": 1, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    nodo = _NodoEdgeSimulado(r.json()["id_dispositivo_iot"], r.json()["serial"])
    sensores = [_crear(admin, f"/configuracion/dispositivos-iot/{nodo.device_id}/sensores",
                       {"nombre": f"Sensor {v[1]} {suf}", "categoria": v[0]}, "id_sensores") for v in variables]
    return nodo, sensores


def _contar(admin, sensor_id: int, desde: datetime) -> int:
    r = admin.get(f"{BASE_URL}/iot/monitoreo/historial", params={
        "fecha_inicio": str((desde - timedelta(days=1)).date()),
        "fecha_fin": str((datetime.now(timezone.utc) + timedelta(days=1)).date()),
        "sensor_id": sensor_id, "por_pagina": 1}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Historial: HTTP {r.status_code} {r.text}"
    return r.json()["total"]


def _estado(admin, device_id: int) -> str:
    r = admin.get(f"{BASE_URL}/iot/dispositivos/{device_id}/estado", timeout=TIMEOUT)
    assert r.status_code == 200, f"Estado del dispositivo: HTTP {r.status_code} {r.text}"
    return r.json()["estado"]["estado_actual"]


# --------------------------------------------------------------------------- TC-M03-046
@pytest.fixture(scope="module")
def corrida_046(admin, area):
    nodo, sensores = _nodo(admin, area, "046", VARIABLES)
    fin = datetime.now(timezone.utc)
    inicio = fin - timedelta(hours=72) + timedelta(minutes=MARGEN_MIN)
    esperado = {}
    for sensor_id, (_, tipo, unidad, cada, base) in zip(sensores, VARIABLES):
        n, t = 0, inicio
        while t < fin:
            nodo.capturar_offline(sensor_id, tipo, unidad, round(base + (n % 10) / 10, 2), t)
            n += 1
            t += timedelta(minutes=cada)
        esperado[sensor_id] = n
    total = len(nodo.buffer)
    respuestas = nodo.sincronizar_todo()
    obtenido = {s: _contar(admin, s, inicio) for s in sensores}
    return {"total": total, "esperado": esperado, "respuestas": respuestas, "obtenido": obtenido}


def test_tc_m03_046_el_volumen_de_72_horas_se_acepta_completo(corrida_046):
    rechazos = []
    for i, r in enumerate(corrida_046["respuestas"], start=1):
        assert r.status_code == 200, f"Lote {i}: HTTP {r.status_code} {r.text[:300]}"
        cuerpo = r.json()
        if cuerpo["rechazados"] or cuerpo["duplicados"]:
            motivos = {d["error"][:80] for d in cuerpo["detalle"] if d.get("error")}
            rechazos.append((i, cuerpo["rechazados"], cuerpo["duplicados"], motivos))
    assert not rechazos, f"Lotes con rechazos/duplicados (lote, rechazados, duplicados, motivos): {rechazos}"
    assert sum(r.json()["aceptados"] for r in corrida_046["respuestas"]) == corrida_046["total"]


def test_tc_m03_046_sin_perdida_por_variable(corrida_046):
    assert corrida_046["obtenido"] == corrida_046["esperado"], (
        f"Lecturas por sensor: esperado {corrida_046['esperado']}, obtenido {corrida_046['obtenido']}"
    )


def test_tc_m03_046_sin_politica_de_buffer_lleno_antes_de_72_horas_en_el_nodo():
    pytest.skip("Que el nodo no aplique la politica de buffer lleno antes de 72 h depende de su almacenamiento real: "
                "requiere el nodo o el simulador del equipo de IoT")


# --------------------------------------------------------------------------- TC-M03-055
@pytest.fixture(scope="module")
def corrida_055(admin, area):
    nodo, sensores = _nodo(admin, area, "055", VARIABLES[:2])
    assert nodo.monitorear(), "Heartbeat inicial con el backend disponible"

    nodo.url = URL_CAIDA  # el servicio de ingesta deja de estar disponible
    inicio = datetime.now(timezone.utc) - timedelta(hours=6)
    for hora in range(6):  # 6 horas de caida (aceleradas): captura continua + un monitoreo por hora
        for minuto in range(0, 60, 5):
            t = inicio + timedelta(hours=hora, minutes=minuto)
            nodo.capturar_offline(sensores[0], "TEMPERATURA_AMBIENTAL", "°C", 22.0, t)
            if minuto % 10 == 0:
                nodo.capturar_offline(sensores[1], "HUMEDAD_RELATIVA", "%", 65.0, t)
        nodo.monitorear()
    pendientes = len(nodo.buffer)
    monitoreos_en_caida = list(nodo.monitoreos[1:])

    nodo.url = BASE_URL  # el servicio vuelve
    reconectado = nodo.monitorear()
    estado_con_buffer = _estado(admin, nodo.device_id)
    respuestas = nodo.sincronizar_todo()
    nodo.monitorear()
    return {"nodo": nodo, "pendientes": pendientes, "monitoreos_en_caida": monitoreos_en_caida,
            "reconectado": reconectado, "estado_con_buffer": estado_con_buffer, "respuestas": respuestas,
            "estado_final": _estado(admin, nodo.device_id),
            "persistidos": sum(_contar(admin, s, inicio) for s in sensores)}


def test_tc_m03_055_durante_la_caida_el_backend_no_responde_y_se_sigue_capturando(corrida_055):
    assert corrida_055["monitoreos_en_caida"] and not any(corrida_055["monitoreos_en_caida"])
    assert corrida_055["pendientes"] == 6 * (12 + 6)


def test_tc_m03_055_al_volver_el_servicio_se_detecta_el_buffer_y_se_sincroniza_todo(corrida_055):
    assert corrida_055["reconectado"], "El primer monitoreo tras restablecer el servicio no tuvo exito"
    assert corrida_055["estado_con_buffer"] == "BUFFER_ACTIVO"
    for i, r in enumerate(corrida_055["respuestas"], start=1):
        assert r.status_code == 200 and r.json()["rechazados"] == 0, f"Lote {i}: {r.text[:300]}"
    assert corrida_055["persistidos"] == corrida_055["pendientes"]
    assert corrida_055["nodo"].buffer == []
    assert corrida_055["estado_final"] == "ACTIVO"


def test_tc_m03_055_politica_de_retencion_y_backend_unavailable_en_el_nodo():
    pytest.skip("La politica de retencion y el evento BACKEND_UNAVAILABLE son internos del nodo Edge: requieren el nodo o "
                "el simulador del equipo de IoT")
