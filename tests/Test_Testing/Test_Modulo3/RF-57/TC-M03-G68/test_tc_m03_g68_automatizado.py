"""TC-M03-G68 - subcaso 1.5: ausencia de reportes > 2x la frecuencia de muestreo. SCRIPT SIN EJECUTAR.
Reloj controlado: se envejece el ultimo contacto del dispositivo en la BD de PRUEBAS y se verifica la alerta DISPOSITIVO_SIN_SENAL (RF-60).

CARACTERISTICAS: script independiente (no importa ningun modulo comun) y con su propio reporte HTML.
Ambiente: BASE_URL por defecto https://api.inmero.co/api-sgpmp-test (TEST). MAIN (/sigab) NO se prueba: el script se detiene.
SANDBOX TRANSACCIONAL: todas las llamadas a la API van con X-Test-Run-Id + X-Sandbox-Secret (run_id propio de este archivo) y un fixture de cierre hace DELETE /test-control/runs/{run_id} (rollback) al terminar; por eso no hay codigo de limpieza. Las lecturas de BD van por POST /test-control/query.
Dependencias:   pip install pytest pytest-html requests psycopg2-binary
Variables de entorno usadas: BASE_URL, DEVICE_ID, ESPERA_JOB_SLA_S, PERMITIR_FUERA_DE_SANDBOX, TEST_DATABASE_URL, TEST_SANDBOX_SECRET, CORREO_<ROL>, CONTRASENA_<ROL>
  (credenciales y secretos solo por variable de entorno, nunca en el repositorio; si falta una, el test queda SKIPPED con el motivo)
Resultados: PASSED = cumple el RF; FAILED = el backend no cumple el RF (hallazgo); XFAIL = funcionalidad aun no implementada; SKIPPED = falta una variable.
Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m03_g68_automatizado.py -v --noconftest --html=<ruta>\\resultados\\resultado_TC-M03-G68.html --self-contained-html
  o, desde esta misma carpeta:   python test_tc_m03_g68_automatizado.py
  (genera resultados/resultado_TC-M03-G68.html junto al script)
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


def fuera_de_sandbox() -> None:
    """Para subcasos que NO caben en el sandbox: manipulan la BD con otra conexion (viaje en el tiempo, estado del dispositivo) o
    dependen de un job en segundo plano, que no ven datos sin confirmar. Dejan datos en TEST, por eso exigen autorizacion explicita
    (PERMITIR_FUERA_DE_SANDBOX=1). Llamarla ANTES de crear datos en el test."""
    requiere_env("PERMITIR_FUERA_DE_SANDBOX", "TEST_DATABASE_URL")
    _estado["sandbox"] = False


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


def esperar(segundos: float) -> None:
    time.sleep(segundos)


# ---------------------------------------------------------------- casos de prueba
def test_1_5_ausencia_de_reportes_mayor_a_2x_frecuencia():
    """Subcaso 1.5: un dispositivo sin reportes durante mas de 2x la frecuencia de muestreo debe quedar en SIN_SEÑAL / generar alerta tecnica.
    La frecuencia de muestreo global esta en SEGUNDOS (modulo9.configuraciones_globales.frecuencia_muestreo). El job de RF-60 corre cada 60 s.
    El script crea (si no existe) la fila de estado del dispositivo, la deja con el ultimo contacto envejecido a 2x la frecuencia + 10 s
    (siempre por debajo del umbral fijo de 300 s del RF-60, para no provocar transiciones ni alertas reales), espera un ciclo del job,
    comprueba el estado y al final borra la fila que creo (o restaura la original)."""
    fuera_de_sandbox()   # el job que evalua el estado corre en otro proceso y solo ve datos confirmados
    requiere_env("DEVICE_ID")
    id_disp = int(os.environ["DEVICE_ID"])
    freq_seg = int((sql("SELECT frecuencia_muestreo FROM modulo9.configuraciones_globales WHERE es_activo = true LIMIT 1") or [(45,)])[0][0] or 45)
    edad_seg = freq_seg * 2 + 10          # "mas de 2x" la frecuencia, con un margen de 10 s
    previo = sql("SELECT estado_actual, fecha_ultimo_contacto FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot = %s", (id_disp,))
    n_antes = len(api("GET", "/iot/alertas-tecnicas", params={"por_pagina": 200}).json().get("items", []))
    try:
        if previo:
            sql("UPDATE modulo3.estados_dispositivos_iot SET estado_actual = 'ACTIVO', fecha_ultimo_contacto = now() - (%s || ' seconds')::interval WHERE id_dispositivo_iot = %s",
                (str(edad_seg), id_disp))
        else:
            sql("INSERT INTO modulo3.estados_dispositivos_iot (id_dispositivo_iot, estado_actual, fecha_ultimo_contacto) VALUES (%s, 'ACTIVO', now() - (%s || ' seconds')::interval)",
                (id_disp, str(edad_seg)))
        esperar(int(os.getenv("ESPERA_JOB_SLA_S", "70")))
        fila = sql("SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot = %s", (id_disp,))
        estado = fila[0][0] if fila else None
        tecnicas = api("GET", "/iot/alertas-tecnicas", params={"por_pagina": 200}).json().get("items", [])
        assert (estado or "").upper().replace("Ñ", "N") == "SIN_SENAL" or len(tecnicas) > n_antes, \
            (f"RF-57 (ausencia de reportes): con {edad_seg} s sin reportes (2x la frecuencia de muestreo de {freq_seg} s) el dispositivo sigue en "
             f"estado {estado!r} y no se genero alerta tecnica. El job de RF-60 usa un umbral fijo de 300 s (5 min), no 2x la frecuencia.")
    finally:      # la prueba corre fuera del sandbox: deja la tabla como estaba
        if previo:
            sql("UPDATE modulo3.estados_dispositivos_iot SET estado_actual = %s, fecha_ultimo_contacto = %s WHERE id_dispositivo_iot = %s",
                (previo[0][0], previo[0][1], id_disp))
        else:
            sql("DELETE FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot = %s", (id_disp,))



if __name__ == "__main__":
    import pathlib
    import sys
    _aqui = pathlib.Path(__file__).resolve().parent
    (_aqui / "resultados").mkdir(exist_ok=True)
    sys.exit(pytest.main([__file__, "-v", "--noconftest", "--html=" + str(_aqui / "resultados" / "resultado_TC-M03-G68.html"), "--self-contained-html"]))
