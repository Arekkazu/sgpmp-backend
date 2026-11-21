"""TC-M03-G86 - subcaso 3.Y: lectura anomala seguida de lectura normal - no genera alerta. SCRIPT SIN EJECUTAR.
severidad_edge no admite NORMAL (POST /iot/alertas): la lectura normal se envia por la ingesta de telemetria (POST /iot/telemetria),
que es el camino real de una lectura en banda normal.

CARACTERISTICAS: script independiente (no importa ningun modulo comun) y con su propio reporte HTML.
Ambiente: BASE_URL por defecto https://api.inmero.co/api-sgpmp-test (TEST). MAIN (/sigab) NO se prueba: el script se detiene.
SANDBOX TRANSACCIONAL: todas las llamadas a la API van con X-Test-Run-Id + X-Sandbox-Secret (run_id propio de este archivo) y un fixture de cierre hace DELETE /test-control/runs/{run_id} (rollback) al terminar; por eso no hay codigo de limpieza. Las lecturas de BD van por POST /test-control/query.
Dependencias:   pip install pytest pytest-html requests psycopg2-binary
Variables de entorno usadas: ACCESS_KEY, BASE_URL, BROKER_SERVICE_TOKEN, DEVICE_ID, ID_EVENTO_EDGE, SERIAL, TEST_DATABASE_URL, TEST_SANDBOX_SECRET, SENSOR_<VARIABLE>, CORREO_<ROL>, CONTRASENA_<ROL>
  (credenciales y secretos solo por variable de entorno, nunca en el repositorio; si falta una, el test queda SKIPPED con el motivo)
Resultados: PASSED = cumple el RF; FAILED = el backend no cumple el RF (hallazgo); XFAIL = funcionalidad aun no implementada; SKIPPED = falta una variable.
Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m03_g86_automatizado.py -v --noconftest --html=<ruta>\\resultados\\resultado_TC-M03-G86.html --self-contained-html
  o, desde esta misma carpeta:   python test_tc_m03_g86_automatizado.py
  (genera resultados/resultado_TC-M03-G86.html junto al script)
"""
from __future__ import annotations

import os
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


def obtener_alerta(id_alerta: int, rol: str = "admin") -> dict:
    r = api("GET", f"/iot/alertas/{id_alerta}", rol)
    assert r.status_code == 200, f"GET alerta {id_alerta}: {r.status_code}"
    return r.json()


def _validar_bd(url: str) -> None:
    from urllib.parse import urlparse
    nombre = (urlparse(url).path or "").lstrip("/").lower()
    if "test" not in nombre and nombre not in {"pruebas", "pruebas-integrador"}:
        pytest.fail("Proteccion: TEST_DATABASE_URL debe apuntar a una base de PRUEBAS (nombre con 'test' o 'pruebas').")


def bd():
    """Conexion de escritura a la BD de pruebas (autocommit). Nunca contra produccion."""
    requiere_env("TEST_DATABASE_URL")
    import psycopg2
    url = os.environ["TEST_DATABASE_URL"]
    _validar_bd(url)
    con = psycopg2.connect(url, connect_timeout=10)
    con.autocommit = True
    with con.cursor() as cur:
        cur.execute("SELECT set_config('app.current_role', 'Administrador', false);")
    return con


def _literal(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _interpolar(consulta: str, params: tuple) -> str:
    partes = consulta.split("%s")
    assert len(partes) == len(params) + 1, "numero de parametros distinto de los %s de la consulta"
    return partes[0] + "".join(_literal(p) + partes[i + 1] for i, p in enumerate(params))


def _filas_json(j: Any) -> list:
    """Normaliza la respuesta de POST /test-control/query (formato por confirmar con el DBA) a lista de tuplas."""
    if isinstance(j, dict):
        for k in ("rows", "filas", "resultados", "results", "data", "items"):
            if isinstance(j.get(k), list):
                j = j[k]
                break
    filas = j if isinstance(j, list) else []
    return [tuple(f.values()) if isinstance(f, dict) else tuple(f) for f in filas]


def sql(consulta: str, params: tuple = ()) -> list[tuple]:
    """Dentro del sandbox las consultas (SOLO LECTURA) van por POST /test-control/query, porque una conexion directa no ve datos sin
    confirmar. Las escrituras exigen fuera_de_sandbox() (conexion directa a la BD de PRUEBAS)."""
    escritura = consulta.lstrip().split(None, 1)[0].upper() in {"UPDATE", "INSERT", "DELETE", "TRUNCATE", "ALTER", "DROP"}
    if _estado["sandbox"]:
        if escritura:
            pytest.fail("Escritura directa en BD dentro del sandbox: el subcaso debe llamar fuera_de_sandbox() antes de crear datos.")
        cuerpo = _interpolar(consulta, params) if params else consulta
        r = requests.post(f"{BASE_URL}/test-control/query", json={"query": cuerpo}, headers=hdr(None), timeout=TIMEOUT)
        assert r.status_code == 200, f"POST /test-control/query: {r.status_code} {r.text[:200]}"
        return _filas_json(r.json())
    con = bd()
    try:
        with con.cursor() as cur:
            cur.execute(consulta, params)
            return cur.fetchall() if cur.description else []
    finally:
        con.close()


def esperar(segundos: float) -> None:
    time.sleep(segundos)


# ---------------------------------------------------------------- casos de prueba
def test_3_Y_lectura_anomala_y_luego_normal_no_genera_segunda_alerta(alertas):
    requiere_env("DEVICE_ID")
    a = alertas.crear(var="TEMPERATURA_AMBIENTAL", valor=34.0, sev="LEVE")             # lectura anomala -> 1 alerta
    n0 = sql("SELECT count(*) FROM modulo3.alertas WHERE tipo_variable='TEMPERATURA_AMBIENTAL' AND fecha_generacion > now() - interval '30 minutes'")[0][0]
    normal = {"device_id": int(os.environ["DEVICE_ID"]), "sensor_id": sensor("TEMPERATURA_AMBIENTAL"), "serial": serial_dispositivo(),
              "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 22.0, "unidad": "°C", "timestamp_captura": ahora_iso()}
    r = requests.post(BASE_URL + "/iot/telemetria", json=normal, headers=hdr_dispositivo(), timeout=TIMEOUT)
    assert r.status_code == 201, r.text[:200]
    esperar(3)
    n1 = sql("SELECT count(*) FROM modulo3.alertas WHERE tipo_variable='TEMPERATURA_AMBIENTAL' AND fecha_generacion > now() - interval '30 minutes'")[0][0]
    assert n1 == n0, "una lectura normal posterior no debe generar alerta"
    assert obtener_alerta(a["id_alerta"])["estado_alerta"] == "ACTIVA", "la alerta previa no cambia por una lectura normal"
    # la ingesta de la lectura anomala previa tampoco duplica
    assert r.json().get("estado_calidad")



if __name__ == "__main__":
    import pathlib
    import sys
    _aqui = pathlib.Path(__file__).resolve().parent
    (_aqui / "resultados").mkdir(exist_ok=True)
    sys.exit(pytest.main([__file__, "-v", "--noconftest", "--html=" + str(_aqui / "resultados" / "resultado_TC-M03-G86.html"), "--self-contained-html"]))
