"""TC-M03-G66 - subcaso 8.4: un evento invalido descartado no genera notificacion a productor ni veterinario.
Requiere cuentas de productor y veterinario de la finca del sensor (CORREO_PRODUCTOR/VETERINARIO y sus CONTRASENA_).

CARACTERISTICAS: script independiente (no importa ningun modulo comun) y con su propio reporte HTML.
Ambiente: BASE_URL por defecto https://api.inmero.co/api-sgpmp-test (TEST). MAIN (/sigab) NO se prueba: el script se detiene.
SANDBOX TRANSACCIONAL: todas las llamadas a la API van con X-Test-Run-Id + X-Sandbox-Secret (run_id propio de este archivo) y un fixture de cierre hace DELETE /test-control/runs/{run_id} (rollback) al terminar; por eso no hay codigo de limpieza. Las lecturas de BD van por POST /test-control/query.
Dependencias:   pip install pytest pytest-html requests psycopg2-binary
Variables de entorno usadas: ACCESS_KEY, BASE_URL, BROKER_SERVICE_TOKEN, DEVICE_ID, ID_EVENTO_EDGE, SERIAL, TEST_SANDBOX_SECRET, SENSOR_<VARIABLE>, CORREO_<ROL>, CONTRASENA_<ROL>
  (credenciales y secretos solo por variable de entorno, nunca en el repositorio; si falta una, el test queda SKIPPED con el motivo)
Resultados: PASSED = cumple el RF; FAILED = el backend no cumple el RF (hallazgo); XFAIL = funcionalidad aun no implementada; SKIPPED = falta una variable.
Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m03_g66_automatizado.py -v --noconftest --html=<ruta>\\resultados\\resultado_TC-M03-G66.html --self-contained-html
  o, desde esta misma carpeta:   python test_tc_m03_g66_automatizado.py
  (genera resultados/resultado_TC-M03-G66.html junto al script)
"""
from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest
import requests


# ---------------------------------------------------------------- utilidades propias de este script
BASE_URL = os.getenv("BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")   # TEST; MAIN = /sigab (NO se prueba)
SANDBOX_SECRET = os.getenv("TEST_SANDBOX_SECRET", "")
RUN_ID = "test-pytest-" + uuid.uuid4().hex        # un run_id por archivo (una corrida)
_estado = {"sandbox": True}
TIMEOUT = 30
UNIDADES = {"TEMPERATURA_AMBIENTAL": "°C", "HUMEDAD_RELATIVA": "%", "PH_AGUA": "pH", "NH3": "ppm", "CO2": "ppm",
            "TEMPERATURA_CORPORAL": "°C", "FRECUENCIA_CARDIACA": "lpm", "FRECUENCIA_RESPIRATORIA": "rpm",
            "ACTIVIDAD": "%", "OXIGENO_DISUELTO": "mg/L", "TDS": "µS/cm"}


def ahora_iso(delta_s: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_s)).isoformat()


def requiere_env(*nombres: str) -> None:
    faltan = [n for n in nombres if not os.getenv(n)]
    if faltan:
        pytest.skip("Falta configurar: " + ", ".join(faltan))


_tokens: dict[str, str] = {}


def _verificar_ambiente() -> None:
    if BASE_URL.endswith("/sigab"):
        pytest.exit("BASE_URL apunta al ambiente MAIN (produccion): las pruebas solo se ejecutan en DEV o TEST.", returncode=2)


def _cabeceras_sandbox() -> dict:
    """Headers del sandbox transaccional: el backend ejecuta la peticion dentro de una transaccion que nunca se confirma."""
    if not _estado["sandbox"]:
        return {}
    if not SANDBOX_SECRET:
        pytest.skip("Falta TEST_SANDBOX_SECRET (secreto del sandbox transaccional; pedirlo al DBA por un canal seguro)")
    return {"X-Test-Run-Id": RUN_ID, "X-Sandbox-Secret": SANDBOX_SECRET}


def login(rol: str = "admin") -> str:
    clave_cache = rol if _estado["sandbox"] else rol + ":directo"
    if clave_cache in _tokens:
        return _tokens[clave_cache]
    r = rol.upper()
    correo = os.getenv(f"CORREO_{r}") or ("admin.test@sgpmp.com.co" if rol == "admin" else None)
    clave = os.getenv(f"CONTRASENA_{r}")
    if not correo or not clave:
        pytest.skip(f"Falta CORREO_{r} / CONTRASENA_{r}")
    resp = requests.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": correo, "contrasena": clave}, timeout=TIMEOUT)  # login SIN sandbox: dentro de un run solo funciona el primer login
    assert resp.status_code == 200, f"login {rol}: {resp.status_code} {resp.text[:200]}"
    _tokens[clave_cache] = resp.json()["token"]
    return _tokens[clave_cache]


def hdr(rol: Optional[str] = "admin") -> dict:
    h = {"Content-Type": "application/json", **_cabeceras_sandbox()}
    if rol:
        h["Authorization"] = "Bearer " + login(rol)
    return h


def hdr_dispositivo() -> dict:
    """Headers de los endpoints /iot/* de dispositivo: sandbox + Authorization: Bearer <BROKER_SERVICE_TOKEN> (credencial M2M del broker)."""
    requiere_env("BROKER_SERVICE_TOKEN")
    h = hdr(None)
    h["Authorization"] = "Bearer " + os.environ["BROKER_SERVICE_TOKEN"]
    return h


def serial_dispositivo() -> str:
    v = os.getenv("SERIAL") or os.getenv("ACCESS_KEY")
    if not v:
        pytest.skip("Falta configurar: SERIAL")
    return v


def api(metodo: str, ruta: str, rol: Optional[str] = "admin", **kw) -> requests.Response:
    return requests.request(metodo, BASE_URL + ruta, headers=hdr(rol), timeout=kw.pop("timeout", TIMEOUT), **kw)


def sensor(var: str) -> int:
    v = os.getenv("SENSOR_" + var.upper())
    if not v:
        pytest.skip(f"Falta SENSOR_{var.upper()}")
    return int(v)


_EDGE_ID: dict = {}


def id_evento_edge() -> int:
    """id de un evento edge valido. Usa ID_EVENTO_EDGE si esta definida; si no, crea uno con POST /iot/eventos-edge dentro del sandbox
    (un id inexistente hace que /iot/alertas responda 400 REFERENCIA_INVALIDA). Se crea una sola vez por archivo."""
    if os.getenv("ID_EVENTO_EDGE"):
        return int(os.environ["ID_EVENTO_EDGE"])
    if "id" not in _EDGE_ID:
        ahora = ahora_iso()
        base = {"device_id": int(os.environ["DEVICE_ID"]), "sensor_id": sensor("TEMPERATURA_AMBIENTAL"), "serial": serial_dispositivo(),
                "severidad": "LEVE", "timestamp_captura": ahora, "timestamp_procesamiento_edge": ahora, "origen": "TIEMPO_REAL",
                "estado_conectividad": True,
                "variables_involucradas": [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 25.0, "unidad": "\u00b0C"}]}
        ultimo = None
        for clasif in ("NORMAL", "LEVE", "ANOMALIA", "ALERTA", "CRITICO"):
            r = requests.post(BASE_URL + "/iot/eventos-edge", json={**base, "clasificacion_rf55": clasif}, headers=hdr_dispositivo(), timeout=TIMEOUT)
            ultimo = r
            if r.status_code == 201:
                j = r.json()
                k = next((n for n in ("id_evento_edge_computing", "id_evento_edge", "id_evento", "id") if j.get(n) is not None),
                         next((n for n, v in j.items() if n.startswith("id_") and isinstance(v, int)), None))
                if k:
                    _EDGE_ID["id"] = int(j[k])
                    break
            if r.status_code not in (400, 422):
                break
        if "id" not in _EDGE_ID:
            pytest.skip("No se pudo crear un evento edge de referencia (POST /iot/eventos-edge): " + (f"{ultimo.status_code} {ultimo.text[:200]}" if ultimo is not None else "sin respuesta")
                        + ". Defina ID_EVENTO_EDGE con el id de un evento existente.")
    return _EDGE_ID["id"]


def evento(var: str = "TEMPERATURA_AMBIENTAL", valor: float = 31.0, sev: str = "LEVE", origen: str = "EDGE", **kw) -> dict:
    requiere_env("DEVICE_ID")
    d = {"device_id": int(os.environ["DEVICE_ID"]), "sensor_id": sensor(var), "serial": serial_dispositivo(),
         "tipo_variable": var, "valor": valor, "unidad": UNIDADES.get(var, "u"), "timestamp_evento": ahora_iso(),
         "estado_dato": "LECTURA_VALIDA", "severidad_edge": sev, "origen_evento": origen,
         "id_evento_edge_computing": id_evento_edge(), "reglas_activadas": []}
    if origen == "IA":
        d.update({"tipo_alerta_ia": "PREDICCION_PATOLOGIA", "severidad_ia": sev, "probabilidad_ia": 0.9})
    d.update(kw)
    return d


class Registro:
    """Lleva las alertas creadas para cerrarlas al terminar (DESCARTADA o, si no, RESUELTA)."""
    def __init__(self):
        self.ids: list[int] = []

    def crear(self, **kw) -> dict:
        self.en_sandbox = _estado["sandbox"]
        r = requests.post(BASE_URL + "/iot/alertas", json=evento(**kw), headers=hdr_dispositivo(), timeout=TIMEOUT)
        assert r.status_code in (200, 201), f"POST /iot/alertas {r.status_code}: {r.text[:300]}"
        j = r.json()
        if j.get("id_alerta") and j["id_alerta"] not in self.ids:
            self.ids.append(j["id_alerta"])
        return j

    def limpiar(self):
        if getattr(self, "en_sandbox", True):      # dentro del sandbox el rollback del teardown revierte todo: no hay limpieza
            self.ids.clear()
            return
        for i in self.ids:
            for est in ("DESCARTADA", "RESUELTA"):
                r = cambiar_estado(i, est, "QA limpieza automatica TC-M03")
                if r.status_code == 200:
                    break
            else:
                cambiar_estado(i, "EN_ATENCION", "QA limpieza")
                cambiar_estado(i, "RESUELTA", "QA limpieza")
        self.ids.clear()


@pytest.fixture(scope="module", autouse=True)
def _sandbox_cierre():
    """Teardown obligatorio: DELETE /test-control/runs/{run_id} = rollback de toda la corrida del archivo."""
    yield
    if SANDBOX_SECRET:
        try:
            requests.delete(f"{BASE_URL}/test-control/runs/{RUN_ID}", headers={"X-Test-Run-Id": RUN_ID, "X-Sandbox-Secret": SANDBOX_SECRET}, timeout=TIMEOUT)
        except Exception:  # el backend cierra solo las corridas abandonadas a los 180 s
            pass


@pytest.fixture(autouse=True)
def _modo_por_defecto():
    _verificar_ambiente()
    _estado["sandbox"] = True
    yield
    _estado["sandbox"] = True


@pytest.fixture
def alertas():
    reg = Registro()
    yield reg
    reg.limpiar()


def cambiar_estado(id_alerta: int, estado: str, motivo: str = "QA automatizado", rol: str = "admin") -> requests.Response:
    return api("PATCH", f"/iot/alertas/{id_alerta}/estado", rol, json={"nuevo_estado": estado, "motivo": motivo})


def notificaciones(rol: str, solo_no_leidas: bool = False, tamano: int = 50) -> list[dict]:
    r = api("GET", "/notificaciones", rol, params={"solo_no_leidas": str(solo_no_leidas).lower(), "tamano": tamano})
    assert r.status_code == 200, f"GET /notificaciones ({rol}): {r.status_code}"
    j = r.json()
    return j.get("items") or j.get("notificaciones") or j.get("resultados") or []


def esperar(segundos: float) -> None:
    time.sleep(segundos)


# ---------------------------------------------------------------- casos de prueba
def _id_max_notificacion(rol: str) -> int:
    ids = [n.get("id_notificacion") for n in notificaciones(rol) if isinstance(n.get("id_notificacion"), int)]
    return max(ids) if ids else 0


def _notificaciones_nuevas(rol: str, base: int) -> list[dict]:
    """Notificaciones posteriores al punto de referencia, sin contar las de inicio de sesion (las crea el propio login de la prueba)."""
    return [n for n in notificaciones(rol)
            if isinstance(n.get("id_notificacion"), int) and n["id_notificacion"] > base and not re.search("sesi", str(n), re.I)]


def test_8_4_evento_invalido_descartado_no_notifica_a_productor_ni_veterinario():
    """Ficha G66 subcaso 8: por cada evento invalido descartado (E1) no debe haber notificacion a productor ni veterinario."""
    base = {rol: _id_max_notificacion(rol) for rol in ("productor", "veterinario")}
    invalido = evento(var="TEMPERATURA_AMBIENTAL", valor=33.0, sev="MODERADO")
    sin_sensor = {k: v for k, v in invalido.items() if k != "sensor_id"}
    casos = {
        "sin sensor_id (campo obligatorio)": sin_sensor,
        "estado_dato fuera de catalogo": {**invalido, "estado_dato": "NO_EXISTE"},
        "severidad_edge fuera de catalogo": {**invalido, "severidad_edge": "EXTREMO"},
        "valor con tipo incorrecto": {**invalido, "valor": "abc"},
        "probabilidad_ia fuera de [0,1]": evento(var="TEMPERATURA_AMBIENTAL", valor=33.0, sev="MODERADO", origen="IA", probabilidad_ia=1.01),
    }
    for nombre, cuerpo in casos.items():
        r = requests.post(BASE_URL + "/iot/alertas", json=cuerpo, headers=hdr_dispositivo(), timeout=TIMEOUT)
        assert r.status_code in (400, 422), f"{nombre}: debia rechazarse (400/422) y respondio {r.status_code}: {r.text[:200]}"
    esperar(3)
    for rol in ("productor", "veterinario"):
        nuevas = _notificaciones_nuevas(rol, base[rol])
        assert not nuevas, f"{rol}: no debe recibir notificaciones por eventos invalidos descartados, pero recibio {len(nuevas)}: {str(nuevas)[:300]}"


if __name__ == "__main__":
    import pathlib
    import sys
    _aqui = pathlib.Path(__file__).resolve().parent
    (_aqui / "resultados").mkdir(exist_ok=True)
    sys.exit(pytest.main([__file__, "-v", "--noconftest", "--html=" + str(_aqui / "resultados" / "resultado_TC-M03-G66.html"), "--self-contained-html"]))
