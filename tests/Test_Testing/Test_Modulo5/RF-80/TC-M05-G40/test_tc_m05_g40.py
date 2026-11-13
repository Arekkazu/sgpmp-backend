# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G40: Resiliencia ante caida repositorio, cola y latencia RF-80 |
# | 2026-11-12 | Juan Sebastian Gutierrez | TC-M05-G40 rediseno RF-80 v2.0 (RFC-025 C25.1): atomicidad commit/rollback |
"""Suite de pruebas para TC-M05-G40 (RF-80 v2.0, RFC-025 C25.1): Atomicidad de auditoria y rollback.

Cubre el caso TC-M05-031 v2.0 (hoja plana TC-M05-095):
"Atomicidad de la auditoria: con commit queda exactamente 1 evento por tipo de la operacion y con
hash_integridad; con rollback, ninguno".

Nota de vigencia (RFC-025 C25.1 / RF-80 v2.0):
- El A01 anterior (cola persistente M05->M12 de 100.000 eventos, alertas 90%/100%, FIFO 48h y
  degradacion <=50 ms sin auditoria) queda RETIRADO por no aplicar bajo RF-80 v2.0.
- C02 no ejecutable por API: todos los casos de uso hacen flush de la auditoria y de la operacion
  en la misma sesion con un unico commit, sin paso fallable por API entre ambos y sin endpoint de
  inyeccion de fallos en /test-control; el rollback tecnico queda cubierto por C01.

Escenarios ejecutados secuencialmente en sandbox sobre TEST:
- T00: Linea base de auditoria en corrida sandbox independiente de solo lectura (DELETE -> 200).
- A01: Atomicidad en commit RF-78 (POST /suministros/costeo-directo valido unidad "servicio" -> 200
  [RF-78 CA-14/E8; RF-79]; exactamente 1 SUMINISTRO_REGISTRADO, 1 PRECIO_MANUAL_INGRESADO y
  1 ACUMULADO_ACTUALIZADO; hash_integridad 64 hex; version_hash_integridad in {1, 2}; <=2.0s CA-1).
- A02: Atomicidad en commit RF-79 (POST /activos-biologicos/{id}/cierre -> 200 [OpenAPI];
  exactamente 1 CICLO_CONSOLIDADO y 1 REPORTE_COSTOS_GENERADO con entidad_afectada="provision_nic41";
  conteo pasivo de eventos resultado_ica sin asercion de campos; provision persistida en clave
  "versiones" [ListaVersionesProvisionResponse, provision_nic41_schema.py:63-67] == 1 CONSOLIDADO).
- A03: Atomicidad en commit RF-81 (GET /suministros/historial -> 200 [OpenAPI]; exactamente 1
  CONSULTA_HISTORIAL_EJECUTADA nuevo del Admin con entidad_afectada="historial_suministros").
- B01: Rollback / no persistencia parcial en errores API:
  (a) RF-78 sobre activo de prueba SIN fase abierta -> 409 (anota error_code);
      0 SUMINISTRO_REGISTRADO y 0 ACUMULADO_ACTUALIZADO nuevos.
  (b) RF-79 repetir POST /activos-biologicos/{id}/cierre sobre activo cerrado en A02 -> 4xx
      (anota codigo y error_code); 0 CICLO_CONSOLIDADO y 0 REPORTE_COSTOS_GENERADO nuevos,
      y "versiones" del ciclo sigue en 1.
  (c) RF-81 rango invertido -> 422 COMBINACION_FILTROS_INVALIDA;
      0 CONSULTA_HISTORIAL_EJECUTADA nuevos con EXITOSO.
  (Eventos de fallo, solo como observacion, sin asercion.)
- T98: Cierre limpio de la corrida sandbox principal (DELETE /test-control/runs/{id} -> 200).
- C01: Rollback tecnico en corrida sandbox APARTE abierta despues de T98 (Admin, 1 login):
  crear 1 activo con fase, 1 RF-78 valido (200), cierre RF-79 (200) y 1 consulta RF-81 (200);
  capturar ids de eventos nuevos de cada operacion (>=1 por operacion con su tipo) e ids de
  recursos (activo, fase); DELETE -> 200; luego en corrida SOLO LECTURA aparte:
  GET /suministros/auditoria/{id} de cada id capturado -> 404, GET /activos-biologicos/{id} -> 404,
  total y ultimo_id iguales a los previos a C01.
- T99: Inocuidad post-rollback en corrida sandbox aparte de solo lectura (total/ultimo_id == T00;
  todos los activos creados, incluido C01, y sus acumulados -> 404; DELETE -> 200).
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
ARCHIVO_OBSERVACIONES = "observaciones_g40.json"
PREFIJO_JWT = "ey" + "J"
_LOCK_TRAZA = threading.Lock()
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_IDS_PROHIBIDOS = (930, 900, 901, 825)

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

_CONTEXTO: dict[str, Any] = {
    "total_base": None,
    "ultimo_id_base": None,
    "admin_id_usuario": None,
    "activos_creados": [],
    "id_activo_1": None,
    "id_fase_1": None,
    "id_activo_2": None,
    "c01_recursos": {},
    "c01_eventos_capturados": [],
    "obs_a01_eventos": [],
    "obs_a02_resultado_ica_conteo": 0,
    "obs_a02_eventos_app": [],
    "obs_a03_evento": None,
    "obs_b01_fallos": [],
    "obs_latencias_a01_a03_ms": {},
    "obs_latencia_a01_a03_resumen": {},
    "checkpoints_detalle": {},
    "obs_c02_analisis": (
        "C02 no ejecutable por API: todos los casos de uso hacen flush de la auditoria y de la "
        "operacion en la misma sesion con un unico commit, sin paso fallable por API entre ambos "
        "y sin endpoint de inyeccion de fallos en /test-control; el rollback tecnico queda cubierto por C01."
    ),
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
    candidatos = (
        "TEST_SANDBOX_SECRET",
        "TEST_ADMIN_PASSWORD",
        "TEST_ADMIN_EMAIL",
        "TEST_PRODUCER_PASSWORD",
        "TEST_PRODUCER_EMAIL",
        "TEST_VET_PASSWORD",
        "TEST_VET_EMAIL",
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
    texto = (texto or "")[:800]
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


def _error_code(resp: requests.Response) -> str | None:
    try:
        j = resp.json()
        if isinstance(j, dict):
            ec = j.get("error_code")
            return str(ec) if ec is not None else None
    except Exception:
        pass
    return None


def _agrupar_eventos_por_tipo(eventos: list[dict[str, Any]]) -> dict[str, list[int]]:
    grupos: dict[str, list[int]] = {}
    for ev in eventos:
        tipo = str(ev.get("tipo_operacion") or "DESCONOCIDO")
        eid = int(ev["id_auditoria_suministro"])
        grupos.setdefault(tipo, []).append(eid)
    return {k: sorted(v) for k, v in sorted(grupos.items())}


def _formatear_eventos_por_tipo(eventos: list[dict[str, Any]]) -> str:
    if not eventos:
        return "NINGUNO"
    grupos = _agrupar_eventos_por_tipo(eventos)
    return ", ".join(f"{tipo}={len(ids)} {ids}" for tipo, ids in grupos.items())


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
                if len(resp.content) <= 15000:
                    resp_body = resp.json()
                    if isinstance(resp_body, dict):
                        error_code = resp_body.get("error_code")
                else:
                    resp_body = f"<json extenso bytes={len(resp.content)}>"
            except Exception:
                resp_body = resp.text[:400]
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


def _sub_jwt(token: str) -> int | None:
    try:
        parte = token.split(".")[1]
        parte += "=" * (-len(parte) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parte).decode("utf-8"))
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except Exception:
        return None


class ErrorConexion(AssertionError):
    def __init__(self, paso: str, ruta: str, original: requests.RequestException):
        self.paso = paso
        self.ruta = ruta
        self.original = original
        super().__init__(f"ERROR_CONEXION paso={paso} ruta={ruta}: {type(original).__name__} ({original})")


class CorridaSandbox:
    """Administra un run_id de sandbox con max 1 login por cuenta y cierre limpio."""

    def __init__(self, etiqueta: str) -> None:
        self.etiqueta = etiqueta
        self.run_id = f"tc-m05-g40-{etiqueta}-{uuid.uuid4().hex[:8]}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.cerrada = False
        self.token: str | None = None
        self.id_usuario: int | None = None
        self.http = requests.Session()
        self.http.headers.update({
            "X-Test-Run-Id": self.run_id,
            "X-Sandbox-Secret": self.secret,
            "X-Zona-Horaria": NOMBRE_ZONA,
        })

    def seguro(self, texto: str) -> str:
        return _seguro(texto, (self.token,) if self.token else ())

    def login_admin(self) -> int:
        assert self.token is None, "Regla R2: solo 1 login por cuenta por run_id"
        email = _env("TEST_ADMIN_EMAIL")
        pwd = _env("TEST_ADMIN_PASSWORD")
        r = self.post("/sesiones/", {"correo_electronico": email, "contrasena": pwd}, paso=f"login_{self.etiqueta}")
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login admin HTTP {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {self.seguro(r.text)}"
        )
        j = r.json()
        token = j.get("token") or j.get("access_token") or j.get("token_acceso")
        assert token, "PRECONDICION_NO_CUMPLIDA: login admin sin token"
        uid = (j.get("usuario") or {}).get("id_usuario") or j.get("id_usuario") or _sub_jwt(token)
        assert uid is not None, "PRECONDICION_NO_CUMPLIDA: login admin sin id_usuario"
        self.token = token
        self.id_usuario = int(uid)
        self.http.headers["Authorization"] = f"Bearer {token}"
        return self.id_usuario

    def request(
        self,
        metodo: str,
        ruta: str,
        paso: str | None = None,
        params: Any = None,
        json_body: Any = None,
        nota: str | None = None,
        **kw,
    ) -> requests.Response:
        assert ruta.startswith("/"), f"Ruta relativa esperada: {ruta!r}"
        inicio = time.perf_counter()
        tok = self.token
        try:
            resp = self.http.request(metodo, self.base + ruta, timeout=TIMEOUT_S, params=params, json=json_body, **kw)
        except requests.RequestException as exc:
            _trazar(metodo, ruta, None, inicio, params=params, req_body=json_body, token_extra=tok, error=type(exc).__name__, nota=nota)
            raise ErrorConexion(paso or _TEST_ACTUAL, ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio, params=params, req_body=json_body, token_extra=tok, nota=nota)
        return resp

    def get(self, ruta: str, paso: str | None = None, params: Any = None, nota: str | None = None, **kw) -> requests.Response:
        return self.request("GET", ruta, paso=paso, params=params, nota=nota, **kw)

    def post(self, ruta: str, json_body: Any, paso: str | None = None, params: Any = None, nota: str | None = None) -> requests.Response:
        return self.request("POST", ruta, paso=paso, params=params, json_body=json_body, nota=nota)

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            return self.request("DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.etiqueta}")
        finally:
            self.http.close()


_PRINCIPAL: CorridaSandbox | None = None


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    try:
        yield
    finally:
        _guardar_observaciones()


@pytest.fixture(scope="module", autouse=True)
def _respaldo_cierre_principal():
    yield
    if _PRINCIPAL is not None and not _PRINCIPAL.cerrada:
        _PRINCIPAL.cerrar()
    _guardar_observaciones()


def _principal() -> CorridaSandbox:
    global _PRINCIPAL
    if _PRINCIPAL is None:
        _PRINCIPAL = CorridaSandbox("adm")
        uid = _PRINCIPAL.login_admin()
        _CONTEXTO["admin_id_usuario"] = uid
    return _PRINCIPAL


def _leer_estado_auditoria_api(c: CorridaSandbox, paso: str) -> tuple[int, int]:
    """Consulta total y mayor id_auditoria_suministro via GET /suministros/auditoria [OpenAPI]."""
    r = c.get(
        "/suministros/auditoria",
        paso=paso,
        params={"pagina": 1, "registros_por_pagina": 20, "ordenar_por": "fecha_evento"},
    )
    assert r.status_code == 200, (
        f"{paso}: GET /suministros/auditoria fallo HTTP {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    j = r.json()
    total = j.get("total")
    assert isinstance(total, int), f"{paso}: total entero esperado, obtenido {total!r}"
    items = j.get("items") or []
    ultimo_id = max((int(it["id_auditoria_suministro"]) for it in items), default=0)
    return total, ultimo_id


def _recolectar_eventos_nuevos(
    c: CorridaSandbox,
    ultimo_id_previo: int,
    paso: str,
    id_activo: int | None = None,
) -> list[dict[str, Any]]:
    por_id: dict[int, dict[str, Any]] = {}
    pagina = 1
    while True:
        params: dict[str, Any] = {
            "pagina": pagina,
            "registros_por_pagina": 100,
            "ordenar_por": "fecha_evento",
        }
        if id_activo is not None:
            params["activo_biologico_id"] = id_activo
        r = c.get("/suministros/auditoria", paso=f"{paso}_pag_{pagina}", params=params)
        assert r.status_code == 200, (
            f"{paso}: GET /suministros/auditoria fallo HTTP {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
        )
        items = r.json().get("items") or []
        if not items:
            break
        encontro_nuevo = False
        for it in items:
            eid = int(it["id_auditoria_suministro"])
            if eid > ultimo_id_previo:
                if id_activo is None or it.get("id_activo_biologico") == id_activo:
                    por_id[eid] = it
                encontro_nuevo = True
        if not encontro_nuevo or len(items) < 100 or pagina >= 5:
            break
        pagina += 1
    return [por_id[k] for k in sorted(por_id.keys())]


def _esperar_eventos_nuevos(
    c: CorridaSandbox,
    ultimo_id_previo: int,
    t0_operacion: float,
    paso: str,
    min_eventos: int,
    id_activo: int | None = None,
) -> tuple[list[dict[str, Any]], float]:
    nuevos: list[dict[str, Any]] = []
    latencia = 0.0
    for intento, espera in enumerate((0.0, 0.25, 0.5, 1.0), start=1):
        if espera:
            time.sleep(espera)
        nuevos = _recolectar_eventos_nuevos(c, ultimo_id_previo, f"{paso}_poll_{intento}", id_activo=id_activo)
        latencia = time.perf_counter() - t0_operacion
        if len(nuevos) >= min_eventos:
            break
    return nuevos, latencia


def _crear_activo_sin_fase(c: CorridaSandbox, etiqueta: str) -> int:
    tag = uuid.uuid4().hex[:8]
    hoy = _hoy()
    fecha_ciclo = (hoy - timedelta(days=20)).isoformat()
    payload_activo = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": 1,
        "id_infraestructura": 2,
        "identificador_unico": f"QA-G40-{etiqueta}-{tag}",
        "cantidad_inicial": 80,
        "fecha_ingreso": fecha_ciclo,
        "fecha_inicio_ciclo": fecha_ciclo,
        "origen_financiero": "nacimiento",
        "peso_actual": 24.0,
    }
    r_act = c.post("/activos-biologicos", payload_activo, paso=f"{etiqueta}_crear_activo")
    assert r_act.status_code == 201, (
        f"{etiqueta}: POST /activos-biologicos esperaba HTTP 201 [OpenAPI], obtenido {r_act.status_code} "
        f"[X-Request-Id={r_act.headers.get('X-Request-Id', '')}]: {c.seguro(r_act.text)}"
    )
    id_activo = int(r_act.json()["id_activo_biologico"])
    assert id_activo not in _IDS_PROHIBIDOS, f"{etiqueta}: ID prohibido {id_activo}"
    _CONTEXTO["activos_creados"].append(id_activo)
    return id_activo


def _crear_activo_con_fase(c: CorridaSandbox, etiqueta: str) -> tuple[int, int]:
    id_activo = _crear_activo_sin_fase(c, etiqueta)
    payload_fase = {"id_ciclo_productiva": 1, "motivo_cambio": f"Apertura fase QA G40 {etiqueta}"}
    r_fase = c.post(f"/activos-biologicos/{id_activo}/fases", payload_fase, paso=f"{etiqueta}_abrir_fase")
    assert r_fase.status_code in (200, 201), (
        f"{etiqueta}: POST /activos-biologicos/{id_activo}/fases esperaba 200/201 [OpenAPI], obtenido {r_fase.status_code} "
        f"[X-Request-Id={r_fase.headers.get('X-Request-Id', '')}]: {c.seguro(r_fase.text)}"
    )
    id_fase = int(r_fase.json()["id_gestion_fases"])
    return id_activo, id_fase


def _payload_suministro_servicio(
    id_activo: int,
    cantidad: float = 1.0,
    precio: float = 50000.0,
    fecha_aplicacion: str | None = None,
) -> dict[str, Any]:
    return {
        "id_activo_biologico": id_activo,
        "tipo_suministro": "SERVICIO_VETERINARIO",
        "cantidad": cantidad,
        "unidad_medida": "servicio",
        "precio_unitario": precio,
        "fecha_aplicacion": fecha_aplicacion or _hoy().isoformat(),
        "justificacion_precio": "Tarifa estandar segun contrato veterinario vigente QA",
        "id_idempotencia": str(uuid.uuid4()),
    }


def _validar_evento_base(ev: dict[str, Any], id_activo: int, id_usuario: int, ctx: str) -> None:
    eid = ev.get("id_auditoria_suministro")
    assert ev.get("id_activo_biologico") == id_activo, (
        f"{ctx} id={eid}: id_activo_biologico={ev.get('id_activo_biologico')!r} != {id_activo} "
        "[RF-80 v2.0 Seccion Auditoria local de M05]"
    )
    assert ev.get("id_usuario") == id_usuario, (
        f"{ctx} id={eid}: id_usuario={ev.get('id_usuario')!r} != {id_usuario} [RF-80 v2.0 Auditoria local]"
    )
    assert ev.get("resultado") == "EXITOSO", (
        f"{ctx} id={eid}: resultado={ev.get('resultado')!r} != 'EXITOSO' [RF-80 v2.0 CA-1]"
    )
    h = ev.get("hash_integridad")
    assert isinstance(h, str) and bool(_HEX64_RE.fullmatch(h)), (
        f"{ctx} id={eid}: hash_integridad invalido {h!r} [RF-80 v2.0; TC-M05-031 v2.0]"
    )
    vh = ev.get("version_hash_integridad")
    assert vh in (1, 2), (
        f"{ctx} id={eid}: version_hash_integridad={vh!r} fuera de {{1, 2}} [RF-80 v2.0]"
    )
    assert bool(ev.get("fecha_evento")) and bool(ev.get("fecha_emision")), (
        f"{ctx} id={eid}: fecha_evento/fecha_emision vacios [RF-80 v2.0 CA-11]"
    )


def _resumen_evento(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": ev.get("id_auditoria_suministro"),
        "tipo_operacion": ev.get("tipo_operacion"),
        "entidad_afectada": ev.get("entidad_afectada"),
        "resultado": ev.get("resultado"),
        "id_usuario": ev.get("id_usuario"),
        "id_activo_biologico": ev.get("id_activo_biologico"),
        "version_hash_integridad": ev.get("version_hash_integridad"),
        "hash_prefijo": (ev.get("hash_integridad") or "")[:16],
        "fecha_evento": ev.get("fecha_evento"),
        "fecha_emision": ev.get("fecha_emision"),
    }


def _actualizar_resumen_latencia_a01_a03() -> None:
    vals = sorted(float(v) for v in _CONTEXTO["obs_latencias_a01_a03_ms"].values())
    if not vals:
        return
    n = len(vals)
    _CONTEXTO["obs_latencia_a01_a03_resumen"] = {
        "muestras": n,
        "min_ms": round(vals[0], 2),
        "p50_ms": round(vals[n // 2], 2),
        "max_ms": round(vals[-1], 2),
        "por_operacion_ms": dict(_CONTEXTO["obs_latencias_a01_a03_ms"]),
    }


def _guardar_observaciones() -> None:
    directorio = os.environ.get("TEST_EVIDENCE_DIR")
    if not directorio:
        return
    _actualizar_resumen_latencia_a01_a03()
    destino = Path(directorio) / ARCHIVO_OBSERVACIONES
    obs = {
        "total_base": _CONTEXTO["total_base"],
        "ultimo_id_base": _CONTEXTO["ultimo_id_base"],
        "activos_creados": _CONTEXTO["activos_creados"],
        "a01_eventos_commit_rf78": _CONTEXTO["obs_a01_eventos"],
        "a02_resultado_ica_conteo": _CONTEXTO["obs_a02_resultado_ica_conteo"],
        "a02_eventos_app_rf79": _CONTEXTO["obs_a02_eventos_app"],
        "a03_evento_rf81": _CONTEXTO["obs_a03_evento"],
        "b01_fallos_observados": _CONTEXTO["obs_b01_fallos"],
        "latencia_a01_a03_resumen": _CONTEXTO["obs_latencia_a01_a03_resumen"],
        "c01_recursos": _CONTEXTO["c01_recursos"],
        "c01_eventos_capturados": _CONTEXTO["c01_eventos_capturados"],
        "checkpoints_detalle": _CONTEXTO["checkpoints_detalle"],
        "c02_analisis": _CONTEXTO["obs_c02_analisis"],
    }
    destino.write_text(json.dumps(obs, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# T00 - Linea base de auditoria en corrida sandbox independiente
# =============================================================================

def test_t00_linea_base():
    """T00 (Testing Harness / Inocuidad): lectura inicial en sandbox independiente y cierre DELETE -> 200."""
    c = CorridaSandbox("inopre")
    total = None
    ultimo_id = None
    r_close = None
    try:
        c.login_admin()
        total, ultimo_id = _leer_estado_auditoria_api(c, "t00_get_auditoria_base")
        _CONTEXTO["total_base"] = total
        _CONTEXTO["ultimo_id_base"] = ultimo_id
    finally:
        r_close = c.cerrar()
        _CONTEXTO["checkpoints_detalle"]["test_t00_linea_base"] = {
            "obtenido_texto": (
                f"GET /suministros/auditoria -> HTTP 200 (total_base={total}, ultimo_id_base={ultimo_id}); "
                f"DELETE /test-control/runs/{c.run_id} -> HTTP {r_close.status_code if r_close else None}"
            ),
            "total_base": total,
            "ultimo_id_base": ultimo_id,
            "delete_status_code": r_close.status_code if r_close else None,
        }
        assert r_close is not None and r_close.status_code == 200, (
            f"T00 cierre sandbox inesperado: {r_close.status_code if r_close else None}"
        )
        assert "rollback exitoso" in r_close.text.lower(), (
            f"T00 confirmacion rollback inesperada: {c.seguro(r_close.text)}"
        )


# =============================================================================
# A01 - Atomicidad en commit RF-78 (POST /suministros/costeo-directo)
# =============================================================================

def test_a01_atomicidad_commit_rf78():
    """A01 (RF-80 v2.0 + TC-M05-031 v2.0): costeo directo valido -> 200 [RF-78 CA-14/E8] + 3 eventos atomicos con hash."""
    c = _principal()
    uid = _CONTEXTO["admin_id_usuario"]
    assert uid is not None, "Precondicion A01: Admin id_usuario faltante"

    id_activo, id_fase = _crear_activo_con_fase(c, "a01")
    _CONTEXTO["id_activo_1"] = id_activo
    _CONTEXTO["id_fase_1"] = id_fase

    _, prev_id = _leer_estado_auditoria_api(c, "a01_snap_pre")
    payload = _payload_suministro_servicio(id_activo, cantidad=1.0, precio=50000.0)
    t0 = time.perf_counter()
    r_sum = c.post("/suministros/costeo-directo", payload, paso="a01_rf78_costeo_valido")
    op_ms = round((time.perf_counter() - t0) * 1000, 2)
    _CONTEXTO["obs_latencias_a01_a03_ms"]["A01_post_costeo_directo"] = op_ms

    ec_sum = _error_code(r_sum)
    _CONTEXTO["checkpoints_detalle"]["test_a01_atomicidad_commit_rf78"] = {
        "obtenido_texto": (
            f"POST /suministros/costeo-directo -> HTTP {r_sum.status_code}"
            f"{f' (error_code={ec_sum})' if ec_sum else ''}; eventos_nuevos=PENDIENTE"
        ),
        "http_status": r_sum.status_code,
        "error_code": ec_sum,
        "op_duracion_ms": op_ms,
    }
    assert r_sum.status_code == 200, (
        f"A01 esperaba HTTP 200 en POST /suministros/costeo-directo [RF-78 CA-14 y E8; resiliencia RF-79], "
        f"obtenido {r_sum.status_code} [X-Request-Id={r_sum.headers.get('X-Request-Id', '')}]: {c.seguro(r_sum.text)}"
    )

    nuevos, lat_aud = _esperar_eventos_nuevos(c, prev_id, t0, "a01_auditoria", min_eventos=3, id_activo=id_activo)
    grupos_evs = _agrupar_eventos_por_tipo(nuevos)
    str_evs = _formatear_eventos_por_tipo(nuevos)
    _CONTEXTO["checkpoints_detalle"]["test_a01_atomicidad_commit_rf78"].update({
        "eventos_por_tipo": grupos_evs,
        "lat_aud_s": round(lat_aud, 3),
        "obtenido_texto": (
            f"POST /suministros/costeo-directo -> HTTP {r_sum.status_code}; "
            f"eventos: {str_evs} (lat_aud={lat_aud:.3f} s)"
        ),
    })
    assert lat_aud <= 2.0, f"A01 persistencia de auditoria excedio 2.0 s: {lat_aud:.3f} s [RF-80 v2.0 CA-1]"

    tipos_esperados = ("SUMINISTRO_REGISTRADO", "PRECIO_MANUAL_INGRESADO", "ACUMULADO_ACTUALIZADO")
    conteos = {t: sum(1 for e in nuevos if e.get("tipo_operacion") == t) for t in tipos_esperados}
    assert all(conteos[t] == 1 for t in tipos_esperados) and len(nuevos) == 3, (
        f"A01 esperaba exactamente 1 de cada {tipos_esperados} (total 3), obtenido conteos={conteos}, total={len(nuevos)} "
        "[RF-80 v2.0 Auditoria local; TC-M05-031 v2.0]"
    )
    for ev in nuevos:
        _validar_evento_base(ev, id_activo, uid, "A01")

    r_acum = c.get(f"/suministros/costeo-directo/acumulado/activo/{id_activo}", paso="a01_verificar_acumulado")
    assert r_acum.status_code == 200, (
        f"A01 acumulado esperaba HTTP 200 [OpenAPI], obtenido {r_acum.status_code}: {c.seguro(r_acum.text)}"
    )
    acum = r_acum.json()
    assert float(acum.get("acumulado_total_ciclo", 0)) == 50000.0, (
        f"A01 acumulado_total_ciclo={acum.get('acumulado_total_ciclo')!r} != 50000.0 [TC-M05-031 v2.0]"
    )
    _CONTEXTO["obs_a01_eventos"] = [_resumen_evento(e) for e in nuevos]
    _CONTEXTO["checkpoints_detalle"]["test_a01_atomicidad_commit_rf78"]["acumulado_total_ciclo"] = acum.get("acumulado_total_ciclo")
    _CONTEXTO["checkpoints_detalle"]["test_a01_atomicidad_commit_rf78"]["obtenido_texto"] = (
        f"POST /suministros/costeo-directo -> HTTP {r_sum.status_code}; "
        f"GET acumulado/activo/{id_activo} -> HTTP {r_acum.status_code} (total={acum.get('acumulado_total_ciclo')}); "
        f"eventos: {str_evs}"
    )


# =============================================================================
# A02 - Atomicidad en commit RF-79 (POST /activos-biologicos/{id}/cierre)
# =============================================================================

def test_a02_atomicidad_commit_rf79():
    """A02 (RF-80 v2.0 + TC-M05-031 v2.0): cierre ciclo RF-79 -> 200 [OpenAPI] + CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO."""
    c = _principal()
    uid = _CONTEXTO["admin_id_usuario"]
    id_activo = _CONTEXTO["id_activo_1"]
    id_fase = _CONTEXTO["id_fase_1"]
    assert uid is not None and id_activo is not None and id_fase is not None, (
        "Precondicion A02: A01 debe haber creado y fondeado el activo 1"
    )

    _, prev_id = _leer_estado_auditoria_api(c, "a02_snap_pre")
    payload_cierre = {
        "fecha_cierre": _hoy().isoformat(),
        "motivo_cierre": "finalizacion_lote",
        "descripcion_cierre": "Cierre QA TC-M05-G40 atomicidad RF-79",
    }
    t0 = time.perf_counter()
    r_cierre = c.post(f"/activos-biologicos/{id_activo}/cierre", payload_cierre, paso="a02_rf79_cierre")
    op_ms = round((time.perf_counter() - t0) * 1000, 2)
    _CONTEXTO["obs_latencias_a01_a03_ms"]["A02_post_cierre"] = op_ms

    ec_cierre = _error_code(r_cierre)
    _CONTEXTO["checkpoints_detalle"]["test_a02_atomicidad_commit_rf79"] = {
        "obtenido_texto": (
            f"POST /activos-biologicos/{id_activo}/cierre -> HTTP {r_cierre.status_code}"
            f"{f' (error_code={ec_cierre})' if ec_cierre else ''}"
        ),
        "http_status": r_cierre.status_code,
        "error_code": ec_cierre,
        "op_duracion_ms": op_ms,
    }
    assert r_cierre.status_code == 200, (
        f"A02 cierre esperaba HTTP 200 [OpenAPI / activo_biologico_router.py], obtenido {r_cierre.status_code} "
        f"[X-Request-Id={r_cierre.headers.get('X-Request-Id', '')}]: {c.seguro(r_cierre.text)}"
    )

    nuevos, lat_aud = _esperar_eventos_nuevos(c, prev_id, t0, "a02_auditoria", min_eventos=2, id_activo=id_activo)
    eventos_ica = [e for e in nuevos if e.get("entidad_afectada") == "resultado_ica"]
    _CONTEXTO["obs_a02_resultado_ica_conteo"] = len(eventos_ica)
    eventos_app = [e for e in nuevos if e.get("entidad_afectada") != "resultado_ica"]

    str_app = _formatear_eventos_por_tipo(eventos_app)
    str_ica = _formatear_eventos_por_tipo(eventos_ica)
    _CONTEXTO["checkpoints_detalle"]["test_a02_atomicidad_commit_rf79"].update({
        "eventos_app_por_tipo": _agrupar_eventos_por_tipo(eventos_app),
        "eventos_ica_por_tipo": _agrupar_eventos_por_tipo(eventos_ica),
        "resultado_ica_conteo": len(eventos_ica),
        "lat_aud_s": round(lat_aud, 3),
        "obtenido_texto": (
            f"POST /activos-biologicos/{id_activo}/cierre -> HTTP {r_cierre.status_code}; "
            f"eventos_app: {str_app}; resultado_ica(solo conteo): {str_ica}"
        ),
    })
    assert lat_aud <= 2.0, f"A02 persistencia de auditoria excedio 2.0 s: {lat_aud:.3f} s [RF-80 v2.0 CA-1]"

    consolidados = [e for e in eventos_app if e.get("tipo_operacion") == "CICLO_CONSOLIDADO"]
    reportes = [e for e in eventos_app if e.get("tipo_operacion") == "REPORTE_COSTOS_GENERADO"]
    assert len(consolidados) == 1 and len(reportes) == 1, (
        f"A02 esperaba 1 CICLO_CONSOLIDADO y 1 REPORTE_COSTOS_GENERADO nuevos del activo; "
        f"obtenidos {[e.get('tipo_operacion') for e in eventos_app]} [RF-80 v2.0; TC-M05-031 v2.0]"
    )
    ev_cons = consolidados[0]
    ev_rep = reportes[0]
    assert int(ev_cons["id_auditoria_suministro"]) < int(ev_rep["id_auditoria_suministro"]), (
        f"A02 secuencia esperada CICLO_CONSOLIDADO antes de REPORTE_COSTOS_GENERADO: "
        f"{ev_cons['id_auditoria_suministro']} vs {ev_rep['id_auditoria_suministro']} [TC-M05-031 v2.0]"
    )
    evs_oblig = [ev_cons, ev_rep]
    assert len(evs_oblig) == 2
    for ev in evs_oblig:
        assert ev.get("entidad_afectada") == "provision_nic41", (
            f"A02 id={ev.get('id_auditoria_suministro')}: entidad_afectada={ev.get('entidad_afectada')!r} "
            "!= 'provision_nic41' [RF-80 v2.0 Auditoria local; ConsolidarCicloUseCase]"
        )
        _validar_evento_base(ev, id_activo, uid, "A02")

    r_prov = c.get(f"/suministros/nic41/ciclo/{id_fase}/versiones", paso="a02_verificar_provision")
    ec_prov = _error_code(r_prov)
    assert r_prov.status_code == 200, (
        f"A02 GET versiones NIC-41 esperaba HTTP 200 [OpenAPI], obtenido {r_prov.status_code}"
        f"{f' (error_code={ec_prov})' if ec_prov else ''}: {c.seguro(r_prov.text)}"
    )
    prov_json = r_prov.json()
    versiones = prov_json.get("versiones") if isinstance(prov_json, dict) else prov_json
    assert isinstance(versiones, list), (
        f"A02 esperaba lista en clave 'versiones' [ListaVersionesProvisionResponse, provision_nic41_schema.py:63-67], "
        f"obtenido {type(versiones).__name__}"
    )
    consolidadas = [v for v in versiones if isinstance(v, dict) and v.get("modalidad") == "CONSOLIDADO"]
    _CONTEXTO["checkpoints_detalle"]["test_a02_atomicidad_commit_rf79"]["versiones_total"] = len(versiones)
    _CONTEXTO["checkpoints_detalle"]["test_a02_atomicidad_commit_rf79"]["versiones_consolidado"] = len(consolidadas)
    assert len(versiones) == 1 and len(consolidadas) == 1, (
        f"A02 esperaba exactamente 1 version CONSOLIDADO del ciclo {id_fase} "
        f"[ListaVersionesProvisionResponse, provision_nic41_schema.py:63-67; TC-M05-031 v2.0], "
        f"obtenido versiones={len(versiones)}, consolidado={len(consolidadas)}"
    )

    _CONTEXTO["obs_a02_eventos_app"] = [_resumen_evento(e) for e in evs_oblig]
    _CONTEXTO["checkpoints_detalle"]["test_a02_atomicidad_commit_rf79"]["obtenido_texto"] = (
        f"POST /activos-biologicos/{id_activo}/cierre -> HTTP {r_cierre.status_code}; "
        f"GET versiones -> HTTP {r_prov.status_code} (versiones={len(versiones)}, CONSOLIDADO={len(consolidadas)}); "
        f"eventos_app: {str_app}; resultado_ica(solo conteo): {str_ica}"
    )


# =============================================================================
# A03 - Atomicidad en commit RF-81 (GET /suministros/historial)
# =============================================================================

def test_a03_atomicidad_commit_rf81():
    """A03 (RF-80 v2.0 + TC-M05-031 v2.0): GET /suministros/historial -> 200 [OpenAPI] + 1 CONSULTA_HISTORIAL_EJECUTADA."""
    c = _principal()
    uid = _CONTEXTO["admin_id_usuario"]
    id_activo = _CONTEXTO["id_activo_1"]
    assert uid is not None and id_activo is not None, "Precondicion A03: activo 1 faltante"

    _, prev_id = _leer_estado_auditoria_api(c, "a03_snap_pre")
    t0 = time.perf_counter()
    r_hist = c.get("/suministros/historial", paso="a03_rf81_historial", params={"id_activo_biologico": id_activo})
    op_ms = round((time.perf_counter() - t0) * 1000, 2)
    _CONTEXTO["obs_latencias_a01_a03_ms"]["A03_get_historial"] = op_ms

    ec_hist = _error_code(r_hist)
    _CONTEXTO["checkpoints_detalle"]["test_a03_atomicidad_commit_rf81"] = {
        "obtenido_texto": (
            f"GET /suministros/historial -> HTTP {r_hist.status_code}"
            f"{f' (error_code={ec_hist})' if ec_hist else ''}"
        ),
        "http_status": r_hist.status_code,
        "error_code": ec_hist,
        "op_duracion_ms": op_ms,
    }
    assert r_hist.status_code == 200, (
        f"A03 GET /suministros/historial esperaba HTTP 200 [OpenAPI], obtenido {r_hist.status_code} "
        f"[X-Request-Id={r_hist.headers.get('X-Request-Id', '')}]: {c.seguro(r_hist.text)}"
    )

    nuevos, lat_aud = _esperar_eventos_nuevos(c, prev_id, t0, "a03_auditoria", min_eventos=1, id_activo=id_activo)
    str_evs = _formatear_eventos_por_tipo(nuevos)
    _CONTEXTO["checkpoints_detalle"]["test_a03_atomicidad_commit_rf81"].update({
        "eventos_por_tipo": _agrupar_eventos_por_tipo(nuevos),
        "lat_aud_s": round(lat_aud, 3),
        "obtenido_texto": (
            f"GET /suministros/historial -> HTTP {r_hist.status_code}; "
            f"eventos: {str_evs} (lat_aud={lat_aud:.3f} s)"
        ),
    })
    assert lat_aud <= 2.0, f"A03 persistencia de auditoria excedio 2.0 s: {lat_aud:.3f} s [RF-80 v2.0 CA-1]"

    consultas = [e for e in nuevos if e.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA"]
    assert len(consultas) == 1, (
        f"A03 esperaba exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo del Admin, obtenidos {len(consultas)} "
        "[RF-80 v2.0 Auditoria local; TC-M05-031 v2.0]"
    )
    ev = consultas[0]
    assert ev.get("entidad_afectada") == "historial_suministros", (
        f"A03 entidad_afectada={ev.get('entidad_afectada')!r} != 'historial_suministros' [ConsultarHistorialUseCase]"
    )
    _validar_evento_base(ev, id_activo, uid, "A03")
    _CONTEXTO["obs_a03_evento"] = _resumen_evento(ev)


# =============================================================================
# B01 - Rollback / no persistencia parcial ante errores por API
# =============================================================================

def test_b01_rollback_errores_api():
    """B01 (RF-80 v2.0 + TC-M05-031 v2.0): rechazos en RF-78 (sin fase -> 409), RF-79 (repetido -> 4xx) y RF-81 (rango invertido -> 422)."""
    c = _principal()
    id_activo_1 = _CONTEXTO["id_activo_1"]
    id_fase_1 = _CONTEXTO["id_fase_1"]
    assert id_activo_1 is not None and id_fase_1 is not None, "Precondicion B01: A01/A02 requeridos"

    detalle_b01: dict[str, Any] = {}
    _CONTEXTO["checkpoints_detalle"]["test_b01_rollback_errores_api"] = detalle_b01

    # (a) RF-78 sobre un activo de prueba SIN fase abierta -> 409; 0 SUMINISTRO_REGISTRADO y 0 ACUMULADO_ACTUALIZADO nuevos
    id_activo_2 = _crear_activo_sin_fase(c, "b01a")
    _CONTEXTO["id_activo_2"] = id_activo_2
    _, prev_a = _leer_estado_auditoria_api(c, "b01a_snap_pre")
    r_sin_fase = c.post(
        "/suministros/costeo-directo",
        _payload_suministro_servicio(id_activo_2, cantidad=1.0, precio=30000.0),
        paso="b01a_rf78_sin_fase_abierta",
    )
    ec_a = _error_code(r_sin_fase)
    evs_a = _recolectar_eventos_nuevos(c, prev_a, "b01a_auditoria")
    sum_reg_a = [e for e in evs_a if e.get("tipo_operacion") == "SUMINISTRO_REGISTRADO"]
    acum_act_a = [e for e in evs_a if e.get("tipo_operacion") == "ACUMULADO_ACTUALIZADO"]
    for ev in evs_a:
        _CONTEXTO["obs_b01_fallos"].append({"caso": "B01a", **_resumen_evento(ev)})
    detalle_b01["a"] = {
        "http_status": r_sin_fase.status_code,
        "error_code": ec_a,
        "SUMINISTRO_REGISTRADO": len(sum_reg_a),
        "ACUMULADO_ACTUALIZADO": len(acum_act_a),
        "obs_eventos": _agrupar_eventos_por_tipo(evs_a),
    }
    assert r_sin_fase.status_code == 409, (
        f"B01(a) esperaba HTTP 409 en RF-78 sobre activo sin fase abierta [RF-78; OpenAPI], "
        f"obtenido {r_sin_fase.status_code} (error_code={ec_a}) "
        f"[X-Request-Id={r_sin_fase.headers.get('X-Request-Id', '')}]: {c.seguro(r_sin_fase.text)}"
    )
    assert len(sum_reg_a) == 0 and len(acum_act_a) == 0, (
        f"B01(a) esperaba 0 SUMINISTRO_REGISTRADO y 0 ACUMULADO_ACTUALIZADO nuevos; "
        f"hallados SUMINISTRO_REGISTRADO={len(sum_reg_a)}, ACUMULADO_ACTUALIZADO={len(acum_act_a)} "
        "[RF-80 v2.0 RNF-02; TC-M05-031 v2.0]"
    )

    # (b) RF-79 repetir POST /activos-biologicos/{id}/cierre sobre activo cerrado en A02 -> 4xx;
    #     0 CICLO_CONSOLIDADO y 0 REPORTE_COSTOS_GENERADO nuevos, y "versiones" sigue en 1.
    _, prev_b = _leer_estado_auditoria_api(c, "b01b_snap_pre")
    r_rep = c.post(
        f"/activos-biologicos/{id_activo_1}/cierre",
        {
            "fecha_cierre": _hoy().isoformat(),
            "motivo_cierre": "finalizacion_lote",
            "descripcion_cierre": "Reintento cierre QA B01b sobre activo ya cerrado",
        },
        paso="b01b_rf79_cierre_repetido",
    )
    ec_b = _error_code(r_rep)
    evs_b = _recolectar_eventos_nuevos(c, prev_b, "b01b_auditoria")
    cons_b = [e for e in evs_b if e.get("tipo_operacion") == "CICLO_CONSOLIDADO"]
    rep_b = [e for e in evs_b if e.get("tipo_operacion") == "REPORTE_COSTOS_GENERADO"]
    for ev in evs_b:
        _CONTEXTO["obs_b01_fallos"].append({"caso": "B01b", **_resumen_evento(ev)})
    r_prov_b = c.get(f"/suministros/nic41/ciclo/{id_fase_1}/versiones", paso="b01b_verificar_versiones")
    versiones_b = (r_prov_b.json().get("versiones") or []) if r_prov_b.status_code == 200 else []
    detalle_b01["b"] = {
        "http_status": r_rep.status_code,
        "error_code": ec_b,
        "CICLO_CONSOLIDADO": len(cons_b),
        "REPORTE_COSTOS_GENERADO": len(rep_b),
        "versiones_status": r_prov_b.status_code,
        "versiones_total": len(versiones_b),
        "obs_eventos": _agrupar_eventos_por_tipo(evs_b),
    }
    assert 400 <= r_rep.status_code < 500, (
        f"B01(b) esperaba HTTP 4xx al repetir cierre RF-79 sobre activo {id_activo_1} ya cerrado [RF-79; OpenAPI], "
        f"obtenido {r_rep.status_code} (error_code={ec_b}) "
        f"[X-Request-Id={r_rep.headers.get('X-Request-Id', '')}]: {c.seguro(r_rep.text)}"
    )
    assert len(cons_b) == 0 and len(rep_b) == 0, (
        f"B01(b) esperaba 0 CICLO_CONSOLIDADO y 0 REPORTE_COSTOS_GENERADO nuevos; "
        f"hallados CICLO_CONSOLIDADO={len(cons_b)}, REPORTE_COSTOS_GENERADO={len(rep_b)} "
        "[RF-80 v2.0 RNF-02; TC-M05-031 v2.0]"
    )
    assert r_prov_b.status_code == 200 and len(versiones_b) == 1, (
        f"B01(b) 'versiones' del ciclo {id_fase_1} debio seguir en 1 (HTTP 200), "
        f"obtenido HTTP {r_prov_b.status_code}, len(versiones)={len(versiones_b)} [TC-M05-031 v2.0]"
    )

    # (c) RF-81 rango invertido -> 422 COMBINACION_FILTROS_INVALIDA; 0 CONSULTA_HISTORIAL_EJECUTADA EXITOSO
    _, prev_c = _leer_estado_auditoria_api(c, "b01c_snap_pre")
    hoy = _hoy()
    r_hist_inv = c.get(
        "/suministros/historial",
        paso="b01c_rf81_rango_invertido",
        params={
            "id_activo_biologico": id_activo_1,
            "fecha_inicio_filtro": hoy.isoformat(),
            "fecha_fin_filtro": (hoy - timedelta(days=5)).isoformat(),
        },
    )
    ec_c = _error_code(r_hist_inv)
    evs_c = _recolectar_eventos_nuevos(c, prev_c, "b01c_auditoria")
    consultas_exitosas_c = [
        e for e in evs_c
        if e.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA" and e.get("resultado") == "EXITOSO"
    ]
    if not evs_c:
        _CONTEXTO["obs_b01_fallos"].append({"caso": "B01c", "observacion": "Sin evento de auditoria emitido en rechazo 422 de RF-81"})
    else:
        for ev in evs_c:
            _CONTEXTO["obs_b01_fallos"].append({"caso": "B01c", **_resumen_evento(ev)})
    detalle_b01["c"] = {
        "http_status": r_hist_inv.status_code,
        "error_code": ec_c,
        "CONSULTA_HISTORIAL_EJECUTADA_EXITOSO": len(consultas_exitosas_c),
        "obs_eventos": _agrupar_eventos_por_tipo(evs_c),
    }
    detalle_b01["obtenido_texto"] = (
        f"(a) RF-78 sin fase -> HTTP {r_sin_fase.status_code} ({ec_a}), "
        f"SUMINISTRO_REGISTRADO=0 [], ACUMULADO_ACTUALIZADO=0 [] (obs: {_formatear_eventos_por_tipo(evs_a)}); "
        f"(b) RF-79 cierre repetido -> HTTP {r_rep.status_code} ({ec_b}), "
        f"CICLO_CONSOLIDADO=0 [], REPORTE_COSTOS_GENERADO=0 [], versiones={len(versiones_b)} "
        f"(obs: {_formatear_eventos_por_tipo(evs_b)}); "
        f"(c) RF-81 rango invertido -> HTTP {r_hist_inv.status_code} ({ec_c}), "
        f"CONSULTA_HISTORIAL_EJECUTADA_EXITOSO=0 [] (obs: {_formatear_eventos_por_tipo(evs_c)})"
    )
    assert r_hist_inv.status_code == 422, (
        f"B01(c) esperaba HTTP 422 en rango invertido RF-81 [OpenAPI; RF-81 R7/E5], obtenido {r_hist_inv.status_code} "
        f"[X-Request-Id={r_hist_inv.headers.get('X-Request-Id', '')}]: {c.seguro(r_hist_inv.text)}"
    )
    assert ec_c == "COMBINACION_FILTROS_INVALIDA", (
        f"B01(c) esperaba error_code='COMBINACION_FILTROS_INVALIDA', obtenido {ec_c!r} [RF-81 R7/E5]"
    )
    assert len(consultas_exitosas_c) == 0, (
        f"B01(c) no debio emitir CONSULTA_HISTORIAL_EJECUTADA con resultado EXITOSO; hallados {len(consultas_exitosas_c)} "
        "[RF-80 v2.0; TC-M05-031 v2.0]"
    )


# =============================================================================
# T98 - Cierre de corrida sandbox principal
# =============================================================================

def test_t98_cierre_sandbox_principal():
    """T98 (Testing Harness): cierre limpio de la corrida sandbox principal via DELETE /test-control/runs/{id} -> 200."""
    c = _principal()
    r = c.cerrar()
    _CONTEXTO["checkpoints_detalle"]["test_t98_cierre_sandbox_principal"] = {
        "obtenido_texto": f"DELETE /test-control/runs/{c.run_id} -> HTTP {r.status_code if r else None}",
        "http_status": r.status_code if r else None,
        "run_id": c.run_id,
    }
    assert r is not None, "T98: el sandbox principal ya habia sido cerrado"
    assert r.status_code == 200, (
        f"T98 cierre sandbox principal HTTP {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    assert "rollback exitoso" in r.text.lower(), (
        f"T98 respuesta inesperada al cerrar sandbox: {c.seguro(r.text)}"
    )


# =============================================================================
# C01 - Rollback tecnico en corrida sandbox propia + verificacion de no persistencia por ID
# =============================================================================

def test_c01_rollback_tecnico_sandbox():
    """C01 (TC-M05-031 v2.0 / RF-80 v2.0 RNF-02): rollback tecnico en corrida aparte y verificacion 404 por ID."""
    c1 = CorridaSandbox("c01")
    detalle_c01: dict[str, Any] = {}
    _CONTEXTO["checkpoints_detalle"]["test_c01_rollback_tecnico_sandbox"] = detalle_c01

    ids_capturados: list[int] = []
    pre_total = 0
    pre_ultimo = 0
    id_act = 0
    id_fase = 0

    try:
        c1.login_admin()
        pre_total, pre_ultimo = _leer_estado_auditoria_api(c1, "c01_estado_previo")
        id_act, id_fase = _crear_activo_con_fase(c1, "c01")
        _CONTEXTO["c01_recursos"] = {"id_activo_biologico": id_act, "id_gestion_fases": id_fase}

        # 1 RF-78 valido (200)
        _, prev_78 = _leer_estado_auditoria_api(c1, "c01_snap_pre_rf78")
        t0_78 = time.perf_counter()
        r_78 = c1.post("/suministros/costeo-directo", _payload_suministro_servicio(id_act), paso="c01_rf78_valido")
        assert r_78.status_code == 200, (
            f"C01 RF-78 esperaba HTTP 200, obtenido {r_78.status_code}: {c1.seguro(r_78.text)}"
        )
        evs_78, _ = _esperar_eventos_nuevos(c1, prev_78, t0_78, "c01_aud_rf78", min_eventos=1, id_activo=id_act)
        assert len(evs_78) >= 1, "C01 esperaba >= 1 evento nuevo en RF-78 [TC-M05-031 v2.0]"

        # Cierre RF-79 (200)
        _, prev_79 = _leer_estado_auditoria_api(c1, "c01_snap_pre_rf79")
        t0_79 = time.perf_counter()
        r_79 = c1.post(
            f"/activos-biologicos/{id_act}/cierre",
            {
                "fecha_cierre": _hoy().isoformat(),
                "motivo_cierre": "finalizacion_lote",
                "descripcion_cierre": "Cierre QA C01 rollback tecnico RF-79",
            },
            paso="c01_rf79_cierre",
        )
        assert r_79.status_code == 200, (
            f"C01 RF-79 esperaba HTTP 200, obtenido {r_79.status_code}: {c1.seguro(r_79.text)}"
        )
        evs_79, _ = _esperar_eventos_nuevos(c1, prev_79, t0_79, "c01_aud_rf79", min_eventos=1, id_activo=id_act)
        assert len(evs_79) >= 1, "C01 esperaba >= 1 evento nuevo en RF-79 [TC-M05-031 v2.0]"

        # 1 consulta RF-81 (200)
        _, prev_81 = _leer_estado_auditoria_api(c1, "c01_snap_pre_rf81")
        t0_81 = time.perf_counter()
        r_81 = c1.get("/suministros/historial", paso="c01_rf81_historial", params={"id_activo_biologico": id_act})
        assert r_81.status_code == 200, (
            f"C01 RF-81 esperaba HTTP 200, obtenido {r_81.status_code}: {c1.seguro(r_81.text)}"
        )
        evs_81, _ = _esperar_eventos_nuevos(c1, prev_81, t0_81, "c01_aud_rf81", min_eventos=1, id_activo=id_act)
        assert len(evs_81) >= 1, "C01 esperaba >= 1 evento nuevo en RF-81 [TC-M05-031 v2.0]"

        todos_evs = [*evs_78, *evs_79, *evs_81]
        por_id_cap: dict[int, str] = {}
        for ev in todos_evs:
            eid = int(ev["id_auditoria_suministro"])
            por_id_cap[eid] = str(ev.get("tipo_operacion") or "DESCONOCIDO")
        ids_capturados = sorted(por_id_cap.keys())
        _CONTEXTO["c01_eventos_capturados"] = [
            {"id_auditoria_suministro": eid, "tipo_operacion": por_id_cap[eid]} for eid in ids_capturados
        ]
        detalle_c01.update({
            "pre_total": pre_total,
            "pre_ultimo_id": pre_ultimo,
            "id_activo": id_act,
            "id_fase": id_fase,
            "rf78_status": r_78.status_code,
            "rf78_eventos": _agrupar_eventos_por_tipo(evs_78),
            "rf79_status": r_79.status_code,
            "rf79_eventos": _agrupar_eventos_por_tipo(evs_79),
            "rf81_status": r_81.status_code,
            "rf81_eventos": _agrupar_eventos_por_tipo(evs_81),
            "ids_capturados": ids_capturados,
        })
    finally:
        r_close_c1 = c1.cerrar()
        detalle_c01["delete_c01_status"] = r_close_c1.status_code if r_close_c1 else None
        assert r_close_c1 is not None and r_close_c1.status_code == 200, (
            f"C01 cierre sandbox DELETE HTTP {r_close_c1.status_code if r_close_c1 else None}"
        )
        assert "rollback exitoso" in r_close_c1.text.lower(), (
            f"C01 confirmacion rollback inesperada: {c1.seguro(r_close_c1.text)}"
        )

    # Corrida de SOLO LECTURA aparte para verificar desaparicion total tras rollback
    c2 = CorridaSandbox("c01verif")
    verif_eventos: list[dict[str, Any]] = []
    act_verif: dict[str, Any] = {}
    post_total = None
    post_ultimo = None
    try:
        c2.login_admin()
        for eid in ids_capturados:
            re_ev = c2.get(f"/suministros/auditoria/{eid}", paso=f"c01_verif_ev_{eid}")
            ec_ev = _error_code(re_ev)
            verif_eventos.append({"id": eid, "status_code": re_ev.status_code, "error_code": ec_ev})
            assert re_ev.status_code == 404, (
                f"C01 FALLO ROLLBACK: evento de auditoria id={eid} sobrevivio tras DELETE rollback "
                f"(HTTP {re_ev.status_code}, error_code={ec_ev}) [TC-M05-031 v2.0; RF-80 v2.0 RNF-02]"
            )

        re_act = c2.get(f"/activos-biologicos/{id_act}", paso=f"c01_verif_activo_{id_act}")
        ec_act = _error_code(re_act)
        act_verif = {"id_activo": id_act, "status_code": re_act.status_code, "error_code": ec_act}
        assert re_act.status_code == 404, (
            f"C01 FALLO ROLLBACK: activo id={id_act} sobrevivio tras DELETE rollback "
            f"(HTTP {re_act.status_code}, error_code={ec_act}) [TC-M05-031 v2.0; RF-80 v2.0 RNF-02]"
        )

        post_total, post_ultimo = _leer_estado_auditoria_api(c2, "c01_verif_estado_global")
        detalle_c01.update({
            "verif_eventos_404": verif_eventos,
            "verif_activo_404": act_verif,
            "post_total": post_total,
            "post_ultimo_id": post_ultimo,
            "obtenido_texto": (
                f"C01 recursos(activo={id_act}, fase={id_fase}); "
                f"RF-78=200 ({_formatear_eventos_por_tipo(evs_78)}); "
                f"RF-79=200 ({_formatear_eventos_por_tipo(evs_79)}); "
                f"RF-81=200 ({_formatear_eventos_por_tipo(evs_81)}); "
                f"DELETE=200; post-rollback: {len(verif_eventos)} eventos -> 404 "
                f"({sorted({v['error_code'] for v in verif_eventos if v.get('error_code')})}), "
                f"activo {id_act} -> {re_act.status_code} ({ec_act}), "
                f"total={post_total} (pre={pre_total}), ultimo_id={post_ultimo} (pre={pre_ultimo})"
            ),
        })
        assert post_total == pre_total, (
            f"C01 total tras rollback ({post_total}) != previo a C01 ({pre_total}) [TC-M05-031 v2.0]"
        )
        assert post_ultimo == pre_ultimo, (
            f"C01 ultimo_id tras rollback ({post_ultimo}) != previo a C01 ({pre_ultimo}) [TC-M05-031 v2.0]"
        )
    finally:
        r_close_c2 = c2.cerrar()
        assert r_close_c2 is not None and r_close_c2.status_code == 200, (
            f"C01 verif cierre sandbox inesperado: {r_close_c2.status_code if r_close_c2 else None}"
        )
        assert "rollback exitoso" in r_close_c2.text.lower(), (
            f"C01 verif confirmacion rollback inesperada: {c2.seguro(r_close_c2.text)}"
        )


# =============================================================================
# T99 - Inocuidad post-rollback (incluye activos de A01, B01 y C01)
# =============================================================================

def test_t99_inocuidad_post_rollback():
    """T99 (Testing Harness / Inocuidad): total y ultimo_id iguales a T00; todos los activos creados y acumulados -> 404."""
    assert _CONTEXTO["total_base"] is not None and _CONTEXTO["ultimo_id_base"] is not None, (
        "Precondicion T99: T00 no registro linea base"
    )
    activos = list(dict.fromkeys(_CONTEXTO["activos_creados"]))
    assert len(activos) >= 3, (
        f"Precondicion T99: se esperaban >=3 activos creados (A01, B01a, C01), encontrados {activos}"
    )

    c = CorridaSandbox("inopost")
    detalle_t99: dict[str, Any] = {}
    _CONTEXTO["checkpoints_detalle"]["test_t99_inocuidad_post_rollback"] = detalle_t99
    verif_activos: list[dict[str, Any]] = []
    verif_acumulados: list[dict[str, Any]] = []
    total_post = None
    ultimo_post = None

    try:
        c.login_admin()
        total_post, ultimo_post = _leer_estado_auditoria_api(c, "t99_get_auditoria_post")
        for aid in activos:
            rg = c.get(f"/activos-biologicos/{aid}", paso=f"t99_get_activo_{aid}")
            verif_activos.append({"id": aid, "status_code": rg.status_code, "error_code": _error_code(rg)})
            assert rg.status_code == 404, (
                f"T99 activo {aid} aun accesible tras rollback: HTTP {rg.status_code} "
                f"[X-Request-Id={rg.headers.get('X-Request-Id', '')}]"
            )
            ra = c.get(f"/suministros/costeo-directo/acumulado/activo/{aid}", paso=f"t99_get_acum_{aid}")
            verif_acumulados.append({"id": aid, "status_code": ra.status_code, "error_code": _error_code(ra)})
            assert ra.status_code == 404, (
                f"T99 acumulado de activo {aid} aun accesible tras rollback: HTTP {ra.status_code} "
                f"[X-Request-Id={ra.headers.get('X-Request-Id', '')}]"
            )

        assert total_post == _CONTEXTO["total_base"], (
            f"T99 total post-rollback ({total_post}) != total_base T00 ({_CONTEXTO['total_base']}) "
            "[RF-80 v2.0 RNF-02; Inocuidad]"
        )
        assert ultimo_post == _CONTEXTO["ultimo_id_base"], (
            f"T99 ultimo_id post-rollback ({ultimo_post}) != ultimo_id_base T00 ({_CONTEXTO['ultimo_id_base']}) "
            "[RF-80 v2.0 RNF-02; Inocuidad]"
        )
    finally:
        r_close = c.cerrar()
        detalle_t99.update({
            "total_post": total_post,
            "ultimo_id_post": ultimo_post,
            "activos_verificados": verif_activos,
            "acumulados_verificados": verif_acumulados,
            "delete_status_code": r_close.status_code if r_close else None,
            "obtenido_texto": (
                f"GET /suministros/auditoria -> HTTP 200 (total={total_post}, ultimo_id={ultimo_post}); "
                f"activos 404 {activos}; acumulados 404 {activos}; "
                f"DELETE /test-control/runs/{c.run_id} -> HTTP {r_close.status_code if r_close else None}"
            ),
        })
        assert r_close is not None and r_close.status_code == 200, (
            f"T99 cierre sandbox inesperado: {r_close.status_code if r_close else None}"
        )
        assert "rollback exitoso" in r_close.text.lower(), (
            f"T99 confirmacion rollback inesperada: {c.seguro(r_close.text)}"
        )
