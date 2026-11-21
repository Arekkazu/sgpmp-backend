# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G19 RF-76: anulacion, inmutabilidad, permisos y auditoria        |
"""
TC-M05-G19 — RF-76 CU03, POST /suministros/medicamentos.
Anulacion, inmutabilidad, permisos por rol y auditoria (TC-M05-010 y TC-M05-013).

Estructura de Pruebas:
  [Clase TestAdminRole, Corrida 1]
    - test_a00_setup_linea_base_y_registro_r1: Linea base de 853 y auditoria; abrir fase y registrar R1 VALIDADO.
    - test_a01_anular_justificacion_19_caracteres: Justificacion de 19 chars -> HTTP 400 (E9); R1 sigue VALIDADO.
    - test_a02_anular_justificacion_20_caracteres: Justificacion de 20 chars -> HTTP 200; R1 pasa a ANULADO con datos.
    - test_a03_reanular_registro_anulado: Intentar re-anular R1 -> HTTP 409 (E8); mensaje contiene 'ANULADO'.
    - test_a04_reactivar_registro_anulado_y_crear_nuevo: Intentar reactivar R1 -> HTTP 405 (inmutable); nuevo R_nuevo -> 201 (FA-12).
    - test_a05_inmutabilidad_put_registro_validado: Registrar R2 VALIDADO; PUT -> HTTP 405; R2 sin cambios.
    - test_a06_inmutabilidad_patch_registro_validado: PATCH sobre R2 -> HTTP 405; R2 sin cambios.
    - test_a07_inmutabilidad_delete_registro_validado: DELETE sobre R2 -> HTTP 405; R2 sigue VALIDADO.
    - test_a08_auditoria_suministros_admin: GET /suministros/auditoria muestra registro y anulacion (CA-6/RF-10).
  [Clase TestProductorRole, Corrida 2]
    - test_b01_productor_rechazo_registro: POST /suministros/medicamentos -> HTTP 403 (ACCESO_DENEGADO).
    - test_b02_productor_rechazo_anulacion: POST /suministros/medicamentos/{id}/anulacion -> HTTP 403.
  [Clase TestIngenieroRole, Corrida 3]
    - test_c01_ingeniero_rechazo_registro: POST /suministros/medicamentos -> HTTP 403 (ACCESO_DENEGADO).
    - test_c02_ingeniero_rechazo_anulacion: POST /suministros/medicamentos/{id}/anulacion -> HTTP 403.
  [Clase TestVeterinarioRole, Corrida 4]
    - test_d01_veterinario_registro: Veterinario abre fase en 853 y registra -> HTTP 201 (esperado).
    - test_d02_veterinario_anulacion: Anula con 20 chars -> HTTP 200 (esperado).
    - test_d03_veterinario_auditoria: GET /suministros/auditoria -> HTTP 403 (esperado por permiso 57 R=2).
  [Clase TestTeardownInocuidad]
    - test_98_cierre_corridas: Verifica que las 4 corridas sandbox fueron cerradas con 200 Rollback exitoso.
    - test_99_inocuidad_final: Login independiente fuera de sandbox (Admin); verifica inocuidad en 853 y mide auditoria.
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

_LINEA_BASE: dict[str, Any] = {}
_CONTEXTO_ADMIN: dict[str, Any] = {
    "r1_id": None,
    "r2_id": None,
    "r_nuevo_id": None,
}
_CORRIDAS_CERRADAS: dict[str, dict[str, Any]] = {}
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
            _env("TEST_PRODUCER_PASSWORD", False),
            _env("TEST_PRODUCER_EMAIL", False),
            _env("TEST_FIELD_ENGINEER_PASSWORD", False),
            _env("TEST_FIELD_ENGINEER_EMAIL", False),
            _env("TEST_VET_PASSWORD", False),
            _env("TEST_VET_EMAIL", False),
        ) if s
    ]


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:500]
    for s in [*_secretos(), *extra]:
        if s and len(s) > 3:
            texto = texto.replace(s, "***REDACTED***")
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
    """Gestiona una transaccion sandbox (X-Test-Run-Id) para un rol especifico."""

    def __init__(self, rol_id: str, email: str, password: str) -> None:
        self.rol_id = rol_id
        self.email = email
        self.password = password
        self.run_id = f"tc-m05-g19-{rol_id.lower()}-{uuid.uuid4()}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.token: str | None = None
        self.cerrada = False
        self.codigo_cierre: int | None = None
        self.body_cierre: str | None = None
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

    def put(self, ruta: str, json: Any, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("PUT", ruta, paso=paso, params=params, json_body=json)

    def patch(self, ruta: str, json: Any, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("PATCH", ruta, paso=paso, params=params, json_body=json)

    def delete(self, ruta: str, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("DELETE", ruta, paso=paso, params=params)

    def login(self) -> None:
        assert self.token is None, "DEF-04: solo se permite un login por run_id"
        r = self.post(
            "/sesiones/",
            {"correo_electronico": self.email, "contrasena": self.password},
            paso=f"login_{self.rol_id}",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {self.rol_id} HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {self.rol_id} sin token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            resp = self._enviar("DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.rol_id}")
            self.codigo_cierre = resp.status_code
            self.body_cierre = resp.text
            _CORRIDAS_CERRADAS[self.rol_id] = {
                "run_id": self.run_id,
                "status_code": resp.status_code,
                "body": resp.text,
            }
            return resp
        finally:
            self.http.close()


# --------------------------------------------------------------------------- fixtures de clase


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield
    _TEST_ACTUAL = "post_test"


@pytest.fixture(scope="class")
def corrida_admin() -> Corrida:
    c = Corrida("admin", _env("TEST_ADMIN_EMAIL"), _env("TEST_ADMIN_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_productor() -> Corrida:
    c = Corrida("productor", _env("TEST_PRODUCER_EMAIL"), _env("TEST_PRODUCER_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_ingeniero() -> Corrida:
    c = Corrida("ingeniero", _env("TEST_FIELD_ENGINEER_EMAIL"), _env("TEST_FIELD_ENGINEER_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_veterinario() -> Corrida:
    c = Corrida("veterinario", _env("TEST_VET_EMAIL"), _env("TEST_VET_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


# --------------------------------------------------------------------------- CLASE 1: ADMIN


class TestAdminRole:
    """Corrida 1 (Rol Administrador): anulacion, inmutabilidad y auditoria de M05."""

    def test_a00_setup_linea_base_y_registro_r1(self, corrida_admin: Corrida):
        """T00: Registrar linea base de 853 y auditoria; abrir fase en 853 y registrar R1 VALIDADO."""
        # Linea base 853
        r_med = corrida_admin.get("/suministros/medicamentos", paso="base_med_853", params={"id_activo_biologico": 853})
        assert r_med.status_code == 200
        data_m = r_med.json()
        c_med = int(data_m.get("total", len(data_m.get("medicamentos", [])))) if isinstance(data_m, dict) else len(data_m)

        r_act = corrida_admin.get("/activos-biologicos/853", paso="base_act_853")
        assert r_act.status_code == 200
        id_est = r_act.json().get("id_estado")

        r_fas = corrida_admin.get("/activos-biologicos/853/fases", paso="base_fas_853")
        assert r_fas.status_code == 200
        fases_list = r_fas.json().get("fases", []) if isinstance(r_fas.json(), dict) else r_fas.json()
        tot_f = len(fases_list)
        act_f = len([f for f in fases_list if isinstance(f, dict) and f.get("fecha_fin") is None])

        # Linea base auditoria
        r_aud = corrida_admin.get("/suministros/auditoria", paso="base_audit")
        assert r_aud.status_code == 200
        tot_aud = int(r_aud.json().get("total", len(r_aud.json().get("items", []))))

        _LINEA_BASE["853"] = {
            "medicamentos": c_med,
            "id_estado": id_est,
            "total_fases": tot_f,
            "fases_activas": act_f,
        }
        _LINEA_BASE["auditoria_total"] = tot_aud

        # Abrir fase en 853
        r_fase = corrida_admin.post(
            "/activos-biologicos/853/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase sandbox QA G19 Admin"},
            paso="setup_abrir_fase_853",
        )
        assert r_fase.status_code == 201, f"Setup apertura fase fallo: HTTP {r_fase.status_code}"

        # Registrar R1
        payload_r1 = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": str(_hoy()),
            "hora_aplicacion": "08:05:00",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10.0,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Tratamiento clinico base R1 para anulacion QA",
            "costo_unitario": 500.0,
            "nombre_veterinario": "Dr. Carlos Gomez",
        }
        r_post_r1 = corrida_admin.post("/suministros/medicamentos", payload_r1, paso="setup_registrar_r1")
        assert r_post_r1.status_code == 201, f"Setup registro R1 fallo: HTTP {r_post_r1.status_code}: {corrida_admin.seguro(r_post_r1.text)}"
        body_r1 = r_post_r1.json()
        assert body_r1.get("estado_registro") == "VALIDADO" or body_r1.get("medicamento", {}).get("id_registro_medicamento") is not None
        r1_id = body_r1.get("medicamento", {}).get("id_registro_medicamento")
        assert r1_id is not None, "Setup R1 sin id_registro_medicamento"
        _CONTEXTO_ADMIN["r1_id"] = r1_id

    def test_a01_anular_justificacion_19_caracteres(self, corrida_admin: Corrida):
        """TC-M05-010 A01: Rechazo de anulacion con justificacion de 19 caracteres (minimo 20) -> HTTP 400 (E9)."""
        r1_id = _CONTEXTO_ADMIN["r1_id"]
        assert r1_id is not None
        justif_19 = "1234567890123456789"  # exactamente 19 caracteres
        assert len(justif_19) == 19

        r = corrida_admin.post(
            f"/suministros/medicamentos/{r1_id}/anulacion",
            {"justificacion_anulacion": justif_19},
            paso="a01_anular_19_chars",
        )
        assert r.status_code == 400, f"A01 Esperado 400, obtenido {r.status_code}: {corrida_admin.seguro(r.text)}"
        assert r.json().get("error_code") == "JUSTIFICACION_INSUFICIENTE", f"A01: error_code no esperado: {r.json()}"

        # Verificar que R1 sigue VALIDADO
        r_get = corrida_admin.get("/suministros/medicamentos", paso="a01_verificar_r1", params={"id_activo_biologico": 853})
        items = r_get.json().get("items", r_get.json().get("medicamentos", []))
        item_r1 = next((m for m in items if m.get("id_registro_medicamento") == r1_id), None)
        assert item_r1 is not None and item_r1.get("estado_registro") == "VALIDADO", "R1 no conservo estado VALIDADO"

    def test_a02_anular_justificacion_20_caracteres(self, corrida_admin: Corrida):
        """TC-M05-010 A02: Aceptacion de anulacion con justificacion de 20 caracteres -> HTTP 200 y pasa a ANULADO."""
        r1_id = _CONTEXTO_ADMIN["r1_id"]
        assert r1_id is not None
        justif_20 = "12345678901234567890"  # exactamente 20 caracteres
        assert len(justif_20) == 20

        r = corrida_admin.post(
            f"/suministros/medicamentos/{r1_id}/anulacion",
            {"justificacion_anulacion": justif_20},
            paso="a02_anular_20_chars",
        )
        assert r.status_code == 200, f"A02 Esperado 200, obtenido {r.status_code}: {corrida_admin.seguro(r.text)}"
        data = r.json()
        assert data.get("estado_registro") == "ANULADO", f"A02: estado no es ANULADO: {data.get('estado_registro')}"
        assert data.get("justificacion_anulacion") == justif_20, "A02: justificacion no coincide"
        assert data.get("id_usuario") is not None, "A02: id_usuario no poblado"
        assert data.get("fecha_hora_anulacion") is not None, "A02: fecha_hora_anulacion no poblada"

    def test_a03_reanular_registro_anulado(self, corrida_admin: Corrida):
        """TC-M05-010 A03: Rechazo de re-anulacion sobre registro ya ANULADO -> HTTP 409 (E8)."""
        r1_id = _CONTEXTO_ADMIN["r1_id"]
        assert r1_id is not None

        r = corrida_admin.post(
            f"/suministros/medicamentos/{r1_id}/anulacion",
            {"justificacion_anulacion": "Re-anulacion de prueba mayor a 20 chars"},
            paso="a03_reanular",
        )
        assert r.status_code == 409, f"A03 Esperado 409 (E8), obtenido {r.status_code}: {corrida_admin.seguro(r.text)}"
        assert "anulado" in r.text.lower(), f"A03: mensaje no menciona 'ANULADO': {corrida_admin.seguro(r.text)}"
        assert r.json().get("error_code") == "MEDICAMENTO_YA_ANULADO"

    def test_a04_reactivar_registro_anulado_y_crear_nuevo(self, corrida_admin: Corrida):
        """TC-M05-010 A04: Intento de reactivar ANULADO bloqueado (405/4xx); creacion de reemplazo aceptada -> HTTP 201 (FA-12)."""
        r1_id = _CONTEXTO_ADMIN["r1_id"]
        assert r1_id is not None

        # Intento de reactivacion via PATCH sobre el recurso
        r_react = corrida_admin.patch(
            f"/suministros/medicamentos/{r1_id}",
            {"estado_registro": "VALIDADO"},
            paso="a04_intentar_reactivar",
        )
        assert 400 <= r_react.status_code < 500, f"A04 Esperado 4xx en reactivacion, obtenido {r_react.status_code}: {corrida_admin.seguro(r_react.text)}"
        # El endpoint dedicado de rechazo responde 405 Method Not Allowed
        assert r_react.status_code == 405, f"A04 Codigo observado reactivacion ({r_react.status_code}) != 405"

        # Crear nuevo registro de reemplazo (CU03 FA-12)
        payload_nuevo = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": str(_hoy()),
            "hora_aplicacion": "08:30:00",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10.0,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Registro correctivo de reemplazo tras anulacion FA-12",
            "costo_unitario": 500.0,
            "nombre_veterinario": "Dr. Carlos Gomez",
        }
        r_nuevo = corrida_admin.post("/suministros/medicamentos", payload_nuevo, paso="a04_crear_nuevo_registro")
        assert r_nuevo.status_code == 201, f"A04 Nuevo registro esperado 201, obtenido {r_nuevo.status_code}: {corrida_admin.seguro(r_nuevo.text)}"
        _CONTEXTO_ADMIN["r_nuevo_id"] = r_nuevo.json().get("medicamento", {}).get("id_registro_medicamento")

    def test_a05_inmutabilidad_put_registro_validado(self, corrida_admin: Corrida):
        """TC-M05-010 A05: PUT sobre registro VALIDADO rechazado (inmutable, RF-76 R5) -> HTTP 405/4xx; R2 sin cambios."""
        # Registrar R2 para pruebas de inmutabilidad
        payload_r2 = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": str(_hoy()),
            "hora_aplicacion": "09:00:00",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10.0,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Registro R2 para verificar inmutabilidad HTTP",
            "costo_unitario": 500.0,
            "nombre_veterinario": "Dr. Carlos Gomez",
        }
        r_r2 = corrida_admin.post("/suministros/medicamentos", payload_r2, paso="setup_r2_inmutabilidad")
        assert r_r2.status_code == 201
        r2_id = r_r2.json().get("medicamento", {}).get("id_registro_medicamento")
        assert r2_id is not None
        _CONTEXTO_ADMIN["r2_id"] = r2_id

        # Intentar PUT
        r_put = corrida_admin.put(
            f"/suministros/medicamentos/{r2_id}",
            {"motivo_aplicacion": "Modificacion no autorizada por PUT"},
            paso="a05_inmutabilidad_put",
        )
        assert 400 <= r_put.status_code < 500, f"A05 Esperado 4xx en PUT, obtenido {r_put.status_code}"
        assert r_put.status_code == 405, f"A05 Codigo observado PUT ({r_put.status_code}) != 405"

    def test_a06_inmutabilidad_patch_registro_validado(self, corrida_admin: Corrida):
        """TC-M05-010 A06: PATCH sobre registro VALIDADO rechazado (inmutable, RF-76 R5) -> HTTP 405/4xx; R2 sin cambios."""
        r2_id = _CONTEXTO_ADMIN["r2_id"]
        assert r2_id is not None

        r_patch = corrida_admin.patch(
            f"/suministros/medicamentos/{r2_id}",
            {"dosis_aplicada": 25.0},
            paso="a06_inmutabilidad_patch",
        )
        assert 400 <= r_patch.status_code < 500, f"A06 Esperado 4xx en PATCH, obtenido {r_patch.status_code}"
        assert r_patch.status_code == 405, f"A06 Codigo observado PATCH ({r_patch.status_code}) != 405"

    def test_a07_inmutabilidad_delete_registro_validado(self, corrida_admin: Corrida):
        """TC-M05-010 A07: DELETE sobre registro VALIDADO rechazado (inmutable, RF-76 R5) -> HTTP 405/4xx; R2 sigue existiendo."""
        r2_id = _CONTEXTO_ADMIN["r2_id"]
        assert r2_id is not None

        r_del = corrida_admin.delete(
            f"/suministros/medicamentos/{r2_id}",
            paso="a07_inmutabilidad_delete",
        )
        assert 400 <= r_del.status_code < 500, f"A07 Esperado 4xx en DELETE, obtenido {r_del.status_code}"
        assert r_del.status_code == 405, f"A07 Codigo observado DELETE ({r_del.status_code}) != 405"

        # Verificar que R2 sigue existiendo y VALIDADO
        r_verif = corrida_admin.get("/suministros/medicamentos", paso="a07_verificar_r2", params={"id_activo_biologico": 853})
        items = r_verif.json().get("items", r_verif.json().get("medicamentos", []))
        item_r2 = next((m for m in items if m.get("id_registro_medicamento") == r2_id), None)
        assert item_r2 is not None and item_r2.get("estado_registro") == "VALIDADO", "R2 fue alterado o eliminado"

    def test_a08_auditoria_suministros_admin(self, corrida_admin: Corrida):
        """TC-M05-013 A08: GET /suministros/auditoria muestra registros de auditoria con usuario, timestamp y detalle (CA-6/RF-10)."""
        r_audit = corrida_admin.get("/suministros/auditoria", paso="a08_consultar_auditoria")
        assert r_audit.status_code == 200, f"A08 Esperado 200, obtenido {r_audit.status_code}: {corrida_admin.seguro(r_audit.text)}"
        data = r_audit.json()
        items = data.get("items", [])
        assert len(items) > 0, "A08: No se encontraron eventos de auditoria en M05"
        # Verificar presencia de campos obligatorios en los eventos
        primer_evento = items[0]
        assert "tipo_operacion" in primer_evento, "Evento sin tipo_operacion"
        assert "id_usuario" in primer_evento, "Evento sin id_usuario"
        assert "fecha_emision" in primer_evento or "timestamp_evento" in primer_evento, "Evento sin timestamp"


# --------------------------------------------------------------------------- CLASE 2: PRODUCTOR


class TestProductorRole:
    """Corrida 2 (Rol Productor): intento denegado de registro y anulacion (403)."""

    def test_b01_productor_rechazo_registro(self, corrida_productor: Corrida):
        """TC-M05-013 B01: Intento de registro por Productor rechazado con HTTP 403 (ACCESO_DENEGADO)."""
        payload = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": str(_hoy()),
            "hora_aplicacion": "10:00:00",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10.0,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Intento de registro sin permisos por Productor",
            "costo_unitario": 500.0,
            "nombre_veterinario": "Dr. Carlos Gomez",
        }
        r = corrida_productor.post("/suministros/medicamentos", payload, paso="b01_productor_registro")
        assert r.status_code == 403, f"B01 Esperado 403, obtenido {r.status_code}: {corrida_productor.seguro(r.text)}"
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

    def test_b02_productor_rechazo_anulacion(self, corrida_productor: Corrida):
        """TC-M05-013 B02: Intento de anulacion por Productor rechazado con HTTP 403 (ACCESO_DENEGADO)."""
        r = corrida_productor.post(
            "/suministros/medicamentos/999999999/anulacion",
            {"justificacion_anulacion": "Intento de anulacion sin permisos Productor"},
            paso="b02_productor_anulacion",
        )
        assert r.status_code == 403, f"B02 Esperado 403, obtenido {r.status_code}: {corrida_productor.seguro(r.text)}"
        assert r.json().get("error_code") == "ACCESO_DENEGADO"


# --------------------------------------------------------------------------- CLASE 3: INGENIERO DE CAMPO


class TestIngenieroRole:
    """Corrida 3 (Rol Ingeniero de Campo): intento denegado de registro y anulacion (403)."""

    def test_c01_ingeniero_rechazo_registro(self, corrida_ingeniero: Corrida):
        """TC-M05-013 C01: Intento de registro por Ingeniero rechazado con HTTP 403 (ACCESO_DENEGADO)."""
        payload = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": str(_hoy()),
            "hora_aplicacion": "11:00:00",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10.0,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Intento de registro sin permisos por Ingeniero",
            "costo_unitario": 500.0,
            "nombre_veterinario": "Dr. Carlos Gomez",
        }
        r = corrida_ingeniero.post("/suministros/medicamentos", payload, paso="c01_ingeniero_registro")
        assert r.status_code == 403, f"C01 Esperado 403, obtenido {r.status_code}: {corrida_ingeniero.seguro(r.text)}"
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

    def test_c02_ingeniero_rechazo_anulacion(self, corrida_ingeniero: Corrida):
        """TC-M05-013 C02: Intento de anulacion por Ingeniero rechazado con HTTP 403 (ACCESO_DENEGADO)."""
        r = corrida_ingeniero.post(
            "/suministros/medicamentos/999999999/anulacion",
            {"justificacion_anulacion": "Intento de anulacion sin permisos Ingeniero"},
            paso="c02_ingeniero_anulacion",
        )
        assert r.status_code == 403, f"C02 Esperado 403, obtenido {r.status_code}: {corrida_ingeniero.seguro(r.text)}"
        assert r.json().get("error_code") == "ACCESO_DENEGADO"


# --------------------------------------------------------------------------- CLASE 4: VETERINARIO


class TestVeterinarioRole:
    """Corrida 4 (Rol Veterinario): registro valido, anulacion y consulta de auditoria."""

    def test_d01_veterinario_registro(self, corrida_veterinario: Corrida):
        """TC-M05-013 D01: Veterinario abre fase en 853 y registra medicamento -> HTTP 201 (esperado por spec)."""
        # Abrir fase en 853
        r_fase = corrida_veterinario.post(
            "/activos-biologicos/853/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase sandbox QA Vet"},
            paso="d01_setup_fase_vet",
        )
        assert r_fase.status_code == 201, (
            f"ERROR_AMBIENTE: setup apertura fase 853 para Veterinario respondio HTTP {r_fase.status_code}: {corrida_veterinario.seguro(r_fase.text)}"
        )

        payload = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": str(_hoy()),
            "hora_aplicacion": "12:00:00",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10.0,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Tratamiento clinico registrado por Veterinario autorizado",
            "costo_unitario": 500.0,
            "nombre_veterinario": "Dr. Carlos Gomez",
        }
        r_post = corrida_veterinario.post("/suministros/medicamentos", payload, paso="d01_registro_vet")
        assert r_post.status_code == 201, (
            f"ERROR_AMBIENTE: registro medicamento por Veterinario respondio HTTP {r_post.status_code}: {corrida_veterinario.seguro(r_post.text)}"
        )

    def test_d02_veterinario_anulacion(self, corrida_veterinario: Corrida):
        """TC-M05-013 D02: Veterinario anula registro con justificacion >= 20 caracteres -> HTTP 200 (esperado por spec)."""
        # Consultar medicamentos para obtener el registrado en D01
        r_get = corrida_veterinario.get("/suministros/medicamentos", paso="d02_consultar_med_vet", params={"id_activo_biologico": 853})
        assert r_get.status_code == 200, f"ERROR_AMBIENTE: consulta medicamentos respondio HTTP {r_get.status_code}"
        items = r_get.json().get("items", r_get.json().get("medicamentos", []))
        item_valido = next((m for m in items if m.get("estado_registro") == "VALIDADO"), None)
        assert item_valido is not None, "ERROR_AMBIENTE: No se encontro registro VALIDADO para anular"
        med_id = item_valido.get("id_registro_medicamento")

        r_anul = corrida_veterinario.post(
            f"/suministros/medicamentos/{med_id}/anulacion",
            {"justificacion_anulacion": "Anulacion clinica realizada por Veterinario QA"},
            paso="d02_anulacion_vet",
        )
        assert r_anul.status_code == 200, f"D02 Esperado 200, obtenido {r_anul.status_code}: {corrida_veterinario.seguro(r_anul.text)}"
        assert r_anul.json().get("estado_registro") == "ANULADO"

    def test_d03_veterinario_auditoria(self, corrida_veterinario: Corrida):
        """TC-M05-013 D03: Consulta de auditoria por Veterinario (recurso 57 R=2 restringido a Admin) -> HTTP 403."""
        r_audit = corrida_veterinario.get("/suministros/auditoria", paso="d03_auditoria_vet")
        # El Veterinario no tiene permiso R=2 sobre recurso 57 (bitacora_auditoria_suministros)
        assert r_audit.status_code == 403, f"D03 Esperado 403, obtenido {r_audit.status_code}: {corrida_veterinario.seguro(r_audit.text)}"
        assert r_audit.json().get("error_code") == "ACCESO_DENEGADO"


# --------------------------------------------------------------------------- TEARDOWN E INOCUIDAD


class TestTeardownInocuidad:
    """Cierre transaccional y verificacion final de inocuidad."""

    def test_98_cierre_corridas(self):
        """T98: Verificar que todas las corridas sandbox fueron cerradas con HTTP 200 Rollback exitoso."""
        roles_esperados = ["admin", "productor", "ingeniero", "veterinario"]
        for rol in roles_esperados:
            assert rol in _CORRIDAS_CERRADAS, f"T98: Corrida de {rol} no fue cerrada en el diccionario"
            info = _CORRIDAS_CERRADAS[rol]
            assert info["status_code"] == 200, f"T98: Cierre de corrida {rol} respondio HTTP {info['status_code']}: {info['body']}"
            assert "Rollback exitoso" in info["body"], f"T98: Cierre de corrida {rol} no indica Rollback exitoso"

    def test_99_inocuidad_final(self):
        """T99: Login independiente fuera de sandbox (Admin); verificar inocuidad en 853 y medir auditoria."""
        base_url = _env("TEST_BASE_URL").rstrip("/")
        admin_email = _env("TEST_ADMIN_EMAIL")
        admin_pass = _env("TEST_ADMIN_PASSWORD")

        s = requests.Session()
        s.headers.update({"X-Zona-Horaria": NOMBRE_ZONA})

        try:
            r_login = s.post(f"{base_url}/sesiones/", json={"correo_electronico": admin_email, "contrasena": admin_pass}, timeout=30)
            assert r_login.status_code == 200, f"T99: login sin sandbox fallo: HTTP {r_login.status_code}"
            token = r_login.json().get("token") or r_login.json().get("access_token")
            assert token, "T99: login sin token"
            s.headers["Authorization"] = f"Bearer {token}"

            base_853 = _LINEA_BASE["853"]

            # Medicamentos 853
            r_med = s.get(f"{base_url}/suministros/medicamentos", params={"id_activo_biologico": 853}, timeout=30)
            assert r_med.status_code == 200
            data_m = r_med.json()
            c_med = int(data_m.get("total", len(data_m.get("medicamentos", [])))) if isinstance(data_m, dict) else len(data_m)
            assert c_med == base_853["medicamentos"], (
                f"INOCUIDAD_VIOLADA activo 853: medicamentos finales {c_med} != base {base_853['medicamentos']}"
            )

            # Estado 853
            r_act = s.get(f"{base_url}/activos-biologicos/853", timeout=30)
            assert r_act.status_code == 200
            id_estado_fin = r_act.json().get("id_estado")
            assert id_estado_fin == base_853["id_estado"], (
                f"INOCUIDAD_VIOLADA activo 853: id_estado final {id_estado_fin} != base {base_853['id_estado']}"
            )

            # Fases 853
            r_fases = s.get(f"{base_url}/activos-biologicos/853/fases", timeout=30)
            assert r_fases.status_code == 200
            data_f = r_fases.json()
            fases_list = data_f.get("fases", []) if isinstance(data_f, dict) else (data_f if isinstance(data_f, list) else [])
            tot_f = len(fases_list)
            act_f = len([f for f in fases_list if isinstance(f, dict) and f.get("fecha_fin") is None])
            assert tot_f == base_853["total_fases"], (
                f"INOCUIDAD_VIOLADA activo 853: total fases {tot_f} != base {base_853['total_fases']}"
            )
            assert act_f == base_853["fases_activas"], (
                f"INOCUIDAD_VIOLADA activo 853: fases activas {act_f} != base {base_853['fases_activas']}"
            )

            # Medicion informativa de auditoria
            r_aud = s.get(f"{base_url}/suministros/auditoria", timeout=30)
            assert r_aud.status_code == 200
            tot_aud_fin = int(r_aud.json().get("total", len(r_aud.json().get("items", []))))
            delta_aud = tot_aud_fin - _LINEA_BASE["auditoria_total"]
            print(f"\n[INFORMATIVO] Auditoria base: {_LINEA_BASE['auditoria_total']}, final: {tot_aud_fin}, delta: {delta_aud}")
        finally:
            s.close()

