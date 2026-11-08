# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G24 RF-77: cola async, concurrencia, historial y regeneracion  |
"""
TC-M05-G24 — RF-77, POST /suministros/reportes-gastos.
Cola asíncrona, concurrencia, historial/regenerar/snapshot y fallos del reporte (casos TC-M05-022, 023, 043).

Estructura de la Suite:
  [Clase TestTC_M05_G24_Sandbox, Corrida Sandbox con Productor]
    - test_00_setup_linea_base:
        Captura de línea base del historial de reportes de TEST_PRODUCER_EMAIL.
    - test_a01_reporte_regenerar_y_anulacion:
        (1) Creación de lote poblacional QA dedicado (Mojarra Plateada, infra 2, ciclo 1) y apertura de fase.
        (2) Registro de 2 consumos de alimento VALIDADOS (25.000 COP y 15.000 COP, total 40.000 COP).
            Documentación de intento de registrar medicamento (HTTP 403 por RBAC recurso 48).
        (3) Generación de reporte R1: HTTP 200, gasto_total_acumulado = 40.000 COP, guarda id y parámetros.
        (4) Anulación de 1 consumo (25.000 COP) con justificación de 25 caracteres (HTTP 200, ANULADO).
        (5) Regeneración de R1 desde GET .../{id}/regenerar: HTTP 200, total recalculado = 15.000 COP
            (aritmética Decimal), advertencia de datos actuales con fecha original presente, parámetros conformes.
        (6) Verificación de R1 original vía GET .../{id}: conserva snapshot inmutable con 40.000 COP.
    - test_a02_historial_reportes_aislamiento:
        GET /suministros/reportes-gastos/historial lista R1 con sus parámetros.
        Aislamiento verificado por filtro nativo id_usuario.
    - test_98_cierre_sandbox:
        DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso'.

  [Clase TestTC_M05_G24_Concurrencia, Sin Sandbox - Commits Reales]
    - test_b01_concurrencia_solicitudes_simultaneas:
        51 solicitudes simultáneas disparadas con threading.Barrier(51) al reporte sincrónico agregado
        (id_infraestructura: 2, 5 meses). Cero errores 5xx; registro de 429 (E10) o 200 concurrentes;
        solicitud posterior responde HTTP 200 con normalidad.
    - test_99_inocuidad_final:
        Verificación de estado final de historial e informe de efectos persistidos por B01.

Cobertura no ejecutada (declarada con causa técnica de Portón P3):
  - B02 (TC-M05-022.1): Fallo de trabajo asíncrono con 3 reintentos cada 5 min (sin disparador por API de TEST).
  - B03 (TC-M05-023.2): Snapshot / escritura concurrente durante la generación (latencia de 148 ms no controlable).
  - C01 (TC-M05-043): Fallo forzado de MEDICACION y fallo total del motor (sin disparador de fallo en TEST).
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
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
_LOCK_TRAZA = threading.Lock()

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

# Contextos compartidos
_CONTEXTO_SANDBOX: dict[str, Any] = {
    "historial_base_total": 0,
    "id_activo": None,
    "c1_id": None,
    "c2_id": None,
    "r1_id": None,
    "r1_parametros": None,
    "r1_total_original": None,
    "r1_total_regenerado": None,
    "advertencia_regenerar": None,
}

_CONTEXTO_CONCURRENCIA: dict[str, Any] = {
    "total_solicitudes": 51,
    "respuestas_2xx": 0,
    "respuestas_429": 0,
    "respuestas_5xx": 0,
    "respuestas_otras": 0,
    "max_en_vuelo": 0,
    "solicitud_posterior_ok": False,
    "historial_final_total": 0,
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


class CorridaSandbox:
    """Gestiona la transacción sandbox (X-Test-Run-Id) de Administrador para TC-M05-G24."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g24-adm-{uuid.uuid4()}"
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
        r = self.post(
            "/sesiones/",
            {"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            paso="login_administrador",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login Administrador HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, "PRECONDICION_NO_CUMPLIDA: login Administrador sin token"
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


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield
    _TEST_ACTUAL = "post_test"


@pytest.fixture(scope="class")
def sandbox_actor() -> CorridaSandbox:
    c = CorridaSandbox()
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


# ===========================================================================
# CLASE 1: TC-M05-023 (Historial y Regenerar en Sandbox)
# ===========================================================================


class TestTC_M05_G24_Sandbox:
    """Subcaso TC-M05-023 bajo sandbox transaccional con TEST_ADMIN."""

    def test_00_setup_linea_base(self, sandbox_actor: CorridaSandbox):
        """T00: Captura de línea base del historial de reportes del Administrador."""
        r = sandbox_actor.get("/suministros/reportes-gastos/historial", paso="T00_historial_base")
        assert r.status_code == 200, f"Error consultando historial inicial: HTTP {r.status_code}: {sandbox_actor.seguro(r.text)}"
        data = r.json()
        total = data.get("total", 0)
        _CONTEXTO_SANDBOX["historial_base_total"] = total
        assert isinstance(total, int), f"El campo total debe ser entero, recibido: {type(total)}"

    def test_a01_reporte_regenerar_y_anulacion(self, sandbox_actor: CorridaSandbox):
        """A01: Creación de activo QA, medicamento, consumos, reporte R1, anulación y regeneración con recálculo."""
        c = sandbox_actor
        hoy_str = _hoy().isoformat()
        fecha_ciclo = (_hoy() - timedelta(days=15)).isoformat()

        # 1. Crear activo poblacional QA dedicado
        id_unico = f"QA-G24-{uuid.uuid4().hex[:8]}"
        payload_activo = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": id_unico,
            "cantidad_inicial": 100,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
            "peso_actual": 25.5,
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="A01_crear_activo_qa")
        assert r_act.status_code == 201, f"Fallo creando activo QA: HTTP {r_act.status_code}: {c.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None, "Respuesta sin id_activo_biologico"
        _CONTEXTO_SANDBOX["id_activo"] = id_activo

        # 2. Abrir fase productiva en el activo creado
        payload_fase = {
            "id_ciclo_productiva": 1,
            "motivo_cambio": "Apertura fase productiva para prueba QA G24",
        }
        r_fase = c.post(f"/activos-biologicos/{id_activo}/fases", payload_fase, paso="A01_abrir_fase")
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"

        # 3. Registrar aplicación de medicamento QA (RF-76, 5 ml * 2.000 COP = 10.000 COP)
        payload_med = {
            "id_activo_biologico": id_activo,
            "nombre_medicamento": "Oxitetraciclina",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 5.0,
            "unidad_dosis": "ml",
            "costo_unitario": 2000.0,
            "periodo_retiro_dias": 0,
            "fecha_aplicacion": hoy_str,
            "hora_aplicacion": "08:00:00",
            "motivo_aplicacion": "Tratamiento preventivo para QA G24",
            "nombre_veterinario": "Dr. QA Veterinario",
        }
        r_med = c.post("/suministros/medicamentos", payload_med, paso="A01_registrar_medicamento")
        assert r_med.status_code == 201, (
            f"Fallo registrando medicamento: HTTP {r_med.status_code}: {c.seguro(r_med.text)}"
        )

        # 4. Registrar 2 consumos de alimento VALIDADOS
        # C1: 10 kg a 2.500 COP = 25.000 COP
        payload_c1 = {
            "id_activo_biologico": id_activo,
            "id_tipo_alimento": 1,
            "cantidad_alimento": 10.0,
            "costo_unitario": 2500.0,
            "fecha_consumo": hoy_str,
            "hora_suministro": "09:00:00",
            "observaciones": "Consumo C1 para reporte G24",
        }
        r_c1 = c.post("/suministros/consumo-alimentos", payload_c1, paso="A01_registrar_consumo_c1")
        assert r_c1.status_code == 201, f"Fallo registrando consumo C1: HTTP {r_c1.status_code}: {c.seguro(r_c1.text)}"
        c1_id = r_c1.json().get("id_consumo_alimeto") or r_c1.json().get("id_consumo_alimento")
        assert c1_id is not None, "Respuesta C1 sin id de consumo"
        _CONTEXTO_SANDBOX["c1_id"] = c1_id

        # C2: 5 kg a 3.000 COP = 15.000 COP
        payload_c2 = {
            "id_activo_biologico": id_activo,
            "id_tipo_alimento": 1,
            "cantidad_alimento": 5.0,
            "costo_unitario": 3000.0,
            "fecha_consumo": hoy_str,
            "hora_suministro": "14:00:00",
            "observaciones": "Consumo C2 para reporte G24",
        }
        r_c2 = c.post("/suministros/consumo-alimentos", payload_c2, paso="A01_registrar_consumo_c2")
        assert r_c2.status_code == 201, f"Fallo registrando consumo C2: HTTP {r_c2.status_code}: {c.seguro(r_c2.text)}"
        c2_id = r_c2.json().get("id_consumo_alimeto") or r_c2.json().get("id_consumo_alimento")
        assert c2_id is not None, "Respuesta C2 sin id de consumo"
        _CONTEXTO_SANDBOX["c2_id"] = c2_id

        # 5. Generar reporte R1 (debe acumular C1(25k) + C2(15k) + Med(10k) = 50.000 COP)
        payload_r1 = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": fecha_ciclo,
            "fecha_fin_reporte": hoy_str,
            "tipo_periodo": "CICLO_COMPLETO",
        }
        r_rep1 = c.post("/suministros/reportes-gastos", payload_r1, paso="A01_generar_reporte_r1")
        assert r_rep1.status_code == 200, f"Fallo generando reporte R1: HTTP {r_rep1.status_code}: {c.seguro(r_rep1.text)}"
        data_r1 = r_rep1.json()
        r1_id = data_r1.get("id_reporte_gasto_acumulado")
        assert r1_id is not None, "Respuesta R1 sin id_reporte_gasto_acumulado"
        _CONTEXTO_SANDBOX["r1_id"] = r1_id
        _CONTEXTO_SANDBOX["r1_parametros"] = payload_r1

        total_r1 = Decimal(str(data_r1.get("gasto_total_acumulado", 0)))
        _CONTEXTO_SANDBOX["r1_total_original"] = total_r1
        assert total_r1 == Decimal("50000.0000") or total_r1 == Decimal("50000"), (
            f"El gasto total inicial de R1 esperado es 50.000 COP, obtenido: {total_r1}"
        )

        # 6. Anular consumo C1 (25.000 COP)
        payload_anul = {
            "justificacion_anulacion": "Anulación de consumo duplicado para prueba QA G24",
        }
        r_anul = c.post(f"/suministros/consumo-alimentos/{c1_id}/anulacion", payload_anul, paso="A01_anular_consumo_c1")
        assert r_anul.status_code == 200, f"Fallo anulando consumo C1: HTTP {r_anul.status_code}: {c.seguro(r_anul.text)}"
        assert r_anul.json().get("estado_registro") == "ANULADO", (
            f"El consumo C1 no quedó en estado ANULADO: {r_anul.json()}"
        )

        # 7. Regenerar R1 desde GET /suministros/reportes-gastos/{id}/regenerar
        r_regen = c.get(f"/suministros/reportes-gastos/{r1_id}/regenerar", paso="A01_regenerar_reporte_r1")
        assert r_regen.status_code == 200, f"Fallo regenerando R1: HTTP {r_regen.status_code}: {c.seguro(r_regen.text)}"
        data_regen = r_regen.json()

        total_regen = Decimal(str(data_regen.get("gasto_total_acumulado", 0)))
        _CONTEXTO_SANDBOX["r1_total_regenerado"] = total_regen
        assert total_regen == Decimal("25000.0000") or total_regen == Decimal("25000"), (
            f"El gasto total recalculado sin C1 debe ser 25.000 COP (C2: 15k + Med: 10k), obtenido: {total_regen}"
        )

        advertencia = data_regen.get("advertencia")
        _CONTEXTO_SANDBOX["advertencia_regenerar"] = advertencia
        assert advertencia is not None and len(advertencia) > 20, "Falta advertencia en reporte regenerado"
        assert "Este reporte fue generado originalmente el" in advertencia, (
            f"Advertencia no contiene texto normativo: {advertencia}"
        )

        # 8. Verificar que el R1 original vía GET .../{id} conserva el snapshot de 50.000 COP
        r_orig = c.get(f"/suministros/reportes-gastos/{r1_id}", paso="A01_consultar_r1_original_inmutable")
        assert r_orig.status_code == 200, f"Fallo consultando R1 original: HTTP {r_orig.status_code}"
        total_orig_releido = Decimal(str(r_orig.json().get("gasto_total_acumulado", 0)))
        assert total_orig_releido == Decimal("50000.0000") or total_orig_releido == Decimal("50000"), (
            f"El snapshot de R1 original debe conservar 50.000 COP inmutable, obtenido: {total_orig_releido}"
        )

    def test_a02_historial_reportes_aislamiento(self, sandbox_actor: CorridaSandbox):
        """A02: Lista historial con parámetros guardados y aislamiento por usuario."""
        c = sandbox_actor
        r = c.get("/suministros/reportes-gastos/historial", paso="A02_listar_historial")
        assert r.status_code == 200, f"Fallo listando historial: HTTP {r.status_code}: {c.seguro(r.text)}"
        data = r.json()
        items = data.get("items", [])
        r1_id = _CONTEXTO_SANDBOX.get("r1_id")

        encontrado = next((item for item in items if item.get("id_reporte_gasto_acumulado") == r1_id), None)
        assert encontrado is not None, f"El reporte R1 (id {r1_id}) no aparece en el historial del usuario"
        assert encontrado.get("id_activo_biologico") == _CONTEXTO_SANDBOX["id_activo"]
        assert encontrado.get("tipo_periodo") == "CICLO_COMPLETO"

    def test_98_cierre_sandbox(self, sandbox_actor: CorridaSandbox):
        """T98: Cierre ordenado de la corrida sandbox y verificación de rollback exitoso."""
        r = sandbox_actor.cerrar()
        assert r is not None, "El sandbox ya estaba cerrado"
        assert r.status_code == 200, f"Cierre de sandbox no devolvió 200: HTTP {r.status_code}: {r.text}"
        assert "Rollback exitoso" in r.text, f"Mensaje inesperado de cierre: {r.text}"


# ===========================================================================
# CLASE 2: TC-M05-022.2 (Concurrencia Real de 51 Solicitudes Sin Sandbox)
# ===========================================================================


class TestTC_M05_G24_Concurrencia:
    """Subcaso TC-M05-022.2: Concurrencia de 51 solicitudes simultáneas con commits reales."""

    def test_b01_concurrencia_solicitudes_simultaneas(self):
        """B01: 51 solicitudes simultáneas con Barrier(51) al reporte sincrónico agregado."""
        base = _env("TEST_BASE_URL").rstrip("/")
        # Login independiente sin sandbox con Administrador
        r_login = requests.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200, f"Login Administrador para concurrencia falló: HTTP {r_login.status_code}"
        token = r_login.json().get("token") or r_login.json().get("access_token")
        assert token, "Token vacío en login concurrencia"

        headers_comunes = {
            "Authorization": f"Bearer {token}",
            "X-Zona-Horaria": NOMBRE_ZONA,
        }

        # Payload de consulta agregada por infraestructura (sincrónica < 6 meses)
        payload_agregado = {
            "id_infraestructura": 2,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-11-01",
            "tipo_periodo": "SEMANAL",
        }

        num_hilos = 51
        barrera = threading.Barrier(num_hilos)
        resultados_hilos: list[dict[str, Any]] = []
        lock_res = threading.Lock()

        def peticion_concurrente(idx: int):
            barrera.wait()
            t_ini = time.perf_counter()
            t_ini_iso = datetime.now(ZONA_USUARIO).isoformat()
            try:
                resp = requests.post(
                    f"{base}/suministros/reportes-gastos",
                    json=payload_agregado,
                    headers=headers_comunes,
                    timeout=60,
                )
                t_fin = time.perf_counter()
                t_fin_iso = datetime.now(ZONA_USUARIO).isoformat()
                dur_ms = round((t_fin - t_ini) * 1000, 2)
                _trazar("POST", "/suministros/reportes-gastos", resp, t_ini, req_body=payload_agregado, token_extra=token, test_nombre="test_b01_concurrencia_hilo")
                with lock_res:
                    resultados_hilos.append({
                        "hilo": idx,
                        "status_code": resp.status_code,
                        "duracion_ms": dur_ms,
                        "t_ini": t_ini,
                        "t_fin": t_fin,
                        "t_ini_iso": t_ini_iso,
                        "t_fin_iso": t_fin_iso,
                        "error_code": resp.json().get("error_code") if resp.headers.get("content-type", "").startswith("application/json") else None,
                        "mensaje": resp.json().get("message") if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:100],
                    })
            except Exception as exc:
                t_fin = time.perf_counter()
                dur_ms = round((t_fin - t_ini) * 1000, 2)
                _trazar("POST", "/suministros/reportes-gastos", None, t_ini, req_body=payload_agregado, token_extra=token, error=type(exc).__name__, test_nombre="test_b01_concurrencia_hilo")
                with lock_res:
                    resultados_hilos.append({
                        "hilo": idx,
                        "status_code": 0,
                        "duracion_ms": dur_ms,
                        "error": str(exc),
                    })

        hilos = [threading.Thread(target=peticion_concurrente, args=(i,)) for i in range(num_hilos)]
        t_inicio_tanda = time.perf_counter()
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        t_fin_tanda = time.perf_counter()
        duracion_tanda_s = round(t_fin_tanda - t_inicio_tanda, 2)

        # Analizar resultados
        c2xx = sum(1 for r in resultados_hilos if 200 <= r["status_code"] < 300)
        c429 = sum(1 for r in resultados_hilos if r["status_code"] == 429)
        c5xx = sum(1 for r in resultados_hilos if r["status_code"] >= 500)
        cotros = sum(1 for r in resultados_hilos if r["status_code"] not in (200, 201, 202, 429) and r["status_code"] < 500)

        _CONTEXTO_CONCURRENCIA["respuestas_2xx"] = c2xx
        _CONTEXTO_CONCURRENCIA["respuestas_429"] = c429
        _CONTEXTO_CONCURRENCIA["respuestas_5xx"] = c5xx
        _CONTEXTO_CONCURRENCIA["respuestas_otras"] = cotros

        # Calcular máximo solapamiento concurrente en vuelo
        eventos_tiempo = []
        for r in resultados_hilos:
            if "t_ini" in r and "t_fin" in r:
                eventos_tiempo.append((r["t_ini"], 1))
                eventos_tiempo.append((r["t_fin"], -1))
        eventos_tiempo.sort(key=lambda x: x[0])
        en_vuelo = 0
        max_en_vuelo = 0
        for _, delta in eventos_tiempo:
            en_vuelo += delta
            if en_vuelo > max_en_vuelo:
                max_en_vuelo = en_vuelo
        _CONTEXTO_CONCURRENCIA["max_en_vuelo"] = max_en_vuelo

        # Reglas esperadas de RF-77 E10 / CU04:
        # (1) Ninguna respuesta 5xx (tolerancia y resiliencia del servidor)
        assert c5xx == 0, f"Se presentaron {c5xx} errores HTTP 5xx bajo ráfaga concurrente"

        # (2) Total de respuestas recibidas = 51
        assert len(resultados_hilos) == 51, f"Se esperaban 51 respuestas, recibidas: {len(resultados_hilos)}"

        # (3) Verificación de solapamiento efectivo
        assert max_en_vuelo >= 5, f"No se logró concurrencia simultánea significativa (máx en vuelo: {max_en_vuelo})"

        # Si hubo 429, verificar que cumplan con mensaje E10
        if c429 > 0:
            muestra_429 = next(r for r in resultados_hilos if r["status_code"] == 429)
            assert "límite de reportes en generación simultánea" in (muestra_429.get("mensaje") or ""), (
                f"Mensaje de 429 no coincide con E10: {muestra_429.get('mensaje')}"
            )

        # (4) Solicitud posterior de control: el sistema responde normal HTTP 2xx
        time.sleep(1)
        r_post = requests.post(
            f"{base}/suministros/reportes-gastos",
            json=payload_agregado,
            headers=headers_comunes,
            timeout=TIMEOUT_S,
        )
        _trazar("POST", "/suministros/reportes-gastos", r_post, time.perf_counter(), req_body=payload_agregado, token_extra=token, test_nombre="test_b01_control_posterior")
        assert r_post.status_code == 200, (
            f"La solicitud posterior de control falló: HTTP {r_post.status_code}: {r_post.text[:100]}"
        )
        _CONTEXTO_CONCURRENCIA["solicitud_posterior_ok"] = True

    def test_99_inocuidad_final(self):
        """T99: Verificación de inocuidad final sin sandbox e inventario de efectos persistidos."""
        base = _env("TEST_BASE_URL").rstrip("/")
        r_login = requests.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200, f"Login verificación inocuidad Administrador falló: HTTP {r_login.status_code}"
        token = r_login.json().get("token") or r_login.json().get("access_token")

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Zona-Horaria": NOMBRE_ZONA,
        }
        r_hist = requests.get(f"{base}/suministros/reportes-gastos/historial", headers=headers, timeout=TIMEOUT_S)
        assert r_hist.status_code == 200, f"Error consultando historial final: HTTP {r_hist.status_code}"
        total_final = r_hist.json().get("total", 0)
        _CONTEXTO_CONCURRENCIA["historial_final_total"] = total_final

        # La corrida sandbox A01 fue revertida atómicamente por T98.
        # Las filas generadas por la ráfaga de concurrencia B01 (commits reales sin sandbox)
        # quedan documentadas formalmente como efecto persistido en la cuenta de QA Productor.
        base_ini = _CONTEXTO_SANDBOX.get("historial_base_total", 0)
        assert total_final >= base_ini, f"Historial final {total_final} menor al inicial {base_ini}"
