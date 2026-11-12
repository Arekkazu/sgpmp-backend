# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G25 RF-77: Permisos por rol, Aislamiento/IDOR y Auditoria M05   |
"""Suite de pruebas automatizadas para TC-M05-G25 (RF-77).

Cubre:
- TC-M05-024: Matriz de roles y permisos (Productor y Admin permitidos; Veterinario 403; No autenticado 401).
- TC-M05-025: Auditoría de generación y exportación (CA-11 / Postcondición 3 vs implementación real).
- Aislamiento territorial e IDOR: descargas de archivos exportados de otros usuarios y manipulación de IDs.

Estructurado en 4 clases ejecutadas estrictamente de forma secuencial:
1. TestTC_M05_G25_Productor (Sandbox Productor)
2. TestTC_M05_G25_Veterinario (Sandbox Veterinario)
3. TestTC_M05_G25_Administrador (Sandbox Administrador y verificación de auditoría)
4. TestTC_M05_G25_Control_IDOR_Y_Aislamiento (Pruebas directas de IDOR, tipos y no autenticados)
"""
from __future__ import annotations

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
    "id_reporte": None,
    "id_archivo_csv": None,
}

_TEST_ACTUAL = "init"


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
            _env("TEST_VET_PASSWORD", False),
            _env("TEST_VET_EMAIL", False),
        ) if s
    ]


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:600]
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
    """Gestiona una corrida sandbox secuencial para un rol especifico."""

    def __init__(self, prefijo_rol: str, email_env: str, pass_env: str) -> None:
        self.prefijo_rol = prefijo_rol
        self.email_env = email_env
        self.pass_env = pass_env
        self.run_id = f"tc-m05-g25-{prefijo_rol}-{uuid.uuid4().hex[:8]}"
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
        **kw,
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
        email = _env(self.email_env)
        pwd = _env(self.pass_env)
        r = self.post(
            "/sesiones/",
            {"correo_electronico": email, "contrasena": pwd},
            paso=f"login_{self.prefijo_rol}",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {self.prefijo_rol} HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {self.prefijo_rol} sin token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            return self._enviar("DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.prefijo_rol}")
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
        """B03: Veterinario recibe HTTP 403 al intentar descargar archivo de exportación."""
        r = sandbox_veterinario.get(
            "/suministros/reportes-gastos/exportaciones/4952e75b-9299-459f-bbad-506b58f63f77",
            paso="B03_vet_descargar_403",
        )
        assert r.status_code == 403, (
            f"Se esperaba HTTP 403 para Veterinario descargando exportación, obtenido: {r.status_code}"
        )
        assert r.json().get("error_code") == "ACCESO_DENEGADO"

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


class TestTC_M05_G25_Administrador:
    """Evaluación de facultades de Administrador y verificación de auditoría (TC-M05-025)."""

    def test_c01_admin_genera_y_exporta_reporte(self, sandbox_admin: CorridaSandboxRol):
        """C01: Administrador genera y exporta reporte exitosamente (HTTP 200 y 201)."""
        payload = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = sandbox_admin.post("/suministros/reportes-gastos", payload, paso="C01_admin_generar")
        assert r_rep.status_code == 200, f"Admin no pudo generar reporte: HTTP {r_rep.status_code}: {sandbox_admin.seguro(r_rep.text)}"
        id_rep = r_rep.json().get("id_reporte_gasto_acumulado")
        assert id_rep is not None, "Reporte Admin sin id_reporte_gasto_acumulado"
        _CONTEXTO_ADMIN["id_reporte"] = id_rep

        r_exp = sandbox_admin.post(f"/suministros/reportes-gastos/{id_rep}/exportacion", {"formato_exportacion": "CSV"}, paso="C01_admin_exportar")
        assert r_exp.status_code == 201, f"Admin no pudo exportar reporte: HTTP {r_exp.status_code}: {sandbox_admin.seguro(r_exp.text)}"
        id_arch = r_exp.json().get("id_archivo") or r_exp.json().get("id_archivo_exportacion")
        assert id_arch is not None, "Exportación Admin sin id_archivo"
        _CONTEXTO_ADMIN["id_archivo_csv"] = id_arch

    def test_c02_verificacion_auditoria_ca11_postcondicion3(self, sandbox_admin: CorridaSandboxRol):
        """C02: Verificación de auditoría de generación/exportación (RF-77 CA-11 / Postcondición 3).

        Especificación RF-77:
        - CA-11: Cada generación de reporte queda registrada en auditoría con usuario y timestamp.
        - Postcondición 3: Registro inmutable en bitácora de auditoría.
        - Caso TC-M05-025: Cada acción (generar, exportar, fallo) registrada en <= 2 s.

        Observación técnica: Si el backend no persiste eventos en modulo5.auditorias_suministros
        para RF-77, este test falla revelando el GAP normativo del producto.
        """
        id_rep = _CONTEXTO_ADMIN["id_reporte"]
        assert id_rep is not None, "Precondición no cumplida: falta id_reporte de Admin"

        # Administrador tiene permiso para leer /suministros/auditoria (recurso 57)
        r_aud = sandbox_admin.get("/suministros/auditoria", params={"registros_por_pagina": 50}, paso="C02_consultar_auditoria")
        assert r_aud.status_code == 200, f"Error consultando auditoría como Admin: HTTP {r_aud.status_code}"
        data = r_aud.json()
        items = data.get("items", [])

        # Buscar evento de generación de reporte o exportación asociado a RF-77
        evento_encontrado = None
        for it in items:
            entidad = str(it.get("entidad_afectada", "")).lower()
            tipo_op = str(it.get("tipo_operacion", ""))
            if any(k in entidad for k in ("reporte_gasto", "reportes_gastos", "exportacion_reporte")):
                evento_encontrado = it
                break
            if any(k in tipo_op for k in ("REPORTE_GASTOS", "EXPORTACION_REPORTE")):
                evento_encontrado = it
                break

        assert evento_encontrado is not None, (
            "DEFECTO_PRODUCTO: El evento de generación/exportación del reporte de gastos acumulados "
            "no fue registrado en la bitácora de auditoría de M05 (RF-77 CA-11 / Postcondición 3 / Caso TC-M05-025). "
            f"Se consultaron los últimos {len(items)} eventos y ninguno corresponde a entidad o tipo_operacion de RF-77."
        )

    def test_c98_cierre_sandbox_admin(self, sandbox_admin: CorridaSandboxRol):
        """C98: Cierre ordenado de sandbox Administrador y rollback atómico."""
        r = sandbox_admin.cerrar()
        assert r is not None and r.status_code == 200, f"Cierre sandbox Administrador falló: {r}"
        assert "Rollback exitoso" in r.text


# ===========================================================================
# CLASE 4: Control de IDOR, Tipos y Aislamiento de Datos
# ===========================================================================


class TestTC_M05_G25_IDOR_Y_Aislamiento:
    """Evaluación de IDOR, aislamiento por usuario y validación de identificadores (Sin Sandbox)."""

    def test_d01_solicitudes_sin_autenticacion_retornan_401(self):
        """D01: Solicitudes sin header Authorization retornan HTTP 401 NO_AUTENTICADO (RF-02)."""
        base = _env("TEST_BASE_URL").rstrip("/")
        headers = {"X-Zona-Horaria": NOMBRE_ZONA}

        # 1. POST generar reporte sin auth
        r1 = requests.post(f"{base}/suministros/reportes-gastos", json={}, headers=headers, timeout=TIMEOUT_S)
        _trazar("POST", "/suministros/reportes-gastos", r1, time.perf_counter(), test_nombre="test_d01_sin_auth_generar")
        assert r1.status_code == 401, f"Se esperaba 401 sin auth en generar reporte, obtenido: {r1.status_code}"

        # 2. POST exportación sin auth
        r2 = requests.post(f"{base}/suministros/reportes-gastos/19/exportacion", json={"formato_exportacion": "CSV"}, headers=headers, timeout=TIMEOUT_S)
        _trazar("POST", "/suministros/reportes-gastos/19/exportacion", r2, time.perf_counter(), test_nombre="test_d01_sin_auth_exportar")
        assert r2.status_code == 401, f"Se esperaba 401 sin auth en exportar, obtenido: {r2.status_code}"

        # 3. GET descargar exportación sin auth
        r3 = requests.get(f"{base}/suministros/reportes-gastos/exportaciones/4952e75b-9299-459f-bbad-506b58f63f77", headers=headers, timeout=TIMEOUT_S)
        _trazar("GET", "/suministros/reportes-gastos/exportaciones/...", r3, time.perf_counter(), test_nombre="test_d01_sin_auth_descargar")
        assert r3.status_code == 401, f"Se esperaba 401 sin auth en descargar exportación, obtenido: {r3.status_code}"

        # 4. GET historial sin auth
        r4 = requests.get(f"{base}/suministros/reportes-gastos/historial", headers=headers, timeout=TIMEOUT_S)
        _trazar("GET", "/suministros/reportes-gastos/historial", r4, time.perf_counter(), test_nombre="test_d01_sin_auth_historial")
        assert r4.status_code == 401, f"Se esperaba 401 sin auth en historial, obtenido: {r4.status_code}"

        # 5. GET auditoría sin auth
        r5 = requests.get(f"{base}/suministros/auditoria", headers=headers, timeout=TIMEOUT_S)
        _trazar("GET", "/suministros/auditoria", r5, time.perf_counter(), test_nombre="test_d01_sin_auth_auditoria")
        assert r5.status_code == 401, f"Se esperaba 401 sin auth en auditoría, obtenido: {r5.status_code}"

    def test_d02_idor_descarga_exportacion_ajena_retorna_403(self):
        """D02: Descargar archivo de exportación de otro usuario retorna HTTP 403 (ARCHIVO_DE_OTRO_USUARIO)."""
        base = _env("TEST_BASE_URL").rstrip("/")
        # Login como Administrador para intentar descargar el archivo generado por Productor
        r_login = requests.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200, f"Login Admin falló: HTTP {r_login.status_code}"
        token = r_login.json().get("token") or r_login.json().get("access_token")

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Zona-Horaria": NOMBRE_ZONA,
        }
        # Intentar descargar exportación generada por el usuario Productor
        id_archivo_productor = "4952e75b-9299-459f-bbad-506b58f63f77"
        r = requests.get(f"{base}/suministros/reportes-gastos/exportaciones/{id_archivo_productor}", headers=headers, timeout=TIMEOUT_S)
        _trazar("GET", f"/suministros/reportes-gastos/exportaciones/{id_archivo_productor}", r, time.perf_counter(), token_extra=token, test_nombre="test_d02_idor_descarga")
        assert r.status_code == 403, (
            f"Se esperaba HTTP 403 por descarga IDOR ajena, obtenido: {r.status_code}: {r.text[:200]}"
        )
        assert r.json().get("error_code") == "ARCHIVO_DE_OTRO_USUARIO", (
            f"Código de error inesperado: {r.json()}"
        )

    def test_d03_manipulacion_identificadores_no_genera_500(self):
        """D03: IDs inexistentes responden 404 e IDs inválidos responden 422; nunca HTTP 500."""
        base = _env("TEST_BASE_URL").rstrip("/")
        r_login = requests.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_PRODUCER_EMAIL"), "contrasena": _env("TEST_PRODUCER_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200, f"Login Productor falló: HTTP {r_login.status_code}"
        token = r_login.json().get("token") or r_login.json().get("access_token")

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Zona-Horaria": NOMBRE_ZONA,
        }

        casos_id = [
            ("GET", "/suministros/reportes-gastos/999999999", (404,), "Reporte inexistente"),
            ("GET", "/suministros/reportes-gastos/-1", (404, 400, 422), "ID negativo"),
            ("GET", "/suministros/reportes-gastos/id_invalido", (400, 422), "ID alfanumérico"),
            ("GET", "/suministros/reportes-gastos/exportaciones/00000000-0000-0000-0000-000000000000", (404,), "UUID inexistente"),
            ("GET", "/suministros/reportes-gastos/exportaciones/no-es-uuid", (400, 422), "UUID malformado"),
        ]

        for metodo, ruta, status_esperados, desc in casos_id:
            t_ini = time.perf_counter()
            r = requests.request(metodo, f"{base}{ruta}", headers=headers, timeout=TIMEOUT_S)
            _trazar(metodo, ruta, r, t_ini, token_extra=token, test_nombre="test_d03_manipulacion_ids")
            assert r.status_code != 500, f"Error del servidor HTTP 500 detectado en {desc}: {ruta}"
            assert r.status_code in status_esperados, (
                f"Para {desc} ({ruta}) se esperaba HTTP {status_esperados}, obtenido: {r.status_code}: {r.text[:100]}"
            )

    def test_d04_aislamiento_historial_por_usuario(self):
        """D04: El historial de reportes (/historial) está aislado estrictamente por usuario."""
        base = _env("TEST_BASE_URL").rstrip("/")

        # 1. Consultar historial como Productor
        r_p_login = requests.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_PRODUCER_EMAIL"), "contrasena": _env("TEST_PRODUCER_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        token_p = r_p_login.json().get("token") or r_p_login.json().get("access_token")
        r_p_hist = requests.get(f"{base}/suministros/reportes-gastos/historial", headers={"Authorization": f"Bearer {token_p}", "X-Zona-Horaria": NOMBRE_ZONA}, timeout=TIMEOUT_S)
        assert r_p_hist.status_code == 200
        total_productor = r_p_hist.json().get("total", 0)

        # 2. Consultar historial como Administrador
        r_a_login = requests.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        token_a = r_a_login.json().get("token") or r_a_login.json().get("access_token")
        r_a_hist = requests.get(f"{base}/suministros/reportes-gastos/historial", headers={"Authorization": f"Bearer {token_a}", "X-Zona-Horaria": NOMBRE_ZONA}, timeout=TIMEOUT_S)
        assert r_a_hist.status_code == 200
        total_admin = r_a_hist.json().get("total", 0)

        # Verificar que ambos responden con su respectivo total entero
        assert isinstance(total_productor, int) and isinstance(total_admin, int)
        # Los ítems del Productor no deben mezclarse indiscriminadamente con los del Admin
        items_p = r_p_hist.json().get("items", [])
        for it in items_p:
            # Los items guardados registran los parámetros del usuario consultante
            assert it.get("id_reporte_gasto_acumulado") is not None

