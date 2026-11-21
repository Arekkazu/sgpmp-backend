# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G21 RF-77: Sin costo, sin datos y tendencia (016 y 018)        |
"""
TC-M05-G21 — RF-77, POST /suministros/reportes-gastos.
Sin costo registrado, reporte sin datos y cálculo de tendencia (casos TC-M05-016 y TC-M05-018).

Cobertura No Ejecutada (Declarada por limitación de API según Portón P1):
  - A01 (TC-M05-016): Registros SIN costo_unitario.
    El DTO de consumo de alimentos (RF-75) y el DTO de aplicación de medicamentos (RF-76)
    validan estrictamente 'costo_unitario > 0' a nivel de esquema (pydantic), respondiendo HTTP 400
    ante valores null o <= 0. La API pública no permite crear suministros sin costo. Conforme
    a las reglas del prompt, no se simula en base de datos y se declara como limitación de contrato.

Checkpoints Evaluados:
  - test_00_setup_linea_base:
      Línea base previa del historial de reportes del Administrador.
  - test_a02_rango_sin_registros_sin_datos:
      Rango de fechas sin consumos ni medicaciones: HTTP 200, estado 'SIN_DATOS',
      sin_datos=True, gasto_total_acumulado=0 (RF-77 E1 / TC-M05-016).
  - test_b01_tendencia_variacion_calculada:
      Escenario (a): anterior > 0 y actual > 0.
      Variación porcentual exacta ((actual - anterior) / anterior * 100), estado 'CALCULADA' (TC-M05-018).
  - test_b02_tendencia_sin_base_comparativa:
      Escenario (b): anterior = 0 y actual > 0.
      Estado 'SIN_BASE_COMPARATIVA' con nota de la spec (TC-M05-018).
  - test_b03_tendencia_sin_movimiento:
      Escenario (c): anterior = 0 y actual = 0.
      Estado 'SIN_MOVIMIENTO' (TC-M05-018).
  - test_b04_tendencia_recorte_inicio_ciclo:
      Escenario (d): período anterior cae antes de fecha_inicio_ciclo.
      Período anterior recortado al ciclo con nota que incluye la fecha de inicio del ciclo (TC-M05-018).
  - test_98_cierre_sandbox:
      DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso'.
  - test_99_inocuidad_final:
      Verificación fuera de sandbox: historial del Admin coincide con la línea base.
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

NOMBRE_ZONA = "America/Bogota"
ZONA_USUARIO = timezone(timedelta(hours=-5))
TIMEOUT_S = 30
ARCHIVO_TRAZA = "trazas_http.jsonl"
_LOCK_TRAZA = threading.Lock()

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

_CONTEXTO: dict[str, Any] = {
    "historial_base_total": 0,
    "id_activo_a02": None,
    "id_activo_b01": None,
    "id_activo_b02": None,
    "id_activo_b03": None,
    "id_activo_b04": None,
}

_TEST_ACTUAL = "init"


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: falta la variable de entorno {nombre}")
    return valor or ""


def _secretos() -> list[str]:
    return [
        s for s in (
            _env("TEST_SANDBOX_SECRET", False),
            _env("TEST_ADMIN_PASSWORD", False),
            _env("TEST_ADMIN_EMAIL", False),
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


class CorridaSandboxG21:
    """Gestiona la transacción sandbox (X-Test-Run-Id) de Administrador para TC-M05-G21."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g21-adm-{uuid.uuid4().hex[:12]}"
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
def corrida_g21() -> CorridaSandboxG21:
    c = CorridaSandboxG21()
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G21_SinCosto_Tendencia:
    """Suite TC-M05-G21: Sin costo, sin datos y análisis de tendencia (RF-77, TC-M05-016 y 018)."""

    def test_00_setup_linea_base(self, corrida_g21: CorridaSandboxG21):
        """T00: Captura de línea base del historial de reportes del Administrador."""
        c = corrida_g21
        r_hist = c.get("/suministros/reportes-gastos/historial", paso="T00_historial_linea_base")
        assert r_hist.status_code == 200, (
            f"Error capturando línea base: HTTP {r_hist.status_code}: {c.seguro(r_hist.text)}"
        )
        datos = r_hist.json()
        total_base = len(datos) if isinstance(datos, list) else len(datos.get("items", []))
        _CONTEXTO["historial_base_total"] = total_base

    def test_a02_rango_sin_registros_sin_datos(self, corrida_g21: CorridaSandboxG21):
        """A02 (TC-M05-016): Rango de fechas sin registros con costo.
        HTTP 200 con estado 'SIN_DATOS', sin_datos=True, reporte en cero y mensaje informativo (E1)."""
        c = corrida_g21

        # 1. Crear activo dedicado sin consumos en el rango
        fecha_ciclo = "2026-05-01"
        id_unico = f"QA-G21-SINDATOS-{uuid.uuid4().hex[:6]}"
        payload_activo = {
            "tipo_activo": "INDIVIDUAL",
            "id_especie": 5,
            "id_infraestructura": 389,
            "identificador": id_unico,
            "raza": "Holstein",
            "sexo": "Hembra",
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="A02_crear_activo_sin_datos")
        assert r_act.status_code == 201, f"Fallo creando activo: HTTP {r_act.status_code}: {c.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        _CONTEXTO["id_activo_a02"] = id_activo

        # 2. Abrir fase
        r_fase = c.post(
            f"/activos-biologicos/{id_activo}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase QA G21", "fecha_inicio": "2026-05-01T05:00:00Z"},
            paso="A02_abrir_fase",
        )
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"

        # 3. Solicitar reporte en un rango donde NO hay gastos registrados (junio 2026)
        payload_rep = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2026-06-01",
            "fecha_fin_reporte": "2026-06-30",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = c.post("/suministros/reportes-gastos", payload_rep, paso="A02_reporte_sin_datos")
        assert r_rep.status_code == 200, f"Reporte sin datos respondió HTTP {r_rep.status_code}: {c.seguro(r_rep.text)}"
        rep = r_rep.json()

        assert rep["sin_datos"] is True, f"sin_datos debe ser True: {rep['sin_datos']}"
        assert rep["estado"] == "SIN_DATOS", f"estado debe ser 'SIN_DATOS': {rep['estado']}"
        assert Decimal(str(rep["gasto_total_acumulado"])) == Decimal("0"), f"Total debe ser 0: {rep['gasto_total_acumulado']}"
        assert rep.get("mensaje") is not None, "El reporte SIN_DATOS debe incluir mensaje de RF-77 E1"
        assert len(rep.get("desglose_categorias", [])) == 0, "desglose_categorias debe ser vacío"

    def test_b01_tendencia_variacion_calculada(self, corrida_g21: CorridaSandboxG21):
        """B01 (TC-M05-018 Escenario a): anterior > 0 y actual > 0.
        Variación porcentual calculada exactamente según la fórmula ((actual - anterior)/anterior * 100)."""
        c = corrida_g21

        # Activo con ciclo desde 2026-06-01
        fecha_ciclo = "2026-06-01"
        id_unico = f"QA-G21-TEND-A-{uuid.uuid4().hex[:6]}"
        payload_activo = {
            "tipo_activo": "INDIVIDUAL",
            "id_especie": 5,
            "id_infraestructura": 389,
            "identificador": id_unico,
            "raza": "Holstein",
            "sexo": "Hembra",
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="B01_crear_activo")
        assert r_act.status_code == 201
        id_activo = r_act.json()["id_activo_biologico"]
        _CONTEXTO["id_activo_b01"] = id_activo

        c.post(f"/activos-biologicos/{id_activo}/fases", {"id_ciclo_productiva": 5, "motivo_cambio": "Fase", "fecha_inicio": "2026-06-01T05:00:00Z"})

        # Período actual: 2026-08-01 al 2026-08-31 (31 días)
        # Período anterior equivalente: 2026-07-01 al 2026-07-31 (31 días)
        # Gasto anterior: 20.000 COP
        r_ant = c.post("/suministros/consumo-alimentos", {
            "id_activo_biologico": id_activo, "id_tipo_alimento": 1, "fecha_consumo": "2026-07-15",
            "hora_suministro": "08:00:00", "cantidad_alimento": 20.0, "costo_unitario": 1000.0,
        }, paso="B01_consumo_anterior")
        assert r_ant.status_code == 201

        # Gasto actual: 30.000 COP
        r_act_c = c.post("/suministros/consumo-alimentos", {
            "id_activo_biologico": id_activo, "id_tipo_alimento": 1, "fecha_consumo": "2026-08-15",
            "hora_suministro": "08:00:00", "cantidad_alimento": 30.0, "costo_unitario": 1000.0,
        }, paso="B01_consumo_actual")
        assert r_act_c.status_code == 201

        # Generar reporte de agosto (31 días)
        r_rep = c.post("/suministros/reportes-gastos", {
            "activo_biologico_id": id_activo, "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": "2026-08-31", "tipo_periodo": "MENSUAL",
        }, paso="B01_reporte_tendencia_a")
        assert r_rep.status_code == 200
        rep = r_rep.json()
        tend = rep.get("tendencia") or {}

        g_actual = Decimal(str(tend.get("gasto_periodo_actual")))
        g_anterior = Decimal(str(tend.get("gasto_periodo_anterior")))
        var_pct = Decimal(str(tend.get("variacion_porcentual")))

        assert g_actual == Decimal("30000.0000"), f"Gasto actual incorrecto: {g_actual}"
        assert g_anterior == Decimal("20000.0000"), f"Gasto anterior incorrecto: {g_anterior}"
        # ((30000 - 20000) / 20000) * 100 = 50.00%
        esperado_pct = ((Decimal("30000") - Decimal("20000")) / Decimal("20000")) * Decimal("100")
        assert abs(var_pct - esperado_pct) <= Decimal("0.01"), f"Variación esperada {esperado_pct}%, obtenida {var_pct}%"
        assert tend.get("estado") == "CALCULADA", f"Estado de tendencia incorrecto: {tend.get('estado')}"

    def test_b02_tendencia_sin_base_comparativa(self, corrida_g21: CorridaSandboxG21):
        """B02 (TC-M05-018 Escenario b): anterior = 0 y actual > 0.
        Estado 'SIN_BASE_COMPARATIVA', variacion_porcentual=None y nota de la spec."""
        c = corrida_g21

        fecha_ciclo = "2026-06-01"
        id_unico = f"QA-G21-TEND-B-{uuid.uuid4().hex[:6]}"
        payload_activo = {
            "tipo_activo": "INDIVIDUAL",
            "id_especie": 5,
            "id_infraestructura": 389,
            "identificador": id_unico,
            "raza": "Holstein",
            "sexo": "Hembra",
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="B02_crear_activo")
        assert r_act.status_code == 201
        id_activo = r_act.json()["id_activo_biologico"]
        _CONTEXTO["id_activo_b02"] = id_activo

        c.post(f"/activos-biologicos/{id_activo}/fases", {"id_ciclo_productiva": 5, "motivo_cambio": "Fase", "fecha_inicio": "2026-06-01T05:00:00Z"})

        # Período actual: 2026-08-01 al 2026-08-31 (31 días). Gasto = 25.000 COP
        # Período anterior (2026-07-01 al 2026-07-31): 0 COP
        r_act_c = c.post("/suministros/consumo-alimentos", {
            "id_activo_biologico": id_activo, "id_tipo_alimento": 1, "fecha_consumo": "2026-08-15",
            "hora_suministro": "08:00:00", "cantidad_alimento": 25.0, "costo_unitario": 1000.0,
        }, paso="B02_consumo_actual")
        assert r_act_c.status_code == 201

        r_rep = c.post("/suministros/reportes-gastos", {
            "activo_biologico_id": id_activo, "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": "2026-08-31", "tipo_periodo": "MENSUAL",
        }, paso="B02_reporte_tendencia_b")
        assert r_rep.status_code == 200
        rep = r_rep.json()
        tend = rep.get("tendencia") or {}

        assert Decimal(str(tend.get("gasto_periodo_actual"))) == Decimal("25000.0000")
        assert Decimal(str(tend.get("gasto_periodo_anterior"))) == Decimal("0")
        assert tend.get("variacion_porcentual") is None
        assert tend.get("estado") == "SIN_BASE_COMPARATIVA"
        nota = tend.get("nota") or ""
        assert "No existen gastos registrados en el período anterior equivalente" in nota, (
            f"Nota de SIN_BASE_COMPARATIVA no conforme con spec: {nota!r}"
        )

    def test_b03_tendencia_sin_movimiento(self, corrida_g21: CorridaSandboxG21):
        """B03 (TC-M05-018 Escenario c): anterior = 0 y actual = 0.
        Estado 'SIN_MOVIMIENTO' y variacion_porcentual=None."""
        c = corrida_g21

        fecha_ciclo = "2026-06-01"
        id_unico = f"QA-G21-TEND-C-{uuid.uuid4().hex[:6]}"
        payload_activo = {
            "tipo_activo": "INDIVIDUAL",
            "id_especie": 5,
            "id_infraestructura": 389,
            "identificador": id_unico,
            "raza": "Holstein",
            "sexo": "Hembra",
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="B03_crear_activo")
        assert r_act.status_code == 201
        id_activo = r_act.json()["id_activo_biologico"]
        _CONTEXTO["id_activo_b03"] = id_activo

        c.post(f"/activos-biologicos/{id_activo}/fases", {"id_ciclo_productiva": 5, "motivo_cambio": "Fase", "fecha_inicio": "2026-06-01T05:00:00Z"})

        # Sin consumos registrados en ningún período
        r_rep = c.post("/suministros/reportes-gastos", {
            "activo_biologico_id": id_activo, "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": "2026-08-31", "tipo_periodo": "MENSUAL",
        }, paso="B03_reporte_tendencia_c")
        assert r_rep.status_code == 200
        rep = r_rep.json()
        tend = rep.get("tendencia") or {}

        assert Decimal(str(tend.get("gasto_periodo_actual"))) == Decimal("0")
        assert Decimal(str(tend.get("gasto_periodo_anterior"))) == Decimal("0")
        assert tend.get("variacion_porcentual") is None
        assert tend.get("estado") == "SIN_MOVIMIENTO"

    def test_b04_tendencia_recorte_inicio_ciclo(self, corrida_g21: CorridaSandboxG21):
        """B04 (TC-M05-018 Escenario d): anterior antes del inicio del ciclo.
        El período anterior se recorta al inicio del ciclo y se incluye la nota con la fecha del ciclo."""
        c = corrida_g21

        # Ciclo que inicia el 2026-08-10
        fecha_ciclo = "2026-08-10"
        id_unico = f"QA-G21-TEND-D-{uuid.uuid4().hex[:6]}"
        payload_activo = {
            "tipo_activo": "INDIVIDUAL",
            "id_especie": 5,
            "id_infraestructura": 389,
            "identificador": id_unico,
            "raza": "Holstein",
            "sexo": "Hembra",
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="B04_crear_activo")
        assert r_act.status_code == 201
        id_activo = r_act.json()["id_activo_biologico"]
        _CONTEXTO["id_activo_b04"] = id_activo

        c.post(f"/activos-biologicos/{id_activo}/fases", {"id_ciclo_productiva": 5, "motivo_cambio": "Fase", "fecha_inicio": "2026-08-10T05:00:00Z"})

        # Período actual: 2026-08-20 al 2026-08-31 (12 días)
        # Período anterior no recortado sería: 2026-08-08 al 2026-08-19 (12 días)
        # Pero 2026-08-08 < 2026-08-10, por lo que se RECORTA al 2026-08-10 (10 días: 2026-08-10 a 2026-08-19).
        # Gasto en el anterior recortado (2026-08-12): 10.000 COP
        r_ant = c.post("/suministros/consumo-alimentos", {
            "id_activo_biologico": id_activo, "id_tipo_alimento": 1, "fecha_consumo": "2026-08-12",
            "hora_suministro": "08:00:00", "cantidad_alimento": 10.0, "costo_unitario": 1000.0,
        }, paso="B04_consumo_anterior_recortado")
        assert r_ant.status_code == 201

        # Gasto en el actual (2026-08-25): 15.000 COP
        r_act_c = c.post("/suministros/consumo-alimentos", {
            "id_activo_biologico": id_activo, "id_tipo_alimento": 1, "fecha_consumo": "2026-08-25",
            "hora_suministro": "08:00:00", "cantidad_alimento": 15.0, "costo_unitario": 1000.0,
        }, paso="B04_consumo_actual")
        assert r_act_c.status_code == 201

        # Generar reporte del 2026-08-20 al 2026-08-31
        r_rep = c.post("/suministros/reportes-gastos", {
            "activo_biologico_id": id_activo, "fecha_inicio_reporte": "2026-08-20",
            "fecha_fin_reporte": "2026-08-31", "tipo_periodo": "SEMANAL",
        }, paso="B04_reporte_tendencia_d")
        assert r_rep.status_code == 200
        rep = r_rep.json()
        tend = rep.get("tendencia") or {}

        g_actual = Decimal(str(tend.get("gasto_periodo_actual")))
        g_anterior = Decimal(str(tend.get("gasto_periodo_anterior")))
        var_pct = Decimal(str(tend.get("variacion_porcentual")))

        assert g_actual == Decimal("15000.0000")
        assert g_anterior == Decimal("10000.0000")
        esperado_pct = ((Decimal("15000") - Decimal("10000")) / Decimal("10000")) * Decimal("100")  # 50.00%
        assert abs(var_pct - esperado_pct) <= Decimal("0.01")
        assert tend.get("estado") == "CALCULADA"

        nota = tend.get("nota") or ""
        assert "El período anterior fue recortado al inicio del ciclo productivo (2026-08-10)" in nota, (
            f"Nota de recorte no conforme con spec: {nota!r}"
        )

    def test_98_cierre_sandbox(self, corrida_g21: CorridaSandboxG21):
        """T98: Cierre ordenado de la sesión sandbox y verificación de rollback atómico."""
        c = corrida_g21
        r_del = c.cerrar()
        assert r_del is not None, "Error: cierre ya invocado previamente"
        assert r_del.status_code == 200, (
            f"DELETE /test-control/runs/{c.run_id} respondió HTTP {r_del.status_code}: {c.seguro(r_del.text)}"
        )
        assert "Rollback exitoso" in r_del.text, f"Mensaje de rollback no encontrado: {c.seguro(r_del.text)}"

    def test_99_inocuidad_final(self):
        """T99: Inocuidad final fuera de sandbox. Historial base coincide con final."""
        base = _env("TEST_BASE_URL").rstrip("/")
        s = requests.Session()
        r_login = s.post(
            f"{base}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200, "Login de verificación final falló"
        token = r_login.json().get("token") or r_login.json().get("access_token")
        s.headers["Authorization"] = f"Bearer {token}"

        r_hist = s.get(f"{base}/suministros/reportes-gastos/historial", timeout=TIMEOUT_S)
        assert r_hist.status_code == 200, "Consulta de historial final falló"
        datos = r_hist.json()
        total_final = len(datos) if isinstance(datos, list) else len(datos.get("items", []))
        total_base = _CONTEXTO["historial_base_total"]

        assert total_final == total_base, (
            f"Efectos persistidos detectados: historial inicial {total_base} != final {total_final}"
        )

