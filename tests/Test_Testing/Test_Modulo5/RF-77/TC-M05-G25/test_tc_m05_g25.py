# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G25 RF-77: Permisos por rol, Aislamiento/IDOR y Auditoria M05   |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G25 fase 3: sandbox en Clase 4, D02/D04 y C02 estrictos        |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G25 fase 3 (1b): C03 auditoría Productor, D05 IDOR de reporte, B03 con archivo real, patrón de escáner |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G25 fase 3 (1c): D02 403/404 por RLS, setup D05 alineado, ps1 ASCII |
"""Suite de pruebas automatizadas para TC-M05-G25 (RF-77).

Cubierta:
- TC-M05-024: Matriz de roles y permisos (Productor y Admin permitidos; Veterinario 403; No autenticado 401),
  prevención de IDOR sobre archivos exportados (403 ARCHIVO_DE_OTRO_USUARIO) y reportes ajenos (403/404).
- TC-M05-025: Auditoría de generación y exportación para Admin y Productor (CA-11 / Postcondición 3, <= 2 s).
- Aislamiento estricto de historial y manipulación segura de identificadores (23 verificaciones).

Estructurado en 4 clases ejecutadas estrictamente de forma secuencial bajo sandbox transaccional
(máximo un POST /sesiones/ por cuenta dentro de un mismo run_id):
1. TestTC_M05_G25_Productor (Sandbox Productor)
2. TestTC_M05_G25_Veterinario (Sandbox Veterinario + exportación real de Admin en B03)
3. TestTC_M05_G25_Administrador (Sandbox Administrador y auditoría estricta de Admin C02 y Productor C03)
4. TestTC_M05_G25_IDOR_Y_Aislamiento (Sandbox IDOR, archivos/reportes ajenos, tipos y no autenticados)
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import requests
from dotenv import dotenv_values

NOMBRE_ZONA = "America/Bogota"
ZONA_USUARIO = timezone(timedelta(hours=-5))
TIMEOUT_S = 30
ARCHIVO_TRAZA = "trazas_http.jsonl"
_LOCK_TRAZA = threading.Lock()
_PREFIJO_JWT = "ey" + "J"

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

# Contextos compartidos
_CONTEXTO_PROD: dict[str, Any] = {
    "id_reporte": None,
    "id_archivo_csv": None,
    "id_archivo_pdf": None,
}

_CONTEXTO_ADMIN: dict[str, Any] = {
    "id_usuario_admin": None,
    "top_id_previo": None,
    "id_reporte": None,
    "id_archivo_csv": None,
    "formato_exp": None,
    "t_fin_gen": None,
    "t_fin_exp": None,
}

_CONTEXTO_IDOR: dict[str, Any] = {
    "id_reporte_admin": None,
    "uuid_csv_admin": None,
    "id_reporte_d05": None,
}

_TEST_ACTUAL = "init"


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: falta la variable de entorno {nombre}")
    return valor or ""


def _hoy() -> date:
    return datetime.now(ZONA_USUARIO).date()


def _id_usuario_desde_token(token: str) -> int:
    partes = token.split(".")
    assert len(partes) >= 2, "PRECONDICION_NO_CUMPLIDA: token de sesion sin estructura JWT esperada"
    b64 = partes[1] + "=" * (-len(partes[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(b64.encode("ascii")).decode("utf-8"))
    sub = payload.get("sub")
    assert sub is not None, "PRECONDICION_NO_CUMPLIDA: claim sub ausente en sesion"
    return int(sub)


def _secretos() -> list[str]:
    return [
        s for s in (
            _env("TEST_SANDBOX_SECRET", False),
            _env("TEST_ADMIN_PASSWORD", False),
            _env("TEST_ADMIN_EMAIL", False),
            _env("TEST_PRODUCER_PASSWORD", False),
            _env("TEST_PRODUCER_EMAIL", False),
            _env("TEST_VET_PASSWORD", False),
            _env("TEST_VET_EMAIL", False),
        ) if s
    ]


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:600]
    for s in [*_secretos(), *extra]:
        if s and len(s) > 3:
            texto = texto.replace(s, "[OMITIDO]")
    if _PREFIJO_JWT in texto:
        texto = re.sub(_PREFIJO_JWT + r"[a-zA-Z0-9_\-\.]+", "[JWT_OMITIDO]", texto)
    return texto


def _sanitizar_objeto(obj: Any, extra: tuple[str, ...] = ()) -> Any:
    if isinstance(obj, dict):
        san = {}
        for k, v in obj.items():
            if k.lower() in ("contrasena", "password", "token", "authorization", "correo_electronico", "access_token"):
                san[k] = "[OMITIDO]"
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
    test_nombre: str | None = None,
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
        "test": test_nombre or _TEST_ACTUAL,
        "metodo": metodo,
        "ruta": ruta,
        "params": _sanitizar_objeto(params, extra),
        "status_code": status_code,
        "error_code": error_code,
        "error_conexion": error,
        "request_body": _sanitizar_objeto(req_body, extra),
        "response_body": _sanitizar_objeto(resp_body, extra),
    }

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
        super().__init__(
            f"ERROR_CONEXION paso={paso} ruta={ruta}: {type(original).__name__} ({original})"
        )


class CorridaSandboxRol:
    """Gestiona una corrida sandbox secuencial (admite múltiples cuentas distintas con 1 login por cuenta)."""

    def __init__(self, prefijo_rol: str, email_env: str | None = None, pass_env: str | None = None) -> None:
        self.prefijo_rol = prefijo_rol
        self.email_env = email_env
        self.pass_env = pass_env
        self.run_id = f"tc-m05-g25-{prefijo_rol}-{uuid.uuid4().hex[:8]}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.token: str | None = None
        self.tokens: dict[str, str] = {}
        self.cerrada = False
        self.http = requests.Session()
        self.http.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "X-Zona-Horaria": NOMBRE_ZONA,
        })

    def seguro(self, texto: str) -> str:
        tokens_activos = tuple({t for t in (self.token, *self.tokens.values()) if t})
        return _seguro(texto, tokens_activos)

    def _enviar_con_token(
        self,
        token: str | None,
        metodo: str,
        ruta: str,
        paso: str | None = None,
        params: Any = None,
        json_body: Any = None,
        **kw,
    ) -> requests.Response:
        assert ruta.startswith("/"), f"Ruta relativa esperada: {ruta!r}"
        headers = dict(kw.pop("headers", {}) or {})
        if token is not None and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {token}"
        inicio = time.perf_counter()
        try:
            resp = self.http.request(
                metodo,
                self.base + ruta,
                headers=headers or None,
                timeout=TIMEOUT_S,
                params=params,
                json=json_body,
                **kw,
            )
        except requests.RequestException as exc:
            _trazar(metodo, ruta, None, inicio, params=params, req_body=json_body, token_extra=token, error=type(exc).__name__)
            raise ErrorConexion(paso or _TEST_ACTUAL, ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio, params=params, req_body=json_body, token_extra=token)
        return resp

    def enviar_rol(
        self,
        rol: str | None,
        metodo: str,
        ruta: str,
        paso: str | None = None,
        params: Any = None,
        json_body: Any = None,
        **kw,
    ) -> requests.Response:
        token = None
        if rol is not None:
            token = self.tokens.get(rol)
            assert token is not None, f"PRECONDICION_NO_CUMPLIDA: falta sesion para rol={rol}"
        return self._enviar_con_token(token, metodo, ruta, paso=paso, params=params, json_body=json_body, **kw)

    def get(self, ruta: str, paso: str | None = None, params: Any = None, **kw) -> requests.Response:
        return self._enviar_con_token(self.token, "GET", ruta, paso=paso, params=params, **kw)

    def post(self, ruta: str, json: Any, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar_con_token(self.token, "POST", ruta, paso=paso, params=params, json_body=json)

    def login_rol(self, rol: str, email_env: str, pass_env: str) -> str:
        """Inicia sesión una única vez por clave de rol dentro del mismo run_id."""
        if rol in self.tokens:
            return self.tokens[rol]
        r = self._enviar_con_token(
            None,
            "POST",
            "/sesiones/",
            paso=f"login_{self.prefijo_rol}_{rol}",
            json_body={"correo_electronico": _env(email_env), "contrasena": _env(pass_env)},
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {rol} HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {rol} sin token"
        self.tokens[rol] = token
        if rol == self.prefijo_rol and self.token is None:
            self.token = token
        return token

    def login(self) -> None:
        assert self.email_env and self.pass_env, "Faltan variables de entorno de cuenta principal"
        assert self.token is None, "Solo se permite un login por cuenta y run_id"
        self.login_rol(self.prefijo_rol, self.email_env, self.pass_env)

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            return self._enviar_con_token(None, "DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.prefijo_rol}")
        finally:
            self.http.close()


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield
    _TEST_ACTUAL = "post_test"


# ===========================================================================
# CLASE 1: Productor (Generar, Exportar CSV/PDF, Descargar, Auditoría 403)
# ===========================================================================


@pytest.fixture(scope="class")
def sandbox_productor() -> CorridaSandboxRol:
    c = CorridaSandboxRol("prod", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G25_Productor:
    """Evaluación de facultades del rol Productor bajo sandbox transaccional."""

    def test_a01_productor_genera_reporte_sincronico(self, sandbox_productor: CorridaSandboxRol):
        """A01: Productor genera exitosamente reporte sincrónico (HTTP 200)."""
        payload = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r = sandbox_productor.post("/suministros/reportes-gastos", payload, paso="A01_productor_generar")
        assert r.status_code == 200, f"Productor no pudo generar reporte: HTTP {r.status_code}: {sandbox_productor.seguro(r.text)}"
        data = r.json()
        id_rep = data.get("id_reporte_gasto_acumulado")
        assert id_rep is not None, "Reporte generado sin id_reporte_gasto_acumulado"
        _CONTEXTO_PROD["id_reporte"] = id_rep

    def test_a02_productor_exporta_reporte_csv(self, sandbox_productor: CorridaSandboxRol):
        """A02: Productor exporta reporte generado a formato CSV (HTTP 201)."""
        id_rep = _CONTEXTO_PROD["id_reporte"]
        assert id_rep is not None, "Precondición no cumplida: falta id_reporte"
        payload = {"formato_exportacion": "CSV"}
        r = sandbox_productor.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", payload, paso="A02_productor_exportar_csv")
        assert r.status_code == 201, f"Productor no pudo exportar a CSV: HTTP {r.status_code}: {sandbox_productor.seguro(r.text)}"
        data = r.json()
        id_arch = data.get("id_archivo") or data.get("id_archivo_exportacion")
        assert id_arch is not None, "Exportación sin id_archivo"
        assert data.get("formato") == "CSV"
        assert "Gastos_" in data.get("nombre_archivo", "")
        _CONTEXTO_PROD["id_archivo_csv"] = id_arch

    def test_a03_productor_exporta_reporte_pdf(self, sandbox_productor: CorridaSandboxRol):
        """A03: Productor exporta reporte generado a formato PDF (HTTP 201)."""
        id_rep = _CONTEXTO_PROD["id_reporte"]
        assert id_rep is not None, "Precondición no cumplida: falta id_reporte"
        payload = {"formato_exportacion": "PDF"}
        r = sandbox_productor.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", payload, paso="A03_productor_exportar_pdf")
        assert r.status_code == 201, f"Productor no pudo exportar a PDF: HTTP {r.status_code}: {sandbox_productor.seguro(r.text)}"
        data = r.json()
        id_arch = data.get("id_archivo") or data.get("id_archivo_exportacion")
        assert id_arch is not None, "Exportación sin id_archivo"
        assert data.get("formato") == "PDF"
        assert "Reporte_Gastos_" in data.get("nombre_archivo", "")
        _CONTEXTO_PROD["id_archivo_pdf"] = id_arch

    def test_a04_productor_descarga_su_propia_exportacion(self, sandbox_productor: CorridaSandboxRol):
        """A04: Productor descarga archivo CSV que generó (HTTP 200 y headers correctos)."""
        id_arch = _CONTEXTO_PROD["id_archivo_csv"]
        assert id_arch is not None, "Precondición no cumplida: falta id_archivo_csv"
        r = sandbox_productor.get(f"/suministros/reportes-gastos/exportaciones/{id_arch}", paso="A04_productor_descargar")
        assert r.status_code == 200, f"Productor no pudo descargar su exportación: HTTP {r.status_code}: {sandbox_productor.seguro(r.text)}"
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct, f"Content-Type inesperado: {ct}"
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and ".csv" in cd, f"Content-Disposition inesperado: {cd}"
        assert len(r.content) > 10, "El archivo CSV descargado está vacío"

    def test_a05_productor_no_accede_a_auditoria_m05(self, sandbox_productor: CorridaSandboxRol):
        """A05: Productor recibe HTTP 403 al intentar consultar bitácora de auditoría (Recurso 57)."""
        r = sandbox_productor.get("/suministros/auditoria", paso="A05_productor_auditoria_403")
        assert r.status_code == 403, (
            f"Se esperaba HTTP 403 para Productor en /suministros/auditoria, obtenido: {r.status_code}"
        )
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

    def test_a98_cierre_sandbox_productor(self, sandbox_productor: CorridaSandboxRol):
        """A98: Cierre ordenado de sandbox Productor y rollback atómico."""
        r = sandbox_productor.cerrar()
        assert r is not None and r.status_code == 200, f"Cierre sandbox Productor falló: {r}"
        assert "Rollback exitoso" in r.text


# ===========================================================================
# CLASE 2: Veterinario (Acceso denegado 403 en reporte, exportación y auditoría)
# ===========================================================================


@pytest.fixture(scope="class")
def sandbox_veterinario() -> CorridaSandboxRol:
    c = CorridaSandboxRol("vet", "TEST_VET_EMAIL", "TEST_VET_PASSWORD")
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G25_Veterinario:
    """Evaluación de restricciones del rol Veterinario bajo sandbox transaccional."""

    def test_b01_veterinario_generar_reporte_denegado(self, sandbox_veterinario: CorridaSandboxRol):
        """B01: Veterinario recibe HTTP 403 al intentar generar reporte de gastos (RF-77 RNF)."""
        payload = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r = sandbox_veterinario.post("/suministros/reportes-gastos", payload, paso="B01_vet_generar_403")
        assert r.status_code == 403, (
            f"Se esperaba HTTP 403 para Veterinario generando reporte (recurso 51), obtenido: {r.status_code}"
        )
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

    def test_b02_veterinario_exportar_reporte_denegado(self, sandbox_veterinario: CorridaSandboxRol):
        """B02: Veterinario recibe HTTP 403 al intentar exportar un reporte existente."""
        payload = {"formato_exportacion": "CSV"}
        r = sandbox_veterinario.post("/suministros/reportes-gastos/19/exportacion", payload, paso="B02_vet_exportar_403")
        assert r.status_code == 403, (
            f"Se esperaba HTTP 403 para Veterinario exportando reporte, obtenido: {r.status_code}"
        )
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

    def test_b03_veterinario_descargar_exportacion_denegado(self, sandbox_veterinario: CorridaSandboxRol):
        """B03: Veterinario recibe HTTP 403 al intentar descargar una exportación CSV real de Admin (RF-77 RNF Seguridad / TC-M05-024)."""
        sandbox_veterinario.login_rol("adm", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        payload_rep = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = sandbox_veterinario.enviar_rol(
            "adm", "POST", "/suministros/reportes-gastos", paso="B03_admin_generar", json_body=payload_rep
        )
        assert r_rep.status_code == 200, f"Precondición B03 Admin generar falló: HTTP {r_rep.status_code}"
        id_rep = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep is not None, "Precondición B03: reporte Admin sin id_reporte_gasto_acumulado"

        r_exp = sandbox_veterinario.enviar_rol(
            "adm",
            "POST",
            f"/suministros/reportes-gastos/{id_rep}/exportacion",
            paso="B03_admin_exportar_csv",
            json_body={"formato_exportacion": "CSV"},
        )
        assert r_exp.status_code == 201, f"Precondición B03 Admin exportar CSV falló: HTTP {r_exp.status_code}"
        id_arch_real = r_exp.json().get("id_archivo") or r_exp.json().get("id_archivo_exportacion")
        assert id_arch_real, "Precondición B03: exportación Admin sin id_archivo"

        r = sandbox_veterinario.get(
            f"/suministros/reportes-gastos/exportaciones/{id_arch_real}",
            paso="B03_vet_descargar_403",
        )
        assert r.status_code == 403, (
            f"[RF-77 RNF Seguridad / TC-M05-024] Se esperaba HTTP 403 para Veterinario descargando "
            f"exportación real, obtenido: {r.status_code}"
        )
        assert r.json().get("error_code") == "ACCESO_DENEGADO"
        ct = r.headers.get("content-type", "")
        cd = r.headers.get("content-disposition", "")
        assert "text/csv" not in ct and "attachment" not in cd, (
            f"[RF-77 RNF Seguridad / TC-M05-024] Cabeceras impropias de descarga para Veterinario: ct={ct!r}, cd={cd!r}"
        )
        assert "fecha,categoria" not in r.text, "[RF-77 RNF Seguridad / TC-M05-024] Se filtró contenido CSV a Veterinario"

    def test_b04_veterinario_acceder_auditoria_denegado(self, sandbox_veterinario: CorridaSandboxRol):
        """B04: Veterinario recibe HTTP 403 al intentar acceder a /suministros/auditoria."""
        r = sandbox_veterinario.get("/suministros/auditoria", paso="B04_vet_auditoria_403")
        assert r.status_code == 403, (
            f"Se esperaba HTTP 403 para Veterinario en bitácora de auditoría, obtenido: {r.status_code}"
        )
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

    def test_b98_cierre_sandbox_veterinario(self, sandbox_veterinario: CorridaSandboxRol):
        """B98: Cierre ordenado de sandbox Veterinario y rollback atómico."""
        r = sandbox_veterinario.cerrar()
        assert r is not None and r.status_code == 200, f"Cierre sandbox Veterinario falló: {r}"
        assert "Rollback exitoso" in r.text


# ===========================================================================
# CLASE 3: Administrador y Verificación Normativa de Auditoría
# ===========================================================================


@pytest.fixture(scope="class")
def sandbox_admin() -> CorridaSandboxRol:
    c = CorridaSandboxRol("adm", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


def _verificar_auditoria_gen_y_exp(
    sandbox_lector_admin: CorridaSandboxRol,
    *,
    rol_lector: str | None,
    etiqueta_actor: str,
    id_actor: int,
    id_rep: int,
    id_arch: str,
    formato_exp: str,
    top_id_previo: int,
    t_fin_gen: float,
    t_fin_exp: float,
    paso_auditoria: str,
) -> None:
    """Verifica en /suministros/auditoria (polling 0/1/2 s) exactamente 1 GENERACION y 1 EXPORTACION del actor."""
    evs_gen: list[dict[str, Any]] = []
    evs_exp: list[dict[str, Any]] = []
    lat_gen: float | None = None
    lat_exp: float | None = None

    for pausa in (0.0, 1.0, 1.0):
        if pausa > 0:
            time.sleep(pausa)
        if rol_lector is None:
            r_aud = sandbox_lector_admin.get(
                "/suministros/auditoria", params={"registros_por_pagina": 50}, paso=paso_auditoria
            )
        else:
            r_aud = sandbox_lector_admin.enviar_rol(
                rol_lector, "GET", "/suministros/auditoria", params={"registros_por_pagina": 50}, paso=paso_auditoria
            )
        t_check = time.perf_counter()
        assert r_aud.status_code == 200, f"Error consultando auditoría como Admin: HTTP {r_aud.status_code}"
        nuevos = [
            it for it in r_aud.json().get("items", [])
            if int(it.get("id_auditoria_suministro") or 0) > top_id_previo
        ]
        evs_gen = [
            it for it in nuevos
            if it.get("entidad_afectada") == "reporte_gastos_acumulados"
            and it.get("tipo_operacion") == "INSERT"
            and (it.get("datos_nuevos") or {}).get("accion") == "GENERACION"
            and (it.get("datos_nuevos") or {}).get("id_reporte_gasto_acumulado") == id_rep
            and it.get("id_usuario") == id_actor
        ]
        evs_exp = [
            it for it in nuevos
            if it.get("entidad_afectada") == "archivos_exportacion_suministros"
            and it.get("tipo_operacion") == "INSERT"
            and (it.get("datos_nuevos") or {}).get("accion") == "EXPORTACION"
            and (it.get("datos_nuevos") or {}).get("id_reporte_gasto_acumulado") == id_rep
            and (it.get("datos_nuevos") or {}).get("id_archivo") == id_arch
            and (it.get("datos_nuevos") or {}).get("formato") == formato_exp
            and it.get("id_usuario") == id_actor
        ]
        if evs_gen and lat_gen is None:
            lat_gen = round(t_check - t_fin_gen, 3)
        if evs_exp and lat_exp is None:
            lat_exp = round(t_check - t_fin_exp, 3)
        if evs_gen and evs_exp:
            break

    assert len(evs_gen) == 1, (
        f"[RF-77 CA-11 / Postcondición 3 / TC-M05-025] Se esperaba exactamente 1 evento GENERACION "
        f"(id>{top_id_previo}, id_reporte={id_rep}, actor {etiqueta_actor}={id_actor}); encontrados={len(evs_gen)}"
    )
    ev_gen = evs_gen[0]
    assert ev_gen.get("resultado") == "EXITOSO" and ev_gen.get("fecha_evento"), (
        f"[RF-77 CA-11] Evento GENERACION incompleto para {etiqueta_actor}: {ev_gen}"
    )
    assert lat_gen is not None and lat_gen <= 2.0, (
        f"[TC-M05-025] Latencia de auditoría GENERACION ({etiqueta_actor})={lat_gen}s supera SLA <= 2.0 s"
    )

    assert len(evs_exp) == 1, (
        f"[RF-77 CA-11 / Postcondición 3 / TC-M05-025] Se esperaba exactamente 1 evento EXPORTACION "
        f"(id>{top_id_previo}, id_archivo={id_arch}, formato={formato_exp}, actor {etiqueta_actor}={id_actor}); "
        f"encontrados={len(evs_exp)}"
    )
    ev_exp = evs_exp[0]
    assert ev_exp.get("resultado") == "EXITOSO" and ev_exp.get("fecha_evento"), (
        f"[RF-77 CA-11] Evento EXPORTACION incompleto para {etiqueta_actor}: {ev_exp}"
    )
    assert lat_exp is not None and lat_exp <= 2.0, (
        f"[TC-M05-025] Latencia de auditoría EXPORTACION ({etiqueta_actor})={lat_exp}s supera SLA <= 2.0 s"
    )


class TestTC_M05_G25_Administrador:
    """Evaluación de facultades de Administrador y verificación estricta de auditoría (TC-M05-025)."""

    def test_c01_admin_genera_y_exporta_reporte(self, sandbox_admin: CorridaSandboxRol):
        """C01: Captura top_id base de auditoría; Admin genera reporte (200) y exporta CSV (201)."""
        assert sandbox_admin.token is not None
        _CONTEXTO_ADMIN["id_usuario_admin"] = _id_usuario_desde_token(sandbox_admin.token)

        r_pre = sandbox_admin.get("/suministros/auditoria", params={"registros_por_pagina": 5}, paso="C01_auditoria_base")
        assert r_pre.status_code == 200, f"Precondición auditoría Admin HTTP {r_pre.status_code}"
        items_pre = r_pre.json().get("items", [])
        _CONTEXTO_ADMIN["top_id_previo"] = int(items_pre[0].get("id_auditoria_suministro") or 0) if items_pre else 0

        payload = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = sandbox_admin.post("/suministros/reportes-gastos", payload, paso="C01_admin_generar")
        t_fin_gen = time.perf_counter()
        assert r_rep.status_code == 200, f"Admin no pudo generar reporte: HTTP {r_rep.status_code}: {sandbox_admin.seguro(r_rep.text)}"
        id_rep = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep is not None, "Reporte Admin sin id_reporte_gasto_acumulado"
        _CONTEXTO_ADMIN["id_reporte"] = id_rep
        _CONTEXTO_ADMIN["t_fin_gen"] = t_fin_gen

        r_exp = sandbox_admin.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", {"formato_exportacion": "CSV"}, paso="C01_admin_exportar")
        t_fin_exp = time.perf_counter()
        assert r_exp.status_code == 201, f"Admin no pudo exportar reporte: HTTP {r_exp.status_code}: {sandbox_admin.seguro(r_exp.text)}"
        exp_j = r_exp.json()
        id_arch = exp_j.get("id_archivo") or exp_j.get("id_archivo_exportacion")
        assert id_arch is not None, "Exportación Admin sin id_archivo"
        _CONTEXTO_ADMIN["id_archivo_csv"] = id_arch
        _CONTEXTO_ADMIN["formato_exp"] = exp_j.get("formato") or "CSV"
        _CONTEXTO_ADMIN["t_fin_exp"] = t_fin_exp

    def test_c02_verificacion_auditoria_ca11_postcondicion3(self, sandbox_admin: CorridaSandboxRol):
        """C02: Verificación estricta de auditoría en <= 2 s para generación y exportación de Admin (RF-77 CA-11 / Postcondición 3)."""
        id_rep = _CONTEXTO_ADMIN["id_reporte"]
        id_arch = _CONTEXTO_ADMIN["id_archivo_csv"]
        formato_exp = _CONTEXTO_ADMIN["formato_exp"]
        top_id_previo = _CONTEXTO_ADMIN["top_id_previo"]
        id_admin = _CONTEXTO_ADMIN["id_usuario_admin"]
        t_fin_gen = _CONTEXTO_ADMIN["t_fin_gen"]
        t_fin_exp = _CONTEXTO_ADMIN["t_fin_exp"]
        assert all(v is not None for v in (id_rep, id_arch, formato_exp, top_id_previo, id_admin, t_fin_gen, t_fin_exp)), (
            "Precondición no cumplida: falta contexto completo de C01"
        )
        _verificar_auditoria_gen_y_exp(
            sandbox_admin,
            rol_lector=None,
            etiqueta_actor="Admin",
            id_actor=id_admin,
            id_rep=id_rep,
            id_arch=id_arch,
            formato_exp=formato_exp,
            top_id_previo=top_id_previo,
            t_fin_gen=t_fin_gen,
            t_fin_exp=t_fin_exp,
            paso_auditoria="C02_consultar_auditoria",
        )

    def test_c03_auditoria_productor_ca11_postcondicion3(self, sandbox_admin: CorridaSandboxRol):
        """C03: Verificación estricta de auditoría en <= 2 s para generación y exportación de Productor (RF-77 CA-11 / Postcondición 3 / TC-M05-025)."""
        r_pre = sandbox_admin.get("/suministros/auditoria", params={"registros_por_pagina": 5}, paso="C03_auditoria_base")
        assert r_pre.status_code == 200, f"Precondición auditoría C03 Admin HTTP {r_pre.status_code}"
        items_pre = r_pre.json().get("items", [])
        top_id_previo = int(items_pre[0].get("id_auditoria_suministro") or 0) if items_pre else 0

        tok_prod = sandbox_admin.login_rol("prod", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
        id_prod = _id_usuario_desde_token(tok_prod)

        payload_prod = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = sandbox_admin.enviar_rol("prod", "POST", "/suministros/reportes-gastos", paso="C03_prod_generar", json_body=payload_prod)
        t_fin_gen = time.perf_counter()
        assert r_rep.status_code == 200, f"Productor no pudo generar reporte en C03: HTTP {r_rep.status_code}: {sandbox_admin.seguro(r_rep.text)}"
        id_rep_prod = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep_prod is not None, "Reporte Productor en C03 sin id_reporte_gasto_acumulado"

        r_exp = sandbox_admin.enviar_rol(
            "prod",
            "POST",
            f"/suministros/reportes-gastos/{id_rep_prod}/exportacion",
            paso="C03_prod_exportar",
            json_body={"formato_exportacion": "CSV"},
        )
        t_fin_exp = time.perf_counter()
        assert r_exp.status_code == 201, f"Productor no pudo exportar reporte en C03: HTTP {r_exp.status_code}: {sandbox_admin.seguro(r_exp.text)}"
        exp_j = r_exp.json()
        id_arch_prod = exp_j.get("id_archivo") or exp_j.get("id_archivo_exportacion")
        assert id_arch_prod, "Exportación Productor en C03 sin id_archivo"
        formato_exp = exp_j.get("formato") or "CSV"

        _verificar_auditoria_gen_y_exp(
            sandbox_admin,
            rol_lector=None,
            etiqueta_actor="Productor",
            id_actor=id_prod,
            id_rep=id_rep_prod,
            id_arch=id_arch_prod,
            formato_exp=formato_exp,
            top_id_previo=top_id_previo,
            t_fin_gen=t_fin_gen,
            t_fin_exp=t_fin_exp,
            paso_auditoria="C03_consultar_auditoria",
        )

    def test_c98_cierre_sandbox_admin(self, sandbox_admin: CorridaSandboxRol):
        """C98: Cierre ordenado de sandbox Administrador y rollback atómico."""
        r = sandbox_admin.cerrar()
        assert r is not None and r.status_code == 200, f"Cierre sandbox Administrador falló: {r}"
        assert "Rollback exitoso" in r.text


# ===========================================================================
# CLASE 4: Control de IDOR, Tipos y Aislamiento de Datos (Sandbox Unico)
# ===========================================================================


class CorridaSandboxIDOR(CorridaSandboxRol):
    """Corrida sandbox secuencial de Clase 4 (1 login por cuenta involucrada)."""

    def __init__(self) -> None:
        super().__init__("idor")

    def enviar(
        self,
        rol: str | None,
        metodo: str,
        ruta: str,
        paso: str | None = None,
        params: Any = None,
        json_body: Any = None,
    ) -> requests.Response:
        return self.enviar_rol(rol, metodo, ruta, paso=paso, params=params, json_body=json_body)


@pytest.fixture(scope="class")
def sandbox_idor() -> CorridaSandboxIDOR:
    c = CorridaSandboxIDOR()
    try:
        yield c
    finally:
        c.cerrar()


def _asegurar_reporte_d05(sandbox_idor: CorridaSandboxIDOR) -> tuple[int, int]:
    """Prepara sesiones Admin/Productor y crea un activo+gasto+reporte R perteneciente a Admin si aún no existe."""
    sandbox_idor.login_rol("adm", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
    tok_prod = sandbox_idor.login_rol("prod", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
    id_prod = _id_usuario_desde_token(tok_prod)

    if _CONTEXTO_IDOR["id_reporte_d05"] is None:
        hoy_str = _hoy().isoformat()
        fecha_ciclo = (_hoy() - timedelta(days=15)).isoformat()
        payload_activo = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G25-D05-{uuid.uuid4().hex[:8]}",
            "cantidad_inicial": 100,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_act = sandbox_idor.enviar("adm", "POST", "/activos-biologicos", paso="D05_setup_crear_activo", json_body=payload_activo)
        assert r_act.status_code == 201, f"Setup D05 crear activo falló: HTTP {r_act.status_code}: {sandbox_idor.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None, "Setup D05: activo sin id_activo_biologico"

        r_fase = sandbox_idor.enviar(
            "adm",
            "POST",
            f"/activos-biologicos/{id_activo}/fases",
            paso="D05_setup_abrir_fase",
            json_body={
                "id_ciclo_productiva": 1,
                "motivo_cambio": "Setup QA TC-M05-G25 D05",
                "fecha_inicio": f"{fecha_ciclo}T05:00:00Z",
            },
        )
        assert r_fase.status_code in (200, 201), f"Setup D05 abrir fase falló: HTTP {r_fase.status_code}: {sandbox_idor.seguro(r_fase.text)}"

        r_cons = sandbox_idor.enviar(
            "adm",
            "POST",
            "/suministros/consumo-alimentos",
            paso="D05_setup_crear_consumo",
            json_body={
                "id_activo_biologico": id_activo,
                "id_tipo_alimento": 1,
                "fecha_consumo": hoy_str,
                "hora_suministro": "09:00:00",
                "cantidad_alimento": 10.0,
                "costo_unitario": 2500.0,
            },
        )
        assert r_cons.status_code == 201, f"Setup D05 consumo falló: HTTP {r_cons.status_code}: {sandbox_idor.seguro(r_cons.text)}"

        r_rep = sandbox_idor.enviar(
            "adm",
            "POST",
            "/suministros/reportes-gastos",
            paso="D05_setup_generar_reporte",
            json_body={
                "activo_biologico_id": id_activo,
                "fecha_inicio_reporte": fecha_ciclo,
                "fecha_fin_reporte": hoy_str,
                "tipo_periodo": "MENSUAL",
            },
        )
        assert r_rep.status_code == 200, f"Setup D05 generar reporte falló: HTTP {r_rep.status_code}: {sandbox_idor.seguro(r_rep.text)}"
        id_rep_d05 = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep_d05 is not None, "Setup D05: respuesta sin id_reporte_gasto_acumulado"
        _CONTEXTO_IDOR["id_reporte_d05"] = id_rep_d05

    return int(_CONTEXTO_IDOR["id_reporte_d05"]), id_prod


def _capturar_top_id_auditoria_idor(sandbox_idor: CorridaSandboxIDOR, paso: str) -> int:
    r_aud = sandbox_idor.enviar("adm", "GET", "/suministros/auditoria", params={"registros_por_pagina": 10}, paso=paso)
    assert r_aud.status_code == 200, f"Error leyendo auditoría previa ({paso}): HTTP {r_aud.status_code}"
    items = r_aud.json().get("items", [])
    return int(items[0].get("id_auditoria_suministro") or 0) if items else 0


def _verificar_bloqueo_idor_reporte(
    sandbox_idor: CorridaSandboxIDOR,
    *,
    id_rep_ajeno: int,
    id_prod: int,
    top_id_previo: int,
    resp_idor: requests.Response,
    operacion: str,
) -> None:
    """Valida bloqueo IDOR (403 o 404 sin datos del reporte ajeno ni efectos secundarios en auditoría)."""
    assert resp_idor.status_code in (403, 404), (
        f"[RF-77 RNF Seguridad / TC-M05-024] IDOR {operacion} sobre reporte ajeno {id_rep_ajeno} "
        f"debía responder 403 o 404, obtenido HTTP {resp_idor.status_code}: {sandbox_idor.seguro(resp_idor.text)}"
    )
    ct = resp_idor.headers.get("content-type", "")
    cd = resp_idor.headers.get("content-disposition", "")
    assert "text/csv" not in ct and "application/pdf" not in ct and "attachment" not in cd, (
        f"[RF-77 RNF Seguridad / TC-M05-024] Cabeceras de descarga impropias en rechazo IDOR {operacion}: ct={ct!r}, cd={cd!r}"
    )
    assert "fecha,categoria" not in resp_idor.text and not resp_idor.text.startswith("%PDF-"), (
        f"[RF-77 RNF Seguridad / TC-M05-024] Contenido de archivo filtrado en rechazo IDOR {operacion}"
    )
    try:
        cuerpo = resp_idor.json()
    except Exception:
        cuerpo = {}
    if isinstance(cuerpo, dict):
        claves_sensibles = (
            "gasto_total_acumulado",
            "desglose_categorias",
            "desglose_temporal",
            "id_reporte_gasto_acumulado",
            "id_archivo",
            "id_archivo_exportacion",
        )
        presentes = [k for k in claves_sensibles if k in cuerpo and cuerpo[k] is not None]
        assert not presentes, (
            f"[RF-77 RNF Seguridad / TC-M05-024] Fuga de datos de reporte ajeno en IDOR {operacion}: claves={presentes}"
        )

    r_aud = sandbox_idor.enviar(
        "adm",
        "GET",
        "/suministros/auditoria",
        params={"registros_por_pagina": 20},
        paso=f"D05_{operacion}_auditoria_post",
    )
    assert r_aud.status_code == 200, f"Error verificando auditoría post {operacion}: HTTP {r_aud.status_code}"
    nuevos = [
        it for it in r_aud.json().get("items", [])
        if int(it.get("id_auditoria_suministro") or 0) > top_id_previo
    ]
    indebidos = [
        it for it in nuevos
        if (it.get("datos_nuevos") or {}).get("accion") in ("GENERACION", "REGENERACION", "EXPORTACION")
        and (
            it.get("id_usuario") == id_prod
            or (it.get("datos_nuevos") or {}).get("id_reporte_gasto_acumulado") == id_rep_ajeno
        )
    ]
    assert not indebidos, (
        f"[RF-77 RNF Seguridad / TC-M05-024] Se registró evento indebido tras intento IDOR {operacion}: {indebidos}"
    )


class TestTC_M05_G25_IDOR_Y_Aislamiento:
    """Evaluación de IDOR, tipos y aislamiento por usuario bajo sandbox transaccional."""

    def test_d01_solicitudes_sin_autenticacion_retornan_401(self, sandbox_idor: CorridaSandboxIDOR):
        """D01: Solicitudes con cabeceras sandbox y sin Authorization retornan HTTP 401 (RF-02 / RF-77 RNF Seguridad)."""
        r1 = sandbox_idor.enviar(None, "POST", "/suministros/reportes-gastos", paso="D01_sin_auth_generar", json_body={})
        assert r1.status_code == 401, f"[RF-02] Se esperaba 401 sin auth en generar reporte, obtenido: {r1.status_code}"

        r2 = sandbox_idor.enviar(
            None,
            "POST",
            "/suministros/reportes-gastos/19/exportacion",
            paso="D01_sin_auth_exportar",
            json_body={"formato_exportacion": "CSV"},
        )
        assert r2.status_code == 401, f"[RF-02] Se esperaba 401 sin auth en exportar, obtenido: {r2.status_code}"

        r3 = sandbox_idor.enviar(
            None,
            "GET",
            "/suministros/reportes-gastos/exportaciones/00000000-0000-0000-0000-000000000001",
            paso="D01_sin_auth_descargar",
        )
        assert r3.status_code == 401, f"[RF-02] Se esperaba 401 sin auth en descargar exportación, obtenido: {r3.status_code}"

        r4 = sandbox_idor.enviar(None, "GET", "/suministros/reportes-gastos/historial", paso="D01_sin_auth_historial")
        assert r4.status_code == 401, f"[RF-02] Se esperaba 401 sin auth en historial, obtenido: {r4.status_code}"

        r5 = sandbox_idor.enviar(None, "GET", "/suministros/auditoria", paso="D01_sin_auth_auditoria")
        assert r5.status_code == 401, f"[RF-02] Se esperaba 401 sin auth en auditoría, obtenido: {r5.status_code}"

    def test_d02_idor_descarga_exportacion_ajena_retorna_403(self, sandbox_idor: CorridaSandboxIDOR):
        """D02: Descarga de exportación CSV ajena en el mismo sandbox impide el acceso sin contenido del archivo.

        Se genera y exporta dinámicamente dentro de la misma corrida (los archivos exportados expiran en 24 h
        según RF-77 Postcondición 2) en lugar de usar un UUID fijo. RF-77 RNF Seguridad / TC-M05-024 exigen impedir
        el acceso sin fijar 403 vs 404; en sandbox la RLS de modulo5 responde 404 (observado en el Paso 0e,
        X-Request-Id 7cc058d7-5c49-4d1b-a4e4-34bbdc0661e7).
        """
        sandbox_idor.login_rol("adm", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        payload_rep = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = sandbox_idor.enviar("adm", "POST", "/suministros/reportes-gastos", paso="D02_admin_generar", json_body=payload_rep)
        assert r_rep.status_code == 200, f"Precondición D02 Admin generar falló: HTTP {r_rep.status_code}"
        id_rep_admin = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep_admin is not None
        _CONTEXTO_IDOR["id_reporte_admin"] = id_rep_admin

        r_exp = sandbox_idor.enviar(
            "adm",
            "POST",
            f"/suministros/reportes-gastos/{id_rep_admin}/exportacion",
            paso="D02_admin_exportar_csv",
            json_body={"formato_exportacion": "CSV"},
        )
        assert r_exp.status_code == 201, f"Precondición D02 Admin exportar falló: HTTP {r_exp.status_code}"
        uuid_admin = r_exp.json().get("id_archivo") or r_exp.json().get("id_archivo_exportacion")
        assert uuid_admin is not None
        _CONTEXTO_IDOR["uuid_csv_admin"] = uuid_admin

        sandbox_idor.login_rol("prod", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
        r = sandbox_idor.enviar(
            "prod",
            "GET",
            f"/suministros/reportes-gastos/exportaciones/{uuid_admin}",
            paso="D02_idor_descarga_prod",
        )
        assert r.status_code in (403, 404), (
            f"RF-77 RNF Seguridad / TC-M05-024 exigen impedir el acceso sin fijar 403 vs 404; en sandbox la RLS de modulo5 "
            f"responde 404 (observado en el Paso 0e, X-Request-Id 7cc058d7-5c49-4d1b-a4e4-34bbdc0661e7); "
            f"obtenido: {r.status_code}: {sandbox_idor.seguro(r.text)}"
        )
        assert r.json().get("error_code") in ("ARCHIVO_DE_OTRO_USUARIO", "ARCHIVO_NO_ENCONTRADO"), (
            f"RF-77 RNF Seguridad / TC-M05-024 exigen impedir el acceso sin fijar 403 vs 404; en sandbox la RLS de modulo5 "
            f"responde 404 (observado en el Paso 0e, X-Request-Id 7cc058d7-5c49-4d1b-a4e4-34bbdc0661e7); "
            f"código de error inesperado: {r.json()}"
        )
        ct = r.headers.get("content-type", "")
        cd = r.headers.get("content-disposition", "")
        assert "text/csv" not in ct and "attachment" not in cd, (
            f"[RF-77 RNF Seguridad / TC-M05-024] Cabeceras impropias de descarga en rechazo IDOR: ct={ct!r}, cd={cd!r}"
        )
        assert "fecha,categoria" not in r.text, "[RF-77 RNF Seguridad / TC-M05-024] Se filtró contenido CSV en rechazo IDOR"

    def test_d03_manipulacion_identificadores_no_genera_500(self, sandbox_idor: CorridaSandboxIDOR):
        """D03: IDs inexistentes responden 404 e IDs inválidos responden 400/422; jamás HTTP 500."""
        sandbox_idor.login_rol("prod", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
        casos_id = [
            ("GET", "/suministros/reportes-gastos/999999999", (404,), "Reporte inexistente"),
            ("GET", "/suministros/reportes-gastos/-1", (404, 400, 422), "ID negativo"),
            ("GET", "/suministros/reportes-gastos/id_invalido", (400, 422), "ID alfanumérico"),
            ("GET", "/suministros/reportes-gastos/exportaciones/00000000-0000-0000-0000-000000000000", (404,), "UUID inexistente"),
            ("GET", "/suministros/reportes-gastos/exportaciones/no-es-uuid", (400, 422), "UUID malformado"),
        ]

        for metodo, ruta, status_esperados, desc in casos_id:
            r = sandbox_idor.enviar("prod", metodo, ruta, paso=f"D03_{desc}")
            assert r.status_code != 500, f"[Robustez API] Error del servidor HTTP 500 en {desc}: {ruta}"
            assert r.status_code in status_esperados, (
                f"[Robustez API] Para {desc} ({ruta}) se esperaba HTTP {status_esperados}, "
                f"obtenido: {r.status_code}: {sandbox_idor.seguro(r.text)}"
            )

    def test_d04_aislamiento_historial_por_usuario(self, sandbox_idor: CorridaSandboxIDOR):
        """D04: El historial (/historial) está aislado estrictamente por usuario (RF-77 RNF Historial / TC-M05-024)."""
        sandbox_idor.login_rol("adm", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        sandbox_idor.login_rol("prod", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")

        id_rep_admin = _CONTEXTO_IDOR["id_reporte_admin"]
        if id_rep_admin is None:
            r_a_gen = sandbox_idor.enviar(
                "adm",
                "POST",
                "/suministros/reportes-gastos",
                paso="D04_admin_generar",
                json_body={
                    "id_infraestructura": 2,
                    "fecha_inicio_reporte": "2026-06-01",
                    "fecha_fin_reporte": "2026-11-01",
                    "tipo_periodo": "MENSUAL",
                },
            )
            assert r_a_gen.status_code == 200, f"Precondición D04 Admin generar falló: HTTP {r_a_gen.status_code}"
            id_rep_admin = r_a_gen.json().get("id_reporte_gasto_acumulado")
            assert id_rep_admin is not None
            _CONTEXTO_IDOR["id_reporte_admin"] = id_rep_admin

        payload_prod = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r_p_gen = sandbox_idor.enviar("prod", "POST", "/suministros/reportes-gastos", paso="D04_prod_generar", json_body=payload_prod)
        assert r_p_gen.status_code == 200, f"Productor no pudo generar reporte en D04: HTTP {r_p_gen.status_code}"
        id_rep_prod = r_p_gen.json().get("id_reporte_gasto_acumulado")
        assert id_rep_prod is not None

        r_p_hist = sandbox_idor.enviar("prod", "GET", "/suministros/reportes-gastos/historial", params={"limite": 100}, paso="D04_prod_historial")
        assert r_p_hist.status_code == 200
        items_p = r_p_hist.json().get("items", [])
        ids_p = [it.get("id_reporte_gasto_acumulado") for it in items_p]
        assert all(i is not None for i in ids_p)
        assert id_rep_prod in ids_p, "[RF-77 RNF Historial] Reporte recién generado por Productor no figura en su historial"
        assert id_rep_admin not in ids_p, f"[RF-77 RNF Historial] Fuga IDOR: reporte ajeno {id_rep_admin} apareció en historial de Productor"

        r_a_hist = sandbox_idor.enviar("adm", "GET", "/suministros/reportes-gastos/historial", params={"limite": 100}, paso="D04_admin_historial")
        assert r_a_hist.status_code == 200
        items_a = r_a_hist.json().get("items", [])
        ids_a = [it.get("id_reporte_gasto_acumulado") for it in items_a]
        assert id_rep_admin in ids_a, "[RF-77 RNF Historial] Reporte generado por Admin no figura en su historial"
        assert id_rep_prod not in ids_a, f"[RF-77 RNF Historial] Fuga IDOR: reporte de Productor {id_rep_prod} apareció en historial de Admin"
        assert set(ids_p).isdisjoint(set(ids_a)), (
            f"[RF-77 RNF Historial] Intersección indebida entre historiales: {set(ids_p) & set(ids_a)}"
        )

    def test_d05a_idor_consultar_reporte_ajeno(self, sandbox_idor: CorridaSandboxIDOR):
        """D05a: Productor no puede consultar un reporte generado por otro usuario (RF-77 RNF Seguridad / TC-M05-024).

        La especificación (RF-77 / TC-M05-024) exige impedir el acceso sin fijar HTTP 403 vs 404 para reporte
        ajeno, por lo que se aceptan únicamente 403 o 404 sin datos del reporte y sin eventos de auditoría.
        Paso 0d (código) no mostró comprobación de dueño en el caso de uso; el Paso 0e observó 404 por RLS de modulo5. El esperado sale de la especificación.
        """
        id_rep_ajeno, id_prod = _asegurar_reporte_d05(sandbox_idor)
        top_id = _capturar_top_id_auditoria_idor(sandbox_idor, "D05a_auditoria_pre")
        r = sandbox_idor.enviar("prod", "GET", f"/suministros/reportes-gastos/{id_rep_ajeno}", paso="D05a_idor_consultar")
        _verificar_bloqueo_idor_reporte(
            sandbox_idor,
            id_rep_ajeno=id_rep_ajeno,
            id_prod=id_prod,
            top_id_previo=top_id,
            resp_idor=r,
            operacion="consultar",
        )

    def test_d05b_idor_regenerar_reporte_ajeno(self, sandbox_idor: CorridaSandboxIDOR):
        """D05b: Productor no puede regenerar un reporte generado por otro usuario (RF-77 RNF Seguridad / TC-M05-024).

        La especificación (RF-77 / TC-M05-024) exige impedir el acceso sin fijar HTTP 403 vs 404 para reporte
        ajeno, por lo que se aceptan únicamente 403 o 404 sin datos del reporte y sin evento REGENERACION.
        Paso 0d (código) no mostró comprobación de dueño en el caso de uso; el Paso 0e observó 404 por RLS de modulo5. El esperado sale de la especificación.
        """
        id_rep_ajeno, id_prod = _asegurar_reporte_d05(sandbox_idor)
        top_id = _capturar_top_id_auditoria_idor(sandbox_idor, "D05b_auditoria_pre")
        r = sandbox_idor.enviar("prod", "GET", f"/suministros/reportes-gastos/{id_rep_ajeno}/regenerar", paso="D05b_idor_regenerar")
        _verificar_bloqueo_idor_reporte(
            sandbox_idor,
            id_rep_ajeno=id_rep_ajeno,
            id_prod=id_prod,
            top_id_previo=top_id,
            resp_idor=r,
            operacion="regenerar",
        )

    def test_d05c_idor_exportar_reporte_ajeno(self, sandbox_idor: CorridaSandboxIDOR):
        """D05c: Productor no puede exportar un reporte generado por otro usuario (RF-77 RNF Seguridad / TC-M05-024).

        La especificación (RF-77 / TC-M05-024) exige impedir el acceso sin fijar HTTP 403 vs 404 para reporte
        ajeno, por lo que se aceptan únicamente 403 o 404 sin archivo creado y sin evento EXPORTACION.
        Paso 0d (código) no mostró comprobación de dueño en el caso de uso; el Paso 0e observó 404 por RLS de modulo5. El esperado sale de la especificación.
        """
        id_rep_ajeno, id_prod = _asegurar_reporte_d05(sandbox_idor)
        top_id = _capturar_top_id_auditoria_idor(sandbox_idor, "D05c_auditoria_pre")
        r = sandbox_idor.enviar(
            "prod",
            "POST",
            f"/suministros/reportes-gastos/{id_rep_ajeno}/exportacion",
            paso="D05c_idor_exportar",
            json_body={"formato_exportacion": "CSV"},
        )
        _verificar_bloqueo_idor_reporte(
            sandbox_idor,
            id_rep_ajeno=id_rep_ajeno,
            id_prod=id_prod,
            top_id_previo=top_id,
            resp_idor=r,
            operacion="exportar",
        )

    def test_d98_cierre_sandbox_idor(self, sandbox_idor: CorridaSandboxIDOR):
        """D98: Cierre ordenado de sandbox IDOR/Aislamiento y rollback atómico."""
        r = sandbox_idor.cerrar()
        assert r is not None and r.status_code == 200, f"Cierre sandbox IDOR falló: {r}"
        assert "Rollback exitoso" in r.text

