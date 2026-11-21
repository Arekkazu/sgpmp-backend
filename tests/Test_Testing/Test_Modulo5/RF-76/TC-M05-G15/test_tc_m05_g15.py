# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 RF-76: precondiciones del activo (sandbox transaccional)   |
"""
TC-M05-G15 — RF-76 CU03, POST /suministros/medicamentos.
Precondiciones del activo: estado, ciclo productivo y cantidad poblacional.

Subcasos:
  (a) TC-M05-005 (A01–A06):
      - Rechazo por estado no permitido: INACTIVO (2), CERRADO (12), BAJA (10), AISLADO (812) -> HTTP 422 (E1).
      - Rechazo por activo ACTIVO sin ciclo abierto: 853 -> HTTP 422 (E7).
      - Rechazo por ID inexistente: 999999999 -> HTTP 404 (CU03 FA-02).
  (b) TC-M05-041 (B01):
      - Activo POBLACIONAL ACTIVO con ciclo abierto y cantidad_actual NULL: 462 con dosis_aplicada=100 -> HTTP 422 (FA-08).
      - Nota: cantidad_actual=0 con ACTIVO + ciclo abierto no es alcanzable por API en M02 (baja total cierra fase y pasa a BAJA).
  (c) Inocuidad y Teardown:
      - T00: Línea base de medicamentos, estados y fases de los 6 activos evaluados.
      - T98: Cierre de la corrida sandbox y verificación de Rollback exitoso.
      - T99: Verificación de inocuidad final sin sandbox (conteos y fases idénticos a T00).

Diseño y Reglas Duras:
- Cliente: requests.Session contra $TEST_BASE_URL de .env.test.
- UNA sola corrida sandbox (un solo POST /sesiones/ por run_id — DEF-04) para todos los rechazos.
- Headers obligatorios: X-Test-Run-Id + X-Sandbox-Secret + X-Zona-Horaria ("America/Bogota").
- periodo_retiro_dias = 0 en todos los payloads.
- Hora única por test (08:01, 08:02, etc.).
- Traza automática JSONL en $TEST_EVIDENCE_DIR/trazas_http.jsonl sanitizada (sin credenciales, tokens ni datos personales).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZONA_USUARIO = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")

NOMBRE_ZONA = "America/Bogota"
TIMEOUT_S = 45
ARCHIVO_TRAZA = "trazas_http.jsonl"

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

# Línea base de los activos evaluados (guardada en T00)
_LINEA_BASE: dict[int, dict[str, Any]] = {}
_TEST_ACTUAL = "init"


# --------------------------------------------------------------------------- utilidades


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: falta la variable de entorno {nombre}")
    return valor or ""


def _hoy() -> date:
    return datetime.now(ZONA_USUARIO).date()


def _secretos() -> list[str]:
    return [
        s for s in (
            _env("TEST_SANDBOX_SECRET", False),
            _env("TEST_ADMIN_PASSWORD", False),
            _env("TEST_ADMIN_EMAIL", False),
        ) if s
    ]


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:500]
    for s in [*_secretos(), *extra]:
        if s and len(s) > 3:
            texto = texto.Replace(s, "***REDACTED***") if hasattr(texto, "Replace") else texto.replace(s, "***REDACTED***")
    return texto


def _sanitizar_objeto(obj: Any, extra: tuple[str, ...] = ()) -> Any:
    if isinstance(obj, dict):
        san = {}
        for k, v in obj.items():
            if k.lower() in ("contrasena", "password", "token", "authorization", "correo_electronico"):
                san[k] = "***REDACTED***"
            elif isinstance(v, (dict, list)):
                san[k] = _sanitizar_objeto(v, extra)
            elif isinstance(v, str):
                san[k] = _seguro(v, extra)
            else:
                san[k] = v
        return san
    elif isinstance(obj, list):
        return [_sanitizar_objeto(x, extra) for x in obj]
    elif isinstance(obj, str):
        return _seguro(obj, extra)
    return obj


def _trazar(
    metodo: str,
    ruta: str,
    resp: requests.Response | None,
    inicio_perf: float,
    req_body: Any = None,
    token_extra: str | None = None,
    error: str | None = None,
) -> None:
    directorio = os.environ.get("TEST_EVIDENCE_DIR")
    if not directorio:
        return
    destino = Path(directorio) / ARCHIVO_TRAZA
    duracion_ms = round((time.perf_counter() - inicio_perf) * 1000, 2)
    now_iso = datetime.now(ZONA_USUARIO).isoformat()
    extra = (token_extra,) if token_extra else ()

    resp_body = None
    server_date = ""
    status_code = None
    error_code = None

    if resp is not None:
        status_code = resp.status_code
        server_date = resp.headers.get("Date", "")
        try:
            resp_body = resp.json()
            if isinstance(resp_body, dict):
                error_code = resp_body.get("error_code")
        except Exception:
            resp_body = resp.text[:300]

    registro = {
        "timestamp_local": now_iso,
        "server_date": server_date,
        "duracion_ms": duracion_ms,
        "test": _TEST_ACTUAL,
        "metodo": metodo,
        "ruta": ruta,
        "status_code": status_code,
        "error_code": error_code,
        "error_conexion": error,
        "request_body": _sanitizar_objeto(req_body, extra),
        "response_body": _sanitizar_objeto(resp_body, extra),
    }

    try:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception:
        pass


class ErrorConexion(AssertionError):
    def __init__(self, paso: str, ruta: str, original: requests.RequestException):
        self.paso = paso
        self.ruta = ruta
        self.original = original
        self.reintentable = isinstance(
            original, (requests.ConnectionError, requests.Timeout)
        )
        super().__init__(
            f"ERROR_CONEXION paso={paso} ruta={ruta}: {type(original).__name__} ({original})"
        )


class Corrida:
    """Gestiona la transacción sandbox (X-Test-Run-Id) con ciclo de vida completo."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g15-{uuid.uuid4()}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.token: str | None = None
        self.cerrada = False
        self.http = requests.Session()
        self.http.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "X-Zona-Horaria": NOMBRE_ZONA,
        })

    def seguro(self, texto: str) -> str:
        return _seguro(texto, (self.token,) if self.token else ())

    def _enviar(self, metodo: str, ruta: str, paso: str | None = None, json_body: Any = None, **kw) -> requests.Response:
        assert ruta.startswith("/"), f"Ruta relativa esperada: {ruta!r}"
        inicio = time.perf_counter()
        token_extra = self.token
        try:
            resp = self.http.request(metodo, self.base + ruta, timeout=TIMEOUT_S, json=json_body, **kw)
        except requests.RequestException as exc:
            _trazar(metodo, ruta, None, inicio, req_body=json_body, token_extra=token_extra, error=type(exc).__name__)
            raise ErrorConexion(paso or _TEST_ACTUAL, ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio, req_body=json_body, token_extra=token_extra)
        return resp

    def get(self, ruta: str, paso: str | None = None, **kw) -> requests.Response:
        return self._enviar("GET", ruta, paso=paso, **kw)

    def post(self, ruta: str, json: Any, paso: str | None = None) -> requests.Response:
        return self._enviar("POST", ruta, paso=paso, json_body=json)

    def login(self) -> None:
        assert self.token is None, "DEF-04: solo se permite un login por run_id"
        r = self.post(
            "/sesiones/",
            {"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            paso="login_admin",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: paso=login admin HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token")
        assert token, "PRECONDICION_NO_CUMPLIDA: login sin token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            return self._enviar("DELETE", f"/test-control/runs/{self.run_id}", paso="teardown")
        finally:
            self.http.close()


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def corrida():
    """Corrida sandbox transaccional única para todos los tests de rechazo."""
    c = Corrida()
    try:
        c.login()
        yield c
    finally:
        c.cerrar()


@pytest.fixture(autouse=True)
def _actualizar_nombre_test(request):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name


# --------------------------------------------------------------------------- helpers de dominio


def _payload(id_activo: int, hora: str, dosis_aplicada: float = 10.0, **cambios) -> dict:
    base = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": _hoy().isoformat(),
        "hora_aplicacion": hora,
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": dosis_aplicada,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": f"Tratamiento preventivo {id_activo} prueba automatica",
        "costo_unitario": 500,
        "nombre_veterinario": "Dr. Pérez",
    }
    base.update(cambios)
    return base


def _contar_medicamentos(c: Corrida, id_activo: int) -> int:
    r = c.get("/suministros/medicamentos", params={"id_activo_biologico": id_activo})
    assert r.status_code == 200, f"GET medicamentos {id_activo} HTTP {r.status_code}: {c.seguro(r.text)}"
    return r.json().get("total", 0)


def _leer_activo(c: Corrida, id_activo: int) -> dict:
    r = c.get(f"/activos-biologicos/{id_activo}")
    assert r.status_code == 200, f"GET activo {id_activo} HTTP {r.status_code}: {c.seguro(r.text)}"
    return r.json()


def _leer_fases(c: Corrida, id_activo: int) -> list[dict]:
    r = c.get(f"/activos-biologicos/{id_activo}/fases")
    assert r.status_code == 200, f"GET fases {id_activo} HTTP {r.status_code}: {c.seguro(r.text)}"
    return r.json().get("fases") or []


# --------------------------------------------------------------------------- TESTS


def test_00_linea_base(corrida: Corrida):
    """T00: Registrar la línea base de medicamentos, estado y fases de los activos evaluados."""
    activos = [2, 12, 10, 812, 853, 462]
    for id_act in activos:
        meds = _contar_medicamentos(corrida, id_act)
        act = _leer_activo(corrida, id_act)
        fases = _leer_fases(corrida, id_act)
        fases_activas = [f for f in fases if f.get("es_activa") is True]

        _LINEA_BASE[id_act] = {
            "medicamentos": meds,
            "id_estado": act.get("id_estado"),
            "fases_total": len(fases),
            "fases_activas": len(fases_activas),
        }

    assert len(_LINEA_BASE) == len(activos), "Faltan activos en la línea base"


def test_a01_inactivo_2(corrida: Corrida):
    """A01: Rechazo por activo INACTIVO (Activo 2). Esperado: 422 (RF-76 E1)."""
    id_act = 2
    p = _payload(id_act, "08:01")
    r = corrida.post("/suministros/medicamentos", p)

    assert r.status_code == 422, f"Esperado HTTP 422; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "inactivo" in r.text.lower(), f"Mensaje no contiene 'INACTIVO': {corrida.seguro(r.text)}"

    # Control de no persistencia e inocuidad de estado
    assert _contar_medicamentos(corrida, id_act) == _LINEA_BASE[id_act]["medicamentos"]
    assert _leer_activo(corrida, id_act)["id_estado"] == _LINEA_BASE[id_act]["id_estado"]


def test_a02_cerrado_12(corrida: Corrida):
    """A02: Rechazo por activo CERRADO (Activo 12). Esperado: 422 (RF-76 E1)."""
    id_act = 12
    p = _payload(id_act, "08:02")
    r = corrida.post("/suministros/medicamentos", p)

    assert r.status_code == 422, f"Esperado HTTP 422; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "cerrado" in r.text.lower(), f"Mensaje no contiene 'CERRADO': {corrida.seguro(r.text)}"

    assert _contar_medicamentos(corrida, id_act) == _LINEA_BASE[id_act]["medicamentos"]
    assert _leer_activo(corrida, id_act)["id_estado"] == _LINEA_BASE[id_act]["id_estado"]


def test_a03_baja_10(corrida: Corrida):
    """A03: Rechazo por activo en BAJA (Activo 10). Esperado: 422 (RF-76 E1)."""
    id_act = 10
    p = _payload(id_act, "08:03")
    r = corrida.post("/suministros/medicamentos", p)

    assert r.status_code == 422, f"Esperado HTTP 422; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "baja" in r.text.lower(), f"Mensaje no contiene 'BAJA': {corrida.seguro(r.text)}"

    assert _contar_medicamentos(corrida, id_act) == _LINEA_BASE[id_act]["medicamentos"]
    assert _leer_activo(corrida, id_act)["id_estado"] == _LINEA_BASE[id_act]["id_estado"]


def test_a04_aislado_812(corrida: Corrida):
    """A04: Rechazo por activo AISLADO (Activo 812). Esperado: 422 (RF-76 E1)."""
    id_act = 812
    p = _payload(id_act, "08:04")
    r = corrida.post("/suministros/medicamentos", p)

    assert r.status_code == 422, f"Esperado HTTP 422; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "aislado" in r.text.lower(), f"Mensaje no contiene 'AISLADO': {corrida.seguro(r.text)}"

    assert _contar_medicamentos(corrida, id_act) == _LINEA_BASE[id_act]["medicamentos"]
    assert _leer_activo(corrida, id_act)["id_estado"] == _LINEA_BASE[id_act]["id_estado"]


def test_a05_sin_ciclo_abierto_853(corrida: Corrida):
    """A05: Rechazo por activo ACTIVO sin ciclo abierto (Activo 853). Esperado: 422 (RF-76 E7)."""
    id_act = 853
    p = _payload(id_act, "08:05")
    r = corrida.post("/suministros/medicamentos", p)

    assert r.status_code == 422, f"Esperado HTTP 422; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "ciclo" in r.text.lower(), f"Mensaje no contiene referencia a 'ciclo': {corrida.seguro(r.text)}"

    assert _contar_medicamentos(corrida, id_act) == _LINEA_BASE[id_act]["medicamentos"]
    assert _leer_activo(corrida, id_act)["id_estado"] == _LINEA_BASE[id_act]["id_estado"]


def test_a06_id_inexistente_999999999(corrida: Corrida):
    """A06: Rechazo por ID inexistente (999999999). Esperado: 404 (CU03 FA-02)."""
    id_act = 999999999
    p = _payload(id_act, "08:06")
    r = corrida.post("/suministros/medicamentos", p)

    assert r.status_code == 404, f"Esperado HTTP 404; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "no existe" in r.text.lower(), f"Mensaje no indica 'no existe': {corrida.seguro(r.text)}"


def test_b01_poblacional_cantidad_null_462(corrida: Corrida):
    """B01: Activo POBLACIONAL con ciclo abierto y cantidad_actual NULL (Activo 462). Esperado: 422 (CU03 FA-08)."""
    id_act = 462

    # Setup de fase en sandbox (ciclo 4 cachama)
    rf = corrida.post(
        f"/activos-biologicos/{id_act}/fases",
        {"id_ciclo_productiva": 4, "motivo_cambio": "TC-M05-G15: apertura fase en sandbox"},
        paso="abrir_fase_462",
    )
    assert rf.status_code == 201, (
        f"ERROR_AMBIENTE: no se pudo abrir fase en activo {id_act} (HTTP {rf.status_code}): {corrida.seguro(rf.text)}"
    )

    # POST con dosis_aplicada=100
    p = _payload(id_act, "08:07", dosis_aplicada=100)
    r = corrida.post("/suministros/medicamentos", p)

    # Spec CU03 FA-08 indica rechazo (400 o 422)
    assert r.status_code in (400, 422), f"Esperado HTTP 400 o 422; obtenido {r.status_code}: {corrida.seguro(r.text)}"
    assert "cantidad" in r.text.lower(), f"Mensaje no contiene 'cantidad': {corrida.seguro(r.text)}"

    # Control de no persistencia
    assert _contar_medicamentos(corrida, id_act) == _LINEA_BASE[id_act]["medicamentos"]
    assert _leer_activo(corrida, id_act)["id_estado"] == _LINEA_BASE[id_act]["id_estado"]


def test_98_cierre_corrida(corrida: Corrida):
    """T98: Cierre explícito de la corrida sandbox y validación de Rollback exitoso."""
    resp = corrida.cerrar()
    assert resp is not None, "La corrida ya estaba cerrada previamente"
    assert resp.status_code == 200, f"DELETE /test-control/runs/<run_id> HTTP {resp.status_code}: {corrida.seguro(resp.text)}"
    status = resp.json().get("status", "")
    assert "Rollback exitoso" in status, f"Teardown sin 'Rollback exitoso': {status!r}"


def test_99_inocuidad_final():
    """T99: Verificación de inocuidad final fuera de sandbox (conteos, estados y fases idénticos a T00)."""
    base = _env("TEST_BASE_URL").rstrip("/")
    r_login = requests.post(
        f"{base}/sesiones/",
        json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
        timeout=TIMEOUT_S,
    )
    assert r_login.status_code == 200, f"Login inocuidad final fallo: HTTP {r_login.status_code}"
    token = r_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    for id_act, base_data in _LINEA_BASE.items():
        # 1. Medicamentos
        rm = requests.get(f"{base}/suministros/medicamentos?id_activo_biologico={id_act}", headers=headers, timeout=TIMEOUT_S)
        assert rm.status_code == 200, f"GET medicamentos final {id_act} fallo: {rm.status_code}"
        meds_final = rm.json().get("total", 0)
        assert meds_final == base_data["medicamentos"], f"Activo {id_act}: conteo final ({meds_final}) != base ({base_data['medicamentos']})"

        # 2. Estado
        ra = requests.get(f"{base}/activos-biologicos/{id_act}", headers=headers, timeout=TIMEOUT_S)
        assert ra.status_code == 200, f"GET activo final {id_act} fallo: {ra.status_code}"
        estado_final = ra.json().get("id_estado")
        assert estado_final == base_data["id_estado"], f"Activo {id_act}: estado final ({estado_final}) != base ({base_data['id_estado']})"

        # 3. Fases
        rf = requests.get(f"{base}/activos-biologicos/{id_act}/fases", headers=headers, timeout=TIMEOUT_S)
        assert rf.status_code == 200, f"GET fases final {id_act} fallo: {rf.status_code}"
        fases = rf.json().get("fases") or []
        fases_activas = [f for f in fases if f.get("es_activa") is True]
        assert len(fases) == base_data["fases_total"], f"Activo {id_act}: total fases ({len(fases)}) != base ({base_data['fases_total']})"
        assert len(fases_activas) == base_data["fases_activas"], f"Activo {id_act}: fases activas ({len(fases_activas)}) != base ({base_data['fases_activas']})"

