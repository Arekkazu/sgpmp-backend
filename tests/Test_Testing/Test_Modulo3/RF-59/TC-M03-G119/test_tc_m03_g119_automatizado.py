"""TC-M03-G119 - subcaso 1.3: verificacion contra BD (solo lectura) del conjunto de lecturas devuelto por el historial. SCRIPT SIN EJECUTAR.
Variables: SENSOR_TEMPERATURA_AMBIENTAL y TEST_DATABASE_URL (la conexion se abre en modo SOLO LECTURA).

CARACTERISTICAS: script independiente (no importa ningun modulo comun) y con su propio reporte HTML.
Ambiente: BASE_URL por defecto https://api.inmero.co/api-sgpmp-test (TEST). MAIN (/sigab) NO se prueba: el script se detiene.
SANDBOX TRANSACCIONAL: todas las llamadas a la API van con X-Test-Run-Id + X-Sandbox-Secret (run_id propio de este archivo) y un fixture de cierre hace DELETE /test-control/runs/{run_id} (rollback) al terminar; por eso no hay codigo de limpieza. Las lecturas de BD van por POST /test-control/query.
Dependencias:   pip install pytest pytest-html requests psycopg2-binary
Variables de entorno usadas: BASE_URL, TEST_DATABASE_URL, TEST_SANDBOX_SECRET, SENSOR_<VARIABLE>, CORREO_<ROL>, CONTRASENA_<ROL>
  (credenciales y secretos solo por variable de entorno, nunca en el repositorio; si falta una, el test queda SKIPPED con el motivo)
Resultados: PASSED = cumple el RF; FAILED = el backend no cumple el RF (hallazgo); XFAIL = funcionalidad aun no implementada; SKIPPED = falta una variable.
Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m03_g119_automatizado.py -v --html=<ruta>\\resultados\\resultado_TC-M03-G119.html --self-contained-html
  o, desde esta misma carpeta:   python test_tc_m03_g119_automatizado.py
  (genera resultados/resultado_TC-M03-G119.html junto al script)
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


def api(metodo: str, ruta: str, rol: Optional[str] = "admin", **kw) -> requests.Response:
    return requests.request(metodo, BASE_URL + ruta, headers=hdr(rol), timeout=kw.pop("timeout", TIMEOUT), **kw)


def sensor(var: str) -> int:
    v = os.getenv("SENSOR_" + var.upper())
    if not v:
        pytest.skip(f"Falta SENSOR_{var.upper()}")
    return int(v)


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


# ---------------------------------------------------------------- casos de prueba
def test_1_3_lecturas_del_historial_coinciden_con_la_bd():
    id_sensor = sensor("TEMPERATURA_AMBIENTAL")
    ini, fin = ahora_iso(-30 * 86400)[:10], ahora_iso(86400)[:10]
    ids_api, pagina = [], 1
    while True:
        r = api("GET", "/iot/monitoreo/historial", params={"fecha_inicio": ini, "fecha_fin": fin, "sensor_id": id_sensor, "pagina": pagina, "por_pagina": 500, "orden": "ASC"})
        assert r.status_code == 200, r.text[:200]
        j = r.json(); items = j.get("items", [])
        ids_api += [i.get("id_telemetria") for i in items]
        if pagina * 500 >= j.get("total", len(items)) or not items:
            break
        pagina += 1
    ids_bd = [f[0] for f in sql("SELECT id_telemetria FROM modulo3.telemetrias WHERE id_sensor = %s AND timestamp_captura::date BETWEEN %s AND %s ORDER BY timestamp_captura",
                                (id_sensor, ini, fin))]     # solo lectura; en el sandbox va por POST /test-control/query
    assert len(ids_api) == len(ids_bd), f"conteo API={len(ids_api)} vs BD={len(ids_bd)}"
    assert sorted(ids_api) == sorted(ids_bd), "el conjunto de lecturas del historial debe ser identico al de la BD"



if __name__ == "__main__":
    import pathlib
    import sys
    _aqui = pathlib.Path(__file__).resolve().parent
    (_aqui / "resultados").mkdir(exist_ok=True)
    sys.exit(pytest.main([__file__, "-v", "--html=" + str(_aqui / "resultados" / "resultado_TC-M03-G119.html"), "--self-contained-html"]))
