# | Fecha      | Nombre                   | Que se hizo                                                                                              |
# |------------|--------------------------|----------------------------------------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G38: Consulta de bitacora y cadena de custodia RF-80 (CU06)                                       |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G38 reevaluacion v2.0: custodia y exportacion, rangos invertidos (INC-276), permisos, sandbox en T99 |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G38 correccion: T00/T99/D07 sin SQL (RLS), D08 segun ambiente |
"""Suite de pruebas para TC-M05-G38 (RF-80 v2.0, RFC-025): Consulta y exportacion de bitacora M05.

Cubre los casos agrupados de TC-M05-G38 v2.0:
- TC-M05-096 (antes TC-M05-032): Cadena de custodia por activo y ciclo (RF-80 CA-4, CA-13, RNF-08) y exportacion
  filtrada por activo y ciclo en CSV, Excel (.xlsx) y PDF (.pdf).
  Nota sobre ordenamiento (auditoria_suministros_router.py / auditoria_suministro_read_repository.py):
  GET /suministros/auditoria admite `ordenar_por` en {"fecha_evento", "fecha_emision"}, pero la API solo
  implementa orden descendente (`.desc().nulls_last()`, sin parametro de direccion ascendente), por lo que en C01
  se verifica el orden inverso (fecha_emision no creciente en la respuesta, equivalente a no decreciente cronologico).
- TC-M05-097 (antes TC-M05-044): Criterios de filtro, permisos y manejo de errores:
  (1) Rango invertido (INC-M05-276-G38 / Dev #961 -> 400 VAL_ENTRADA en consulta y exportacion, offsets UTC),
      formato invalido ("2026-13-45" -> 4xx) y limites validos (extremos iguales, solo desde, solo hasta -> 200).
  (2) Consulta valida sin coincidencias -> 200 con items=[], total=0 (observacion sobre mensaje/auditoria de consulta).
  (3) Usuario sin permiso (Productor y Veterinario) -> 403 ACCESO_DENEGADO sin fuga de datos (observacion API M05/M01).
  (4) Fallo forzado de la consulta a BD: NO ejecutable en TEST (no es inyectable por la API publica).
- D08 (lectura de la bitacora por Contador y Revisor Fiscal, RF-80 Actores 3) no ejecutable: faltan cuentas de prueba en .env.test (ambiente). Pendiente para una ronda posterior.
- T00 (linea base) y T99 (inocuidad post-rollback) en corridas sandbox independientes de solo lectura via API autenticada.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import openpyxl
import pytest
import requests
from dotenv import dotenv_values
from pypdf import PdfReader

NOMBRE_ZONA = "America/Bogota"
ZONA_USUARIO = timezone(timedelta(hours=-5))
TIMEOUT_S = 30
ARCHIVO_TRAZA = "trazas_http.jsonl"
PREFIJO_JWT = "ey" + "J"
_LOCK_TRAZA = threading.Lock()

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

_CONTEXTO: dict[str, Any] = {
    "total_base": None,
    "ultimo_id_base": None,
    "id_activo": None,
    "id_ciclo_productivo": None,
    "id_gestion_fases": None,
    "id_activo_vacio": None,
    "c01_ids_eventos": [],
    "c01_fechas_comparacion": [],
    "c02_observacion_pdf": "",
    "d06_observacion": {},
    "d07_observacion": {},
}

_TEST_ACTUAL = "init"


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: falta la variable de entorno {nombre}")
    return valor or ""


def _hoy() -> date:
    return datetime.now(ZONA_USUARIO).date()


def _parse_iso_utc(valor: str) -> datetime:
    norm = valor.strip()
    if norm.endswith("Z"):
        norm = norm[:-1] + "+00:00"
    dt = datetime.fromisoformat(norm)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _secretos() -> list[str]:
    candidatos = (
        "TEST_SANDBOX_SECRET",
        "TEST_ADMIN_PASSWORD",
        "TEST_ADMIN_EMAIL",
        "TEST_VET_PASSWORD",
        "TEST_VET_EMAIL",
        "TEST_PRODUCER_PASSWORD",
        "TEST_PRODUCER_EMAIL",
        "TEST_ACCOUNTANT_PASSWORD",
        "TEST_ACCOUNTANT_EMAIL",
        "TEST_FISCAL_REVIEWER_PASSWORD",
        "TEST_FISCAL_REVIEWER_EMAIL",
    )
    valores: list[str] = []
    for k in candidatos:
        s = _env(k, False)
        if s:
            valores.append(s)
            if len(s) > 20 and ("PASSWORD" in k or "SECRET" in k):
                valores.append(s[-20:])
    return valores


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:600]
    for s in [*_secretos(), *extra]:
        if s and len(s) > 3:
            texto = texto.replace(s, "***REDACTED***")
    if PREFIJO_JWT in texto:
        texto = re.sub(PREFIJO_JWT + r"[a-zA-Z0-9_\-\.]+", "***REDACTED_JWT***", texto)
    return texto


def _sanitizar_objeto(obj: Any, extra: tuple[str, ...] = ()) -> Any:
    if isinstance(obj, dict):
        san: dict[str, Any] = {}
        for k, v in obj.items():
            if k.lower() in (
                "contrasena",
                "password",
                "token",
                "authorization",
                "correo_electronico",
                "access_token",
                "refresh_token",
            ):
                san[k] = "***REDACTED***"
            elif isinstance(v, (dict, list)):
                san[k] = _sanitizar_objeto(v, extra)
            elif isinstance(v, str):
                san[k] = _seguro(v, extra)
            else:
                san[k] = v
        return san
    if isinstance(obj, list):
        return [_sanitizar_objeto(x, extra) for x in obj]
    if isinstance(obj, str):
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
    test_nombre: str | None = None,
    nota: str | None = None,
) -> None:
    directorio = os.environ.get("TEST_EVIDENCE_DIR")
    if not directorio:
        return
    destino = Path(directorio) / ARCHIVO_TRAZA
    duracion_ms = round((time.perf_counter() - inicio_perf) * 1000, 2)
    now_iso = datetime.now(ZONA_USUARIO).isoformat()
    extra = (token_extra,) if token_extra else ()

    resp_body: Any = None
    server_date = ""
    status_code = None
    error_code = None
    x_request_id = ""

    if resp is not None:
        status_code = resp.status_code
        server_date = resp.headers.get("Date", "")
        x_request_id = resp.headers.get("X-Request-Id", "") or resp.headers.get("x-request-id", "")
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "json" in ctype or resp.text.lstrip().startswith(("{", "[")):
            try:
                resp_body = resp.json()
                if isinstance(resp_body, dict):
                    error_code = resp_body.get("error_code")
            except Exception:
                resp_body = resp.text[:400]
        elif "application/pdf" in ctype or "openxmlformats" in ctype:
            resp_body = f"<archivo binario content_type={ctype} bytes={len(resp.content)}>"
        else:
            resp_body = resp.text[:400]

    registro: dict[str, Any] = {
        "timestamp_local": now_iso,
        "server_date": server_date,
        "duracion_ms": duracion_ms,
        "test": test_nombre or _TEST_ACTUAL,
        "metodo": metodo,
        "ruta": ruta,
        "params": _sanitizar_objeto(params, extra),
        "status_code": status_code,
        "error_code": error_code,
        "x_request_id": x_request_id,
        "error_conexion": error,
        "request_body": _sanitizar_objeto(req_body, extra),
        "response_body": _sanitizar_objeto(resp_body, extra),
    }
    if nota:
        registro["nota"] = _seguro(nota, extra)

    with _LOCK_TRAZA:
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
        super().__init__(f"ERROR_CONEXION paso={paso} ruta={ruta}: {type(original).__name__} ({original})")


class CorridaSandbox:
    """Maneja un run_id de sandbox y permite logins unicos por rol dentro del mismo run_id."""

    def __init__(self, etiqueta: str) -> None:
        self.etiqueta = etiqueta
        self.run_id = f"tc-m05-g38-{etiqueta}-{uuid.uuid4().hex[:8]}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.cerrada = False
        self.tokens_por_cuenta: dict[str, str] = {}
        self.sesiones: dict[str, requests.Session] = {}
        self._base_headers = {
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "X-Zona-Horaria": NOMBRE_ZONA,
        }

    def _session_for(self, rol_key: str) -> requests.Session:
        if rol_key not in self.sesiones:
            s = requests.Session()
            s.headers.update(self._base_headers)
            self.sesiones[rol_key] = s
        return self.sesiones[rol_key]

    def seguro(self, texto: str) -> str:
        return _seguro(texto, tuple(self.tokens_por_cuenta.values()))

    def login_actor(self, rol_key: str, email_env: str, pass_env: str) -> str:
        assert rol_key not in self.tokens_por_cuenta, (
            f"Regla R2/login unico: solo se permite un login por cuenta ({rol_key}) en run_id={self.run_id}"
        )
        email = _env(email_env, obligatoria=True)
        pwd = _env(pass_env, obligatoria=True)
        s = self._session_for(rol_key)
        r = self.request(rol_key, "POST", "/sesiones/", json_body={"correo_electronico": email, "contrasena": pwd}, paso=f"login_{rol_key}")
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {rol_key} HTTP {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {rol_key} sin token"
        self.tokens_por_cuenta[rol_key] = token
        s.headers["Authorization"] = f"Bearer {token}"
        return token

    def request(
        self,
        rol_key: str,
        metodo: str,
        ruta: str,
        paso: str | None = None,
        params: Any = None,
        json_body: Any = None,
        nota: str | None = None,
        **kw,
    ) -> requests.Response:
        assert ruta.startswith("/"), f"Ruta relativa esperada: {ruta!r}"
        s = self._session_for(rol_key)
        tok = self.tokens_por_cuenta.get(rol_key)
        inicio = time.perf_counter()
        try:
            resp = s.request(metodo, self.base + ruta, timeout=TIMEOUT_S, params=params, json=json_body, **kw)
        except requests.RequestException as exc:
            _trazar(metodo, ruta, None, inicio, params=params, req_body=json_body, token_extra=tok, error=type(exc).__name__, nota=nota)
            raise ErrorConexion(paso or _TEST_ACTUAL, ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio, params=params, req_body=json_body, token_extra=tok, nota=nota)
        return resp

    def get(self, rol_key: str, ruta: str, paso: str | None = None, params: Any = None, nota: str | None = None, **kw) -> requests.Response:
        return self.request(rol_key, "GET", ruta, paso=paso, params=params, nota=nota, **kw)

    def post(self, rol_key: str, ruta: str, json_body: Any, paso: str | None = None, params: Any = None, nota: str | None = None) -> requests.Response:
        return self.request(rol_key, "POST", ruta, paso=paso, params=params, json_body=json_body, nota=nota)

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            rol_close = "admin" if "admin" in self.sesiones else next(iter(self.sesiones), "close")
            return self.request(rol_close, "DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.etiqueta}")
        finally:
            for s in list(self.sesiones.values()):
                s.close()


_PRINCIPAL: CorridaSandbox | None = None


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield


@pytest.fixture(scope="module", autouse=True)
def _respaldo_cierre_principal():
    yield
    if _PRINCIPAL is not None and not _PRINCIPAL.cerrada:
        _PRINCIPAL.cerrar()


def _principal() -> CorridaSandbox:
    global _PRINCIPAL
    if _PRINCIPAL is None:
        _PRINCIPAL = CorridaSandbox("adm")
        _PRINCIPAL.login_actor("admin", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
    return _PRINCIPAL


def _leer_estado_auditoria_api(corrida: CorridaSandbox, paso: str) -> tuple[int, int]:
    """Obtiene total y ultimo id_auditoria_suministro mediante GET /suministros/auditoria."""
    r_aud = corrida.get(
        "admin",
        "/suministros/auditoria",
        paso=paso,
        params={"pagina": 1, "registros_por_pagina": 1, "ordenar_por": "fecha_evento"},
    )
    assert r_aud.status_code == 200, (
        f"{paso} fallo en GET /suministros/auditoria: HTTP {r_aud.status_code} "
        f"[X-Request-Id={r_aud.headers.get('X-Request-Id', '')}]"
    )
    body = r_aud.json()
    total_api = body.get("total")
    assert isinstance(total_api, int), f"{paso} esperaba total entero, obtenido {total_api!r}"
    items = body.get("items") or []
    ultimo_id_api = int(items[0]["id_auditoria_suministro"]) if items else 0
    return total_api, ultimo_id_api


# =============================================================================
# T00 - Linea base (corrida sandbox independiente de solo lectura)
# =============================================================================

def test_t00_linea_base():
    """T00 (Harness / Inocuidad): /test-control/query no ve filas de modulo5 (FORCE RLS sin app.current_user_id); la linea base se toma por la API autenticada."""
    c = CorridaSandbox("inobase")
    try:
        c.login_actor("admin", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        total_api, ultimo_id_api = _leer_estado_auditoria_api(c, "t00_get_auditoria_base")
        _CONTEXTO["total_base"] = total_api
        _CONTEXTO["ultimo_id_base"] = ultimo_id_api
    finally:
        r_close = c.cerrar()
        assert r_close is not None and r_close.status_code == 200, (
            f"T00 cierre sandbox inesperado: {r_close.status_code if r_close else None}"
        )


# =============================================================================
# CORRIDA PRINCIPAL (Admin + Productor + Veterinario en el mismo run_id)
# =============================================================================

def test_c01_cadena_custodia():
    """C01 (TC-M05-096; RF-80 v2.0 CA-4, CA-13, RNF-08): Cadena de custodia filtrada por activo y ciclo.

    Nota sobre ordenamiento: GET /suministros/auditoria solo soporta orden descendente en
    `ordenar_por` (auditoria_suministro_read_repository.py `.desc().nulls_last()`), sin parametro
    de direccion ascendente; por ello se verifica el orden cronologico inverso (`fecha_emision` no creciente).
    """
    c = _principal()
    hoy = _hoy()
    fecha_ciclo = (hoy - timedelta(days=20)).isoformat()
    tag = uuid.uuid4().hex[:8]

    # 1. Crear activo POBLACIONAL de prueba y abrir fase productiva
    r_act = c.post(
        "admin",
        "/activos-biologicos",
        {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G38-{tag}",
            "cantidad_inicial": 40,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
            "peso_actual": 18.0,
        },
        paso="c01_crear_activo_poblacional",
    )
    assert r_act.status_code == 201, (
        f"PRECONDICION_NO_CUMPLIDA creando activo POBLACIONAL: HTTP {r_act.status_code} "
        f"[X-Request-Id={r_act.headers.get('X-Request-Id', '')}]: {c.seguro(r_act.text)}"
    )
    id_activo = r_act.json().get("id_activo_biologico")
    assert id_activo is not None
    _CONTEXTO["id_activo"] = id_activo

    r_fase = c.post(
        "admin",
        f"/activos-biologicos/{id_activo}/fases",
        {"id_ciclo_productiva": 1, "motivo_cambio": "Fase abierta para cadena de custodia TC-M05-G38"},
        paso="c01_abrir_fase",
    )
    assert r_fase.status_code in (200, 201), (
        f"PRECONDICION_NO_CUMPLIDA abriendo fase: HTTP {r_fase.status_code} "
        f"[X-Request-Id={r_fase.headers.get('X-Request-Id', '')}]: {c.seguro(r_fase.text)}"
    )
    _CONTEXTO["id_gestion_fases"] = r_fase.json().get("id_gestion_fases")

    # 2. Dos registros RF-78 validos (SERVICIO_VETERINARIO, unidad "servicio")
    r_s1 = c.post(
        "admin",
        "/suministros/costeo-directo",
        {
            "id_activo_biologico": id_activo,
            "tipo_suministro": "SERVICIO_VETERINARIO",
            "cantidad": 1.0,
            "unidad_medida": "servicio",
            "precio_unitario": 55000.0,
            "fecha_aplicacion": hoy.isoformat(),
            "justificacion_precio": "Servicio veterinario 1 TC-M05-G38",
            "id_idempotencia": str(uuid.uuid4()),
        },
        paso="c01_registro_rf78_1",
    )
    assert r_s1.status_code == 200, (
        f"Fallo registro RF-78 #1: HTTP {r_s1.status_code} [X-Request-Id={r_s1.headers.get('X-Request-Id', '')}]: {c.seguro(r_s1.text)}"
    )
    id_ciclo = r_s1.json()["registro"]["id_ciclo_productivo"]
    _CONTEXTO["id_ciclo_productivo"] = id_ciclo

    time.sleep(0.05)

    r_s2 = c.post(
        "admin",
        "/suministros/costeo-directo",
        {
            "id_activo_biologico": id_activo,
            "tipo_suministro": "SERVICIO_VETERINARIO",
            "cantidad": 2.0,
            "unidad_medida": "servicio",
            "precio_unitario": 40000.0,
            "fecha_aplicacion": hoy.isoformat(),
            "justificacion_precio": "Servicio veterinario 2 TC-M05-G38",
            "id_idempotencia": str(uuid.uuid4()),
        },
        paso="c01_registro_rf78_2",
    )
    assert r_s2.status_code == 200, (
        f"Fallo registro RF-78 #2: HTTP {r_s2.status_code} [X-Request-Id={r_s2.headers.get('X-Request-Id', '')}]: {c.seguro(r_s2.text)}"
    )

    time.sleep(0.05)

    # 3. Una consulta de historial RF-81
    r_hist = c.get(
        "admin",
        "/suministros/historial",
        paso="c01_consulta_historial_rf81",
        params={"id_activo_biologico": id_activo, "id_ciclo_productivo": id_ciclo},
    )
    assert r_hist.status_code == 200, (
        f"Fallo consulta historial RF-81: HTTP {r_hist.status_code} [X-Request-Id={r_hist.headers.get('X-Request-Id', '')}]: {c.seguro(r_hist.text)}"
    )

    # 4. Consultar bitacora filtrada por id_activo_biologico + id_ciclo_productivo ordenada por fecha_emision
    r_aud_em = c.get(
        "admin",
        "/suministros/auditoria",
        paso="c01_auditoria_por_fecha_emision",
        params={
            "id_activo_biologico": id_activo,
            "id_ciclo_productivo": id_ciclo,
            "ordenar_por": "fecha_emision",
            "registros_por_pagina": 200,
        },
    )
    assert r_aud_em.status_code == 200, (
        f"RF-80 CA-4/RNF-08: HTTP {r_aud_em.status_code} en GET /suministros/auditoria "
        f"[X-Request-Id={r_aud_em.headers.get('X-Request-Id', '')}]"
    )
    body_em = r_aud_em.json()
    items_em = body_em.get("items", [])
    total_em = body_em.get("total", 0)
    assert total_em == len(items_em), (
        f"Paginacion incompleta en C01: total={total_em} vs items={len(items_em)}"
    )
    assert len(items_em) >= 3, (
        f"TC-M05-096 / RF-80 CA-4: se esperaban al menos 3 eventos (2 registros + 1 consulta historial), obtenidos {len(items_em)}"
    )

    # Todos del activo y ciclo, sin ajenos; doble timestamp presente en cada uno
    ids_eventos: list[int] = []
    fechas_emision: list[datetime] = []
    pares_fecha_obs: list[dict[str, Any]] = []
    tipos_vistos: list[str] = []

    for ev in items_em:
        eid = ev.get("id_auditoria_suministro")
        ids_eventos.append(eid)
        tipos_vistos.append(ev.get("tipo_operacion", ""))
        assert ev.get("id_activo_biologico") == id_activo, (
            f"RF-80 CA-4: evento ajeno en filtro activo={id_activo}: id_auditoria={eid}, id_activo={ev.get('id_activo_biologico')}"
        )
        assert ev.get("id_ciclo_productivo") == id_ciclo, (
            f"RF-80 CA-4: evento ajeno en filtro ciclo={id_ciclo}: id_auditoria={eid}, id_ciclo={ev.get('id_ciclo_productivo')}"
        )
        assert ev.get("fecha_emision") is not None, (
            f"RF-80 CA-13 / RNF-08: evento {eid} ({ev.get('tipo_operacion')}) carece de fecha_emision"
        )
        assert ev.get("fecha_evento") is not None, (
            f"RF-80 CA-13 / RNF-08: evento {eid} ({ev.get('tipo_operacion')}) carece de fecha_evento"
        )
        fechas_emision.append(_parse_iso_utc(ev["fecha_emision"]))
        pares_fecha_obs.append({
            "id": eid,
            "tipo": ev.get("tipo_operacion"),
            "fecha_evento": ev.get("fecha_evento"),
            "fecha_emision": ev.get("fecha_emision"),
        })

    _CONTEXTO["c01_ids_eventos"] = ids_eventos
    _CONTEXTO["c01_fechas_comparacion"] = pares_fecha_obs

    # Presencia de eventos esperados del flujo (2 SUMINISTRO_REGISTRADO + >= 1 CONSULTA_HISTORIAL_EJECUTADA)
    reg_events = [ev for ev in items_em if ev.get("tipo_operacion") in ("SUMINISTRO_REGISTRADO", "SUMINISTRO_CORREGIDO")]
    assert sum(1 for ev in items_em if ev.get("tipo_operacion") == "SUMINISTRO_REGISTRADO") == 2, (
        f"RF-80 CA-4 / TC-M05-096: se esperaban exactamente 2 eventos SUMINISTRO_REGISTRADO, vistos: {tipos_vistos}"
    )
    assert sum(1 for ev in items_em if ev.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA") >= 1, (
        f"RF-80 / RF-81: se esperaba al menos 1 CONSULTA_HISTORIAL_EJECUTADA en la bitacora, vistos: {tipos_vistos}"
    )

    for ev in reg_events:
        assert ev.get("costo_afectado") is not None, (
            f"RF-80 CA-4 / Restriccion 8: evento de registro {ev.get('id_auditoria_suministro')} sin costo_afectado"
        )
        assert ev.get("origen_precio") is not None, (
            f"RF-80 CA-4 / Restriccion 8: evento de registro {ev.get('id_auditoria_suministro')} sin origen_precio"
        )

    # Orden inverso (API descendente): fecha_emision[i] >= fecha_emision[i+1] (al invertir es no decreciente)
    fechas_crono = list(reversed(fechas_emision))
    for i in range(len(fechas_crono) - 1):
        assert fechas_crono[i] <= fechas_crono[i + 1], (
            f"RF-80 CA-4 / CA-13 / TC-M05-096: secuencia fuera de orden por fecha_emision: "
            f"{fechas_crono[i].isoformat()} > {fechas_crono[i + 1].isoformat()}"
        )

    # 5. Ordenar por fecha_evento tambien responde 200 (RNF-08)
    r_aud_ev = c.get(
        "admin",
        "/suministros/auditoria",
        paso="c01_auditoria_por_fecha_evento",
        params={
            "id_activo_biologico": id_activo,
            "id_ciclo_productivo": id_ciclo,
            "ordenar_por": "fecha_evento",
            "registros_por_pagina": 200,
        },
    )
    assert r_aud_ev.status_code == 200, (
        f"RF-80 RNF-08: ordenar_por=fecha_evento retorno HTTP {r_aud_ev.status_code} "
        f"[X-Request-Id={r_aud_ev.headers.get('X-Request-Id', '')}]"
    )
    assert r_aud_ev.json().get("total") == total_em, (
        f"RF-80 RNF-08: total distinto entre fecha_emision ({total_em}) y fecha_evento ({r_aud_ev.json().get('total')})"
    )


def test_c02_exportacion_con_filtro():
    """C02 (TC-M05-096; RF-80 v2.0 CA-4 — RF-80 no define formatos): Exportacion filtrada en CSV, XLSX y PDF."""
    c = _principal()
    id_activo = _CONTEXTO.get("id_activo")
    id_ciclo = _CONTEXTO.get("id_ciclo_productivo")
    assert id_activo is not None and id_ciclo is not None, "PRECONDICION_NO_CUMPLIDA: C01 no fijo activo y ciclo"

    # Referencia exacta de eventos del filtro en la corrida
    r_ref = c.get(
        "admin",
        "/suministros/auditoria",
        paso="c02_referencia_filtro",
        params={"id_activo_biologico": id_activo, "id_ciclo_productivo": id_ciclo, "registros_por_pagina": 200},
    )
    assert r_ref.status_code == 200
    ids_esperados = {int(e["id_auditoria_suministro"]) for e in r_ref.json().get("items", [])}
    assert len(ids_esperados) >= 3, f"PRECONDICION_NO_CUMPLIDA: pocos eventos de referencia ({ids_esperados})"

    # 1. CSV
    r_csv = c.get(
        "admin",
        "/suministros/auditoria/exportar",
        paso="c02_exportar_csv",
        params={"id_activo_biologico": id_activo, "id_ciclo_productivo": id_ciclo, "formato": "csv"},
    )
    assert r_csv.status_code == 200, (
        f"TC-M05-096 exportar CSV: HTTP {r_csv.status_code} [X-Request-Id={r_csv.headers.get('X-Request-Id', '')}]"
    )
    assert "text/csv" in (r_csv.headers.get("content-type") or "").lower()
    rows_csv = list(csv.DictReader(io.StringIO(r_csv.content.decode("utf-8-sig"))))
    assert len(rows_csv) == len(ids_esperados), (
        f"TC-M05-096 exportar CSV: cantidad de filas {len(rows_csv)} != esperada {len(ids_esperados)}"
    )
    ids_csv = {int(row["id_auditoria_suministro"]) for row in rows_csv}
    assert ids_csv == ids_esperados, (
        f"TC-M05-096 exportar CSV: IDs exportados {sorted(ids_csv)} != esperados {sorted(ids_esperados)}"
    )
    for row in rows_csv:
        assert int(row["id_activo_biologico"]) == id_activo and int(row["id_ciclo_productivo"]) == id_ciclo

    # 2. XLSX (openpyxl)
    r_xlsx = c.get(
        "admin",
        "/suministros/auditoria/exportar",
        paso="c02_exportar_xlsx",
        params={"id_activo_biologico": id_activo, "id_ciclo_productivo": id_ciclo, "formato": "xlsx"},
    )
    assert r_xlsx.status_code == 200, (
        f"TC-M05-096 exportar XLSX: HTTP {r_xlsx.status_code} [X-Request-Id={r_xlsx.headers.get('X-Request-Id', '')}]"
    )
    assert "openxmlformats" in (r_xlsx.headers.get("content-type") or "").lower()
    assert r_xlsx.content[:4] == b"PK\x03\x04", "El XLSX exportado no tiene firma ZIP valida"

    wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content), data_only=True)
    ws = wb.active
    assert ws is not None
    fila_hdr = None
    col_id = None
    for idx_row, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for idx_col, val in enumerate(row):
            if str(val or "").strip() in ("N.º de evento", "N.° de evento", "id_auditoria_suministro"):
                fila_hdr = idx_row
                col_id = idx_col
                break
        if fila_hdr is not None:
            break
    assert fila_hdr is not None and col_id is not None, (
        f"TC-M05-096 exportar XLSX: no se encontro columna de ID de evento en hoja {ws.title!r}"
    )
    ids_xlsx_list: list[int] = []
    for row in ws.iter_rows(min_row=fila_hdr + 1, values_only=True):
        val = row[col_id] if col_id < len(row) else None
        if val is not None and str(val).strip().isdigit():
            ids_xlsx_list.append(int(str(val).strip()))
    assert len(ids_xlsx_list) == len(ids_esperados), (
        f"TC-M05-096 exportar XLSX: filas de eventos {len(ids_xlsx_list)} != esperadas {len(ids_esperados)}"
    )
    assert set(ids_xlsx_list) == ids_esperados, (
        f"TC-M05-096 exportar XLSX: IDs {sorted(set(ids_xlsx_list))} != esperados {sorted(ids_esperados)}"
    )

    # 3. PDF (extraer texto via pypdf y comprobar IDs)
    r_pdf = c.get(
        "admin",
        "/suministros/auditoria/exportar",
        paso="c02_exportar_pdf",
        params={"id_activo_biologico": id_activo, "id_ciclo_productivo": id_ciclo, "formato": "pdf"},
    )
    assert r_pdf.status_code == 200, (
        f"TC-M05-096 exportar PDF: HTTP {r_pdf.status_code} [X-Request-Id={r_pdf.headers.get('X-Request-Id', '')}]"
    )
    assert "application/pdf" in (r_pdf.headers.get("content-type") or "").lower()
    assert r_pdf.content[:4] == b"%PDF", "El PDF exportado no tiene firma %PDF"
    assert len(r_pdf.content) > 0, "El PDF exportado esta vacio"

    reader = PdfReader(io.BytesIO(r_pdf.content))
    texto_pdf = "\n".join((p.extract_text() or "") for p in reader.pages)
    if texto_pdf.strip():
        faltantes = [eid for eid in sorted(ids_esperados) if str(eid) not in texto_pdf]
        assert not faltantes, (
            f"TC-M05-096 exportar PDF: IDs faltantes en texto extraido {faltantes} de {sorted(ids_esperados)}"
        )
        _CONTEXTO["c02_observacion_pdf"] = (
            f"PDF extraible con pypdf ({len(reader.pages)} pagina(s), {len(r_pdf.content)} bytes): "
            f"todos los IDs presentes {sorted(ids_esperados)}."
        )
    else:
        _CONTEXTO["c02_observacion_pdf"] = (
            f"PDF no vacio ({len(r_pdf.content)} bytes, {len(reader.pages)} pagina(s)), texto no extraible por pypdf."
        )


def test_d01_rango_invertido():
    """D01 (TC-M05-097 (1) / criterio INC-M05-276-G38): GET /suministros/auditoria con fecha_desde > fecha_hasta -> 400 VAL_ENTRADA."""
    c = _principal()
    hoy = _hoy().isoformat()
    r = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d01_rango_invertido",
        params={"fecha_desde": f"{hoy}T12:00:00Z", "fecha_hasta": f"{hoy}T10:00:00Z"},
    )
    assert r.status_code == 400, (
        f"INC-M05-276-G38 / TC-M05-097 (1): esperado HTTP 400, obtenido {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    body = r.json()
    assert body.get("error_code") == "VAL_ENTRADA", (
        f"INC-M05-276-G38: error_code esperado VAL_ENTRADA, obtenido {body.get('error_code')!r}"
    )
    campos = [f.get("field") for f in body.get("fields", []) if isinstance(f, dict)]
    assert "fecha_hasta" in campos, f"INC-M05-276-G38: campo esperado 'fecha_hasta' en fields={campos!r}"
    msg = (body.get("message") or "").lower()
    assert "corrig" in msg, f"INC-M05-276-G38: mensaje no solicita corregir: {body.get('message')!r}"
    assert "items" not in body, "Respuesta 400 no debe contener 'items'"


def test_d02_rango_invertido_offsets_distintos():
    """D02 (INC-M05-276-G38): Comparacion por instante UTC: T10:00:00-05:00 (15:00Z) > T14:00:00Z -> 400 VAL_ENTRADA."""
    c = _principal()
    hoy = _hoy().isoformat()
    r = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d02_rango_invertido_offsets",
        params={"fecha_desde": f"{hoy}T10:00:00-05:00", "fecha_hasta": f"{hoy}T14:00:00Z"},
    )
    assert r.status_code == 400, (
        f"INC-M05-276-G38 (offsets UTC): esperado HTTP 400, obtenido {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    body = r.json()
    assert body.get("error_code") == "VAL_ENTRADA", f"error_code={body.get('error_code')!r}"
    campos = [f.get("field") for f in body.get("fields", []) if isinstance(f, dict)]
    assert "fecha_hasta" in campos, f"fields={campos!r}"
    assert "items" not in body


def test_d03_rango_invertido_exportacion():
    """D03 (TC-M05-097 (1) / INC-M05-276-G38): GET /suministros/auditoria/exportar con fecha_desde > fecha_hasta -> 400 sin archivo."""
    c = _principal()
    hoy = _hoy().isoformat()
    r = c.get(
        "admin",
        "/suministros/auditoria/exportar",
        paso="d03_rango_invertido_exportar",
        params={"formato": "csv", "fecha_desde": f"{hoy}T12:00:00Z", "fecha_hasta": f"{hoy}T10:00:00Z"},
    )
    assert r.status_code == 400, (
        f"INC-M05-276-G38 (exportar): esperado HTTP 400, obtenido {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    ctype = (r.headers.get("content-type") or "").lower()
    assert "application/json" in ctype and "text/csv" not in ctype, f"Content-Type inesperado: {ctype!r}"
    assert not r.headers.get("content-disposition"), f"No debio entregar archivo: {r.headers.get('content-disposition')!r}"
    body = r.json()
    assert body.get("error_code") == "VAL_ENTRADA"


def test_d04_formato_fecha_incorrecto():
    """D04 (TC-M05-097 (1)): fecha_desde='2026-13-45' -> 4xx (400 o 422) con campo identificado, nunca 200 ni 500."""
    c = _principal()
    r = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d04_formato_fecha_incorrecto",
        params={"fecha_desde": "2026-13-45"},
    )
    assert r.status_code in (400, 422), (
        f"TC-M05-097 (1) formato invalido: esperado HTTP 400/422, obtenido {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    body = r.json()
    assert body.get("error_code") is not None
    campos = [str(f.get("field", "")) for f in body.get("fields", []) if isinstance(f, dict)]
    assert any("fecha_desde" in f for f in campos), (
        f"TC-M05-097 (1): campo 'fecha_desde' no identificado en fields={campos!r}"
    )
    assert "items" not in body


def test_d05_limites_validos():
    """D05 (INC-M05-276-G38 / RF-80): Extremos iguales, solo fecha_desde y solo fecha_hasta responden HTTP 200."""
    c = _principal()
    hoy = _hoy().isoformat()

    # 1. Extremos iguales
    r_eq = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d05_extremos_iguales",
        params={"fecha_desde": f"{hoy}T00:00:00Z", "fecha_hasta": f"{hoy}T00:00:00Z", "registros_por_pagina": 5},
    )
    assert r_eq.status_code == 200 and "items" in r_eq.json(), (
        f"INC-M05-276-G38 extremos iguales: HTTP {r_eq.status_code} [X-Request-Id={r_eq.headers.get('X-Request-Id', '')}]"
    )

    # 2. Solo fecha_desde
    r_desde = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d05_solo_fecha_desde",
        params={"fecha_desde": f"{hoy}T00:00:00Z", "registros_por_pagina": 5},
    )
    assert r_desde.status_code == 200 and "items" in r_desde.json(), (
        f"INC-M05-276-G38 solo fecha_desde: HTTP {r_desde.status_code} [X-Request-Id={r_desde.headers.get('X-Request-Id', '')}]"
    )

    # 3. Solo fecha_hasta
    r_hasta = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d05_solo_fecha_hasta",
        params={"fecha_hasta": f"{hoy}T23:59:59Z", "registros_por_pagina": 5},
    )
    assert r_hasta.status_code == 200 and "items" in r_hasta.json(), (
        f"INC-M05-276-G38 solo fecha_hasta: HTTP {r_hasta.status_code} [X-Request-Id={r_hasta.headers.get('X-Request-Id', '')}]"
    )


def test_d06_sin_coincidencias():
    """D06 (TC-M05-097 (2) / INC-M05-276-G38): Filtro valido sin resultados -> HTTP 200 con items=[] y total=0.

    Nota: No se aserta mensaje 'sin eventos' ni evento de auditoria de consulta porque no existe
    especificacion CU06 en el repositorio y RF-80 v2.0 no define evento de consulta de bitacora.
    Se registra lo observado (claves, ausencia/presencia de mensaje y delta en bitacora) para el informe.
    """
    c = _principal()
    hoy = _hoy()
    fecha_ciclo = (hoy - timedelta(days=5)).isoformat()
    tag = uuid.uuid4().hex[:8]

    # Activo de prueba en sandbox sin operaciones en M05
    r_act = c.post(
        "admin",
        "/activos-biologicos",
        {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G38-VACIO-{tag}",
            "cantidad_inicial": 10,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
            "peso_actual": 12.0,
        },
        paso="d06_crear_activo_sin_eventos",
    )
    assert r_act.status_code == 201, f"Fallo creando activo vacio para D06: HTTP {r_act.status_code}"
    id_activo_vacio = r_act.json().get("id_activo_biologico")
    _CONTEXTO["id_activo_vacio"] = id_activo_vacio

    total_antes = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d06_total_antes",
        params={"pagina": 1, "registros_por_pagina": 1},
    ).json().get("total", 0)

    r_vacio = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d06_consulta_sin_coincidencias",
        params={
            "id_activo_biologico": id_activo_vacio,
            "fecha_desde": f"{hoy.isoformat()}T00:00:00Z",
            "fecha_hasta": f"{hoy.isoformat()}T23:59:59Z",
        },
    )
    assert r_vacio.status_code == 200, (
        f"TC-M05-097 (2) / INC-M05-276-G38: esperado HTTP 200, obtenido {r_vacio.status_code} "
        f"[X-Request-Id={r_vacio.headers.get('X-Request-Id', '')}]"
    )
    body = r_vacio.json()
    assert body.get("items") == [], f"Esperado items=[], obtenido {body.get('items')!r}"
    assert body.get("total") == 0, f"Esperado total=0, obtenido {body.get('total')!r}"

    total_despues = c.get(
        "admin",
        "/suministros/auditoria",
        paso="d06_total_despues",
        params={"pagina": 1, "registros_por_pagina": 1},
    ).json().get("total", 0)

    _CONTEXTO["d06_observacion"] = {
        "x_request_id": r_vacio.headers.get("X-Request-Id", ""),
        "claves_cuerpo": list(body.keys()),
        "mensaje_en_cuerpo": body.get("mensaje") if "mensaje" in body else body.get("message"),
        "total_bitacora_antes": total_antes,
        "total_bitacora_despues": total_despues,
        "delta_eventos_auditoria_consulta": total_despues - total_antes,
    }


def test_d07_sin_permiso():
    """D07 (TC-M05-097 (3) / RF-80 RNF-05 / RBAC recurso 57): Productor y Veterinario -> 403 ACCESO_DENEGADO sin items.

    Nota: Ni RF-80 v2.0 (que solo exige evento de seguridad al intentar modificar/eliminar en CA-2)
    ni CU06 literal (ausente del repositorio) exigen evento de seguridad por 403 de lectura;
    como observacion sin asercion se registra el total antes/despues por API en M05 y M01.
    """
    c = _principal()

    # Login unico dentro de la misma corrida principal para Productor y Veterinario
    c.login_actor("productor", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
    c.login_actor("veterinario", "TEST_VET_EMAIL", "TEST_VET_PASSWORD")

    # Observacion previa (API Admin, sin asercion) justo antes de las solicitudes denegadas
    r_m5_antes = c.get("admin", "/suministros/auditoria", paso="d07_obs_m5_antes", params={"pagina": 1, "registros_por_pagina": 1})
    m5_antes = r_m5_antes.json().get("total") if r_m5_antes.status_code == 200 else None

    r_m1_antes = c.get("admin", "/auditoria/", paso="d07_obs_m1_antes", params={"pagina": 1, "tamano": 1})
    m1_antes = r_m1_antes.json().get("total") if r_m1_antes.status_code in (200, 206) else None

    # Intentos de Productor (recurso 57 sin permiso)
    for sufijo_paso, ruta, params in (
        ("prod_lista", "/suministros/auditoria", None),
        ("prod_detalle", "/suministros/auditoria/1", None),
        ("prod_exportar", "/suministros/auditoria/exportar", {"formato": "csv"}),
    ):
        r = c.get("productor", ruta, paso=f"d07_{sufijo_paso}", params=params)
        assert r.status_code == 403, (
            f"RF-80 RNF-05 / RBAC recurso 57 ({sufijo_paso}): esperado HTTP 403, obtenido {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]"
        )
        body = r.json()
        assert body.get("error_code") == "ACCESO_DENEGADO", f"error_code={body.get('error_code')!r}"
        assert "items" not in body, "Fuga de datos en respuesta 403: clave 'items' presente"

    # Intentos de Veterinario (recurso 57 sin permiso)
    for sufijo_paso, ruta, params in (
        ("vet_lista", "/suministros/auditoria", None),
        ("vet_detalle", "/suministros/auditoria/1", None),
        ("vet_exportar", "/suministros/auditoria/exportar", {"formato": "csv"}),
    ):
        r = c.get("veterinario", ruta, paso=f"d07_{sufijo_paso}", params=params)
        assert r.status_code == 403, (
            f"RF-80 RNF-05 / RBAC recurso 57 ({sufijo_paso}): esperado HTTP 403, obtenido {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]"
        )
        body = r.json()
        assert body.get("error_code") == "ACCESO_DENEGADO", f"error_code={body.get('error_code')!r}"
        assert "items" not in body, "Fuga de datos en respuesta 403: clave 'items' presente"

    # Observacion posterior (API Admin, sin asercion)
    r_m5_desp = c.get("admin", "/suministros/auditoria", paso="d07_obs_m5_despues", params={"pagina": 1, "registros_por_pagina": 1})
    m5_desp = r_m5_desp.json().get("total") if r_m5_desp.status_code == 200 else None

    r_m1_desp = c.get("admin", "/auditoria/", paso="d07_obs_m1_despues", params={"pagina": 1, "tamano": 1})
    m1_desp = r_m1_desp.json().get("total") if r_m1_desp.status_code in (200, 206) else None

    _CONTEXTO["d07_observacion"] = {
        "m5_status_antes": r_m5_antes.status_code,
        "m5_status_despues": r_m5_desp.status_code,
        "m5_total_antes": m5_antes,
        "m5_total_despues": m5_desp,
        "m5_delta_total": (m5_desp - m5_antes) if isinstance(m5_antes, int) and isinstance(m5_desp, int) else None,
        "m1_status_antes": r_m1_antes.status_code,
        "m1_status_despues": r_m1_desp.status_code,
        "m1_total_antes": m1_antes,
        "m1_total_despues": m1_desp,
        "m1_delta_total": (m1_desp - m1_antes) if isinstance(m1_antes, int) and isinstance(m1_desp, int) else None,
    }


def test_t98_cierre_corrida_principal():
    """T98 (Harness): Cierre de la corrida sandbox principal con DELETE -> HTTP 200 Rollback exitoso."""
    c = _principal()
    r = c.cerrar()
    assert r is not None, "Corrida principal ya habia sido cerrada"
    assert r.status_code == 200, (
        f"Error cerrando corrida principal: HTTP {r.status_code} [X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    data = r.json()
    msg = (data.get("status") or data.get("mensaje") or "").lower()
    assert "rollback exitoso" in msg or "exitoso" in msg, f"Respuesta inesperada de rollback: {data}"


def test_t99_inocuidad():
    """T99 (Harness / Inocuidad): Corrida sandbox aparte de solo lectura verifica reversion total via API tras T98."""
    total_base = _CONTEXTO.get("total_base")
    ultimo_id_base = _CONTEXTO.get("ultimo_id_base")
    id_activo = _CONTEXTO.get("id_activo")
    id_activo_vacio = _CONTEXTO.get("id_activo_vacio")
    assert total_base is not None and ultimo_id_base is not None, "PRECONDICION_NO_CUMPLIDA: T00 no establecio linea base"

    c = CorridaSandbox("inofin")
    try:
        c.login_actor("admin", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        total_api, ultimo_id_api = _leer_estado_auditoria_api(c, "t99_get_auditoria_final")

        assert total_api == total_base, (
            f"Inocuidad fallida en total API: base={total_base}, api_fin={total_api}"
        )
        assert ultimo_id_api == ultimo_id_base, (
            f"Inocuidad fallida en ultimo_id API: base={ultimo_id_base}, api_fin={ultimo_id_api}"
        )

        if id_activo is not None:
            r_act = c.get("admin", f"/activos-biologicos/{id_activo}", paso="t99_get_activo_borrado")
            assert r_act.status_code == 404, f"Activo {id_activo} persistio tras rollback: HTTP {r_act.status_code}"

            r_acu = c.get("admin", f"/suministros/costeo-directo/acumulado/activo/{id_activo}", paso="t99_get_acumulado_borrado")
            assert r_acu.status_code == 404, f"Acumulado activo {id_activo} persistio tras rollback: HTTP {r_acu.status_code}"

        if id_activo_vacio is not None:
            r_vacio = c.get("admin", f"/activos-biologicos/{id_activo_vacio}", paso="t99_get_activo_vacio_borrado")
            assert r_vacio.status_code == 404, f"Activo vacio {id_activo_vacio} persistio tras rollback: HTTP {r_vacio.status_code}"
    finally:
        r_close = c.cerrar()
        assert r_close is not None and r_close.status_code == 200, (
            f"T99 cierre sandbox inesperado: {r_close.status_code if r_close else None}"
        )
