# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G39: Campos minimos, inmutabilidad y hash RF-80 (CU06)        |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G39 reevaluacion v2.0: incompletos con causa, campos base, inmutabilidad (INC-278), hash v1/v2, C01 retirado |
"""Suite de pruebas para TC-M05-G39 (RF-80 v2.0, RFC-025): Integridad, campos minimos e inmutabilidad.

Cubre los casos activos de RF-80 v2.0 para el grupo G39:
- TC-M05-092 (antes TC-M05-019): Eventos incompletos nuevos con detalle_causa (CA-12, R8, E2; criterio
  INC-M05-278-G39 defecto 1) y presencia obligatoria de campos base tipo_operacion, resultado y
  fecha_emision en todos los eventos nuevos (CA-11, R8).
- TC-M05-093 (antes TC-M05-042): Inmutabilidad por API (PUT/PATCH/DELETE/POST -> 405 Allow: GET +
  exactamente 1 evento RECHAZADO por intento autenticado; Restriccion 1, CA-2, RNF-05; INC-278
  defecto 2), intentos de otros actores (Productor, ID inexistente, sin token 401), recalculo
  determinista de hash_integridad (C25.3, ADR-M05-02) para eventos nuevos v2 e historicos v1, y
  ausencia de endpoints de escritura en OpenAPI (nota ZAP).
  Nota sobre simulacion de alteracion en B03: "simulacion local; la alteracion real en BD no es
  ejecutable en TEST: requiere DML y el trigger lo bloquea".
- TC-M05-094 retirado por RFC-025 (RF-80 v2.0): sin cola no hay reentregas.
- T00 (linea base) y T99 (inocuidad post-rollback) en corridas sandbox independientes de solo lectura
  por API autenticada (sin /test-control/query sobre modulo5 ni modulo1 por FORCE RLS).
"""
from __future__ import annotations

import base64
import hashlib
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
ARCHIVO_OBSERVACIONES = "observaciones_g39.json"
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
    "ultimo_id_inicio_corrida": None,
    "activos_creados": [],
    "id_objetivo_b01": None,
    "objetivo_b01": None,
    "eventos_a01": [],
    "obs_b01_rechazos": [],
    "obs_b02_sin_token": {},
    "obs_historicos_87_88_89": [],
    "obs_simulacion_b03": "simulacion local; la alteracion real en BD no es ejecutable en TEST: requiere DML y el trigger lo bloquea",
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
    allow_header = ""

    if resp is not None:
        status_code = resp.status_code
        server_date = resp.headers.get("Date", "")
        x_request_id = resp.headers.get("X-Request-Id", "") or resp.headers.get("x-request-id", "")
        allow_header = resp.headers.get("Allow", "") or resp.headers.get("allow", "")
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
    if allow_header:
        registro["allow_header"] = allow_header
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
        self.run_id = f"tc-m05-g39-{etiqueta}-{uuid.uuid4().hex[:8]}"
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.secret = _env("TEST_SANDBOX_SECRET")
        self.cerrada = False
        self.tokens_por_cuenta: dict[str, str] = {}
        self.usuarios_por_cuenta: dict[str, int] = {}
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

    def login_actor(self, rol_key: str, email_env: str, pass_env: str) -> int:
        assert rol_key not in self.tokens_por_cuenta, (
            f"Regla login unico por cuenta/run_id violada para {rol_key} en run_id={self.run_id}"
        )
        email = _env(email_env, obligatoria=True)
        pwd = _env(pass_env, obligatoria=True)
        s = self._session_for(rol_key)
        r = self.request(
            rol_key,
            "POST",
            "/sesiones/",
            json_body={"correo_electronico": email, "contrasena": pwd},
            paso=f"login_{rol_key}",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {rol_key} HTTP {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {self.seguro(r.text)}"
        )
        j = r.json()
        token = j.get("token") or j.get("access_token") or j.get("token_acceso")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {rol_key} sin token"
        uid = (j.get("usuario") or {}).get("id_usuario") or j.get("id_usuario") or _sub_jwt(token)
        assert uid is not None, f"PRECONDICION_NO_CUMPLIDA: login {rol_key} sin id_usuario"
        self.tokens_por_cuenta[rol_key] = token
        self.usuarios_por_cuenta[rol_key] = int(uid)
        s.headers["Authorization"] = f"Bearer {token}"
        return int(uid)

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


def _leer_estado_auditoria_api(c: CorridaSandbox, paso: str) -> tuple[int, int]:
    """Consulta total y mayor id_auditoria_suministro via GET /suministros/auditoria."""
    r = c.get(
        "admin",
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
    assert isinstance(total, int), f"{paso}: se esperaba total entero, obtenido {total!r}"
    items = j.get("items") or []
    ultimo_id = max((int(it["id_auditoria_suministro"]) for it in items), default=0)
    return total, ultimo_id


def _esperar_eventos_nuevos(
    c: CorridaSandbox,
    ultimo_id_previo: int,
    t0_operacion: float,
    paso: str,
    min_eventos: int = 1,
) -> tuple[list[dict[str, Any]], float]:
    nuevos: list[dict[str, Any]] = []
    latencia = 0.0
    for intento, espera in enumerate((0.0, 0.25, 0.5, 1.0), start=1):
        if espera:
            time.sleep(espera)
        r = c.get(
            "admin",
            "/suministros/auditoria",
            paso=f"{paso}_poll_{intento}",
            params={"pagina": 1, "registros_por_pagina": 50, "ordenar_por": "fecha_evento"},
        )
        assert r.status_code == 200, (
            f"{paso}: error consultando auditoria HTTP {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
        )
        items = r.json().get("items") or []
        nuevos = [it for it in items if int(it["id_auditoria_suministro"]) > ultimo_id_previo]
        nuevos.sort(key=lambda x: int(x["id_auditoria_suministro"]))
        latencia = time.perf_counter() - t0_operacion
        if len(nuevos) >= min_eventos:
            break
    return nuevos, latencia


def _recolectar_eventos_corrida(c: CorridaSandbox, ultimo_id_base: int, paso: str) -> list[dict[str, Any]]:
    por_id: dict[int, dict[str, Any]] = {}
    pagina = 1
    while True:
        r = c.get(
            "admin",
            "/suministros/auditoria",
            paso=f"{paso}_pag_{pagina}",
            params={"pagina": pagina, "registros_por_pagina": 100, "ordenar_por": "fecha_evento"},
        )
        assert r.status_code == 200, (
            f"{paso}: error listando eventos HTTP {r.status_code} "
            f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
        )
        items = r.json().get("items") or []
        if not items:
            break
        encontro_nuevo_en_pag = False
        for it in items:
            eid = int(it["id_auditoria_suministro"])
            if eid > ultimo_id_base:
                por_id[eid] = it
                encontro_nuevo_en_pag = True
        if not encontro_nuevo_en_pag or len(items) < 100 or pagina >= 5:
            break
        pagina += 1
    return [por_id[k] for k in sorted(por_id.keys())]


def _crear_activo_poblacional(c: CorridaSandbox, paso: str) -> int:
    tag = uuid.uuid4().hex[:8]
    hoy = _hoy()
    fecha_ciclo = (hoy - timedelta(days=15)).isoformat()
    payload = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": 1,
        "id_infraestructura": 2,
        "identificador_unico": f"QA-G39-{tag}",
        "cantidad_inicial": 60,
        "fecha_ingreso": fecha_ciclo,
        "fecha_inicio_ciclo": fecha_ciclo,
        "origen_financiero": "nacimiento",
        "peso_actual": 22.0,
    }
    r = c.post("admin", "/activos-biologicos", payload, paso=paso)
    assert r.status_code == 201, (
        f"Fallo al crear activo QA ({paso}): HTTP {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    id_activo = int(r.json()["id_activo_biologico"])
    assert id_activo not in _IDS_PROHIBIDOS, f"Activo prohibido generado: {id_activo}"
    _CONTEXTO["activos_creados"].append(id_activo)
    return id_activo


def _payload_suministro_servicio(id_activo: int, cantidad: float = 1.0, precio: float = 40000.0) -> dict[str, Any]:
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


def _pg_quote_ident(ident: str) -> str:
    if re.fullmatch(r"[a-z_][a-z0-9_]*", ident):
        return ident
    return '"' + ident.replace('"', '""') + '"'


def _pg_quote_literal(val: str | None) -> str:
    if val is None:
        return "NULL"
    esc = val.replace("'", "''")
    if "\\" in esc:
        return "E'" + esc.replace("\\", "\\\\") + "'"
    return "'" + esc + "'"


def _pg_ts_to_jsonb_text(ts: str | None) -> str | None:
    if ts is None:
        return None
    if ts.endswith("Z"):
        cuerpo = ts[:-1]
        base, sep, frac = cuerpo.partition(".")
        if sep:
            frac = frac.rstrip("0")
            cuerpo = f"{base}.{frac}" if frac else base
        return cuerpo + "+00:00"
    return ts


def _sort_pg_jsonb(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sort_pg_jsonb(obj[k]) for k in sorted(obj.keys(), key=lambda s: (len(s), s))}
    if isinstance(obj, list):
        return [_sort_pg_jsonb(x) for x in obj]
    return obj


def _recalcular_hash_m05(evento: dict[str, Any], version: int) -> str:
    """Replica modulo5.fn_hash_evento_auditoria_m05(to_jsonb(a), version) desde GET /{id}."""
    excl = (
        {"hash_integridad", "creado_en", "id_registro_suministro", "id_evento_m05", "version_hash_integridad"}
        if version == 1
        else {"hash_integridad"}
    )
    partes: list[str] = []
    for k in sorted(evento.keys()):
        if k in excl:
            continue
        v = evento[k]
        if v is None:
            v_str = None
        elif isinstance(v, bool):
            v_str = "true" if v else "false"
        elif k in ("fecha_evento", "fecha_emision"):
            v_str = _pg_ts_to_jsonb_text(str(v))
        elif k == "fecha_intentos":
            v_str = json.dumps([_pg_ts_to_jsonb_text(str(x)) for x in v], ensure_ascii=False, separators=(", ", ": "))
        elif isinstance(v, (dict, list)):
            v_str = json.dumps(_sort_pg_jsonb(v), ensure_ascii=False, separators=(", ", ": "))
        else:
            v_str = str(v)
        partes.append(f"{_pg_quote_ident(k)}={_pg_quote_literal(v_str)}")
    canonico = " & ".join(partes)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _guardar_observaciones(c: CorridaSandbox) -> None:
    directorio = os.environ.get("TEST_EVIDENCE_DIR")
    if not directorio:
        return
    base_id = _CONTEXTO.get("ultimo_id_inicio_corrida") or _CONTEXTO.get("ultimo_id_base") or 0
    eventos = _recolectar_eventos_corrida(c, base_id, "obs_recolectar")
    uuids_detalle: list[dict[str, Any]] = []
    uuids_vistos: set[str] = set()
    duplicados: list[str] = []
    invalidos: list[Any] = []
    for ev in eventos:
        uid_str = ev.get("id_evento_m05")
        es_uuid_valido = False
        if uid_str is not None:
            try:
                uuid.UUID(str(uid_str))
                es_uuid_valido = True
            except Exception:
                es_uuid_valido = False
        if not es_uuid_valido:
            invalidos.append(ev.get("id_auditoria_suministro"))
        else:
            norm = str(uid_str)
            if norm in uuids_vistos:
                duplicados.append(norm)
            uuids_vistos.add(norm)
        uuids_detalle.append(
            {
                "id_auditoria_suministro": ev.get("id_auditoria_suministro"),
                "tipo_operacion": ev.get("tipo_operacion"),
                "entidad_afectada": ev.get("entidad_afectada"),
                "resultado": ev.get("resultado"),
                "id_evento_m05": uid_str,
                "uuid_valido": es_uuid_valido,
                "version_hash_integridad": ev.get("version_hash_integridad"),
            }
        )

    historicos: list[dict[str, Any]] = []
    for hid in (87, 88, 89):
        rg = c.get("admin", f"/suministros/auditoria/{hid}", paso=f"obs_hist_{hid}")
        if rg.status_code == 200:
            hd = rg.json()
            historicos.append(
                {
                    "id_auditoria_suministro": hid,
                    "tipo_operacion": hd.get("tipo_operacion"),
                    "registro_incompleto": hd.get("registro_incompleto"),
                    "detalle_causa": hd.get("detalle_causa"),
                    "version_hash_integridad": hd.get("version_hash_integridad"),
                }
            )
        else:
            historicos.append({"id_auditoria_suministro": hid, "http_status": rg.status_code})

    payload_obs = {
        "total_eventos_corrida": len(eventos),
        "todos_uuids_presentes_y_validos": len(invalidos) == 0 and len(eventos) > 0,
        "todos_uuids_unicos": len(duplicados) == 0,
        "uuids_invalidos": invalidos,
        "uuids_duplicados": duplicados,
        "eventos_corrida": uuids_detalle,
        "historicos_87_88_89": historicos,
        "b01_rechazos_tipo_y_clasificacion": _CONTEXTO.get("obs_b01_rechazos", []),
        "b02_sin_token_401": _CONTEXTO.get("obs_b02_sin_token", {}),
        "b03_etiqueta_simulacion": _CONTEXTO["obs_simulacion_b03"],
    }
    destino = Path(directorio) / ARCHIVO_OBSERVACIONES
    destino.write_text(json.dumps(payload_obs, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# T00 - Linea base (corrida sandbox independiente de solo lectura)
# =============================================================================

def test_t00_linea_base():
    """T00 (Testing Harness / Inocuidad): linea base via API autenticada en sandbox propio."""
    c = CorridaSandbox("inobase")
    try:
        c.login_actor("admin", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        total, ultimo_id = _leer_estado_auditoria_api(c, "t00_get_auditoria_base")
        _CONTEXTO["total_base"] = total
        _CONTEXTO["ultimo_id_base"] = ultimo_id
    finally:
        r_close = c.cerrar()
        assert r_close is not None and r_close.status_code == 200, (
            f"T00 cierre sandbox inesperado: {r_close.status_code if r_close else None}"
        )


# =============================================================================
# A01 / A02 - TC-M05-092: Incompletos con causa y campos base obligatorios
# =============================================================================

def test_a01_incompletos_con_causa():
    """A01 (TC-M05-092; RF-80 v2.0 CA-12, R8, E2; criterio INC-M05-278-G39 defecto 1)."""
    c = _principal()
    _, ultimo_inicio = _leer_estado_auditoria_api(c, "a01_snap_inicio")
    _CONTEXTO["ultimo_id_inicio_corrida"] = ultimo_inicio

    # (a) Activo POBLACIONAL sin fase -> POST /suministros/costeo-directo (unidad 'servicio') -> 409 + REGISTRO_FALLIDO
    id_activo_a = _crear_activo_poblacional(c, "a01a_crear_activo_sin_fase")
    _, prev_a = _leer_estado_auditoria_api(c, "a01a_snap_previo")
    t0_a = time.perf_counter()
    r_fail = c.post(
        "admin",
        "/suministros/costeo-directo",
        _payload_suministro_servicio(id_activo_a),
        paso="a01a_costeo_sin_fase_409",
    )
    assert r_fail.status_code == 409, (
        f"A01(a) esperado HTTP 409 sin fase abierta; obtenido {r_fail.status_code} "
        f"[X-Request-Id={r_fail.headers.get('X-Request-Id', '')}]: {c.seguro(r_fail.text)} [RF-78 / A01(a)]"
    )
    nuevos_a, lat_a = _esperar_eventos_nuevos(c, prev_a, t0_a, "a01a", min_eventos=1)
    assert lat_a <= 2.0, f"A01(a) evento REGISTRO_FALLIDO tardo {lat_a:.3f} s (> 2.0 s) [RF-80 v2.0 CA-1]"
    fallidos_a = [e for e in nuevos_a if e.get("tipo_operacion") == "REGISTRO_FALLIDO"]
    assert fallidos_a, (
        f"A01(a) falta evento REGISTRO_FALLIDO tras 409; obtenidos {[e.get('tipo_operacion') for e in nuevos_a]} "
        "[TC-M05-092; CA-12, E2]"
    )

    # (b) Otro activo POBLACIONAL con fase abierta + RF-78 valido + cierre de ciclo RF-79
    id_activo_b = _crear_activo_poblacional(c, "a01b_crear_activo_cierre")
    r_fase = c.post(
        "admin",
        f"/activos-biologicos/{id_activo_b}/fases",
        {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase productiva QA G39"},
        paso="a01b_abrir_fase",
    )
    assert r_fase.status_code in (200, 201), (
        f"A01(b) fallo apertura de fase HTTP {r_fase.status_code} "
        f"[X-Request-Id={r_fase.headers.get('X-Request-Id', '')}]: {c.seguro(r_fase.text)}"
    )
    r_sum = c.post(
        "admin",
        "/suministros/costeo-directo",
        _payload_suministro_servicio(id_activo_b),
        paso="a01b_rf78_valido",
    )
    assert r_sum.status_code == 200, (
        f"A01(b) fallo registro RF-78 valido HTTP {r_sum.status_code} "
        f"[X-Request-Id={r_sum.headers.get('X-Request-Id', '')}]: {c.seguro(r_sum.text)}"
    )
    _, prev_cierre = _leer_estado_auditoria_api(c, "a01b_snap_pre_cierre")
    t0_cierre = time.perf_counter()
    r_cierre = c.post(
        "admin",
        f"/activos-biologicos/{id_activo_b}/cierre",
        {
            "fecha_cierre": _hoy().isoformat(),
            "motivo_cierre": "finalizacion_lote",
            "descripcion_cierre": "Cierre QA G37 para observacion consolidacion NIC41",
        },
        paso="a01b_rf79_cierre",
    )
    assert r_cierre.status_code == 200, (
        f"A01(b) fallo cierre ciclo RF-79 HTTP {r_cierre.status_code} "
        f"[X-Request-Id={r_cierre.headers.get('X-Request-Id', '')}]: {c.seguro(r_cierre.text)}"
    )
    _esperar_eventos_nuevos(c, prev_cierre, t0_cierre, "a01b_cierre", min_eventos=2)

    eventos_corrida = _recolectar_eventos_corrida(c, ultimo_inicio, "a01_recolectar")
    assert eventos_corrida, "No se recolectaron eventos nuevos en A01 [TC-M05-092]"
    _CONTEXTO["eventos_a01"] = eventos_corrida
    objetivo = next(
        (e for e in eventos_corrida if e.get("tipo_operacion") == "SUMINISTRO_REGISTRADO"),
        eventos_corrida[0],
    )
    _CONTEXTO["id_objetivo_b01"] = int(objetivo["id_auditoria_suministro"])

    # Verificar todos los eventos nuevos con registro_incompleto = true tienen detalle_causa no nulo y no vacio
    for ev in eventos_corrida:
        if ev.get("registro_incompleto") is True:
            causa = ev.get("detalle_causa")
            assert isinstance(causa, str) and bool(causa.strip()), (
                f"Evento {ev.get('id_auditoria_suministro')} ({ev.get('tipo_operacion')}) "
                f"con registro_incompleto=true tiene detalle_causa nulo o vacio: {causa!r} "
                "[TC-M05-092; RF-80 v2.0 CA-12, R8, E2; INC-M05-278-G39 defecto 1]"
            )

    # Consolidacion (CICLO_CONSOLIDADO, REPORTE_COSTOS_GENERADO) no debe marcarse incompleta por conciliacion pendiente
    por_tipo = {ev.get("tipo_operacion"): ev for ev in eventos_corrida}
    for tipo_cons in ("CICLO_CONSOLIDADO", "REPORTE_COSTOS_GENERADO"):
        assert tipo_cons in por_tipo, (
            f"Falta evento de consolidacion {tipo_cons} tras cierre RF-79 [RF-80 v2.0 CA-1]"
        )
        ev_cons = por_tipo[tipo_cons]
        if ev_cons.get("registro_incompleto") is True:
            causa_low = (ev_cons.get("detalle_causa") or "").lower()
            assert "conciliacion pendiente" not in causa_low and "conciliación pendiente" not in causa_low, (
                f"{tipo_cons} id={ev_cons.get('id_auditoria_suministro')} marcado incompleto por "
                f"conciliacion pendiente: {ev_cons.get('detalle_causa')!r} [INC-M05-278-G39 defecto 1]"
            )
            assert any(tok in causa_low for tok in ("campos faltantes", "activo", "ciclo", "costo")), (
                f"{tipo_cons} id={ev_cons.get('id_auditoria_suministro')} marcado incompleto sin nombrar "
                f"campos faltantes reales: {ev_cons.get('detalle_causa')!r} [TC-M05-092; INC-M05-278-G39 defecto 1]"
            )


def test_a02_campos_base_presentes():
    """A02 (TC-M05-092; RF-80 v2.0 CA-11, R8): tipo_operacion, resultado y fecha_emision no nulos en TODO evento nuevo."""
    c = _principal()
    ultimo_inicio = _CONTEXTO.get("ultimo_id_inicio_corrida")
    assert ultimo_inicio is not None, "Precondicion A02: A01 no establecio ultimo_id_inicio_corrida"

    eventos = _recolectar_eventos_corrida(c, int(ultimo_inicio), "a02_recolectar")
    assert eventos, "A02: no se encontraron eventos nuevos en la corrida [TC-M05-092]"

    invalidos: list[str] = []
    for ev in eventos:
        faltantes = [
            campo
            for campo in ("tipo_operacion", "resultado", "fecha_emision")
            if ev.get(campo) is None or (isinstance(ev.get(campo), str) and not ev[campo].strip())
        ]
        if faltantes:
            invalidos.append(
                f"id={ev.get('id_auditoria_suministro')} "
                f"(entidad={ev.get('entidad_afectada')}, tipo_operacion={ev.get('tipo_operacion')}, "
                f"faltantes={faltantes})"
            )

    assert not invalidos, (
        "CA-11/R8 incumplido — eventos nuevos persistidos con campos base nulos o vacios: "
        + "; ".join(invalidos)
        + " [TC-M05-092; RF-80 v2.0 CA-11, R8]"
    )


# =============================================================================
# B01 / B02 / B03 / B04 - TC-M05-093: Inmutabilidad API, actores, hash y OpenAPI
# =============================================================================

def test_b01_inmutabilidad_api():
    """B01 (TC-M05-093; Restriccion 1, CA-2, RNF-05; INC-M05-278-G39 defecto 2)."""
    c = _principal()
    id_obj = _CONTEXTO.get("id_objetivo_b01")
    assert id_obj is not None, "Precondicion B01: falta id_objetivo_b01 de A01"
    id_admin = c.usuarios_por_cuenta["admin"]

    r_antes = c.get("admin", f"/suministros/auditoria/{id_obj}", paso="b01_get_antes")
    assert r_antes.status_code == 200, (
        f"B01 error leyendo evento objetivo {id_obj}: HTTP {r_antes.status_code} "
        f"[X-Request-Id={r_antes.headers.get('X-Request-Id', '')}]"
    )
    antes = r_antes.json()
    _CONTEXTO["objetivo_b01"] = antes

    rechazos_obs: list[dict[str, Any]] = []
    for metodo in ("PUT", "PATCH", "DELETE", "POST"):
        _, ultimo_previo = _leer_estado_auditoria_api(c, f"b01_snap_{metodo.lower()}")
        marcador = f"QA_G39_{metodo}_{uuid.uuid4().hex[:8]}"
        cuerpo = {"marcador_prueba": marcador, "resultado": "ALTERADO_QA"}
        t0 = time.perf_counter()
        resp = c.request(
            "admin",
            metodo,
            f"/suministros/auditoria/{id_obj}",
            json_body=cuerpo,
            paso=f"b01_{metodo.lower()}",
        )
        assert resp.status_code == 405, (
            f"B01 {metodo} esperaba HTTP 405 Method Not Allowed; obtenido {resp.status_code} "
            f"[X-Request-Id={resp.headers.get('X-Request-Id', '')}]: {c.seguro(resp.text)} "
            "[TC-M05-093; Restriccion 1, CA-2]"
        )
        allow_hdr = (resp.headers.get("Allow") or "").strip().upper()
        assert allow_hdr == "GET", (
            f"B01 {metodo}: cabecera Allow esperada 'GET', obtenida {resp.headers.get('Allow')!r} "
            "[TC-M05-093; CA-2]"
        )

        nuevos, lat_s = _esperar_eventos_nuevos(c, ultimo_previo, t0, f"b01_{metodo.lower()}", min_eventos=1)
        assert lat_s <= 2.0, (
            f"B01 {metodo}: evento RECHAZADO tardo {lat_s:.3f} s (> 2.0 s) [TC-M05-093; CA-2]"
        )
        assert len(nuevos) == 1, (
            f"B01 {metodo}: esperado exactamente 1 evento nuevo, obtenidos {len(nuevos)} "
            "[TC-M05-093; INC-M05-278-G39 defecto 2]"
        )
        id_nuevo = int(nuevos[0]["id_auditoria_suministro"])
        r_ev = c.get("admin", f"/suministros/auditoria/{id_nuevo}", paso=f"b01_get_ev_{metodo.lower()}")
        assert r_ev.status_code == 200, f"B01 {metodo}: error leyendo evento nuevo {id_nuevo}"
        ev_det = r_ev.json()

        assert ev_det.get("resultado") == "RECHAZADO", (
            f"B01 {metodo}: esperado resultado=RECHAZADO, obtenido {ev_det.get('resultado')!r} "
            "[TC-M05-093; CA-2]"
        )
        assert ev_det.get("id_usuario") == id_admin, (
            f"B01 {metodo}: esperado id_usuario={id_admin}, obtenido {ev_det.get('id_usuario')!r} [R8]"
        )
        ev_serial = json.dumps(ev_det, ensure_ascii=False)
        assert marcador not in ev_serial and "ALTERADO_QA" not in ev_serial, (
            f"B01 {metodo}: el evento RECHAZADO {id_nuevo} filtro el cuerpo enviado [RNF-05]"
        )

        r_desp = c.get("admin", f"/suministros/auditoria/{id_obj}", paso=f"b01_get_desp_{metodo.lower()}")
        assert r_desp.status_code == 200
        assert r_desp.json() == antes, (
            f"B01 {metodo}: el evento objetivo {id_obj} o su hash_integridad cambio tras el intento "
            "[TC-M05-093; Restriccion 1, CA-2]"
        )

        rechazos_obs.append(
            {
                "metodo": metodo,
                "id_auditoria_suministro": id_nuevo,
                "tipo_operacion": ev_det.get("tipo_operacion"),
                "clasificacion_registro": ev_det.get("clasificacion_registro"),
                "retencion_aplicable": ev_det.get("retencion_aplicable"),
                "resultado": ev_det.get("resultado"),
                "id_evento_m05": ev_det.get("id_evento_m05"),
                "version_hash_integridad": ev_det.get("version_hash_integridad"),
            }
        )
    _CONTEXTO["obs_b01_rechazos"] = rechazos_obs


def test_b02_intentos_otros_actores():
    """B02 (TC-M05-093; RF-80 v2.0 CA-2, RNF-05): Productor 405+RECHAZADO sin fuga, ID 999999999 405+RECHAZADO, sin token 401."""
    c = _principal()
    id_obj = _CONTEXTO.get("id_objetivo_b01")
    obj = _CONTEXTO.get("objetivo_b01")
    assert id_obj is not None and obj is not None, "Precondicion B02: falta objetivo B01"
    id_admin = c.usuarios_por_cuenta["admin"]

    # 1. Productor (unico login de Productor en el run_id principal)
    id_prod = c.login_actor("productor", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD")
    _, prev_prod = _leer_estado_auditoria_api(c, "b02_snap_pre_prod")
    t0_prod = time.perf_counter()
    r_prod = c.request(
        "productor",
        "PUT",
        f"/suministros/auditoria/{id_obj}",
        json_body={"marcador_prueba": "QA_G39_PRODUCTOR_PUT"},
        paso="b02_productor_put",
    )
    assert r_prod.status_code == 405, (
        f"B02 Productor PUT esperaba HTTP 405; obtenido {r_prod.status_code} "
        f"[X-Request-Id={r_prod.headers.get('X-Request-Id', '')}]: {c.seguro(r_prod.text)} "
        "[TC-M05-093; CA-2, RNF-05]"
    )
    assert (r_prod.headers.get("Allow") or "").strip().upper() == "GET", (
        f"B02 Productor PUT cabecera Allow esperada 'GET', obtenida {r_prod.headers.get('Allow')!r}"
    )
    for clave_sens in ("hash_integridad", "id_evento_m05", "entidad_afectada", "detalle_causa"):
        val_sens = obj.get(clave_sens)
        if val_sens:
            assert str(val_sens) not in r_prod.text, (
                f"B02 Productor PUT filtro dato del objetivo ({clave_sens}) en la respuesta [RNF-05]"
            )
    nuevos_prod, lat_prod = _esperar_eventos_nuevos(c, prev_prod, t0_prod, "b02_prod", min_eventos=1)
    assert lat_prod <= 2.0, f"B02 Productor evento RECHAZADO tardo {lat_prod:.3f} s (> 2.0 s) [CA-2]"
    assert len(nuevos_prod) == 1, (
        f"B02 Productor esperaba 1 evento RECHAZADO, obtenidos {len(nuevos_prod)} [TC-M05-093]"
    )
    assert nuevos_prod[0].get("resultado") == "RECHAZADO", "B02 Productor esperaba resultado=RECHAZADO [CA-2]"
    assert nuevos_prod[0].get("id_usuario") == id_prod, (
        f"B02 Productor esperaba id_usuario={id_prod}, obtenido {nuevos_prod[0].get('id_usuario')!r} [R8]"
    )

    # 2. Admin PUT sobre ID inexistente (999999999)
    _, prev_inex = _leer_estado_auditoria_api(c, "b02_snap_pre_inex")
    t0_inex = time.perf_counter()
    r_inex = c.request(
        "admin",
        "PUT",
        "/suministros/auditoria/999999999",
        json_body={"marcador_prueba": "QA_G39_INEXISTENTE"},
        paso="b02_admin_put_999999999",
    )
    assert r_inex.status_code == 405, (
        f"B02 ID inexistente PUT esperaba HTTP 405; obtenido {r_inex.status_code} "
        f"[X-Request-Id={r_inex.headers.get('X-Request-Id', '')}] [TC-M05-093; #964]"
    )
    nuevos_inex, lat_inex = _esperar_eventos_nuevos(c, prev_inex, t0_inex, "b02_inex", min_eventos=1)
    assert lat_inex <= 2.0, f"B02 ID inexistente evento RECHAZADO tardo {lat_inex:.3f} s (> 2.0 s)"
    assert len(nuevos_inex) == 1, (
        f"B02 ID inexistente esperaba 1 evento RECHAZADO, obtenidos {len(nuevos_inex)} [TC-M05-093]"
    )
    assert nuevos_inex[0].get("resultado") == "RECHAZADO", "B02 ID inexistente esperaba resultado=RECHAZADO [CA-2]"
    assert nuevos_inex[0].get("id_usuario") == id_admin, "B02 ID inexistente esperaba id_usuario=Admin [R8]"

    # 3. Sin token (dentro del sandbox con session 'anon' sin Authorization) -> 401; solo observacion sobre eventos
    _, prev_anon = _leer_estado_auditoria_api(c, "b02_snap_pre_anon")
    t0_anon = time.perf_counter()
    r_anon = c.request(
        "anon",
        "PUT",
        f"/suministros/auditoria/{id_obj}",
        json_body={"marcador_prueba": "QA_G39_SIN_TOKEN"},
        paso="b02_sin_token_put",
    )
    assert r_anon.status_code == 401, (
        f"B02 sin token PUT esperaba HTTP 401; obtenido {r_anon.status_code} "
        f"[X-Request-Id={r_anon.headers.get('X-Request-Id', '')}] [TC-M05-093; RNF-05]"
    )
    nuevos_anon, _ = _esperar_eventos_nuevos(c, prev_anon, t0_anon, "b02_anon_obs", min_eventos=1)
    _CONTEXTO["obs_b02_sin_token"] = {
        "http_status": r_anon.status_code,
        "x_request_id": r_anon.headers.get("X-Request-Id", ""),
        "eventos_nuevos_observados": len(nuevos_anon),
        "ids_eventos_observados": [e.get("id_auditoria_suministro") for e in nuevos_anon],
    }


def test_b03_recalculo_hash():
    """B03 (TC-M05-093; RF-80 v2.0 C25.3, ADR-M05-02): hash v2 nuevos + 3 historicos v1 + simulacion local alterada."""
    c = _principal()
    ultimo_inicio = _CONTEXTO.get("ultimo_id_inicio_corrida")
    assert ultimo_inicio is not None, "Precondicion B03: falta ultimo_id_inicio_corrida"

    eventos_nuevos = _recolectar_eventos_corrida(c, int(ultimo_inicio), "b03_recolectar")
    nuevos_v2 = [e for e in eventos_nuevos if e.get("version_hash_integridad") == 2]
    assert nuevos_v2, "B03: no hay eventos nuevos de version_hash_integridad=2 para verificar [TC-M05-093]"

    detalles_v2: list[dict[str, Any]] = []
    for ev in nuevos_v2:
        eid = int(ev["id_auditoria_suministro"])
        rg = c.get("admin", f"/suministros/auditoria/{eid}", paso=f"b03_get_v2_{eid}")
        assert rg.status_code == 200, f"B03 error consultando GET /{eid}: HTTP {rg.status_code}"
        det = rg.json()
        recalc = _recalcular_hash_m05(det, version=2)
        assert recalc == det.get("hash_integridad"), (
            f"B03 discrepancia hash v2 en id={eid}: recalculado={recalc}, almacenado={det.get('hash_integridad')} "
            "[TC-M05-093; C25.3, ADR-M05-02]"
        )
        detalles_v2.append(det)

    detalles_v1: list[dict[str, Any]] = []
    for hid in (87, 88, 89):
        rg = c.get("admin", f"/suministros/auditoria/{hid}", paso=f"b03_get_v1_{hid}")
        assert rg.status_code == 200, f"B03 error consultando historico GET /{hid}: HTTP {rg.status_code}"
        det = rg.json()
        assert det.get("version_hash_integridad") == 1, (
            f"B03 evento historico {hid} esperaba version_hash_integridad=1, obtuvo {det.get('version_hash_integridad')!r}"
        )
        recalc = _recalcular_hash_m05(det, version=1)
        assert recalc == det.get("hash_integridad"), (
            f"B03 discrepancia hash v1 en historico id={hid}: recalculado={recalc}, almacenado={det.get('hash_integridad')} "
            "[TC-M05-093; C25.3, ADR-M05-02]"
        )
        detalles_v1.append(det)

    # Simulacion local con un valor alterado en memoria (sin DML real porque el trigger en BD lo bloquea)
    muestra_v2 = dict(detalles_v2[0])
    muestra_v2["resultado"] = "ALTERADO_SIM_LOCAL"
    hash_sim_v2 = _recalcular_hash_m05(muestra_v2, version=2)
    assert hash_sim_v2 != detalles_v2[0]["hash_integridad"], (
        "B03 simulacion local v2 deberia diferir tras alterar un campo [C25.3; ADR-M05-02]"
    )

    muestra_v1 = dict(detalles_v1[0])
    muestra_v1["resultado"] = "ALTERADO_SIM_LOCAL"
    hash_sim_v1 = _recalcular_hash_m05(muestra_v1, version=1)
    assert hash_sim_v1 != detalles_v1[0]["hash_integridad"], (
        "B03 simulacion local v1 deberia diferir tras alterar un campo [C25.3; ADR-M05-02]"
    )


def test_b04_sin_endpoints_escritura():
    """B04 (TC-M05-093, nota ZAP; RF-80 v2.0 CA-2): GET /openapi.json no expone POST/PUT/PATCH/DELETE en /suministros/auditoria*."""
    c = _principal()
    r = c.get("admin", "/openapi.json", paso="b04_openapi")
    assert r.status_code == 200, (
        f"B04 error consultando /openapi.json: HTTP {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]"
    )
    paths = r.json().get("paths") or {}
    rutas_aud = {k: v for k, v in paths.items() if k.startswith("/suministros/auditoria")}
    assert rutas_aud, "B04: no se encontraron rutas /suministros/auditoria* en /openapi.json"
    escritura_encontrada: list[str] = []
    for ruta, ops in sorted(rutas_aud.items()):
        for metodo in ops:
            if metodo.lower() in ("post", "put", "patch", "delete"):
                escritura_encontrada.append(f"{metodo.upper()} {ruta}")
    assert not escritura_encontrada, (
        f"B04: OpenAPI declara metodos de escritura en /suministros/auditoria*: {escritura_encontrada} "
        "[TC-M05-093, nota ZAP; RF-80 v2.0 CA-2]"
    )


# =============================================================================
# T98 / T99 - Cierre de corrida principal e inocuidad post-rollback
# =============================================================================

def test_t98_cierre_corrida_principal():
    """T98: Registro pasivo de observaciones sin aserciones y cierre con DELETE -> 200 Rollback exitoso."""
    c = _principal()
    _guardar_observaciones(c)
    r = c.cerrar()
    assert r is not None, "T98: el sandbox principal ya habia sido cerrado"
    assert r.status_code == 200, (
        f"T98 cierre sandbox principal HTTP {r.status_code} "
        f"[X-Request-Id={r.headers.get('X-Request-Id', '')}]: {c.seguro(r.text)}"
    )
    assert "rollback exitoso" in r.text.lower(), f"T98 respuesta inesperada al cerrar sandbox: {c.seguro(r.text)}"


def test_t99_inocuidad():
    """T99 (Testing Harness / Inocuidad): total y ultimo_id iguales a T00; activos creados -> 404."""
    assert _CONTEXTO["total_base"] is not None and _CONTEXTO["ultimo_id_base"] is not None, (
        "Precondicion T99: T00 no registro linea base"
    )
    c = CorridaSandbox("inopost")
    try:
        c.login_actor("admin", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        total_post, ultimo_post = _leer_estado_auditoria_api(c, "t99_get_auditoria_post")
        assert total_post == _CONTEXTO["total_base"], (
            f"T99 total post-rollback ({total_post}) != total_base T00 ({_CONTEXTO['total_base']})"
        )
        assert ultimo_post == _CONTEXTO["ultimo_id_base"], (
            f"T99 ultimo_id post-rollback ({ultimo_post}) != ultimo_id_base T00 ({_CONTEXTO['ultimo_id_base']})"
        )
        for aid in _CONTEXTO["activos_creados"]:
            rg = c.get("admin", f"/activos-biologicos/{aid}", paso=f"t99_get_activo_{aid}")
            assert rg.status_code == 404, (
                f"T99 activo {aid} aun accesible tras rollback: HTTP {rg.status_code} "
                f"[X-Request-Id={rg.headers.get('X-Request-Id', '')}]"
            )
    finally:
        r_close = c.cerrar()
        assert r_close is not None and r_close.status_code == 200, (
            f"T99 cierre sandbox inesperado: {r_close.status_code if r_close else None}"
        )
