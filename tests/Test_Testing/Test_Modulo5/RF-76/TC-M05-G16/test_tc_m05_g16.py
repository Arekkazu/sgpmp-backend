# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G16 RF-76: evento sanitario vinculado y duplicados (sandbox)    |
"""
TC-M05-G16 — RF-76 CU03, POST /suministros/medicamentos.
Evento sanitario vinculado y registros duplicados.

Subcasos:
  (a) TC-M05-006 (A01–A04):
      - A01: Vinculo valido con evento sanitario existente del mismo activo -> HTTP 201, medicamento vinculado.
      - A02: Rechazo por evento sanitario inexistente (id 999999999) -> HTTP 422 (E12).
      - A03: Rechazo por evento sanitario perteneciente a OTRO activo -> HTTP 422 (E12).
      - A04: Aplicacion preventiva valida sin evento sanitario vinculado -> HTTP 201, id_evento_sanitario null.
  (b) TC-M05-007 (B01–B02):
      - B01: Registro duplicado exacto (mismo activo, medicamento, dosis, fecha, hora) -> HTTP 409 (E13, CA-7).
      - B02: Dosis subsecuente con hora posterior (mismo activo, medicamento, dosis, fecha) -> HTTP 201.
      - Diagnostico complementario (sin checkpoint): evaluacion con dosis distinta a misma fecha y hora.
  (c) Inocuidad y Teardown:
      - T00: Linea base de inventario y setup de precondiciones en sandbox (fase y eventos sanitarios).
      - T98: Cierre de la corrida sandbox y verificacion de Rollback exitoso.
      - T99: Verificacion de inocuidad final sin sandbox (conteos, estados y fases identicos a T00).

Diseno y Reglas Duras:
- Cliente: requests.Session contra $TEST_BASE_URL de .env.test.
- UNA sola corrida sandbox (un solo POST /sesiones/ por run_id — DEF-04).
- Headers obligatorios: X-Test-Run-Id + X-Sandbox-Secret + X-Zona-Horaria ("America/Bogota").
- periodo_retiro_dias = 0 en todos los payloads de medicamentos.
- Registro estricto de query params y sanitizacion sin fuga de credenciales.
"""
from __future__ import annotations

import json
import os
import re
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

# Linea base y estado de corrida compartida
_LINEA_BASE: dict[int, dict[str, Any]] = {}
_CONTEXTO_SETUP: dict[str, Any] = {
    "ea_id": None,
    "eb_id": None,
    "b01_id_registro": None,
    "diag_status": None,
    "diag_body": None,
}
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
            texto = texto.replace(s, "***REDACTED***")
    # Enmascarar tokens JWT si aparecen en cadenas crudas
    if "eyJ" in texto:
        texto = re.sub(r"eyJ[a-zA-Z0-9_\-\.]+", "***REDACTED_JWT***", texto)
    return texto


def _sanitizar_objeto(obj: Any, extra: tuple[str, ...] = ()) -> Any:
    if isinstance(obj, dict):
        san = {}
        for k, v in obj.items():
            if k.lower() in ("contrasena", "password", "token", "authorization", "correo_electronico", "access_token"):
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
    params: Any = None,
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
        "params": _sanitizar_objeto(params, extra),
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
    """Gestiona la transaccion sandbox (X-Test-Run-Id) con ciclo de vida completo."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g16-{uuid.uuid4()}"
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

    def _enviar(
        self,
        metodo: str,
        ruta: str,
        paso: str | None = None,
        params: Any = None,
        json_body: Any = None,
        **kw
    ) -> requests.Response:
        assert ruta.startswith("/"), f"Ruta relativa esperada: {ruta!r}"
        inicio = time.perf_counter()
        token_extra = self.token
        try:
            resp = self.http.request(metodo, self.base + ruta, timeout=TIMEOUT_S, params=params, json=json_body, **kw)
        except requests.RequestException as exc:
            _trazar(metodo, ruta, None, inicio, params=params, req_body=json_body, token_extra=token_extra, error=type(exc).__name__)
            raise ErrorConexion(paso or _TEST_ACTUAL, ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio, params=params, req_body=json_body, token_extra=token_extra)
        return resp

    def get(self, ruta: str, paso: str | None = None, params: Any = None, **kw) -> requests.Response:
        return self._enviar("GET", ruta, paso=paso, params=params, **kw)

    def post(self, ruta: str, json: Any, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("POST", ruta, paso=paso, params=params, json_body=json)

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
        token = r.json().get("token") or r.json().get("access_token")
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


# --------------------------------------------------------------------------- fixture


@pytest.fixture(scope="session")
def corrida(request: pytest.FixtureRequest) -> Corrida:
    c = Corrida()
    c.login()

    def fin():
        if not c.cerrada:
            c.cerrar()

    request.addfinalizer(fin)
    return c


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield
    _TEST_ACTUAL = "post_test"


# --------------------------------------------------------------------------- helpers de consulta


def _contar_medicamentos(c: Corrida, id_activo: int, paso: str) -> int:
    r = c.get("/suministros/medicamentos", paso=paso, params={"id_activo_biologico": id_activo})
    assert r.status_code == 200, f"Error consultando medicamentos de {id_activo}: HTTP {r.status_code}"
    data = r.json()
    if isinstance(data, dict):
        if "total" in data:
            return int(data["total"])
        if "medicamentos" in data and isinstance(data["medicamentos"], list):
            return len(data["medicamentos"])
    elif isinstance(data, list):
        return len(data)
    return 0


def _consultar_activo(c: Corrida, id_activo: int, paso: str) -> dict[str, Any]:
    r = c.get(f"/activos-biologicos/{id_activo}", paso=paso)
    assert r.status_code == 200, f"Error consultando activo {id_activo}: HTTP {r.status_code}"
    return r.json()


def _consultar_fases(c: Corrida, id_activo: int, paso: str) -> tuple[int, int]:
    r = c.get(f"/activos-biologicos/{id_activo}/fases", paso=paso)
    assert r.status_code == 200, f"Error consultando fases de {id_activo}: HTTP {r.status_code}"
    data = r.json()
    fases = data.get("fases", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    total_fases = len(fases)
    activas = len([f for f in fases if isinstance(f, dict) and f.get("fecha_fin") is None])
    return total_fases, activas


# --------------------------------------------------------------------------- tests


def test_00_linea_base_y_setup(corrida: Corrida):
    """T00: Registrar linea base de activos A=853 y B=5 y configurar precondiciones en sandbox."""
    activos = [853, 5]
    for act_id in activos:
        c_med = _contar_medicamentos(corrida, act_id, paso=f"linea_base_med_{act_id}")
        det = _consultar_activo(corrida, act_id, paso=f"linea_base_det_{act_id}")
        tot_fases, act_fases = _consultar_fases(corrida, act_id, paso=f"linea_base_fases_{act_id}")
        _LINEA_BASE[act_id] = {
            "medicamentos": c_med,
            "id_estado": det.get("id_estado"),
            "tipo": det.get("tipo"),
            "total_fases": tot_fases,
            "fases_activas": act_fases,
        }
        assert det.get("id_estado") == 1, f"Precondicion fallida: activo {act_id} no esta ACTIVO (id_estado={det.get('id_estado')})"

    # Setup en sandbox:
    # 1. Abrir fase en 853
    resp_fase = corrida.post(
        "/activos-biologicos/853/fases",
        {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase sandbox QA G16"},
        paso="setup_abrir_fase_853",
    )
    assert resp_fase.status_code == 201, f"Setup fallido: no se pudo abrir fase en 853 (HTTP {resp_fase.status_code})"

    # 2. Crear evento EA (sanitario) en 853
    resp_ea = corrida.post(
        "/activos-biologicos/853/eventos/sanitario",
        {"tipo": "DIAGNOSTICO", "diagnostico": "Diagnostico clinico preliminar QA EA"},
        paso="setup_crear_ea_853",
    )
    assert resp_ea.status_code == 201, f"Setup fallido: creacion EA en 853 fallo (HTTP {resp_ea.status_code})"
    ea_id = resp_ea.json().get("evento", {}).get("id_eventos")
    assert ea_id is not None, "Setup fallido: respuesta EA sin id_eventos"
    _CONTEXTO_SETUP["ea_id"] = ea_id

    # 3. Crear evento EB (sanitario) en activo B=5
    resp_eb = corrida.post(
        "/activos-biologicos/5/eventos/sanitario",
        {"tipo": "DIAGNOSTICO", "diagnostico": "Diagnostico clinico control QA EB"},
        paso="setup_crear_eb_5",
    )
    assert resp_eb.status_code == 201, f"Setup fallido: creacion EB en 5 fallo (HTTP {resp_eb.status_code})"
    eb_id = resp_eb.json().get("evento", {}).get("id_eventos")
    assert eb_id is not None, "Setup fallido: respuesta EB sin id_eventos"
    _CONTEXTO_SETUP["eb_id"] = eb_id


def test_a01_vinculo_evento_sanitario_valido(corrida: Corrida):
    """TC-M05-006 A01: POST con id_evento_sanitario valido de A (EA) -> HTTP 201 y vinculo confirmado."""
    ea_id = _CONTEXTO_SETUP["ea_id"]
    assert ea_id is not None, "Precondicion interna: EA no disponible"
    conteo_previo = _contar_medicamentos(corrida, 853, paso="conteo_previo_a01")

    payload = {
        "id_activo_biologico": 853,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": str(_hoy()),
        "hora_aplicacion": "08:05:00",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 10.0,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento infeccion respiratoria vinculada QA",
        "costo_unitario": 500.0,
        "nombre_veterinario": "Dr. Carlos Gomez",
        "id_evento_sanitario": ea_id,
    }
    resp = corrida.post("/suministros/medicamentos", payload, paso="a01_vinculo_valido")
    assert resp.status_code == 201, f"A01 Esperado 201, obtenido {resp.status_code}: {corrida.seguro(resp.text)}"

    body = resp.json()
    med = body.get("medicamento", {})
    assert med.get("id_evento_sanitario") == ea_id, f"A01: id_evento_sanitario en respuesta ({med.get('id_evento_sanitario')}) != esperado ({ea_id})"

    conteo_nuevo = _contar_medicamentos(corrida, 853, paso="conteo_post_a01")
    assert conteo_nuevo == conteo_previo + 1, f"A01: conteo de medicamentos ({conteo_nuevo}) != previo + 1 ({conteo_previo + 1})"


def test_a02_evento_sanitario_inexistente(corrida: Corrida):
    """TC-M05-006 A02: POST con id_evento_sanitario inexistente (999999999) -> HTTP 422 (E12)."""
    conteo_previo = _contar_medicamentos(corrida, 853, paso="conteo_previo_a02")

    payload = {
        "id_activo_biologico": 853,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": str(_hoy()),
        "hora_aplicacion": "08:10:00",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 10.0,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento con evento sanitario fantasma QA",
        "costo_unitario": 500.0,
        "nombre_veterinario": "Dr. Carlos Gomez",
        "id_evento_sanitario": 999999999,
    }
    resp = corrida.post("/suministros/medicamentos", payload, paso="a02_evento_inexistente")
    assert resp.status_code == 422, f"A02 Esperado 422 (E12), obtenido {resp.status_code}: {corrida.seguro(resp.text)}"

    msg = resp.text.lower()
    assert "evento sanitario" in msg, f"A02: mensaje no menciona 'evento sanitario': {corrida.seguro(resp.text)}"

    conteo_nuevo = _contar_medicamentos(corrida, 853, paso="conteo_post_a02")
    assert conteo_nuevo == conteo_previo, f"A02: conteo cambio tras rechazo 422 ({conteo_nuevo} != {conteo_previo})"


def test_a03_evento_sanitario_otro_activo(corrida: Corrida):
    """TC-M05-006 A03: POST sobre A (853) con id_evento_sanitario perteneciente a B (EB) -> HTTP 422 (E12)."""
    eb_id = _CONTEXTO_SETUP["eb_id"]
    assert eb_id is not None, "Precondicion interna: EB no disponible"
    conteo_previo = _contar_medicamentos(corrida, 853, paso="conteo_previo_a03")

    payload = {
        "id_activo_biologico": 853,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": str(_hoy()),
        "hora_aplicacion": "08:15:00",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 10.0,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento con evento cruzado de otro activo QA",
        "costo_unitario": 500.0,
        "nombre_veterinario": "Dr. Carlos Gomez",
        "id_evento_sanitario": eb_id,
    }
    resp = corrida.post("/suministros/medicamentos", payload, paso="a03_evento_otro_activo")
    assert resp.status_code == 422, f"A03 Esperado 422 (E12), obtenido {resp.status_code}: {corrida.seguro(resp.text)}"

    msg = resp.text.lower()
    assert "evento sanitario" in msg, f"A03: mensaje no menciona 'evento sanitario': {corrida.seguro(resp.text)}"

    conteo_nuevo = _contar_medicamentos(corrida, 853, paso="conteo_post_a03")
    assert conteo_nuevo == conteo_previo, f"A03: conteo cambio tras rechazo 422 ({conteo_nuevo} != {conteo_previo})"


def test_a04_preventivo_sin_evento_sanitario(corrida: Corrida):
    """TC-M05-006 A04: POST preventivo sin id_evento_sanitario (None) -> HTTP 201, id_evento_sanitario null."""
    conteo_previo = _contar_medicamentos(corrida, 853, paso="conteo_previo_a04")

    payload = {
        "id_activo_biologico": 853,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": str(_hoy()),
        "hora_aplicacion": "08:20:00",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 10.0,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Aplicacion preventiva rutinaria sin evento clinico QA",
        "costo_unitario": 500.0,
        "nombre_veterinario": "Dr. Carlos Gomez",
        "id_evento_sanitario": None,
    }
    resp = corrida.post("/suministros/medicamentos", payload, paso="a04_preventivo_sin_evento")
    assert resp.status_code == 201, f"A04 Esperado 201, obtenido {resp.status_code}: {corrida.seguro(resp.text)}"

    body = resp.json()
    med = body.get("medicamento", {})
    assert med.get("id_evento_sanitario") is None, f"A04: id_evento_sanitario ({med.get('id_evento_sanitario')}) no es null"

    conteo_nuevo = _contar_medicamentos(corrida, 853, paso="conteo_post_a04")
    assert conteo_nuevo == conteo_previo + 1, f"A04: conteo ({conteo_nuevo}) != previo + 1 ({conteo_previo + 1})"


def test_b01_duplicado_exacto(corrida: Corrida):
    """TC-M05-007 B01: Registro base 201, segundo registro IDENTICO -> HTTP 409 (E13, CA-7). Diagnostico exploratorio."""
    conteo_previo = _contar_medicamentos(corrida, 853, paso="conteo_previo_b01")

    payload_base = {
        "id_activo_biologico": 853,
        "nombre_medicamento": "Ivermectina",
        "fecha_aplicacion": str(_hoy()),
        "hora_aplicacion": "08:30:00",
        "via_administracion": "SUBCUTANEA",
        "dosis_aplicada": 5.0,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Desparasitacion preventiva semestral QA B01",
        "costo_unitario": 500.0,
        "nombre_veterinario": "Dr. Carlos Gomez",
        "id_evento_sanitario": None,
    }

    # Primer POST -> 201
    resp1 = corrida.post("/suministros/medicamentos", payload_base, paso="b01_primer_registro")
    assert resp1.status_code == 201, f"B01 primer registro esperado 201, obtenido {resp1.status_code}: {corrida.seguro(resp1.text)}"
    id_reg1 = resp1.json().get("medicamento", {}).get("id_registro_medicamento")
    _CONTEXTO_SETUP["b01_id_registro"] = id_reg1

    # Segundo POST IDENTICO -> 409 Conflict (E13)
    resp2 = corrida.post("/suministros/medicamentos", payload_base, paso="b01_duplicado_exacto")
    assert resp2.status_code == 409, f"B01 duplicado esperado 409 (E13), obtenido {resp2.status_code}: {corrida.seguro(resp2.text)}"
    assert "duplicad" in resp2.text.lower(), f"B01: mensaje 409 no contiene 'duplicad': {corrida.seguro(resp2.text)}"

    # Diagnostico exploratorio SIN checkpoint (mismo activo, medicamento, fecha y hora, pero DOSIS distinta)
    payload_diag = dict(payload_base)
    payload_diag["dosis_aplicada"] = 15.0
    resp_diag = corrida.post("/suministros/medicamentos", payload_diag, paso="diagnostico_dosis_distinta")
    _CONTEXTO_SETUP["diag_status"] = resp_diag.status_code
    _CONTEXTO_SETUP["diag_body"] = resp_diag.text[:200]

    # Verificar que el conteo en BD solo aumento en 1 (el primer registro valido)
    conteo_nuevo = _contar_medicamentos(corrida, 853, paso="conteo_post_b01")
    assert conteo_nuevo == conteo_previo + 1, f"B01: conteo ({conteo_nuevo}) != previo + 1 ({conteo_previo + 1})"


def test_b02_dosis_subsecuente(corrida: Corrida):
    """TC-M05-007 B02: Dosis subsecuente con hora POSTERIOR (14:00:00) -> HTTP 201 y registro independiente."""
    conteo_previo = _contar_medicamentos(corrida, 853, paso="conteo_previo_b02")
    id_reg_prev = _CONTEXTO_SETUP["b01_id_registro"]

    payload_subsecuente = {
        "id_activo_biologico": 853,
        "nombre_medicamento": "Ivermectina",
        "fecha_aplicacion": str(_hoy()),
        "hora_aplicacion": "14:00:00",
        "via_administracion": "SUBCUTANEA",
        "dosis_aplicada": 5.0,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Dosis subsecuente de refuerzo en la tarde QA B02",
        "costo_unitario": 500.0,
        "nombre_veterinario": "Dr. Carlos Gomez",
        "id_evento_sanitario": None,
    }
    resp = corrida.post("/suministros/medicamentos", payload_subsecuente, paso="b02_dosis_subsecuente")
    assert resp.status_code == 201, f"B02 esperado 201, obtenido {resp.status_code}: {corrida.seguro(resp.text)}"

    body = resp.json()
    med = body.get("medicamento", {})
    id_reg_nuevo = med.get("id_registro_medicamento")
    assert id_reg_nuevo is not None and id_reg_nuevo != id_reg_prev, f"B02: id_registro ({id_reg_nuevo}) no es valido o colisiona con previo ({id_reg_prev})"

    conteo_nuevo = _contar_medicamentos(corrida, 853, paso="conteo_post_b02")
    assert conteo_nuevo == conteo_previo + 1, f"B02: conteo ({conteo_nuevo}) != previo + 1 ({conteo_previo + 1})"


def test_98_cierre_corrida(corrida: Corrida):
    """T98: Cierre ordenado de la corrida sandbox y verificacion de Rollback exitoso."""
    resp = corrida.cerrar()
    assert resp is not None, "T98: la corrida ya estaba cerrada"
    assert resp.status_code == 200, f"T98: DELETE /test-control/runs/{corrida.run_id} respondio HTTP {resp.status_code}: {corrida.seguro(resp.text)}"
    assert "Rollback exitoso" in resp.text, f"T98: respuesta no indica 'Rollback exitoso': {corrida.seguro(resp.text)}"


def test_99_inocuidad_final():
    """T99: Login independiente fuera de sandbox e inspeccion de inocuidad en activos A=853 y B=5."""
    assert len(_LINEA_BASE) == 2, "T99: linea base incompleta"
    base_url = _env("TEST_BASE_URL").rstrip("/")
    admin_email = _env("TEST_ADMIN_EMAIL")
    admin_pass = _env("TEST_ADMIN_PASSWORD")

    s = requests.Session()
    s.headers.update({"X-Zona-Horaria": NOMBRE_ZONA})

    resp_login = s.post(
        f"{base_url}/sesiones/",
        json={"correo_electronico": admin_email, "contrasena": admin_pass},
        timeout=30,
    )
    assert resp_login.status_code == 200, f"T99: login sin sandbox fallo: HTTP {resp_login.status_code}"
    token = resp_login.json().get("token") or resp_login.json().get("access_token")
    assert token, "T99: login sin token"
    s.headers["Authorization"] = f"Bearer {token}"

    try:
        for act_id in [853, 5]:
            base = _LINEA_BASE[act_id]
            # Medicamentos
            r_med = s.get(f"{base_url}/suministros/medicamentos", params={"id_activo_biologico": act_id}, timeout=30)
            assert r_med.status_code == 200, f"T99: error consultando medicamentos de {act_id}"
            data_m = r_med.json()
            c_med = 0
            if isinstance(data_m, dict):
                c_med = int(data_m.get("total", len(data_m.get("medicamentos", []))))
            elif isinstance(data_m, list):
                c_med = len(data_m)
            assert c_med == base["medicamentos"], (
                f"INOCUIDAD_VIOLADA activo {act_id}: medicamentos finales {c_med} != base {base['medicamentos']}"
            )

            # Estado
            r_act = s.get(f"{base_url}/activos-biologicos/{act_id}", timeout=30)
            assert r_act.status_code == 200, f"T99: error consultando activo {act_id}"
            id_estado_fin = r_act.json().get("id_estado")
            assert id_estado_fin == base["id_estado"], (
                f"INOCUIDAD_VIOLADA activo {act_id}: id_estado final {id_estado_fin} != base {base['id_estado']}"
            )

            # Fases
            r_fases = s.get(f"{base_url}/activos-biologicos/{act_id}/fases", timeout=30)
            assert r_fases.status_code == 200, f"T99: error consultando fases de {act_id}"
            data_f = r_fases.json()
            fases_list = data_f.get("fases", []) if isinstance(data_f, dict) else (data_f if isinstance(data_f, list) else [])
            tot_f = len(fases_list)
            act_f = len([f for f in fases_list if isinstance(f, dict) and f.get("fecha_fin") is None])
            assert tot_f == base["total_fases"], (
                f"INOCUIDAD_VIOLADA activo {act_id}: total fases {tot_f} != base {base['total_fases']}"
            )
            assert act_f == base["fases_activas"], (
                f"INOCUIDAD_VIOLADA activo {act_id}: fases activas {act_f} != base {base['fases_activas']}"
            )
    finally:
        s.close()
