"""
TC-M03-G27 (sub-caso 1) - Umbrales de ocupacion del buffer (WARNING / CRITICO).

RF relacionado: RF-54 (CU01). Caso: TC-M03-045 (valores limite).

Criterio de la ficha: 79% -> sin alerta; 80% -> BUFFER_CAPACITY_WARNING y estado WARNING; 95% -> CRITICO.
El umbral es configurable (confirmar el valor del ambiente antes de ejecutar; aqui 80% y 95%).

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el driver informa la
ocupacion del buffer por heartbeat (capacidad 100, pendientes 79 / 80 / 95). Lo que se verifica es el lado
del sistema, que es lo que complementa TC-M03-054:
- tras cada heartbeat, el estado del buffer expuesto por la API (la misma consulta de TC-M03-054) debe ser
  NORMAL / WARNING / CRITICO;
- el cruce del 80% debe producir una alerta para el administrador (y el 79% no).
La emision de BUFFER_CAPACITY_WARNING dentro del nodo queda en SKIP.

Nota: el heartbeat (POST /iot/heartbeat) solo informa datos_pendientes_buffer, sin la capacidad del buffer,
y el OpenAPI de TEST no tiene endpoint de estado del buffer; con eso el backend no puede calcular el
porcentaje. Si el contrato del heartbeat agrega la capacidad, ajustar _heartbeat().

Requisitos: acceso de red a TEST. Variables opcionales: BASE_URL, RUTA_ESTADO_BUFFER.

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
RUTA_ESTADO_BUFFER = os.getenv("RUTA_ESTADO_BUFFER", "/dispositivos/{id}/buffer")
TIMEOUT = 30
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
    return requests.post(
        f"{BASE_URL}/iot/heartbeat",
        json={"tipo_mensaje": "HEARTBEAT", "estado_local_buffer": "A", "datos_pendientes_buffer": pendientes,
              "capacidad_buffer": CAPACIDAD, "fecha_registro": datetime.now(timezone.utc).isoformat()},
        headers={"X-Device-Id": str(device_id), "X-Device-API-Key": access_key}, timeout=TIMEOUT,
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

    resultados = {}
    for pendientes, _, _ in ESCALONES:
        desde = datetime.now(timezone.utc) - timedelta(seconds=5)
        hb = _heartbeat(device_id, serial, pendientes)
        estado = admin.get(f"{BASE_URL}{RUTA_ESTADO_BUFFER.format(id=device_id)}", timeout=TIMEOUT)
        alertas = admin.get(f"{BASE_URL}/iot/alertas-tecnicas", params={
            "fecha_desde": desde.isoformat(), "fecha_hasta": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
            "por_pagina": 200}, timeout=TIMEOUT)
        del_dispositivo = [a for a in alertas.json().get("items", []) if a.get("id_dispositivo_ioit") == device_id] \
            if alertas.status_code == 200 else None
        resultados[pendientes] = {"hb": hb, "estado": estado, "alertas": del_dispositivo}
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


@pytest.mark.parametrize("pendientes,_estado,debe_alertar", ESCALONES, ids=["79%", "80%", "95%"])
def test_tc_m03_045_alerta_al_cruzar_el_umbral_de_advertencia(pendientes, _estado, debe_alertar, corrida):
    alertas = corrida[pendientes]["alertas"]
    assert alertas is not None, "La consulta de alertas tecnicas fallo"
    if debe_alertar:
        assert alertas, f"Al {pendientes}% de ocupacion no se genero ninguna alerta para el administrador"
    else:
        assert not alertas, f"Al {pendientes}% (bajo el umbral) no deberia haber alerta: {alertas}"


def test_tc_m03_045_evento_buffer_capacity_warning_en_el_nodo():
    pytest.skip("La emision de BUFFER_CAPACITY_WARNING al cruzar el umbral es interna del nodo Edge: requiere el nodo o el "
                "simulador del equipo de IoT")
