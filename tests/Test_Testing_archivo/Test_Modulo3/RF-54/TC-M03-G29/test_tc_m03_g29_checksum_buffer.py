"""
TC-M03-G29 - Verificacion de integridad de datos en el buffer mediante checksum (negativo y positivo).

RF relacionado: RF-54 (CU01). Casos: TC-M03-047 (flujo alterno E6) y TC-M03-072.

Criterios de la ficha:
    TC-M03-047: un registro alterado en el almacenamiento local (checksum_dato inconsistente) se detecta, se
    aisla, no se envia al backend, se registra BUFFER_DATA_CORRUPTION y se sigue sincronizando lo valido.
    TC-M03-072: un dato integro valida su checksum en cada etapa y se transmite y confirma sin marcarse como
    corrupto (sin falsos positivos).

Alcance (mismo criterio que TC-M03-G22): sin nodo Edge ni simulador en el proyecto, el simulador es el DRIVER.
La deteccion y el aislamiento dentro del nodo y BUFFER_DATA_CORRUPTION quedan en SKIP. En el backend real se
verifica:
- 047: los registros validos que el nodo si envia se aceptan completos (la corrupcion de uno no bloquea al
  resto). Complementario (defensa en profundidad): si un registro con checksum inconsistente llega igual al
  backend, debe rechazarse sin bloquear a los validos del mismo lote.
- 072: los registros integros con checksum correcto se aceptan todos y el checksum queda guardado sin
  alterar (modulo3.telemetrias.metadatos, lectura en BD con el usuario QA).

Algoritmo de checksum: RF-53/RF-54 no lo fijan en el codigo; se asume SHA-256 hex del JSON del registro sin el
campo checksum, con claves ordenadas (el mismo supuesto de TC-M03-G02). Confirmar con Desarrollo.
Nota del codigo: la ingesta recibe `checksum` y lo guarda en metadatos, pero no lo valida.

Requisitos: acceso de red a TEST (API y Postgres 5448).
Variables opcionales: BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-54/TC-M03-G29 -v \
        --html=reporte-TC-M03-G29.html --self-contained-html
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2
import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test")
TIMEOUT = 30
DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


def _checksum(registro: dict) -> str:
    sin_checksum = {k: v for k, v in registro.items() if k != "checksum"}
    return hashlib.sha256(json.dumps(sin_checksum, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# --------------------------------------------------------------------------- simulador (driver)
class _NodoEdgeSimulado:
    def __init__(self, device_id: int, sensor_id: int, access_key: str) -> None:
        self.device_id, self.sensor_id, self.access_key = device_id, sensor_id, access_key
        self.buffer: list[dict] = []

    def capturar_offline(self, ts: datetime, valor: float) -> None:
        registro = {"device_id": self.device_id, "sensor_id": self.sensor_id, "tipo_variable": "TEMPERATURA_AMBIENTAL",
                    "valor": valor, "unidad": "°C", "timestamp_captura": ts.isoformat(), "origen": "BUFFER_LOCAL",
                    "access_key": self.access_key}
        registro["checksum"] = _checksum(registro)  # etapa de escritura
        self.buffer.append(registro)

    def alterar_almacenamiento(self, indice: int, nuevo_valor: float) -> None:
        """Corrupcion del almacenamiento local: cambia el valor sin recalcular el checksum."""
        self.buffer[indice]["valor"] = nuevo_valor

    def integros(self) -> list[dict]:
        return [r for r in self.buffer if _checksum(r) == r["checksum"]]  # etapa previa a la sincronizacion

    def corruptos(self) -> list[dict]:
        return [r for r in self.buffer if _checksum(r) != r["checksum"]]

    def enviar(self, registros: list[dict]) -> requests.Response:
        return requests.post(f"{BASE_URL}/iot/telemetria/batch", json={"registros": registros}, timeout=TIMEOUT)


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
        "nombre": f"Finca Checksum Buffer {suf}",
        "ubicacion": {"departamento": "Huila", "municipio": "Neiva", "vereda": "El Caguan", "latitud": "2.93", "longitud": "-75.28"},
        "tamano_h": "10.0"}, "id_finca")
    especie = _crear(admin, "/configuracion/especies", {
        "nombre": f"Porcinos Checksum Buffer {suf}", "descripcion": "Especie de prueba TC-M03-G29",
        "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}, "id_especie")
    return _crear(admin, "/configuracion/infraestructuras", {
        "nombre_infraestructura": f"Galpon Checksum Buffer {suf}", "tipo_area": "Galpón", "superficie": "500.00",
        "finca_id": finca, "especie_id": especie}, "id_infraestructura")


def _nodo(admin, area, etiqueta) -> _NodoEdgeSimulado:
    suf = _sufijo()
    r = admin.post(f"{BASE_URL}/configuracion/dispositivos-iot", json={
        "serial": f"M03-G29-{etiqueta}-{suf}", "descripcion": f"Nodo Edge {etiqueta} TC-M03-G29",
        "id_infraestructura": area, "id_tipo_dispositivo": 3, "es_activo": True}, timeout=TIMEOUT)
    assert r.status_code == 201, f"Precondicion dispositivo: HTTP {r.status_code} {r.text}"
    device_id, serial = r.json()["id_dispositivo_iot"], r.json()["serial"]
    sensor_id = _crear(admin, f"/configuracion/dispositivos-iot/{device_id}/sensores",
                       {"nombre": f"Sensor {etiqueta} {suf}", "categoria": "TEMPERATURA"}, "id_sensores")
    return _NodoEdgeSimulado(device_id, sensor_id, serial)


def _filas_bd(sensor_id: int) -> list[tuple]:
    con = psycopg2.connect(**DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT timestamp_captura, valor_crudo, metadatos->>'checksum' FROM modulo3.telemetrias "
                        "WHERE id_sensor = %s ORDER BY timestamp_captura", (sensor_id,))
            return cur.fetchall()
    finally:
        con.close()


# --------------------------------------------------------------------------- TC-M03-047
@pytest.fixture(scope="module")
def corrida_047(admin, area):
    nodo = _nodo(admin, area, "047")
    inicio = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(10):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 20.0 + i)
    nodo.alterar_almacenamiento(4, 99.9)
    corrupto = dict(nodo.corruptos()[0])
    validos = nodo.integros()
    envio = nodo.enviar(validos)
    return {"nodo": nodo, "corrupto": corrupto, "validos": validos, "envio": envio, "filas": _filas_bd(nodo.sensor_id)}


def test_tc_m03_047_los_validos_se_sincronizan_completos(corrida_047):
    assert len(corrida_047["validos"]) == 9
    r = corrida_047["envio"]
    assert r.status_code == 200 and r.json()["aceptados"] == 9 and r.json()["rechazados"] == 0, r.text
    capturas = {f[0] for f in corrida_047["filas"]}
    assert len(capturas) == 9
    assert _ts(corrida_047["corrupto"]["timestamp_captura"]) not in capturas, "El dato corrupto llego al backend"


def test_tc_m03_047_defensa_en_profundidad_backend_rechaza_un_corrupto_sin_bloquear_validos(admin, area):
    """Si el corrupto llega igual (nodo sin la verificacion), el backend debe rechazarlo solo a el."""
    nodo = _nodo(admin, area, "047b")
    inicio = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(5):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 30.0 + i)
    nodo.alterar_almacenamiento(2, 88.8)
    r = nodo.enviar(nodo.buffer)
    assert r.status_code == 200, f"Un registro corrupto no debe tumbar el lote: HTTP {r.status_code} {r.text}"
    cuerpo = r.json()
    assert (cuerpo["aceptados"], cuerpo["rechazados"]) == (4, 1), (
        f"El backend deberia rechazar solo el registro con checksum inconsistente (no valida el checksum): {cuerpo}"
    )
    assert all(f[1] != Decimal("88.8") for f in _filas_bd(nodo.sensor_id)), "El valor corrupto quedo persistido"


def test_tc_m03_047_aislamiento_y_buffer_data_corruption_en_el_nodo():
    pytest.skip("La deteccion por checksum en el almacenamiento local, el aislamiento del bloque y BUFFER_DATA_CORRUPTION "
                "son internos del nodo Edge: requieren el nodo o el simulador del equipo de IoT")


# --------------------------------------------------------------------------- TC-M03-072
@pytest.fixture(scope="module")
def corrida_072(admin, area):
    nodo = _nodo(admin, area, "072")
    inicio = datetime.now(timezone.utc) - timedelta(hours=3)
    for i in range(10):
        nodo.capturar_offline(inicio + timedelta(minutes=i), 21.0 + i / 10)
    integros_antes = len(nodo.integros())
    envio = nodo.enviar(nodo.buffer)
    return {"nodo": nodo, "integros_antes": integros_antes, "envio": envio, "filas": _filas_bd(nodo.sensor_id)}


def test_tc_m03_072_ningun_dato_integro_se_marca_como_corrupto(corrida_072):
    assert corrida_072["integros_antes"] == 10, "Guarda del driver: los 10 registros deben validar su checksum"
    r = corrida_072["envio"]
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["aceptados"], cuerpo["rechazados"], cuerpo["duplicados"]) == (10, 0, 0), cuerpo


def test_tc_m03_072_el_checksum_se_conserva_sin_alterar(corrida_072):
    enviados = {_ts(r["timestamp_captura"]): r["checksum"] for r in corrida_072["nodo"].buffer}
    guardados = {f[0]: f[2] for f in corrida_072["filas"]}
    assert guardados == enviados, "El checksum persistido no coincide con el enviado por el nodo"


def test_tc_m03_072_validacion_en_cada_etapa_dentro_del_nodo():
    pytest.skip("La validacion del checksum en la escritura y antes de sincronizar ocurre en el nodo Edge: requiere el nodo "
                "o el simulador del equipo de IoT")
