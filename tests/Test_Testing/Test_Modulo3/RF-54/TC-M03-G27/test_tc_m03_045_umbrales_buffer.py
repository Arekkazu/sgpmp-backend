# | Fecha      | Nombre      | Que se hizo                                                                     |
# |------------|-------------|---------------------------------------------------------------------------------|
# | 2026-10-29 | Juan Manuel | TC-M03-G27 RF-54: metricas_buffer (INC-M03-126) y BUFFER_CAPACITY_WARNING (INC-M03-129) |
"""
TC-M03-G27 (sub-caso 1) - Umbrales de ocupacion del buffer (WARNING / CRITICO).

RF relacionado: RF-54 (CU01). Caso: TC-M03-045 (valores limite).

Criterio de la ficha: 79% -> sin alerta; 80% -> BUFFER_CAPACITY_WARNING y estado WARNING; 95% -> CRITICO.
El umbral es configurable (confirmar el valor del ambiente antes de ejecutar; aqui 80% y 95%).

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el driver hace lo que
haria el broker con lo que publica el nodo (contrato en anotaciones/modulo_3 y repo BROKER-MQTT-SGPMP):
- heartbeat con metricas_buffer (INC-M03-126): capacidad_total 100 y capacidad_utilizada 79 / 80 / 95. El
  estado del buffer se lee en GET /iot/dispositivos/{id}/buffer: NORMAL (<80) / WARNING (>=80) / CRITICO (>=95).
- aviso de capacidad (INC-M03-129): el NODO emite BUFFER_CAPACITY_WARNING por sgpmp/<serial>/status al cruzar su
  umbral (80 %) y de nuevo al 95 %; el broker lo reenvia a POST /iot/eventos-buffer (no valida `evento`). Al 79 %
  el nodo no emite nada. Se espera una alerta tecnica LEVE al 80 % que escala a CRITICO (mismo id) al 95 %, y
  ninguna alerta al 79 %. El backend no convierte el porcentaje del heartbeat en alerta (por diseño).
Que el firmware emita el aviso al cruzar el umbral queda en SKIP (requiere el nodo).

Requisitos: acceso de red a TEST y BROKER_TOKEN (token de servicio del broker de TEST, DEV-06; sin el
/iot/* responde 401). Variables opcionales: BASE_URL, RUTA_ESTADO_BUFFER.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G27 -v \
        --html=reporte-TC-M03-G27.html --self-contained-html
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
RUTA_ESTADO_BUFFER = os.getenv("RUTA_ESTADO_BUFFER", "/iot/dispositivos/{id}/buffer")
TIMEOUT = 30

# DEV-06: los endpoints /iot/* de dispositivo exigen el token de servicio del broker (Authorization: Bearer);
# se toma de BROKER_TOKEN y no se versiona. El serial del cuerpo es la identidad del nodo, no una credencial.
BROKER_TOKEN = os.getenv("BROKER_TOKEN", "")
_HEADERS_BROKER = {"Authorization": f"Bearer {BROKER_TOKEN}"}
CAPACIDAD = 100
ESCALONES = [(79, "NORMAL", False), (80, "WARNING", True), (95, "CRITICO", True)]


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


def _heartbeat(device_id: int, access_key: str, pendientes: int) -> requests.Response:
    ahora = datetime.now(timezone.utc)
    return requests.post(
        f"{BASE_URL}/iot/heartbeat",
        json={
            "device_id": device_id, "serial": access_key, "tipo_mensaje": "HEARTBEAT", "estado_local_buffer": "A",
            "datos_pendientes_buffer": pendientes, "fecha_registro": ahora.isoformat(),
            "metricas_buffer": {"capacidad_total": CAPACIDAD, "capacidad_utilizada": pendientes,
                                "ultimo_timestamp_pendiente": (ahora - timedelta(minutes=1)).isoformat(),
                                "politica_buffer_activa": "POLITICA_RECHAZO"}},
        headers=_HEADERS_BROKER, timeout=TIMEOUT,
    )


def _aviso_capacidad(access_key: str, porcentaje: int) -> requests.Response:
    """Lo que el broker reenvia del EVENTO_BUFFER que el nodo publica en status (D10 ampliado, INC-M03-129)."""
    return requests.post(
        f"{BASE_URL}/iot/eventos-buffer",
        json={"serial": access_key, "evento": "BUFFER_CAPACITY_WARNING", "porcentaje_ocupacion": porcentaje,
              "politica_aplicada": None, "cantidad_datos_afectados": 0,
              "timestamp_evento": datetime.now(timezone.utc).isoformat()},
        headers=_HEADERS_BROKER, timeout=TIMEOUT,
    )


@pytest.fixture(scope="module")
def corrida(admin):
    suf = _sufijo()
    finca = _crear(admin, "/configuracion/fincas", {
        "nombre": f"Finca Umbral Buffer {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Umbral Buffer {suf}", "descripcion": "Especie de prueba TC-M03-045",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    area = _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Umbral Buffer {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-045-{suf}", "descripcion": "Nodo Edge TC-M03-045", "id_infraestructura": area,
        "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]

    desde = datetime.now(timezone.utc) - timedelta(seconds=5)
    resultados = {}
    for pendientes, _, emite_aviso in ESCALONES:
        hb = _heartbeat(device_id, serial, pendientes)
        aviso = _aviso_capacidad(serial, pendientes) if emite_aviso else None
        estado = admin.get(f"{BASE_URL}{RUTA_ESTADO_BUFFER.format(id=device_id)}", timeout=TIMEOUT)
        alertas = admin.get(f"{BASE_URL}/iot/alertas-tecnicas", params={
            "fecha_desde": desde.isoformat(), "fecha_hasta": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
            "por_pagina": 200}, timeout=TIMEOUT)
        del_dispositivo = [a for a in alertas.json().get("items", []) if a.get("id_dispositivo_ioit") == device_id
                           and a.get("tipo_variable") == "BUFFER_CAPACITY_WARNING"] \
            if alertas.status_code == 200 else None
        resultados[pendientes] = {"hb": hb, "aviso": aviso, "estado": estado, "alertas": del_dispositivo}
    return resultados


@pytest.mark.parametrize("pendientes,estado_esperado,_alerta", ESCALONES, ids=["79%", "80%", "95%"])
def test_tc_m03_045_estado_del_buffer_expuesto_segun_ocupacion(pendientes, estado_esperado, _alerta, corrida):
    paso = corrida[pendientes]
    assert paso["hb"].status_code == 200, f"Heartbeat al {pendientes}%: HTTP {paso['hb'].status_code} {paso['hb'].text}"
    r = paso["estado"]
    assert r.status_code == 200, (
        f"No hay consulta del estado del buffer ({RUTA_ESTADO_BUFFER}): HTTP {r.status_code}. Sin ella el estado "
        f"{estado_esperado} al {pendientes}% no es observable desde el sistema"
    )
    cuerpo = r.json().get("buffer", r.json())
    assert cuerpo.get("estado_buffer", "").replace("Í", "I") == estado_esperado, cuerpo


_SEVERIDAD = {79: None, 80: "LEVE", 95: "CRITICO"}


@pytest.mark.parametrize("pendientes,_estado,debe_alertar", ESCALONES, ids=["79%", "80%", "95%"])
def test_tc_m03_045_alerta_al_cruzar_el_umbral_de_advertencia(pendientes, _estado, debe_alertar, corrida):
    paso = corrida[pendientes]
    alertas = paso["alertas"]
    assert alertas is not None, "La consulta de alertas tecnicas fallo"
    if not debe_alertar:
        assert not alertas, f"Al {pendientes}% (bajo el umbral, sin aviso del nodo) no deberia haber alerta: {alertas}"
        return
    r = paso["aviso"]
    assert r.status_code == 201, f"Aviso BUFFER_CAPACITY_WARNING al {pendientes}%: HTTP {r.status_code} {r.text}"
    cuerpo = r.json()
    assert (cuerpo["tipo_alerta_tecnica"], cuerpo["severidad"]) == ("BUFFER_CAPACITY_WARNING", _SEVERIDAD[pendientes]), cuerpo
    assert [(a["id_alerta"], a["severidad"]) for a in alertas] == [(cuerpo["id_alerta"], _SEVERIDAD[pendientes])], (
        f"Al {pendientes}% la bandeja de alertas tecnicas del administrador muestra {alertas}"
    )


def test_tc_m03_045_el_95_escala_la_misma_alerta(corrida):
    al_80, al_95 = corrida[80]["aviso"].json(), corrida[95]["aviso"].json()
    assert al_95["id_alerta"] == al_80["id_alerta"] and al_95["es_duplicado"] is True, (al_80, al_95)


def test_tc_m03_045_evento_buffer_capacity_warning_emitido_por_el_nodo():
    pytest.skip("La emision de BUFFER_CAPACITY_WARNING al cruzar el umbral es interna del nodo Edge: requiere el nodo o el "
                "simulador del equipo de IoT")
