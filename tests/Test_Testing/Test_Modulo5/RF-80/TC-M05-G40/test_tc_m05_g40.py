# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G40: Resiliencia ante caida repositorio, cola y latencia RF-80 |
"""Suite de pruebas para TC-M05-G40: Resiliencia ante caida del repositorio de auditoria, cola y latencia (RF-80).

Cubre el caso TC-M05-095 de la hoja plana (agrupado 031):
- Medicion de latencia de registro de suministros (20 llamadas secuenciales, calculo p50, p95, max).
- Verificacion de presencia de cola persistente / buffer entre M05 y M12 con capacidad para 100.000 eventos (CA-9 / RNF-08).
- Declaracion formal de Cobertura No Ejecutada para escenarios no viables en sandbox:
  * Inyeccion de fallas / caida forzada de M12.
  * Alertas de saturacion de cola al 90% y 100%.
  * Politica de retencion FIFO de 48 horas.
  * Degradacion de latencia <= 50 ms respecto a linea base sin auditoria.
- Cierre ordenado e inocuidad del sandbox.
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

_CONTEXTO: dict[str, Any] = {
    "total_base": 0,
    "id_activo": None,
    "id_fase": None,
    "latencias_ms": [],
    "p50_ms": 0.0,
    "p95_ms": 0.0,
    "max_ms": 0.0,
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
    def __init__(self) -> None:
        self.run_id = f"tc-m05-g40-adm-{uuid.uuid4().hex[:8]}"
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
        email = _env("TEST_ADMIN_EMAIL")
        pwd = _env("TEST_ADMIN_PASSWORD")
        r = self.post(
            "/sesiones/",
            {"correo_electronico": email, "contrasena": pwd},
            paso="login_admin",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login admin HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, "PRECONDICION_NO_CUMPLIDA: login admin sin token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            return self._enviar("DELETE", f"/test-control/runs/{self.run_id}", paso="teardown_admin")
        finally:
            self.http.close()


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield


@pytest.fixture(scope="class")
def sandbox_admin():
    corrida = CorridaSandbox()
    corrida.login()
    try:
        yield corrida
    finally:
        corrida.cerrar()


class TestTCM05G40ResilienciaYLatencia:
    """TC-M05-G40: Resiliencia ante caida del repositorio de auditoria, cola y latencia (TC-M05-095 / 031)."""

    def test_t00_setup_linea_base_y_latencia(self, sandbox_admin: CorridaSandbox):
        """T00: Conteo inicial, activo propio, fase y medicion de latencia en 20 operaciones secuenciales de suministro."""
        c = sandbox_admin

        # Conteo inicial de auditoria
        r_ini = c.get("/suministros/auditoria", paso="t00_conteo_base", params={"pagina": 1, "registros_por_pagina": 1})
        assert r_ini.status_code == 200
        _CONTEXTO["total_base"] = r_ini.json().get("total", 0)

        # Crear activo poblacional dedicado
        tag = uuid.uuid4().hex[:8]
        hoy = _hoy()
        fecha_ciclo = (hoy - timedelta(days=20)).isoformat()
        payload_activo = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G40-{tag}",
            "cantidad_inicial": 100,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
            "peso_actual": 25.0,
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="t00_crear_activo")
        assert r_act.status_code == 201
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None
        _CONTEXTO["id_activo"] = id_activo

        # Abrir fase
        payload_fase = {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase QA G40"}
        r_fase = c.post(f"/activos-biologicos/{id_activo}/fases", payload_fase, paso="t00_abrir_fase")
        assert r_fase.status_code in (200, 201)
        _CONTEXTO["id_fase"] = r_fase.json().get("id_gestion_fases")

        # Ejecutar 20 operaciones secuenciales de suministro registrando la latencia de cada una
        latencias: list[float] = []
        for i in range(1, 21):
            t_inicio = time.perf_counter()
            r_sum = c.post(
                "/suministros/costeo-directo",
                {
                    "id_activo_biologico": id_activo,
                    "tipo_suministro": "SERVICIO_VETERINARIO",
                    "cantidad": 1.0,
                    "unidad_medida": "UNIDAD",
                    "precio_unitario": 50000.0 + (i * 100.0),
                    "fecha_aplicacion": hoy.isoformat(),
                    "justificacion_precio": f"Muestreo de latencia ciclo {i}",
                    "id_idempotencia": str(uuid.uuid4()),
                },
                paso=f"t00_muestra_latencia_{i}",
            )
            duracion_ms = round((time.perf_counter() - t_inicio) * 1000, 2)
            latencias.append(duracion_ms)
            assert r_sum.status_code == 200, f"Fallo en llamada {i}: HTTP {r_sum.status_code}"

        latencias_ordenadas = sorted(latencias)
        p50 = latencias_ordenadas[len(latencias_ordenadas) // 2]
        idx_95 = int(len(latencias_ordenadas) * 0.95)
        p95 = latencias_ordenadas[min(idx_95, len(latencias_ordenadas) - 1)]
        min_lat = min(latencias)
        max_lat = max(latencias)

        _CONTEXTO["latencias_ms"] = latencias
        _CONTEXTO["min_ms"] = min_lat
        _CONTEXTO["p50_ms"] = p50
        _CONTEXTO["p95_ms"] = p95
        _CONTEXTO["max_ms"] = max_lat

    def test_a01_cola_persistente_m12_capacidad_100k(self, sandbox_admin: CorridaSandbox):
        """A01 (TC-M05-095 / 031): Presencia de cola persistente / buffer entre M05 y M12 con capacidad para 100.000 eventos (Precondición 3, Restr. 6, Restr. 7, RNF-02, RNF-07)."""
        c = sandbox_admin

        # Verificar si en la base de datos o en la configuracion existe una cola/buffer persistente dedicada a M12
        # Segun la arquitectura verificada:
        # modulo5 persiste directamente de forma sincronica en PostgreSQL (modulo5.auditorias_suministros).
        # No existe cola en memoria persistente, broker externo (RabbitMQ/Kafka) ni tabla outbox para M12.
        q_sql = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'modulo5' 
          AND table_name IN ('cola_auditoria', 'buffer_auditoria', 'cola_eventos_m12', 'outbox_auditorias')
        """
        r_q = c.post("/test-control/query", {"query": q_sql}, paso="a01_verificar_cola_m12")
        assert r_q.status_code == 200
        tablas_cola = r_q.json().get("data", [])

        assert len(tablas_cola) > 0, (
            "DEFECTO_PRODUCTO (RF-80 Precondición 3, Restr. 6, Restr. 7, RNF-02, RNF-07 / TC-M05-095 / 031): "
            "La especificacion exige una cola persistente entre M05 y M12 con capacidad configurable de hasta 100.000 eventos "
            "para garantizar la resiliencia ante caidas del repositorio de auditoria. El backend carece de broker persistente "
            "(RabbitMQ/Kafka/Celery), buffer o tabla outbox (la persistencia es directa y sincronica en modulo5.auditorias_suministros)."
        )

    def test_t98_cierre_sandbox(self, sandbox_admin: CorridaSandbox):
        """T98: Cierre ordenado de sandbox Administrador y rollback."""
        c = sandbox_admin
        r = c.cerrar()
        assert r is not None
        assert r.status_code == 200
        data = r.json()
        mensaje = data.get("mensaje") or data.get("status") or ""
        assert "exitoso" in mensaje.lower(), f"Respuesta de rollback inesperada: {data}"

    def test_t99_inocuidad_rollback(self):
        """T99: Inocuidad - el conteo final de la bitacora coincide con la linea base."""
        base_url = _env("TEST_BASE_URL").rstrip("/")
        email = _env("TEST_ADMIN_EMAIL")
        pwd = _env("TEST_ADMIN_PASSWORD")

        r_login = requests.post(
            f"{base_url}/sesiones/",
            json={"correo_electronico": email, "contrasena": pwd},
            headers={"X-Zona-Horaria": NOMBRE_ZONA},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200
        token = r_login.json().get("token") or r_login.json().get("access_token")

        r_fin = requests.get(
            f"{base_url}/suministros/auditoria",
            headers={"Authorization": f"Bearer {token}", "X-Zona-Horaria": NOMBRE_ZONA},
            params={"pagina": 1, "registros_por_pagina": 1},
            timeout=TIMEOUT_S,
        )
        assert r_fin.status_code == 200
        total_fin = r_fin.json().get("total", 0)
        total_base = _CONTEXTO.get("total_base", 0)
        assert total_fin == total_base, (
            f"Fallo de inocuidad: el conteo de la bitacora cambio de {total_base} a {total_fin}"
        )

