# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G22 RF-77: Validación de rangos y límites sínc/asínc (017 y 019)|
"""
TC-M05-G22 — RF-77, POST /suministros/reportes-gastos.
Validación de rangos de fechas, reglas de negocio y umbrales síncronos/asíncronos (casos TC-M05-017 y TC-M05-019).

Checkpoints:
  - test_00_setup_linea_base:
      Línea base del historial de reportes y creación de activo individual dedicado con fecha_inicio_ciclo en el pasado.
  - test_a01_rango_fechas_invertido:
      inicio > fin: HTTP 400 (RF-77 E2). El historial no crece.
  - test_a02_fecha_fin_futura:
      fin > hoy (mañana): HTTP 400 (Restr. 2). El historial no crece.
  - test_a03_fecha_inicio_anterior_ciclo:
      inicio < fecha_inicio_ciclo del activo: HTTP 400 (RF-77 E3). El historial no crece.
  - test_a04_activo_sin_ciclo_productivo:
      Activo sin ciclo (fecha_inicio_ciclo null, Activo 9): HTTP 422 (RF-77 E7). El historial no crece.
  - test_a05_consulta_agregada_sin_rango_fechas:
      Consulta agregada sin fechas: HTTP 400 (RF-77 E9 / DTO). El historial no crece.
  - test_b01_limite_sincrono_individual_12_meses:
      Activo individual, rango de exactamente 12 meses (<= 366 días): HTTP 200 en <= 12 s (CA-7 / RNF).
  - test_b02_umbral_asincrono_individual_supera_12_meses:
      Activo individual, rango que supera 12 meses (> 366 días): HTTP 202 con id_cola (RF-77 E4) y mensaje de cola.
  - test_b03_limite_sincrono_agregado_6_meses:
      Consulta agregada, rango de 6 meses (<= 183 días): HTTP 200 en <= 12 s (Restr. 13).
  - test_b04_umbral_asincrono_agregado_supera_6_meses:
      Consulta agregada, rango que supera 6 meses (> 183 días): HTTP 202 con id_cola (RF-77 E8).
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
    "id_activo_ind": None,
    "duracion_b01_s": 0.0,
    "duracion_b03_s": 0.0,
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


class CorridaSandboxG22:
    """Gestiona la transacción sandbox (X-Test-Run-Id) de Administrador para TC-M05-G22."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g22-adm-{uuid.uuid4().hex[:12]}"
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

    def contar_historial(self) -> int:
        r = self.get("/suministros/reportes-gastos/historial", paso="contar_historial")
        if r.status_code != 200:
            return -1
        datos = r.json()
        return len(datos) if isinstance(datos, list) else len(datos.get("items", []))

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
def corrida_g22() -> CorridaSandboxG22:
    c = CorridaSandboxG22()
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G22_Rangos_Limites:
    """Suite TC-M05-G22: Validación de rangos y límites síncronos/asíncronos (RF-77, TC-M05-017 y 019)."""

    def test_00_setup_linea_base(self, corrida_g22: CorridaSandboxG22):
        """T00: Captura de línea base del historial y creación de activo individual QA con ciclo antiguo."""
        c = corrida_g22
        total_base = c.contar_historial()
        assert total_base >= 0, "Fallo obteniendo línea base del historial"
        _CONTEXTO["historial_base_total"] = total_base

        # Crear activo individual con ciclo que inicia hace 15 meses (2025-08-01)
        fecha_ciclo = "2025-08-01"
        id_unico = f"QA-G22-IND-{uuid.uuid4().hex[:6]}"
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
        r_act = c.post("/activos-biologicos", payload_activo, paso="T00_crear_activo_ciclo_antiguo")
        assert r_act.status_code == 201, f"Fallo creando activo con ciclo antiguo: HTTP {r_act.status_code}: {c.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None, "Respuesta sin id_activo_biologico"
        _CONTEXTO["id_activo_ind"] = id_activo

        # Abrir fase productiva en el pasado
        r_fase = c.post(
            f"/activos-biologicos/{id_activo}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase QA G22", "fecha_inicio": "2025-08-01T05:00:00Z"},
            paso="T00_abrir_fase",
        )
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"

    def test_a01_rango_fechas_invertido(self, corrida_g22: CorridaSandboxG22):
        """A01 (TC-M05-017 / E2): fecha_inicio > fecha_fin responde HTTP 400 y no genera reporte."""
        c = corrida_g22
        hist_antes = c.contar_historial()
        id_activo = _CONTEXTO["id_activo_ind"]

        payload = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2026-08-31",
            "fecha_fin_reporte": "2026-08-01",
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="A01_inicio_mayor_fin")
        assert r.status_code == 400, f"Se esperaba HTTP 400, obtenido {r.status_code}: {c.seguro(r.text)}"
        err = r.json()
        assert "no puede ser posterior a la fecha de fin" in err.get("message", "") or "RANGO_FECHAS_INVALIDO" in str(err)
        hist_despues = c.contar_historial()
        assert hist_despues == hist_antes, "El historial creció indebidamente tras error de validación"

    def test_a02_fecha_fin_futura(self, corrida_g22: CorridaSandboxG22):
        """A02 (TC-M05-017 / Restr. 2): fecha_fin futura (mañana) responde HTTP 400 y no genera reporte."""
        c = corrida_g22
        hist_antes = c.contar_historial()
        id_activo = _CONTEXTO["id_activo_ind"]

        manana = (datetime.now(ZONA_USUARIO).date() + timedelta(days=1)).isoformat()
        payload = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": manana,
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="A02_fecha_fin_futura")
        assert r.status_code == 400, f"Se esperaba HTTP 400, obtenido {r.status_code}: {c.seguro(r.text)}"
        err = r.json()
        assert "no puede ser futuro" in err.get("message", "") or "FECHA_FIN_FUTURA" in str(err)
        hist_despues = c.contar_historial()
        assert hist_despues == hist_antes, "El historial creció indebidamente tras fecha futura"

    def test_a03_fecha_inicio_anterior_ciclo(self, corrida_g22: CorridaSandboxG22):
        """A03 (TC-M05-017 / E3): fecha_inicio anterior a fecha_inicio_ciclo responde HTTP 400."""
        c = corrida_g22
        hist_antes = c.contar_historial()
        id_activo = _CONTEXTO["id_activo_ind"]

        # fecha_inicio_ciclo del activo es 2025-08-01
        payload = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2025-07-01",  # 1 mes antes del ciclo
            "fecha_fin_reporte": "2025-08-31",
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="A03_inicio_anterior_ciclo")
        assert r.status_code == 400, f"Se esperaba HTTP 400, obtenido {r.status_code}: {c.seguro(r.text)}"
        err = r.json()
        assert "es anterior a la fecha de inicio del ciclo productivo" in err.get("message", "") or "FECHA_INICIO_ANTERIOR_CICLO" in str(err)
        hist_despues = c.contar_historial()
        assert hist_despues == hist_antes, "El historial creció indebidamente"

    def test_a04_activo_sin_ciclo_productivo(self, corrida_g22: CorridaSandboxG22):
        """A04 (TC-M05-017 / E7): Activo sin ciclo productivo (activo 9 en lectura) responde HTTP 422."""
        c = corrida_g22
        hist_antes = c.contar_historial()

        payload = {
            "activo_biologico_id": 9,
            "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": "2026-08-31",
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="A04_activo_sin_ciclo")
        assert r.status_code == 422, f"Se esperaba HTTP 422, obtenido {r.status_code}: {c.seguro(r.text)}"
        err = r.json()
        assert "no tiene un ciclo productivo registrado" in err.get("message", "") or "ACTIVO_SIN_CICLO" in str(err)
        hist_despues = c.contar_historial()
        assert hist_despues == hist_antes, "El historial creció indebidamente"

    def test_a05_consulta_agregada_sin_rango_fechas(self, corrida_g22: CorridaSandboxG22):
        """A05 (TC-M05-017 / E9): Consulta agregada sin rango de fechas responde HTTP 400."""
        c = corrida_g22
        hist_antes = c.contar_historial()

        payload = {
            "id_infraestructura": 389,
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="A05_agregada_sin_fechas")
        assert r.status_code == 400, f"Se esperaba HTTP 400, obtenido {r.status_code}: {c.seguro(r.text)}"
        err = r.json()
        assert len(err.get("message", "") or err.get("detail", "") or str(err)) > 0
        hist_despues = c.contar_historial()
        assert hist_despues == hist_antes, "El historial creció indebidamente"

    def test_b01_limite_sincrono_individual_12_meses(self, corrida_g22: CorridaSandboxG22):
        """B01 (TC-M05-019): Activo individual, rango de exactamente 12 meses (<= 366 días).
        HTTP 200 síncrono en <= 12 s (CA-7 / RNF)."""
        c = corrida_g22
        id_activo = _CONTEXTO["id_activo_ind"]

        # Rango de exactamente 366 días: 2025-08-01 al 2026-08-01
        payload = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2025-08-01",
            "fecha_fin_reporte": "2026-08-01",
            "tipo_periodo": "MENSUAL",
        }
        t0 = time.perf_counter()
        r = c.post("/suministros/reportes-gastos", payload, paso="B01_individual_12_meses_sincrono")
        duracion_s = time.perf_counter() - t0
        _CONTEXTO["duracion_b01_s"] = duracion_s

        assert r.status_code == 200, f"Se esperaba HTTP 200, obtenido {r.status_code}: {c.seguro(r.text)}"
        assert duracion_s <= 12.0, f"El reporte tardó {duracion_s:.2f} s, superando el límite RNF de 12 s"
        rep = r.json()
        assert rep.get("id_reporte_gasto_acumulado") is not None
        assert rep.get("estado") in ("GENERADO", "SIN_DATOS")

    def test_b02_umbral_asincrono_individual_supera_12_meses(self, corrida_g22: CorridaSandboxG22):
        """B02 (TC-M05-019 / E4): Activo individual, rango que supera 12 meses (> 366 días).
        HTTP 202 con id_cola y mensaje de encolamiento."""
        c = corrida_g22
        id_activo = _CONTEXTO["id_activo_ind"]

        # Rango de 367 días (12 meses + 1 día): 2025-08-01 al 2026-08-02
        payload = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2025-08-01",
            "fecha_fin_reporte": "2026-08-02",
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="B02_individual_supera_12_meses_async")
        assert r.status_code == 202, f"Se esperaba HTTP 202, obtenido {r.status_code}: {c.seguro(r.text)}"
        datos = r.json()
        assert datos.get("id_cola") is not None, f"Respuesta 202 sin id_cola: {datos}"
        assert datos.get("estado") == "PENDIENTE"
        mensaje = datos.get("mensaje") or ""
        assert "meses" in mensaje and ("asíncrona" in mensaje or "asincrona" in mensaje), f"Mensaje 202 no conforme: {mensaje!r}"

    def test_b03_limite_sincrono_agregado_6_meses(self, corrida_g22: CorridaSandboxG22):
        """B03 (TC-M05-019): Consulta agregada, rango de 6 meses (<= 183 días).
        HTTP 200 síncrono en <= 12 s (Restr. 13)."""
        c = corrida_g22

        # Rango de exactamente 183 días: 2026-01-01 al 2026-07-02
        payload = {
            "id_infraestructura": 389,
            "fecha_inicio_reporte": "2026-01-01",
            "fecha_fin_reporte": "2026-07-02",
            "tipo_periodo": "MENSUAL",
        }
        t0 = time.perf_counter()
        r = c.post("/suministros/reportes-gastos", payload, paso="B03_agregada_6_meses_sincrono")
        duracion_s = time.perf_counter() - t0
        _CONTEXTO["duracion_b03_s"] = duracion_s

        assert r.status_code == 200, f"Se esperaba HTTP 200, obtenido {r.status_code}: {c.seguro(r.text)}"
        assert duracion_s <= 12.0, f"Consulta agregada tardó {duracion_s:.2f} s, superando límite de 12 s"
        rep = r.json()
        assert rep.get("id_reporte_gasto_acumulado") is not None

    def test_b04_umbral_asincrono_agregado_supera_6_meses(self, corrida_g22: CorridaSandboxG22):
        """B04 (TC-M05-019 / E8): Consulta agregada que supera 6 meses (> 183 días).
        HTTP 202 con id_cola y mensaje de procesamiento asíncrono."""
        c = corrida_g22

        # Rango de 184 días (6 meses + 1 día): 2026-01-01 al 2026-07-03
        payload = {
            "id_infraestructura": 389,
            "fecha_inicio_reporte": "2026-01-01",
            "fecha_fin_reporte": "2026-07-03",
            "tipo_periodo": "MENSUAL",
        }
        r = c.post("/suministros/reportes-gastos", payload, paso="B04_agregada_supera_6_meses_async")
        assert r.status_code == 202, f"Se esperaba HTTP 202, obtenido {r.status_code}: {c.seguro(r.text)}"
        datos = r.json()
        assert datos.get("id_cola") is not None, f"Respuesta 202 sin id_cola: {datos}"
        assert datos.get("estado") == "PENDIENTE"
        mensaje = datos.get("mensaje") or ""
        assert "meses" in mensaje and ("asíncrona" in mensaje or "asincrona" in mensaje), (
            f"Mensaje 202 no conforme: {mensaje!r}"
        )

    def test_98_cierre_sandbox(self, corrida_g22: CorridaSandboxG22):
        """T98: Cierre ordenado de la sesión sandbox y verificación de rollback atómico."""
        c = corrida_g22
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

