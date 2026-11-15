# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G37: Persistencia y clasificacion de eventos RF-80 (CU06)      |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G37 reevaluacion v2.0: unidad servicio, rechazos RF-78/79/81, R8, clasificacion, sandbox en T99 |
# | 2026-11-15 | Juan Sebastian Gutierrez | Reintento 2 (INC-M05-353-G37): A02c/A02d exactamente 1 evento con confirmacion a 2 s; A04 dividido en A04a/A04b/A04c (R8, E2, CA-11, CA-12, CA-4); obtenido real por checkpoint |
"""Suite de pruebas para TC-M05-G37 (RF-80 v2.0, RFC-025 / TC-M05-090 y TC-M05-091).

Cubre:
- T00: Linea base en corrida sandbox independiente de solo lectura.
- A01a/A01b/A01c: Persistencia inmediata (<= 2.0 s) de operaciones exitosas RF-78, RF-81 y RF-79.
- A02a/A02b/A02c/A02d: Auditoria de rechazos de negocio RF-78 (sin/con fase + repeticion), RF-79 y RF-81.
- A03: Consistencia lista vs detalle GET /{id} y filtros para EXITOSO y REGISTRO_FALLIDO.
- A04a: Restriccion 8 / E2 / CA-11: todo evento del catalogo con un minimo ausente queda registro_incompleto=true.
- A04b: CA-12: detalle_causa nombra cada campo faltante con su nombre de campo.
- A04c: CA-4 / R8: los eventos de RF-78 apuntan al id_registro_suministro creado.
- B01/B02: Clasificacion y retencion NIC41 / 5 años vs TECNICO / 1 año y tipo no catalogado.
- T98/T99: Cierre de corrida principal e inocuidad en corrida sandbox independiente.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
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
ARCHIVO_OBTENIDOS = "obtenidos_checkpoints.jsonl"
VENTANA_CA1_S = 2.0
_LOCK_TRAZA = threading.Lock()
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_COMMIT_FALLBACK = "5b8bcf49ab073ba3b43ef554d4c3799a8b672f0f"

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

_CATALOGO_RF80 = {
    "SUMINISTRO_REGISTRADO",
    "SUMINISTRO_CORREGIDO",
    "PRECIO_MANUAL_INGRESADO",
    "ACUMULADO_ACTUALIZADO",
    "CICLO_CONSOLIDADO",
    "REGISTRO_FALLIDO",
    "REPORTE_COSTOS_GENERADO",
    "PROVISION_INCREMENTAL_ENTREGADA",
    "PROVISION_INCREMENTAL_FALLIDA",
    "PROVISION_PENDIENTE",
    "CONSULTA_HISTORIAL_EJECUTADA",
    "EXPORTACION_HISTORIAL_GENERADA",
}

_TODOS_MINIMOS = (
    "tipo_operacion",
    "resultado",
    "fecha_emision",
    "id_activo_biologico",
    "id_ciclo_productivo",
)

_MINIMOS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "SUMINISTRO_REGISTRADO": _TODOS_MINIMOS + ("id_registro_suministro", "id_tipo_suministro", "costo_afectado", "origen_precio", "id_usuario"),
    "SUMINISTRO_CORREGIDO": _TODOS_MINIMOS + ("id_registro_suministro", "id_tipo_suministro", "costo_afectado", "origen_precio", "id_usuario"),
    "ACUMULADO_ACTUALIZADO": _TODOS_MINIMOS + ("id_registro_suministro", "costo_afectado"),
    "CICLO_CONSOLIDADO": _TODOS_MINIMOS + ("costo_afectado",),
    "PRECIO_MANUAL_INGRESADO": _TODOS_MINIMOS + ("id_registro_suministro", "origen_precio", "id_usuario"),
    "REPORTE_COSTOS_GENERADO": _TODOS_MINIMOS + ("costo_afectado",),
    "PROVISION_INCREMENTAL_ENTREGADA": _TODOS_MINIMOS + ("id_registro_suministro",),
    "PROVISION_INCREMENTAL_FALLIDA": _TODOS_MINIMOS + ("id_registro_suministro", "numero_reintentos", "timestamps_intentos"),
    "PROVISION_PENDIENTE": _TODOS_MINIMOS + ("numero_reintentos",),
    "REGISTRO_FALLIDO": _TODOS_MINIMOS + ("id_tipo_suministro", "numero_reintentos"),
    "CONSULTA_HISTORIAL_EJECUTADA": _TODOS_MINIMOS + ("id_usuario",),
    "EXPORTACION_HISTORIAL_GENERADA": _TODOS_MINIMOS + ("id_usuario",),
}

_CONTEXTO: dict[str, Any] = {
    "total_base": None,
    "ultimo_id_base": None,
    "ultimo_id_corrida": None,
    "id_usuario_admin": None,
    "id_activo_1": None,
    "id_activo_2": None,
    "id_fase_1": None,
    "id_registro_suministro_1": None,
    "id_provision_1": None,
    "evento_rf78": None,
    "evento_a02a": None,
    "evento_rf79_consolidado": None,
    "evento_rf79_reporte": None,
    "evento_rf81": None,
    "ids_eventos_a01a": None,
    "evento_a02c": None,
    "evento_a02d": None,
    "eventos_a04": None,
    "sandbox_cerrado_t98": False,
}

_TEST_ACTUAL = "init"


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: falta la variable de entorno {nombre}")
    return valor or ""


def _hoy() -> date:
    return datetime.now(ZONA_USUARIO).date()


def _commit_local() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_RAIZ_REPO,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return _COMMIT_FALLBACK


def _secretos() -> list[str]:
    claves = (
        "TEST_SANDBOX_SECRET",
        "TEST_ADMIN_PASSWORD",
        "TEST_ADMIN_EMAIL",
        "TEST_PRODUCER_PASSWORD",
        "TEST_FIELD_ENGINEER_PASSWORD",
        "TEST_DB_PASSWORD",
        "BROKER_SERVICE_TOKEN",
        "TEST_VET_PASSWORD",
        "TEST_VET_EMAIL",
    )
    vals: list[str] = []
    for k in claves:
        v = _env(k, False)
        if v:
            vals.append(v)
            if len(v) >= 20:
                vals.append(v[-20:])
    return vals


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:600]
    for s in [*_secretos(), *extra]:
        if s and len(s) > 3:
            texto = texto.replace(s, "***REDACTED***")
    prefijo_jwt = "ey" + "J"
    if prefijo_jwt in texto:
        texto = re.sub(rf"{prefijo_jwt}[a-zA-Z0-9_\-\.]+", "***REDACTED_JWT***", texto)
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
    x_request_id = None

    if resp is not None:
        status_code = resp.status_code
        server_date = resp.headers.get("Date", "")
        x_request_id = resp.headers.get("X-Request-Id")
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
        "x_request_id": x_request_id,
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


def _obt(clave: str, valor: Any) -> None:
    """Registra un valor REAL observado del checkpoint en curso (obtenidos_checkpoints.jsonl).

    Se llama ANTES de cada asercion para que el obtenido quede aunque la asercion falle.
    El generador arma el 'obtenido' del checkpoint con estas lineas, en orden.
    """
    directorio = os.environ.get("TEST_EVIDENCE_DIR")
    if not directorio:
        return
    registro = {"test": _TEST_ACTUAL, "clave": clave, "valor": _sanitizar_objeto(valor)}
    with _LOCK_TRAZA:
        try:
            with open(Path(directorio) / ARCHIVO_OBTENIDOS, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass


def _error_code(resp: requests.Response) -> Any:
    """error_code real de la respuesta, o None si el cuerpo no es un JSON con ese campo."""
    try:
        cuerpo = resp.json()
    except Exception:
        return None
    return cuerpo.get("error_code") if isinstance(cuerpo, dict) else None


def _ev_resumen(ev: dict[str, Any]) -> dict[str, Any]:
    """Campos reales de un evento de la bitacora para el obtenido (sin datos personales)."""
    datos_nuevos = ev.get("datos_nuevos") if isinstance(ev.get("datos_nuevos"), dict) else {}
    return {
        "id": ev.get("id_auditoria_suministro"),
        "tipo_operacion": ev.get("tipo_operacion"),
        "resultado": ev.get("resultado"),
        "id_usuario": ev.get("id_usuario"),
        "id_activo_biologico": ev.get("id_activo_biologico"),
        "id_ciclo_productivo": ev.get("id_ciclo_productivo"),
        "id_gestion_fases": ev.get("id_gestion_fases"),
        "id_registro_suministro": ev.get("id_registro_suministro", datos_nuevos.get("id_registro_suministro")),
        "id_tipo_suministro": ev.get("id_tipo_suministro", datos_nuevos.get("id_tipo_suministro")),
        "costo_afectado": ev.get("costo_afectado"),
        "numero_reintentos": ev.get("numero_reintentos"),
        "registro_incompleto": ev.get("registro_incompleto"),
        "detalle_causa": ev.get("detalle_causa"),
        "clasificacion_registro": ev.get("clasificacion_registro"),
        "retencion_aplicable": ev.get("retencion_aplicable"),
        "fecha_emision": ev.get("fecha_emision"),
    }


def _extraer_sub_jwt(token: str) -> int:
    partes = token.split(".")
    assert len(partes) >= 2, "JWT invalido sin payload"
    seg = partes[1]
    seg += "=" * (-len(seg) % 4)
    payload = json.loads(base64.urlsafe_b64decode(seg.encode("ascii")).decode("utf-8"))
    sub = payload.get("sub")
    assert sub is not None, "JWT sin claim sub"
    return int(sub)


def _es_uuid_valido(valor: Any) -> bool:
    if not isinstance(valor, str):
        return False
    try:
        uuid.UUID(valor)
        return True
    except Exception:
        return False


class ErrorConexion(AssertionError):
    def __init__(self, paso: str, ruta: str, original: requests.RequestException):
        self.paso = paso
        self.ruta = ruta
        self.original = original
        super().__init__(
            f"ERROR_CONEXION paso={paso} ruta={ruta}: {type(original).__name__} ({original})"
        )


class CorridaSandbox:
    def __init__(self, prefijo: str = "tc-m05-g37-adm") -> None:
        self.run_id = f"{prefijo}-{uuid.uuid4().hex[:8]}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.token: str | None = None
        self.id_usuario: int | None = None
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

    def post(self, ruta: str, json: Any = None, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("POST", ruta, paso=paso, params=params, json_body=json)

    def login(self) -> None:
        assert self.token is None, "Regla sandbox: maximo un login por cuenta por run_id"
        email = _env("TEST_ADMIN_EMAIL")
        pwd = _env("TEST_ADMIN_PASSWORD")
        r = self.post(
            "/sesiones/",
            {"correo_electronico": email, "contrasena": pwd},
            paso="login_admin",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login admin HTTP {r.status_code} "
            f"(X-Request-Id={r.headers.get('X-Request-Id')}): {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, "PRECONDICION_NO_CUMPLIDA: login admin sin token"
        self.id_usuario = _extraer_sub_jwt(token)
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


def _snapshot_auditoria(c: CorridaSandbox, paso: str) -> tuple[int, int]:
    r = c.get(
        "/suministros/auditoria",
        paso=paso,
        params={"pagina": 1, "registros_por_pagina": 1, "ordenar_por": "fecha_evento"},
    )
    assert r.status_code == 200, (
        f"Error consultando auditoria ({paso}): HTTP {r.status_code} "
        f"(X-Request-Id={r.headers.get('X-Request-Id')}): {c.seguro(r.text)}"
    )
    data = r.json()
    items = data.get("items") or []
    ultimo_id = int(items[0]["id_auditoria_suministro"]) if items else 0
    return int(data.get("total", 0)), ultimo_id


def _esperar_eventos_nuevos(
    c: CorridaSandbox,
    ultimo_id_previo: int,
    t0_operacion: float,
    paso: str,
    min_eventos: int = 1,
) -> tuple[list[dict[str, Any]], float]:
    nuevos: list[dict[str, Any]] = []
    latencia = 0.0
    for intento in range(3):
        if intento > 0:
            espera = intento - (time.perf_counter() - t0_operacion)
            if espera > 0:
                time.sleep(espera)
        r_aud = c.get(
            "/suministros/auditoria",
            paso=f"{paso}_poll_{intento}s",
            params={"pagina": 1, "registros_por_pagina": 50, "ordenar_por": "fecha_evento"},
        )
        assert r_aud.status_code == 200, (
            f"Error consultando auditoria ({paso}): HTTP {r_aud.status_code} "
            f"(X-Request-Id={r_aud.headers.get('X-Request-Id')}): {c.seguro(r_aud.text)}"
        )
        items = r_aud.json().get("items") or []
        nuevos = [it for it in items if int(it["id_auditoria_suministro"]) > ultimo_id_previo]
        nuevos.sort(key=lambda x: int(x["id_auditoria_suministro"]))
        latencia = time.perf_counter() - t0_operacion
        if len(nuevos) >= min_eventos:
            break
    return nuevos, latencia


def _confirmar_ventana(c: CorridaSandbox, ultimo_id_previo: int, t0_operacion: float, paso: str) -> list[dict[str, Any]]:
    """Relee la bitacora cuando ya paso la ventana de CA-1 (2 s) para confirmar el conteo EXACTO.

    Evita dar por buena una cuenta de 1 evento si llega un segundo evento dentro de la ventana.
    """
    espera = (VENTANA_CA1_S + 0.2) - (time.perf_counter() - t0_operacion)
    if espera > 0:
        time.sleep(espera)
    r_aud = c.get(
        "/suministros/auditoria",
        paso=f"{paso}_confirmacion_2s",
        params={"pagina": 1, "registros_por_pagina": 50, "ordenar_por": "fecha_evento"},
    )
    assert r_aud.status_code == 200, (
        f"Error consultando auditoria ({paso} confirmacion): HTTP {r_aud.status_code} "
        f"(X-Request-Id={r_aud.headers.get('X-Request-Id')}): {c.seguro(r_aud.text)}"
    )
    items = r_aud.json().get("items") or []
    nuevos = [it for it in items if int(it["id_auditoria_suministro"]) > ultimo_id_previo]
    nuevos.sort(key=lambda x: int(x["id_auditoria_suministro"]))
    return nuevos


def _crear_activo_poblacional(c: CorridaSandbox, paso: str) -> int:
    tag = uuid.uuid4().hex[:8]
    hoy = _hoy()
    fecha_ciclo = (hoy - timedelta(days=15)).isoformat()
    payload_activo = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": 1,
        "id_infraestructura": 2,
        "identificador_unico": f"QA-G37-{tag}",
        "cantidad_inicial": 60,
        "fecha_ingreso": fecha_ciclo,
        "fecha_inicio_ciclo": fecha_ciclo,
        "origen_financiero": "nacimiento",
        "peso_actual": 22.0,
    }
    r_act = c.post("/activos-biologicos", payload_activo, paso=paso)
    assert r_act.status_code == 201, (
        f"Fallo al crear activo QA: HTTP {r_act.status_code} "
        f"(X-Request-Id={r_act.headers.get('X-Request-Id')}): {c.seguro(r_act.text)}"
    )
    id_activo = r_act.json().get("id_activo_biologico")
    assert id_activo is not None, "Respuesta sin id_activo_biologico"
    return int(id_activo)


def _payload_suministro(id_activo: int, cantidad: float = 1.0, precio: float = 40000.0) -> dict[str, Any]:
    return {
        "id_activo_biologico": id_activo,
        "tipo_suministro": "SERVICIO_VETERINARIO",
        "cantidad": cantidad,
        "unidad_medida": "servicio",
        "precio_unitario": precio,
        "fecha_aplicacion": _hoy().isoformat(),
        "justificacion_precio": "Tarifa estandar segun contrato veterinario vigente",
        "id_idempotencia": str(uuid.uuid4()),
    }


def _recolectar_eventos_corrida(c: CorridaSandbox, ultimo_id_previo: int, paso: str) -> list[dict[str, Any]]:
    por_id: dict[int, dict[str, Any]] = {}
    pagina = 1
    while True:
        r = c.get(
            "/suministros/auditoria",
            paso=f"{paso}_pag_{pagina}",
            params={"pagina": pagina, "registros_por_pagina": 100, "ordenar_por": "fecha_evento"},
        )
        assert r.status_code == 200, (
            f"Error listando eventos ({paso}): HTTP {r.status_code} "
            f"(X-Request-Id={r.headers.get('X-Request-Id')}): {c.seguro(r.text)}"
        )
        items = r.json().get("items") or []
        if not items:
            break
        for it in items:
            eid = int(it["id_auditoria_suministro"])
            if eid > ultimo_id_previo:
                por_id[eid] = it
        if min(int(it["id_auditoria_suministro"]) for it in items) <= ultimo_id_previo:
            break
        pagina += 1
        if pagina > 10:
            break
    return [por_id[k] for k in sorted(por_id.keys())]


_CAMPOS_BASE_R8 = ("tipo_operacion", "resultado", "fecha_emision")  # tipo_evento_m05, resultado, timestamp_emision


def _valor_r8(ev: dict[str, Any], campo: str) -> Any:
    """Valor de un campo minimo: primer nivel de la respuesta o, si no esta, dentro de datos_nuevos (ronda 1)."""
    if ev.get(campo) is not None:
        return ev.get(campo)
    datos_nuevos = ev.get("datos_nuevos") if isinstance(ev.get("datos_nuevos"), dict) else {}
    return datos_nuevos.get(campo)


def _faltantes_r8(ev: dict[str, Any]) -> list[str]:
    """Campos minimos de la Restriccion 8 (segun el tipo) que el evento no trae, en el orden de la ficha."""
    return [campo for campo in _MINIMOS_POR_TIPO[ev.get("tipo_operacion")] if _valor_r8(ev, campo) is None]


def _eventos_corrida_a04(c: CorridaSandbox) -> list[dict[str, Any]]:
    """Eventos de la corrida (id > ultimo_id de la linea base) recolectados una sola vez para A04a/A04b/A04c."""
    if _CONTEXTO.get("eventos_a04") is None:
        ultimo_id_base = _CONTEXTO["ultimo_id_corrida"]
        assert ultimo_id_base is not None, "Precondicion: falta ultimo_id_corrida"
        eventos = _recolectar_eventos_corrida(c, ultimo_id_base, "a04")
        assert len(eventos) > 0, "No se recolectaron eventos en la corrida para verificar Restriccion 8"
        _CONTEXTO["eventos_a04"] = eventos
    return _CONTEXTO["eventos_a04"]


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield


@pytest.fixture(scope="class")
def sandbox_admin():
    corrida = CorridaSandbox(prefijo="tc-m05-g37-adm")
    corrida.login()
    _CONTEXTO["id_usuario_admin"] = corrida.id_usuario
    try:
        yield corrida
    finally:
        corrida.cerrar()


class TestTCM05G37PersistenciaYClasificacion:
    """TC-M05-G37 (RF-80 v2.0 / RFC-025): Persistencia, auditoria de fallos, R8, clasificacion e inocuidad."""

    def test_t00_linea_base(self):
        """T00: Linea base en corrida sandbox independiente de solo lectura cerrada con DELETE -> 200."""
        corrida = CorridaSandbox(prefijo="tc-m05-g37-inobase")
        try:
            corrida.login()
            total_ini, ultimo_id_ini = _snapshot_auditoria(corrida, "t00_conteo_base")
            _obt("auditoria_base", {"total": total_ini, "ultimo_id": ultimo_id_ini, "run_id": corrida.run_id})
            assert isinstance(total_ini, int) and total_ini >= 0, "Conteo base invalido [Sandbox / Inocuidad]"
            _CONTEXTO["total_base"] = total_ini
            _CONTEXTO["ultimo_id_base"] = ultimo_id_ini
            _CONTEXTO["ultimo_id_corrida"] = ultimo_id_ini
            print(f"T00_BASELINE total={total_ini} ultimo_id={ultimo_id_ini}")
        finally:
            r_close = corrida.cerrar()
        _obt("cierre_t00", {
            "http": r_close.status_code if r_close is not None else None,
            "x_request_id": r_close.headers.get("X-Request-Id") if r_close is not None else None,
        })
        assert r_close is not None and r_close.status_code == 200, (
            f"Fallo cierre corrida T00: {r_close.status_code if r_close else None}"
        )
        msg = (r_close.json().get("mensaje") or r_close.json().get("status") or "")
        assert "exitoso" in msg.lower(), f"Respuesta inesperada en cierre T00: {r_close.json()}"

    def test_a01a_rf78_exito_y_persistencia(self, sandbox_admin: CorridaSandbox):
        """A01a (RF-80 v2.0 CA-1, Entradas, R8, RNF-08 / TC-M05-090): RF-78 SERVICIO_VETERINARIO 'servicio'."""
        c = sandbox_admin
        id_activo = _crear_activo_poblacional(c, "a01a_crear_activo")
        _CONTEXTO["id_activo_1"] = id_activo

        r_fase = c.post(
            f"/activos-biologicos/{id_activo}/fases",
            {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase productiva QA G37"},
            paso="a01a_abrir_fase",
        )
        assert r_fase.status_code in (200, 201), (
            f"Fallo apertura de fase: HTTP {r_fase.status_code} "
            f"(X-Request-Id={r_fase.headers.get('X-Request-Id')}): {c.seguro(r_fase.text)}"
        )
        id_fase = r_fase.json().get("id_gestion_fases")
        assert id_fase is not None, "Respuesta sin id_gestion_fases [Precondicion A01a]"
        _CONTEXTO["id_fase_1"] = int(id_fase)

        _, ultimo_previo = _snapshot_auditoria(c, "a01a_snap_previo")
        _CONTEXTO["ultimo_id_corrida"] = _CONTEXTO["ultimo_id_base"] if _CONTEXTO["ultimo_id_base"] is not None else ultimo_previo

        payload_sum = _payload_suministro(id_activo, cantidad=1.0, precio=40000.0)
        t0 = time.perf_counter()
        r_sum = c.post("/suministros/costeo-directo", payload_sum, paso="a01a_rf78_registrar")
        _obt("rf78_registrar", {
            "id_activo": id_activo, "id_fase": _CONTEXTO["id_fase_1"],
            "http": r_sum.status_code, "x_request_id": r_sum.headers.get("X-Request-Id"),
        })
        assert r_sum.status_code == 200, (
            f"Error registrando suministro RF-78 (unidad 'servicio'): HTTP {r_sum.status_code} "
            f"(X-Request-Id={r_sum.headers.get('X-Request-Id')}): {c.seguro(r_sum.text)} [RF-78]"
        )
        body_sum = r_sum.json()
        id_reg = body_sum.get("id_registro_suministro") or (body_sum.get("registro") or {}).get("id_registro_suministro")
        assert id_reg is not None, "Respuesta RF-78 sin id_registro_suministro"
        _CONTEXTO["id_registro_suministro_1"] = id_reg

        nuevos, latencia_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a01a", min_eventos=3)
        _CONTEXTO["ids_eventos_a01a"] = [int(e["id_auditoria_suministro"]) for e in nuevos]
        _obt("eventos_nuevos", {
            "id_registro_suministro": id_reg, "latencia_s": round(latencia_s, 3),
            "eventos": [_ev_resumen(e) for e in nuevos],
        })
        assert latencia_s <= 2.0, (
            f"Persistencia RF-78 excedio 2.0 s: {latencia_s:.3f} s [RF-80 v2.0 CA-1]"
        )

        tipos_obtenidos = [ev.get("tipo_operacion") for ev in nuevos]
        esperados = ["SUMINISTRO_REGISTRADO", "PRECIO_MANUAL_INGRESADO", "ACUMULADO_ACTUALIZADO"]
        assert sorted(tipos_obtenidos) == sorted(esperados) and len(nuevos) == 3, (
            f"Se esperaban EXACTAMENTE {esperados} tras RF-78; obtenidos: {tipos_obtenidos} [RF-80 v2.0 CA-1, R8]"
        )

        por_tipo = {ev["tipo_operacion"]: ev for ev in nuevos}
        for tipo, ev in por_tipo.items():
            assert ev.get("resultado") == "EXITOSO", f"{tipo}: resultado esperado EXITOSO [RF-80 v2.0 Entradas]"
            assert ev.get("id_usuario") == c.id_usuario, (
                f"{tipo}: id_usuario ({ev.get('id_usuario')}) != sub del JWT ({c.id_usuario}) [RF-80 v2.0 Entradas]"
            )
            assert ev.get("id_activo_biologico") == id_activo, f"{tipo}: id_activo_biologico nulo/distinto [R8]"
            assert ev.get("id_ciclo_productivo") is not None, f"{tipo}: id_ciclo_productivo nulo [R8]"
            assert ev.get("id_gestion_fases") == _CONTEXTO["id_fase_1"], f"{tipo}: id_gestion_fases nulo/distinto [RF-80 M05]"
            assert _es_uuid_valido(ev.get("id_evento_m05")), f"{tipo}: id_evento_m05 no es UUID valido [RF-80 Entradas]"
            assert isinstance(ev.get("hash_integridad"), str) and _HEX64_RE.match(ev["hash_integridad"]), (
                f"{tipo}: hash_integridad debe ser 64 hex [RF-80 v2.0 R5/RNF-06]"
            )
            assert ev.get("fecha_emision") is not None, f"{tipo}: fecha_emision nula [R8 / RNF-08]"
            assert ev.get("fecha_evento") is not None, f"{tipo}: fecha_evento nula [RNF-08]"

        for tipo_costo in ("SUMINISTRO_REGISTRADO", "ACUMULADO_ACTUALIZADO"):
            costo = por_tipo[tipo_costo].get("costo_afectado")
            assert costo is not None and float(costo) == 40000.0, (
                f"{tipo_costo}: costo_afectado esperado 40000.0, obtenido {costo} [RF-80 v2.0 R8]"
            )
        for tipo_origen in ("SUMINISTRO_REGISTRADO", "PRECIO_MANUAL_INGRESADO"):
            assert por_tipo[tipo_origen].get("origen_precio") == "MANUAL", (
                f"{tipo_origen}: origen_precio esperado MANUAL [RF-80 v2.0 R8]"
            )

        _CONTEXTO["evento_rf78"] = por_tipo["SUMINISTRO_REGISTRADO"]

    def test_a01b_rf81_exito_historial(self, sandbox_admin: CorridaSandbox):
        """A01b (RF-80 v2.0 CA-1, R8 / TC-M05-090): GET /suministros/historial -> 1 CONSULTA_HISTORIAL_EJECUTADA."""
        c = sandbox_admin
        id_activo = _CONTEXTO["id_activo_1"]
        _, ultimo_previo = _snapshot_auditoria(c, "a01b_snap_previo")

        t0 = time.perf_counter()
        r_hist = c.get(
            "/suministros/historial",
            paso="a01b_rf81_historial",
            params={"id_activo_biologico": id_activo},
        )
        assert r_hist.status_code == 200, (
            f"Error RF-81 historial: HTTP {r_hist.status_code} "
            f"(X-Request-Id={r_hist.headers.get('X-Request-Id')}): {c.seguro(r_hist.text)}"
        )
        nuevos, latencia_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a01b", min_eventos=1)
        _obt("rf81_historial", {
            "http": r_hist.status_code, "x_request_id": r_hist.headers.get("X-Request-Id"),
            "latencia_s": round(latencia_s, 3), "eventos": [_ev_resumen(e) for e in nuevos],
        })
        assert latencia_s <= 2.0, f"Persistencia RF-81 excedio 2.0 s: {latencia_s:.3f} s [RF-80 v2.0 CA-1]"
        assert len(nuevos) == 1 and nuevos[0].get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA", (
            f"Se esperaba exactamente 1 CONSULTA_HISTORIAL_EJECUTADA; obtenidos: "
            f"{[e.get('tipo_operacion') for e in nuevos]} [RF-80 v2.0 CA-1]"
        )
        ev = nuevos[0]
        assert ev.get("id_usuario") == c.id_usuario, "CONSULTA_HISTORIAL_EJECUTADA: id_usuario != JWT sub [R8]"
        assert isinstance(ev.get("hash_integridad"), str) and _HEX64_RE.match(ev["hash_integridad"]), (
            "CONSULTA_HISTORIAL_EJECUTADA: hash_integridad invalido [R5]"
        )
        _CONTEXTO["evento_rf81"] = ev

    def test_a02a_rf78_rechazo_sin_fase_y_repeticion(self, sandbox_admin: CorridaSandbox):
        """A02a (RF-80 v2.0 CA-1, R8, E2; criterio INC-M05-275-G37): Rechazo 409 sin fase, sin efectos y repeticion."""
        c = sandbox_admin
        id_activo_2 = _crear_activo_poblacional(c, "a02a_crear_activo_2")
        _CONTEXTO["id_activo_2"] = id_activo_2

        _, ultimo_previo = _snapshot_auditoria(c, "a02a_snap_previo")
        payload = _payload_suministro(id_activo_2, cantidad=1.0, precio=40000.0)

        t0 = time.perf_counter()
        r_fail = c.post("/suministros/costeo-directo", payload, paso="a02a_rechazo_sin_fase")
        _obt("rf78_rechazo_sin_fase", {
            "id_activo": id_activo_2, "http": r_fail.status_code,
            "error_code": _error_code(r_fail),
            "x_request_id": r_fail.headers.get("X-Request-Id"),
        })
        assert r_fail.status_code == 409, (
            f"Esperado HTTP 409 sin fase abierta; obtenido {r_fail.status_code} "
            f"(X-Request-Id={r_fail.headers.get('X-Request-Id')}): {c.seguro(r_fail.text)}"
        )
        assert r_fail.json().get("error_code") == "CICLO_NO_ACTIVO", (
            f"Esperado error_code CICLO_NO_ACTIVO; obtenido {r_fail.json()}"
        )

        nuevos, latencia_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a02a", min_eventos=1)
        _obt("eventos_nuevos", {"latencia_s": round(latencia_s, 3), "eventos": [_ev_resumen(e) for e in nuevos]})
        assert latencia_s <= 2.0, f"Persistencia rechazo A02a excedio 2.0 s: {latencia_s:.3f} s [RF-80 v2.0 CA-1]"
        assert len(nuevos) == 1, (
            f"Esperado exactamente 1 evento tras rechazo A02a; obtenidos {len(nuevos)}: "
            f"{[e.get('id_auditoria_suministro') for e in nuevos]} [RF-80 v2.0 CA-1]"
        )

        ev = nuevos[0]
        _CONTEXTO["evento_a02a"] = ev
        print(f"A02A_EVENTO={json.dumps(ev, ensure_ascii=False)}")

        assert ev.get("tipo_operacion") == "REGISTRO_FALLIDO", f"tipo_operacion inesperado: {ev.get('tipo_operacion')} [Catalogo]"
        assert ev.get("resultado") in ("RECHAZADO", "FALLIDO"), f"resultado inesperado: {ev.get('resultado')} [CA-1]"
        assert ev.get("id_usuario") == c.id_usuario, f"id_usuario ({ev.get('id_usuario')}) != JWT sub ({c.id_usuario}) [Entradas]"
        assert ev.get("id_activo_biologico") == id_activo_2, f"id_activo_biologico inesperado: {ev.get('id_activo_biologico')} [R8]"
        assert ev.get("numero_reintentos") == 0, f"numero_reintentos esperado 0, obtenido {ev.get('numero_reintentos')} [R8]"
        assert ev.get("registro_incompleto") is True, f"registro_incompleto esperado True [R8 / E2]"
        causa = ev.get("detalle_causa") or ""
        assert "ciclo" in causa.lower(), f"detalle_causa debe mencionar el ciclo: {causa!r} [R8 / E2]"
        assert ev.get("clasificacion_registro") == "TECNICO", f"clasificacion esperada TECNICO [Fase 3]"
        assert ev.get("retencion_aplicable") == "1 año", f"retencion esperada '1 año' [Fase 3]"
        assert isinstance(ev.get("hash_integridad"), str) and _HEX64_RE.match(ev["hash_integridad"]), (
            "REGISTRO_FALLIDO: hash_integridad invalido [R5]"
        )

        # Sin efectos parciales: acumulado 404 e historial 0 registros
        r_acum = c.get(f"/suministros/costeo-directo/acumulado/activo/{id_activo_2}", paso="a02a_sin_acumulado")
        _obt("acumulado_activo_2", {"http": r_acum.status_code, "x_request_id": r_acum.headers.get("X-Request-Id")})
        assert r_acum.status_code == 404, f"Acumulado debio no existir (404), obtenido {r_acum.status_code} [INC-M05-275-G37]"
        r_hist = c.get("/suministros/historial", paso="a02a_sin_historial", params={"id_activo_biologico": id_activo_2})
        _obt("historial_activo_2", {
            "http": r_hist.status_code, "x_request_id": r_hist.headers.get("X-Request-Id"),
            "items": len((r_hist.json() or {}).get("items") or []) if r_hist.status_code == 200 else None,
        })
        assert r_hist.status_code == 200, f"Historial HTTP inesperado: {r_hist.status_code}"
        items_h = r_hist.json().get("items") or []
        assert len(items_h) == 0, f"Historial debio tener 0 registros tras rechazo; tiene {len(items_h)} [INC-M05-275-G37]"

        # Repeticion con nuevo id_idempotencia -> exactamente +1 evento nuevo
        _, ultimo_antes_rep = _snapshot_auditoria(c, "a02a_snap_antes_rep")
        payload_rep = _payload_suministro(id_activo_2, cantidad=1.0, precio=40000.0)
        t_rep = time.perf_counter()
        r_rep = c.post("/suministros/costeo-directo", payload_rep, paso="a02a_repeticion_rechazo")
        assert r_rep.status_code == 409 and r_rep.json().get("error_code") == "CICLO_NO_ACTIVO", (
            f"Repeticion inesperada: HTTP {r_rep.status_code} ({c.seguro(r_rep.text)})"
        )
        evs_rep, lat_rep = _esperar_eventos_nuevos(c, ultimo_antes_rep, t_rep, "a02a_rep", min_eventos=1)
        _obt("repeticion", {
            "http": r_rep.status_code, "x_request_id": r_rep.headers.get("X-Request-Id"),
            "latencia_s": round(lat_rep, 3), "eventos": [_ev_resumen(e) for e in evs_rep],
        })
        assert lat_rep <= 2.0, f"Persistencia repeticion excedio 2.0 s: {lat_rep:.3f} s [CA-1]"
        assert len(evs_rep) == 1 and evs_rep[0].get("tipo_operacion") == "REGISTRO_FALLIDO", (
            f"Repeticion debio generar exactamente +1 REGISTRO_FALLIDO; obtenidos: {evs_rep} [INC-M05-275-G37]"
        )

    def test_a02b_rf78_rechazo_con_fase_abierta(self, sandbox_admin: CorridaSandbox):
        """A02b (RF-80 v2.0 CA-1, R8 / TC-M05-090): Rechazo con fase abierta (cantidad -1 -> 422) con ciclo y fase no nulos."""
        c = sandbox_admin
        id_activo_1 = _CONTEXTO["id_activo_1"]
        _, ultimo_previo = _snapshot_auditoria(c, "a02b_snap_previo")

        payload_neg = _payload_suministro(id_activo_1, cantidad=-1.0, precio=40000.0)
        t0 = time.perf_counter()
        r_fail = c.post("/suministros/costeo-directo", payload_neg, paso="a02b_rechazo_cantidad_neg")
        _obt("rf78_rechazo_con_fase", {
            "http": r_fail.status_code, "error_code": _error_code(r_fail), "x_request_id": r_fail.headers.get("X-Request-Id"),
        })
        assert r_fail.status_code == 422 and r_fail.json().get("error_code") == "COSTO_REGISTRO_INVALIDO", (
            f"Esperado 422 COSTO_REGISTRO_INVALIDO; obtenido {r_fail.status_code} ({c.seguro(r_fail.text)})"
        )
        nuevos, lat_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a02b", min_eventos=1)
        _obt("eventos_nuevos", {"latencia_s": round(lat_s, 3), "eventos": [_ev_resumen(e) for e in nuevos]})
        assert lat_s <= 2.0, f"Persistencia A02b excedio 2.0 s: {lat_s:.3f} s [CA-1]"
        assert len(nuevos) == 1 and nuevos[0].get("tipo_operacion") == "REGISTRO_FALLIDO", (
            f"Esperado exactamente 1 REGISTRO_FALLIDO en A02b; obtenidos: {nuevos} [CA-1]"
        )
        ev = nuevos[0]
        assert ev.get("id_ciclo_productivo") is not None, "A02b: id_ciclo_productivo no debe ser nulo con fase abierta [R8]"
        assert ev.get("id_gestion_fases") == _CONTEXTO["id_fase_1"], (
            f"A02b: id_gestion_fases esperado {_CONTEXTO['id_fase_1']}, obtenido {ev.get('id_gestion_fases')} [RF-80 M05]"
        )

    def test_a02c_rf79_rechazo_ciclo_activo(self, sandbox_admin: CorridaSandbox):
        """RF-80 v2.0 CA-1 y caso G37 v2.0 exigen auditar operaciones fallidas de RF-79; el catálogo no define el tipo para un rechazo de negocio."""
        c = sandbox_admin
        id_fase_1 = _CONTEXTO["id_fase_1"]
        _, ultimo_previo = _snapshot_auditoria(c, "a02c_snap_previo")

        t0 = time.perf_counter()
        r_fail = c.post(f"/suministros/nic41/ciclo/{id_fase_1}/consolidar", paso="a02c_rf79_consolidar_activo")
        _obt("rf79_consolidar_ciclo_activo", {
            "id_fase": id_fase_1, "http": r_fail.status_code, "error_code": _error_code(r_fail),
            "x_request_id": r_fail.headers.get("X-Request-Id"),
        })
        assert r_fail.status_code == 409 and r_fail.json().get("error_code") == "CICLO_ACTIVO", (
            f"Esperado 409 CICLO_ACTIVO; obtenido {r_fail.status_code} ({c.seguro(r_fail.text)})"
        )
        nuevos, lat_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a02c", min_eventos=1)
        confirmados = _confirmar_ventana(c, ultimo_previo, t0, "a02c")
        _obt("eventos_nuevos", {
            "latencia_primera_deteccion_s": round(lat_s, 3) if nuevos else None,
            "conteo_en_ventana_2s": len(confirmados),
            "eventos": [_ev_resumen(e) for e in confirmados],
        })
        assert len(confirmados) == 1, (
            "RF-80 v2.0 CA-1 / criterio de re-prueba INC-M05-353-G37: se esperaba EXACTAMENTE 1 evento nuevo tras "
            f"HTTP {r_fail.status_code} ({_error_code(r_fail)}, X-Request-Id={r_fail.headers.get('X-Request-Id')}); "
            f"eventos nuevos en la ventana de 2 s: {len(confirmados)} "
            f"({[(e.get('id_auditoria_suministro'), e.get('tipo_operacion'), e.get('resultado')) for e in confirmados]})"
        )
        ev = confirmados[0]
        _CONTEXTO["evento_a02c"] = ev
        assert lat_s <= 2.0, f"Persistencia rechazo RF-79 excedio 2.0 s: {lat_s:.3f} s [RF-80 v2.0 CA-1]"
        assert ev.get("resultado") in ("RECHAZADO", "FALLIDO"), (
            f"Evento {ev.get('id_auditoria_suministro')}: resultado {ev.get('resultado')!r}, esperado RECHAZADO o FALLIDO "
            "[RF-80 v2.0 Variables (resultado) / CA-1 / criterio INC-M05-353-G37]"
        )
        assert ev.get("tipo_operacion") in _CATALOGO_RF80, (
            f"Evento {ev.get('id_auditoria_suministro')}: tipo_operacion {ev.get('tipo_operacion')!r} fuera del catalogo "
            "de eventos de RF-80 v2.0 [RF-80 v2.0 Descripcion / Fase 3]"
        )
        assert ev.get("id_usuario") == c.id_usuario, (
            f"Evento {ev.get('id_auditoria_suministro')}: id_usuario {ev.get('id_usuario')} != sub del JWT {c.id_usuario} "
            "[RF-80 v2.0 Entradas / criterio INC-M05-353-G37]"
        )

    def test_a02d_rf81_rechazo_filtros_invalidos(self, sandbox_admin: CorridaSandbox):
        """RF-80 v2.0 CA-1 y caso G37 v2.0 exigen auditar operaciones fallidas de RF-81; el catálogo no define el tipo para un rechazo de negocio."""
        c = sandbox_admin
        id_activo_1 = _CONTEXTO["id_activo_1"]
        hoy = _hoy()
        _, ultimo_previo = _snapshot_auditoria(c, "a02d_snap_previo")

        t0 = time.perf_counter()
        r_fail = c.get(
            "/suministros/historial",
            paso="a02d_rf81_filtros_invalidos",
            params={
                "id_activo_biologico": id_activo_1,
                "fecha_inicio_filtro": hoy.isoformat(),
                "fecha_fin_filtro": (hoy - timedelta(days=5)).isoformat(),
            },
        )
        _obt("rf81_historial_filtros_invalidos", {
            "id_activo": id_activo_1, "http": r_fail.status_code, "error_code": _error_code(r_fail),
            "x_request_id": r_fail.headers.get("X-Request-Id"),
        })
        assert r_fail.status_code == 422 and r_fail.json().get("error_code") == "COMBINACION_FILTROS_INVALIDA", (
            f"Esperado 422 COMBINACION_FILTROS_INVALIDA; obtenido {r_fail.status_code} ({c.seguro(r_fail.text)})"
        )
        nuevos, lat_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a02d", min_eventos=1)
        confirmados = _confirmar_ventana(c, ultimo_previo, t0, "a02d")
        _obt("eventos_nuevos", {
            "latencia_primera_deteccion_s": round(lat_s, 3) if nuevos else None,
            "conteo_en_ventana_2s": len(confirmados),
            "eventos": [_ev_resumen(e) for e in confirmados],
            "filtros_aplicados": [
                (e.get("datos_nuevos") or {}).get("filtros_aplicados") if isinstance(e.get("datos_nuevos"), dict) else None
                for e in confirmados
            ],
        })
        assert len(confirmados) == 1, (
            "RF-80 v2.0 CA-1 / criterio de re-prueba INC-M05-353-G37: se esperaba EXACTAMENTE 1 evento nuevo tras "
            f"HTTP {r_fail.status_code} ({_error_code(r_fail)}, X-Request-Id={r_fail.headers.get('X-Request-Id')}); "
            f"eventos nuevos en la ventana de 2 s: {len(confirmados)} "
            f"({[(e.get('id_auditoria_suministro'), e.get('tipo_operacion'), e.get('resultado')) for e in confirmados]})"
        )
        ev = confirmados[0]
        _CONTEXTO["evento_a02d"] = ev
        assert lat_s <= 2.0, f"Persistencia rechazo RF-81 excedio 2.0 s: {lat_s:.3f} s [RF-80 v2.0 CA-1]"
        assert ev.get("resultado") in ("RECHAZADO", "FALLIDO"), (
            f"Evento {ev.get('id_auditoria_suministro')}: resultado {ev.get('resultado')!r}, esperado RECHAZADO o FALLIDO "
            "[RF-80 v2.0 Variables (resultado) / CA-1 / criterio INC-M05-353-G37]"
        )
        assert ev.get("tipo_operacion") in _CATALOGO_RF80, (
            f"Evento {ev.get('id_auditoria_suministro')}: tipo_operacion {ev.get('tipo_operacion')!r} fuera del catalogo "
            "de eventos de RF-80 v2.0 [RF-80 v2.0 Descripcion / Fase 3]"
        )
        assert ev.get("id_usuario") == c.id_usuario, (
            f"Evento {ev.get('id_auditoria_suministro')}: id_usuario {ev.get('id_usuario')} != sub del JWT {c.id_usuario} "
            "[RF-80 v2.0 Entradas / criterio INC-M05-353-G37]"
        )

    def test_a01c_rf79_exito_cierre(self, sandbox_admin: CorridaSandbox):
        """A01c (RF-80 v2.0 CA-1, R8 / TC-M05-090): Cierre RF-79 -> CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO."""
        c = sandbox_admin
        id_activo_1 = _CONTEXTO["id_activo_1"]
        id_fase_1 = _CONTEXTO["id_fase_1"]
        _, ultimo_previo = _snapshot_auditoria(c, "a01c_snap_previo")

        payload_cierre = {
            "fecha_cierre": _hoy().isoformat(),
            "motivo_cierre": "finalizacion_lote",
            "descripcion_cierre": "Cierre QA G37 para observacion consolidacion NIC41",
        }
        t0 = time.perf_counter()
        r_cierre = c.post(f"/activos-biologicos/{id_activo_1}/cierre", payload_cierre, paso="a01c_rf79_cierre")
        _obt("rf79_cierre", {"http": r_cierre.status_code, "x_request_id": r_cierre.headers.get("X-Request-Id")})
        assert r_cierre.status_code == 200, (
            f"Error cerrando ciclo RF-79: HTTP {r_cierre.status_code} "
            f"(X-Request-Id={r_cierre.headers.get('X-Request-Id')}): {c.seguro(r_cierre.text)}"
        )
        nuevos, lat_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, "a01c", min_eventos=2)
        _obt("eventos_nuevos", {"latencia_s": round(lat_s, 3), "eventos": [_ev_resumen(e) for e in nuevos]})
        assert lat_s <= 2.0, f"Persistencia RF-79 excedio 2.0 s: {lat_s:.3f} s [RF-80 v2.0 CA-1]"

        por_tipo = {ev.get("tipo_operacion"): ev for ev in nuevos}
        for requerido in ("CICLO_CONSOLIDADO", "REPORTE_COSTOS_GENERADO"):
            assert requerido in por_tipo, (
                f"Falta evento {requerido} tras cierre RF-79; obtenidos: {[e.get('tipo_operacion') for e in nuevos]} [CA-1]"
            )
            ev = por_tipo[requerido]
            assert ev.get("resultado") == "EXITOSO", f"{requerido}: resultado esperado EXITOSO [Entradas]"
            assert ev.get("costo_afectado") is not None, f"{requerido}: costo_afectado nulo [R8]"
            assert isinstance(ev.get("hash_integridad"), str) and _HEX64_RE.match(ev["hash_integridad"]), (
                f"{requerido}: hash_integridad invalido [R5]"
            )
        _CONTEXTO["evento_rf79_consolidado"] = por_tipo["CICLO_CONSOLIDADO"]
        _CONTEXTO["evento_rf79_reporte"] = por_tipo["REPORTE_COSTOS_GENERADO"]

        # Capturar id_provision para T99
        r_ver = c.get(f"/suministros/nic41/ciclo/{id_fase_1}/versiones", paso="a01c_listar_versiones")
        _obt("versiones_nic41", {
            "http": r_ver.status_code, "x_request_id": r_ver.headers.get("X-Request-Id"),
            "ids_provision": [v.get("id_provision") for v in ((r_ver.json() or {}).get("versiones") or [])] if r_ver.status_code == 200 else None,
        })
        assert r_ver.status_code == 200, f"Error listando versiones NIC41: HTTP {r_ver.status_code}"
        versiones = r_ver.json().get("versiones") or []
        assert versiones, "Sin versiones NIC41 tras cierre de ciclo"
        _CONTEXTO["id_provision_1"] = versiones[-1]["id_provision"]

    def test_a03_consistencia_lista_detalle_y_filtros(self, sandbox_admin: CorridaSandbox):
        """A03 (RF-80 v2.0 CA-4, RNF-08 / TC-M05-090): Lista vs detalle y filtros para EXITOSO y REGISTRO_FALLIDO.

        Nota de entorno: /test-control/query devuelve 0 filas por RLS (Fase 1, X-Request-Id 928c594f-...);
        la verificacion de la fila se hace por el detalle de la API.
        """
        c = sandbox_admin
        ev_exito = _CONTEXTO.get("evento_rf78")
        ev_fallo = _CONTEXTO.get("evento_a02a")
        assert ev_exito is not None and ev_fallo is not None, "Precondicion A03: faltan eventos de A01a o A02a"

        now_utc = datetime.now(timezone.utc)
        fecha_desde = (now_utc - timedelta(minutes=15)).isoformat()
        fecha_hasta = (now_utc + timedelta(minutes=15)).isoformat()

        for etiqueta, ev in (("EXITOSO", ev_exito), ("REGISTRO_FALLIDO", ev_fallo)):
            id_ev = int(ev["id_auditoria_suministro"])
            r_det = c.get(f"/suministros/auditoria/{id_ev}", paso=f"a03_detalle_{etiqueta}")
            assert r_det.status_code == 200, (
                f"Error detalle /{id_ev} ({etiqueta}): HTTP {r_det.status_code} ({c.seguro(r_det.text)})"
            )
            det = r_det.json()
            _obt(f"detalle_{etiqueta}", {
                "id": id_ev, "http": r_det.status_code, "x_request_id": r_det.headers.get("X-Request-Id"),
                "campos_distintos_lista_vs_detalle": sorted(k for k in set(ev) | set(det) if ev.get(k) != det.get(k)),
            })
            assert ev == det, (
                f"Discrepancia campo por campo entre lista y GET /{id_ev} ({etiqueta}): "
                f"{ {k: (ev.get(k), det.get(k)) for k in set(ev)|set(det) if ev.get(k) != det.get(k)} } "
                "[RF-80 v2.0 Postc.3 / TC-M05-090]"
            )

            filtros = {
                "id_activo_biologico": {"id_activo_biologico": ev["id_activo_biologico"]},
                "tipo_operacion": {"tipo_operacion": ev["tipo_operacion"]},
                "resultado": {"resultado": ev["resultado"]},
                "clasificacion_registro": {"clasificacion_registro": ev["clasificacion_registro"]},
                "fecha_desde_hasta": {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
                "combinado": {
                    "id_activo_biologico": ev["id_activo_biologico"],
                    "tipo_operacion": ev["tipo_operacion"],
                    "resultado": ev["resultado"],
                    "clasificacion_registro": ev["clasificacion_registro"],
                    "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta,
                },
            }
            for fname, fparams in filtros.items():
                rf = c.get(
                    "/suministros/auditoria",
                    paso=f"a03_filtro_{etiqueta}_{fname}",
                    params={**fparams, "pagina": 1, "registros_por_pagina": 100, "ordenar_por": "fecha_emision"},
                )
                assert rf.status_code == 200, (
                    f"Filtro {fname} ({etiqueta}) HTTP {rf.status_code}: {c.seguro(rf.text)}"
                )
                items_f = rf.json().get("items") or []
                ids_f = {int(x["id_auditoria_suministro"]) for x in items_f}
                _obt(f"filtro_{etiqueta}_{fname}", {
                    "http": rf.status_code, "items": len(items_f), "contiene_evento": id_ev in ids_f,
                    "x_request_id": rf.headers.get("X-Request-Id"),
                })
                assert id_ev in ids_f, (
                    f"Evento {id_ev} ({etiqueta}) no aparecio con filtro {fname}={fparams} [RF-80 v2.0 CA-4]"
                )
                coincidencia = next(x for x in items_f if int(x["id_auditoria_suministro"]) == id_ev)
                assert coincidencia == det, (
                    f"Discrepancia filtro {fname} vs detalle /{id_ev} ({etiqueta}) [TC-M05-090]"
                )

    def test_a04a_r8_minimos_y_flag_incompleto(self, sandbox_admin: CorridaSandbox):
        """A04a (RF-80 v2.0 Restriccion 8, Fase 4, E2, CA-11): todo evento del catalogo con un minimo ausente queda registro_incompleto=true."""
        c = sandbox_admin
        eventos = _eventos_corrida_a04(c)
        evaluados: list[dict[str, Any]] = []
        incumplimientos: list[dict[str, Any]] = []
        for ev in eventos:
            tipo = ev.get("tipo_operacion")
            if tipo not in _CATALOGO_RF80:
                continue
            faltantes = _faltantes_r8(ev)
            base_ausentes = [f for f in faltantes if f in _CAMPOS_BASE_R8]
            evaluados.append({
                "id": ev.get("id_auditoria_suministro"), "tipo_operacion": tipo, "resultado": ev.get("resultado"),
                "faltantes": faltantes, "registro_incompleto": ev.get("registro_incompleto"),
                "origen_por_campo": {
                    campo: ("primer_nivel" if ev.get(campo) is not None
                            else "datos_nuevos" if _valor_r8(ev, campo) is not None else "AUSENTE")
                    for campo in _MINIMOS_POR_TIPO[tipo]
                },
            })
            if base_ausentes:
                incumplimientos.append({
                    "id": ev.get("id_auditoria_suministro"), "tipo_operacion": tipo, "faltantes": base_ausentes,
                    "regla": "CA-11: evento sin campo base (tipo, resultado, timestamp_emision) persistido",
                })
            elif faltantes and ev.get("registro_incompleto") is not True:
                incumplimientos.append({
                    "id": ev.get("id_auditoria_suministro"), "tipo_operacion": tipo, "faltantes": faltantes,
                    "registro_incompleto": ev.get("registro_incompleto"),
                    "regla": "R8 / Fase 4 / E2: faltan minimos del tipo y registro_incompleto no es true",
                })
        _obt("evaluacion_r8", {
            "eventos_corrida": len(eventos), "eventos_catalogo_evaluados": len(evaluados),
            "evaluados": evaluados, "incumplimientos": incumplimientos,
        })
        assert len(evaluados) >= 1, "A04a: 0 eventos del catalogo evaluados en la corrida (verificacion en vacio) [R8]"
        assert not incumplimientos, (
            "RF-80 v2.0 Restriccion 8 / Fase 4 / E2 / CA-11: eventos del catalogo con minimos ausentes sin "
            f"registro_incompleto=true (o sin campo base y persistidos): {incumplimientos}"
        )

    def test_a04b_ca12_detalle_causa_nombra_campos(self, sandbox_admin: CorridaSandbox):
        """A04b (RF-80 v2.0 CA-12, E2, Fase 4): detalle_causa = 'Campos faltantes: <nombre_de_campo>, ...' para cada faltante."""
        c = sandbox_admin
        eventos = _eventos_corrida_a04(c)
        evaluados: list[dict[str, Any]] = []
        incumplimientos: list[dict[str, Any]] = []
        for ev in eventos:
            tipo = ev.get("tipo_operacion")
            if tipo not in _CATALOGO_RF80:
                continue
            faltantes = [f for f in _faltantes_r8(ev) if f not in _CAMPOS_BASE_R8]
            if not faltantes:
                continue
            causa = ev.get("detalle_causa") or ""
            no_nombrados = [
                f for f in faltantes
                if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(f)}(?![A-Za-z0-9_])", causa)
            ]
            evaluados.append({
                "id": ev.get("id_auditoria_suministro"), "tipo_operacion": tipo, "faltantes": faltantes,
                "detalle_causa": causa, "no_nombrados": no_nombrados,
            })
            if no_nombrados:
                incumplimientos.append({
                    "id": ev.get("id_auditoria_suministro"), "tipo_operacion": tipo,
                    "campos_no_nombrados": no_nombrados, "detalle_causa": causa,
                })
        _obt("evaluacion_ca12", {"eventos_con_faltantes": len(evaluados), "evaluados": evaluados, "incumplimientos": incumplimientos})
        assert len(evaluados) >= 1, (
            "A04b: 0 eventos con minimos faltantes en la corrida (verificacion en vacio); A02a sin fase debe "
            "producir al menos un REGISTRO_FALLIDO sin id_ciclo_productivo [R8 / CA-12]"
        )
        assert not incumplimientos, (
            "RF-80 v2.0 CA-12 (detalle_causa = 'Campos faltantes: numero_reintentos, timestamps_intentos') / E2: "
            f"detalle_causa no nombra cada campo faltante por su nombre de campo: {incumplimientos}"
        )

    def test_a04c_referencias_registro_suministro_rf78(self, sandbox_admin: CorridaSandbox):
        """A04c (RF-80 v2.0 Restriccion 8, CA-4): los 3 eventos de RF-78 de A01a llevan el id_registro_suministro creado."""
        c = sandbox_admin
        ids_a01a = _CONTEXTO.get("ids_eventos_a01a") or []
        id_reg = _CONTEXTO.get("id_registro_suministro_1")
        assert ids_a01a and id_reg is not None, "Precondicion A04c: faltan los eventos o el registro de A01a"
        por_id = {int(e["id_auditoria_suministro"]): e for e in _eventos_corrida_a04(c)}
        tipos_rf78 = ("SUMINISTRO_REGISTRADO", "PRECIO_MANUAL_INGRESADO", "ACUMULADO_ACTUALIZADO")
        evaluados: list[dict[str, Any]] = []
        for eid in ids_a01a:
            ev = por_id.get(eid)
            if ev is None or ev.get("tipo_operacion") not in tipos_rf78:
                continue
            evaluados.append({
                "id": eid, "tipo_operacion": ev.get("tipo_operacion"),
                "id_registro_suministro": _valor_r8(ev, "id_registro_suministro"),
                "id_tipo_suministro": _valor_r8(ev, "id_tipo_suministro"),
            })
        _obt("referencias_rf78", {"id_registro_suministro_creado": id_reg, "evaluados": evaluados})
        assert len(evaluados) == 3, (
            f"A04c: se esperaban los 3 eventos de RF-78 de A01a; evaluados {len(evaluados)}: {evaluados} [R8]"
        )
        distintos = [e for e in evaluados if str(e["id_registro_suministro"]) != str(id_reg)]
        assert not distintos, (
            f"RF-80 v2.0 Restriccion 8 / CA-4: eventos de RF-78 cuyo id_registro_suministro no es el registro "
            f"creado ({id_reg}): {distintos}"
        )

    def test_b01_clasificacion_y_retencion_catalogo(self, sandbox_admin: CorridaSandbox):
        """B01 (RF-80 v2.0 Descripcion, Fase 3, CA-3; TC-M05-091): Clasificacion NIC41/5 años vs TECNICO/1 año."""
        c = sandbox_admin
        ultimo_id_base = _CONTEXTO["ultimo_id_corrida"]
        eventos = _recolectar_eventos_corrida(c, ultimo_id_base, "b01")

        tipos_nic41 = {"SUMINISTRO_REGISTRADO", "ACUMULADO_ACTUALIZADO", "CICLO_CONSOLIDADO", "REPORTE_COSTOS_GENERADO"}
        tipos_tecnico = {"PRECIO_MANUAL_INGRESADO", "CONSULTA_HISTORIAL_EJECUTADA", "REGISTRO_FALLIDO"}

        vistos_nic41: set[str] = set()
        vistos_tecnico: set[str] = set()
        _obt("clasificacion_por_evento", [
            {"id": e.get("id_auditoria_suministro"), "tipo_operacion": e.get("tipo_operacion"), "resultado": e.get("resultado"),
             "clasificacion_registro": e.get("clasificacion_registro"), "retencion_aplicable": e.get("retencion_aplicable")}
            for e in eventos
        ])

        for ev in eventos:
            tipo = ev.get("tipo_operacion")
            clasif = ev.get("clasificacion_registro")
            ret = ev.get("retencion_aplicable")
            if tipo in tipos_nic41:
                assert clasif == "NIC41", f"{tipo}: clasificacion esperada NIC41, obtenida {clasif} [RF-80 Fase 3]"
                assert ret == "5 años", f"{tipo}: retencion esperada '5 años', obtenida {ret} [RF-80 CA-3]"
                vistos_nic41.add(tipo)
            elif tipo in tipos_tecnico:
                assert clasif == "TECNICO", f"{tipo}: clasificacion esperada TECNICO, obtenida {clasif} [RF-80 Fase 3]"
                assert ret == "1 año", f"{tipo}: retencion esperada '1 año', obtenida {ret} [RF-80 RNF-04]"
                vistos_tecnico.add(tipo)

        assert vistos_nic41 == tipos_nic41, (
            f"Faltaron tipos NIC41 esperados: {sorted(tipos_nic41 - vistos_nic41)} [TC-M05-091]"
        )
        assert vistos_tecnico == tipos_tecnico, (
            f"Faltaron tipos TECNICO esperados: {sorted(tipos_tecnico - vistos_tecnico)} [TC-M05-091]"
        )

    def test_b02_tipo_no_catalogado_nic41(self, sandbox_admin: CorridaSandbox):
        """B02 (RF-80 v2.0 Descripcion, Fase 3 / TC-M05-091): Tipo no catalogado en TEST y en clasificar_retencion."""
        c = sandbox_admin
        ultimo_id_base = _CONTEXTO["ultimo_id_corrida"]
        eventos = _recolectar_eventos_corrida(c, ultimo_id_base, "b02")

        # (i) Eventos reales en TEST cuyo tipo_operacion no pertenece al catalogo RF-80 (ej. INSERT del cierre)
        no_catalogados = [ev for ev in eventos if ev.get("tipo_operacion") not in _CATALOGO_RF80]
        _obt("no_catalogados", [
            {"id": e.get("id_auditoria_suministro"), "tipo_operacion": e.get("tipo_operacion"),
             "clasificacion_registro": e.get("clasificacion_registro"), "retencion_aplicable": e.get("retencion_aplicable")}
            for e in no_catalogados
        ])
        assert len(no_catalogados) >= 1, (
            "RF-80 v2.0 Fase 3 / TC-M05-091: Se esperaba al menos 1 evento real no catalogado en la corrida "
            "(ej. tipo 'INSERT' generado durante el cierre) para verificar la regla de ambiguedad en TEST, "
            f"pero se encontraron 0. Tipos observados: {sorted({e.get('tipo_operacion') for e in eventos})}"
        )
        for ev in no_catalogados:
            assert ev.get("clasificacion_registro") == "NIC41", (
                f"Evento no catalogado id={ev.get('id_auditoria_suministro')} ({ev.get('tipo_operacion')}) "
                f"clasificado como {ev.get('clasificacion_registro')} en lugar de NIC41 [RF-80 Fase 3]"
            )
            assert ev.get("retencion_aplicable") == "5 años", (
                f"Evento no catalogado id={ev.get('id_auditoria_suministro')} ({ev.get('tipo_operacion')}) "
                f"con retencion {ev.get('retencion_aplicable')} en lugar de '5 años' [RF-80 Fase 3]"
            )

        # (ii) Verificacion unitaria sobre clasificar_retencion con hash de commit local
        from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import clasificar_retencion

        commit_sha = _commit_local()
        clasif, ret = clasificar_retencion("EVENTO_NO_CATALOGADO_EXPERIMENTO_QA")
        _obt("clasificar_retencion_local", {"clasificacion": clasif, "retencion": ret, "commit_local": commit_sha})
        assert clasif == "NIC41", (
            f"clasificar_retencion debio retornar NIC41, obtenido {clasif} (commit local {commit_sha}) [RF-80 Fase 3]"
        )
        assert ret == "5 años", (
            f"clasificar_retencion debio retornar '5 años', obtenido {ret} (commit local {commit_sha}) [RF-80 Fase 3]"
        )
        print(f"B02_OK no_catalogados_test={[e.get('id_auditoria_suministro') for e in no_catalogados]} commit={commit_sha}")

    def test_t98_cierre_sandbox_principal(self, sandbox_admin: CorridaSandbox):
        """T98: Cierre de la corrida sandbox principal con DELETE -> HTTP 200 'Rollback exitoso'."""
        c = sandbox_admin
        r = c.cerrar()
        _obt("cierre_principal", {
            "run_id": c.run_id,
            "http": r.status_code if r is not None else None,
            "x_request_id": r.headers.get("X-Request-Id") if r is not None else None,
        })
        assert r is not None, "Cierre de sandbox principal ya habia sido ejecutado"
        assert r.status_code == 200, (
            f"Error en DELETE /test-control/runs: HTTP {r.status_code} "
            f"(X-Request-Id={r.headers.get('X-Request-Id')}): {c.seguro(r.text)}"
        )
        data = r.json()
        mensaje = data.get("mensaje") or data.get("status") or ""
        assert "exitoso" in mensaje.lower(), f"Respuesta inesperada de rollback T98: {data}"
        _CONTEXTO["sandbox_cerrado_t98"] = True

    def test_t99_inocuidad_post_rollback(self):
        """T99: Inocuidad en corrida sandbox independiente de solo lectura (total/ultimo_id y GET -> 404).

        Nota: costeo_suministros_router.py expone GET /acumulado/activo/{id}, GET /acumulado/ciclo/{id_fase}
        y GET /suministros/historial (no existe GET /suministros/costeo-directo/{id_registro}), usados para
        verificar la desaparicion del registro de suministro y acumulado.
        """
        total_base = _CONTEXTO["total_base"]
        ultimo_id_base = _CONTEXTO["ultimo_id_base"]
        id_activo_1 = _CONTEXTO["id_activo_1"]
        id_activo_2 = _CONTEXTO["id_activo_2"]
        id_fase_1 = _CONTEXTO["id_fase_1"]
        id_provision_1 = _CONTEXTO["id_provision_1"]
        assert total_base is not None and ultimo_id_base is not None, "Precondicion: falta linea base de T00"

        corrida = CorridaSandbox(prefijo="tc-m05-g37-inofin")
        try:
            corrida.login()
            total_fin, ultimo_id_fin = _snapshot_auditoria(corrida, "t99_conteo_final")
            _obt("auditoria_final", {
                "total_base": total_base, "total_final": total_fin,
                "ultimo_id_base": ultimo_id_base, "ultimo_id_final": ultimo_id_fin,
            })
            assert total_fin == total_base, (
                f"Inocuidad: total cambio de {total_base} a {total_fin} tras rollback [Sandbox / Inocuidad]"
            )
            assert ultimo_id_fin == ultimo_id_base, (
                f"Inocuidad: ultimo_id cambio de {ultimo_id_base} a {ultimo_id_fin} tras rollback [Sandbox / Inocuidad]"
            )

            rutas_404: list[tuple[str, str, Any]] = []
            if id_activo_1 is not None:
                rutas_404.append(("activo_1", f"/activos-biologicos/{id_activo_1}", None))
                rutas_404.append(("acumulado_activo_1", f"/suministros/costeo-directo/acumulado/activo/{id_activo_1}", None))
                rutas_404.append(("historial_activo_1", "/suministros/historial", {"id_activo_biologico": id_activo_1}))
            if id_fase_1 is not None:
                rutas_404.append(("acumulado_ciclo_1", f"/suministros/costeo-directo/acumulado/ciclo/{id_fase_1}", None))
            if id_activo_2 is not None:
                rutas_404.append(("activo_2", f"/activos-biologicos/{id_activo_2}", None))
            if id_provision_1 is not None:
                rutas_404.append(("provision_1", f"/suministros/nic41/{id_provision_1}", None))

            assert len(rutas_404) >= 1, "T99: 0 recursos creados por verificar (verificacion en vacio) [Inocuidad]"
            resultados_404 = {}
            for etiqueta, ruta, params in rutas_404:
                r = corrida.get(ruta, paso=f"t99_check_{etiqueta}", params=params)
                resultados_404[etiqueta] = {
                    "status_code": r.status_code,
                    "x_request_id": r.headers.get("X-Request-Id"),
                }
                _obt(f"check_404_{etiqueta}", {"ruta": ruta, **resultados_404[etiqueta]})
                assert r.status_code == 404, (
                    f"Inocuidad fallo en {etiqueta} ({ruta}): esperado 404, obtenido {r.status_code}"
                )
            print(f"T99_INOCUIDAD total={total_fin} ultimo_id={ultimo_id_fin} checks_404={json.dumps(resultados_404)}")
        finally:
            r_close = corrida.cerrar()
        _obt("cierre_t99", {
            "http": r_close.status_code if r_close is not None else None,
            "x_request_id": r_close.headers.get("X-Request-Id") if r_close is not None else None,
        })
        assert r_close is not None and r_close.status_code == 200, "Fallo cierre corrida T99"
