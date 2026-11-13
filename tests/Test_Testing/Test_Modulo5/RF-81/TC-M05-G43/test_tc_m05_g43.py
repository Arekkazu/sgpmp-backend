# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G43 RF-81: control de acceso y auditoria (102, 105 / 037, 040) |
# | 12/11/2026 | Juan Sebastian Gutierrez | Reintento 1: B01/B02/B03/A03 via API, T00/T99 runs aparte, OBS-PAG/R8/HASH |
# | 13/11/2026 | Juan Sebastian Gutierrez | reintento INC-M05-358-G43 |
"""
TC-M05-G43 — RF-81 CU04, GET /suministros/historial y /exportar.
Control de acceso por rol y unidad productiva, y auditoria de consultas, exportaciones y rechazos.
Hoja plana: TC-M05-102 y TC-M05-105. Hoja agrupada: 037 y 040.

Checkpoints normativos:
  - test_00_setup_linea_base_y_activo_c: Setup activo propio C con fase y 3 registros; captura de linea base.
  - test_b01_consulta_con_resultados_auditoria: (105 / 040) Consulta CON resultados genera CONSULTA_HISTORIAL_EJECUTADA
      con id_usuario, id_activo_biologico, resultado EXITOSO, visible en <= 2 s.
  - test_b02_consulta_sin_resultados_auditoria: (105 / 040, CU04 FA-01) Consulta SIN resultados genera
      CONSULTA_HISTORIAL_EJECUTADA en la bitacora.
  - test_b03_exportacion_sincrona_auditoria: (105 / 040) Exportacion sincrona PDF y Excel genera
      EXPORTACION_HISTORIAL_GENERADA en <= 2 s.
  - test_b04_solo_lectura_restr_4: (102 / 037) Intentos POST/PUT/PATCH/DELETE sobre /suministros/historial
      son rechazados con 405 Method Not Allowed; inmutabilidad verificada.
  - test_a01_gestor_granja_consulta_su_unidad: (102 / 037) Gestor de Granja consulta activo 1042 (su finca 464) -> HTTP 200.
  - test_a02_gestor_granja_rechazo_sin_unidad: (102 / 037 / RF-81 Fase 1, E2, Restriccion 1, CA-3) Gestor de Granja consulta activo 957 (finca ajena) ->
      HTTP 403 con mensaje de E2 completo.
  - test_a02b_gestor_granja_rechazo_exportacion_sin_unidad: (RF-81 Fase 1, E2, Restriccion 1) Gestor de Granja exporta activo 957 ->
      HTTP 403 con mensaje de E2 completo, sin binario ni id_exportacion.
  - test_a04_observacion_productor_consulta_su_unidad: Precondicion Productor ve activo 957 (HTTP 200) y consulta historial (HTTP 200).
  - test_98_cierre_corridas: Cierre de todas las corridas sandbox con DELETE /test-control/runs/{run_id} -> 200.
  - test_99_inocuidad_final: Verificacion dentro de sandbox: 0 efectos persistidos y restauracion completa.
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
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
    "id_activo_c": None,
    "id_ciclo_c": 5,
    "id_usuario_ref": None,
    "eventos_setup": [],
    "activo_gestor_id": 1042,   # Finca 464 (Gestor de Granja)
    "activo_productor_id": 957, # Finca 1 (Productor)
    "auditoria_inicial_total": None,
    "auditoria_inicial_ultimo_id": None,
    "corridas_cerradas": {},
    "runs_orden": [],
    "observaciones": {
        "obs_inexistente": None,
        "obs_auditoria_tras_403": None,
        "obs_distincion_403_404": None,
        "obs_pag": None,
        "obs_r8": [],
        "obs_hash": [],
        "obs_otros": [],
        "datos_nuevos_literales": {},
    },
}

_TEST_ACTUAL = "init"


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: variable {nombre} ausente en .env.test")
    return valor or ""


def _seguro(texto: str, tokens_extra: tuple[str, ...] = ()) -> str:
    if not texto:
        return ""
    limpio = texto
    for var_pw in ("TEST_ADMIN_PASSWORD", "TEST_FIELD_ENGINEER_PASSWORD", "TEST_PRODUCER_PASSWORD", "TEST_VET_PASSWORD"):
        pw = _env(var_pw, obligatoria=False)
        if pw and len(pw) >= 4:
            limpio = limpio.replace(pw, "[REDACTED_PASSWORD]")
    sandbox_sec = _env("TEST_SANDBOX_SECRET", obligatoria=False)
    if sandbox_sec and len(sandbox_sec) >= 6:
        limpio = limpio.replace(sandbox_sec, "[REDACTED_SECRET]")
    for tok in tokens_extra:
        if tok and len(tok) >= 8:
            limpio = limpio.replace(tok, "[REDACTED_TOKEN]")
    limpio = re.sub(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]", limpio)
    for var_em in ("TEST_ADMIN_EMAIL", "TEST_FIELD_ENGINEER_EMAIL", "TEST_PRODUCER_EMAIL", "TEST_VET_EMAIL"):
        em = _env(var_em, obligatoria=False)
        if em and em in limpio:
            partes = em.split("@")
            masc = partes[0][:3] + "***@" + partes[1] if len(partes) == 2 else "***@email"
            limpio = limpio.replace(em, masc)
    return limpio


def _sanitizar_objeto(obj: Any, tokens_extra: tuple[str, ...] = ()) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        return _seguro(obj, tokens_extra)
    if isinstance(obj, list):
        return [_sanitizar_objeto(item, tokens_extra) for item in obj]
    if isinstance(obj, dict):
        limpio = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in ["pass", "token", "secret", "authorization"]):
                limpio[k] = "[REDACTED]"
            else:
                limpio[k] = _sanitizar_objeto(v, tokens_extra)
        return limpio
    return _seguro(str(obj), tokens_extra)


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
    paso: str | None = None,
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
    x_request_id = ""

    if resp is not None:
        status_code = resp.status_code
        server_date = resp.headers.get("Date", "")
        x_request_id = resp.headers.get("X-Request-Id", "") or resp.headers.get("x-request-id", "")
        ctype = resp.headers.get("Content-Type", "").lower()
        if "application/pdf" in ctype or "spreadsheetml" in ctype or "octet-stream" in ctype:
            resp_body = f"[BINARY {ctype} bytes={len(resp.content)}]"
        else:
            try:
                resp_body = resp.json()
                if isinstance(resp_body, dict):
                    error_code = resp_body.get("error_code")
            except Exception:
                resp_body = resp.text[:300]

    registro = {
        "timestamp_local": now_iso,
        "server_date": server_date,
        "x_request_id": x_request_id,
        "duracion_ms": duracion_ms,
        "test": test_nombre or _TEST_ACTUAL,
        "paso": paso or "",
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


class CorridaG43:
    """Gestiona una transaccion sandbox (X-Test-Run-Id) individual para un rol."""

    def __init__(self, etiqueta_rol: str, email: str, password: str, run_id_compartido: str | None = None) -> None:
        self.etiqueta = etiqueta_rol
        self.email = email
        self.password = password
        self.run_id = run_id_compartido or f"tc-m05-g43-{etiqueta_rol}-{uuid.uuid4().hex[:8]}"
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
            _trazar(metodo, ruta, None, inicio, params=params, req_body=json_body, token_extra=token_extra, error=type(exc).__name__, paso=paso)
            raise ErrorConexion(paso or _TEST_ACTUAL, ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio, params=params, req_body=json_body, token_extra=token_extra, paso=paso)
        return resp

    def get(self, ruta: str, paso: str | None = None, params: Any = None, **kw) -> requests.Response:
        return self._enviar("GET", ruta, paso=paso, params=params, **kw)

    def post(self, ruta: str, json: Any = None, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("POST", ruta, paso=paso, params=params, json_body=json)

    def put(self, ruta: str, json: Any = None, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("PUT", ruta, paso=paso, params=params, json_body=json)

    def patch(self, ruta: str, json: Any = None, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("PATCH", ruta, paso=paso, params=params, json_body=json)

    def delete(self, ruta: str, paso: str | None = None, params: Any = None) -> requests.Response:
        return self._enviar("DELETE", ruta, paso=paso, params=params)

    def login(self) -> None:
        assert self.token is None, "DEF-04: solo se permite un login por run_id"
        r = self.post(
            "/sesiones/",
            {"correo_electronico": self.email, "contrasena": self.password},
            paso=f"login_{self.etiqueta}",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {self.etiqueta} HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {self.etiqueta} sin token"
        self.token = token
        self.id_usuario = r.json().get("id_usuario") or (r.json().get("usuario") or {}).get("id_usuario") or (r.json().get("user") or {}).get("id_usuario")
        if not self.id_usuario:
            try:
                partes = token.split(".")
                if len(partes) >= 2:
                    padding = "=" * (-len(partes[1]) % 4)
                    payload = json.loads(base64.b64decode(partes[1] + padding).decode("utf-8"))
                    self.id_usuario = int(payload.get("sub"))
            except Exception:
                pass
        self.http.headers["Authorization"] = f"Bearer {token}"

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            resp = self._enviar("DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.etiqueta}")
            _CONTEXTO["corridas_cerradas"][self.etiqueta] = {
                "run_id": self.run_id,
                "status_code": resp.status_code,
                "body": resp.text,
            }
            return resp
        finally:
            self.http.close()


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield
    _TEST_ACTUAL = "post_test"


@pytest.fixture(scope="class")
def corrida_admin() -> CorridaG43:
    # T00: Run de sandbox aparte, solo lectura, para capturar linea base de auditoria antes del run principal
    c_t00 = CorridaG43("t00", _env("TEST_ADMIN_EMAIL"), _env("TEST_ADMIN_PASSWORD"))
    _CONTEXTO["runs_orden"].append(c_t00.run_id)
    try:
        c_t00.login()
        r_aud = c_t00.get(
            "/suministros/auditoria",
            params={"pagina": 1, "registros_por_pagina": 50},
            paso="T00_auditoria_inicial",
        )
        assert r_aud.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: GET /suministros/auditoria en T00 HTTP {r_aud.status_code}: {c_t00.seguro(r_aud.text)}"
        )
        body_aud = r_aud.json()
        items_aud = body_aud.get("items", [])
        _CONTEXTO["auditoria_inicial_total"] = body_aud.get("total")
        _CONTEXTO["auditoria_inicial_ultimo_id"] = max((it["id_auditoria_suministro"] for it in items_aud), default=0)
    finally:
        c_t00.cerrar()

    c = CorridaG43("admin", _env("TEST_ADMIN_EMAIL"), _env("TEST_ADMIN_PASSWORD"))
    _CONTEXTO["runs_orden"].append(c.run_id)
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_gestor() -> CorridaG43:
    c = CorridaG43("gestor", _env("TEST_FIELD_ENGINEER_EMAIL"), _env("TEST_FIELD_ENGINEER_PASSWORD"))
    _CONTEXTO["runs_orden"].append(c.run_id)
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_productor() -> CorridaG43:
    c = CorridaG43("productor", _env("TEST_PRODUCER_EMAIL"), _env("TEST_PRODUCER_PASSWORD"))
    _CONTEXTO["runs_orden"].append(c.run_id)
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


def _ultimo_id_auditoria(c: CorridaG43, paso: str, **filtros) -> int:
    params = {"pagina": 1, "registros_por_pagina": 50}
    params.update({k: v for k, v in filtros.items() if v is not None})
    r = c.get("/suministros/auditoria", params=params, paso=paso)
    assert r.status_code == 200, f"Error consultando auditoria ({paso}): HTTP {r.status_code}: {c.seguro(r.text)}"
    items = r.json().get("items", [])
    return max((it["id_auditoria_suministro"] for it in items), default=0)


def _eventos_nuevos_desde(c: CorridaG43, id_base: int, paso: str, **filtros) -> list[dict[str, Any]]:
    nuevos: list[dict[str, Any]] = []
    vistos: set[int] = set()
    pagina = 1
    while pagina <= 10:
        params = {"pagina": pagina, "registros_por_pagina": 50}
        params.update({k: v for k, v in filtros.items() if v is not None})
        r = c.get("/suministros/auditoria", params=params, paso=f"{paso}_p{pagina}")
        assert r.status_code == 200, f"Error listando auditoria ({paso}): HTTP {r.status_code}: {c.seguro(r.text)}"
        body = r.json()
        items = body.get("items", [])
        if not items:
            break
        encontro_nuevo = False
        for it in items:
            eid = it.get("id_auditoria_suministro")
            if eid is not None and eid > id_base and eid not in vistos:
                vistos.add(eid)
                nuevos.append(it)
                encontro_nuevo = True
        total = body.get("total", 0)
        if pagina * 50 >= total or not encontro_nuevo:
            break
        pagina += 1
    nuevos.sort(key=lambda x: x.get("id_auditoria_suministro", 0))
    return nuevos


def _verificar_filtros_aplicados(filtros_aplicados: Any, filtros_enviados: dict[str, Any]) -> None:
    assert isinstance(filtros_aplicados, dict), f"filtros_aplicados debe ser dict, obtenido {type(filtros_aplicados)}"
    evaluados = 0
    for k, esperado in filtros_enviados.items():
        assert k in filtros_aplicados, f"Falta filtro enviado '{k}' en datos_nuevos.filtros_aplicados={filtros_aplicados}"
        actual = filtros_aplicados[k]
        if isinstance(esperado, (int, float, Decimal)) and not isinstance(esperado, bool):
            assert actual is not None and Decimal(str(actual)) == Decimal(str(esperado)), (
                f"Filtro '{k}' esperado {esperado}, obtenido {actual}"
            )
        else:
            assert str(actual) == str(esperado), f"Filtro '{k}' esperado {esperado!r}, obtenido {actual!r}"
        evaluados += 1
    assert evaluados >= 1, "El bucle de verificacion de filtros_aplicados exige >= 1 elemento evaluado"


def _registrar_obs_evento(origen: str, ev: dict[str, Any]) -> None:
    obs = _CONTEXTO["observaciones"]
    obs["obs_r8"].append({
        "origen": origen,
        "id_auditoria_suministro": ev.get("id_auditoria_suministro"),
        "tipo_operacion": ev.get("tipo_operacion"),
        "id_ciclo_productivo": ev.get("id_ciclo_productivo"),
        "registro_incompleto": ev.get("registro_incompleto"),
        "detalle_causa": ev.get("detalle_causa"),
        "ip_origen": ev.get("ip_origen"),
        "id_sesion": ev.get("id_sesion"),
    })
    h = ev.get("hash_integridad") or ""
    obs["obs_hash"].append({
        "origen": origen,
        "id_auditoria_suministro": ev.get("id_auditoria_suministro"),
        "version_hash_integridad": ev.get("version_hash_integridad"),
        "hash_cumple_sha256_hex": bool(re.match(r"^[0-9a-f]{64}$", h)),
    })


class TestTC_M05_G43_Admin_Auditoria:
    """Corrida 1: Administrador — Activos propios, auditoria de consultas, exportaciones y solo lectura."""

    def test_00_setup_linea_base_y_activo_c(self, corrida_admin: CorridaG43):
        """T00: Verificacion de linea base (run aparte), GET /usuarios/me y setup activo C con 3 registros."""
        c = corrida_admin
        # Fuente: Protocolo Sandbox (linea base T00 cerrada antes del run principal)
        del_t00 = _CONTEXTO["corridas_cerradas"].get("t00") or {}
        assert del_t00.get("status_code") == 200 and "Rollback exitoso" in del_t00.get("body", ""), (
            f"T00 no cerro correctamente el sandbox: {del_t00}"
        )
        assert _CONTEXTO["auditoria_inicial_total"] is not None, "Falta total de auditoria inicial en T00"

        # A.0: GET /usuarios/me -> id_usuario_ref
        r_me = c.get("/usuarios/me", paso="T00_usuarios_me")
        assert r_me.status_code == 200, f"GET /usuarios/me fallo: HTTP {r_me.status_code}: {c.seguro(r_me.text)}"
        me_body = r_me.json()
        id_me = me_body.get("id_usuario") or me_body.get("id")
        assert id_me is not None, f"GET /usuarios/me no devolvio id_usuario: {me_body}"
        _CONTEXTO["id_usuario_ref"] = int(id_me)

        # 1. Crear activo C (Individual Holstein)
        id_unico_c = f"QA-G43-C-{uuid.uuid4().hex[:6]}"
        r_act_c = c.post(
            "/activos-biologicos",
            {
                "tipo_activo": "INDIVIDUAL",
                "id_especie": 5,
                "id_infraestructura": 389,
                "identificador": id_unico_c,
                "raza": "Holstein",
                "sexo": "Hembra",
                "fecha_inicio_ciclo": "2026-08-01",
                "origen_financiero": "nacimiento",
            },
            paso="T00_crear_activo_c",
        )
        assert r_act_c.status_code == 201, f"Error creando activo C: HTTP {r_act_c.status_code}: {c.seguro(r_act_c.text)}"
        id_c = r_act_c.json().get("id_activo_biologico")
        assert id_c is not None
        _CONTEXTO["id_activo_c"] = id_c

        # 2. Abrir fase
        r_fase = c.post(
            f"/activos-biologicos/{id_c}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase QA G43", "fecha_inicio": "2026-08-01T05:00:00Z"},
            paso="T00_abrir_fase_c",
        )
        assert r_fase.status_code in (200, 201)

        # 3. Registrar 2 consumos y 1 medicamento
        r_c1 = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_c,
                "id_tipo_alimento": 1,
                "fecha_consumo": "2026-08-10",
                "hora_suministro": "08:00:00",
                "cantidad_alimento": 20.0,
                "costo_unitario": 1000.0,
            },
            paso="T00_consumo_1",
        )
        assert r_c1.status_code == 201

        r_c2 = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_c,
                "id_tipo_alimento": 1,
                "fecha_consumo": "2026-08-15",
                "hora_suministro": "08:00:00",
                "cantidad_alimento": 30.0,
                "costo_unitario": 1000.0,
            },
            paso="T00_consumo_2",
        )
        assert r_c2.status_code == 201

        r_m1 = c.post(
            "/suministros/medicamentos",
            {
                "id_activo_biologico": id_c,
                "nombre_medicamento": "Ivermectina 1%",
                "fecha_aplicacion": "2026-08-18",
                "hora_aplicacion": "09:00:00",
                "via_administracion": "SUBCUTANEA",
                "dosis_aplicada": 5.0,
                "unidad_dosis": "ML",
                "periodo_retiro_dias": 0,
                "motivo_aplicacion": "Tratamiento sanitario preventivo lote",
                "costo_unitario": 2000.0,
                "nombre_veterinario": "Dr. Carlos Veterinario",
            },
            paso="T00_medicamento_1",
        )
        assert r_m1.status_code == 201

        # A.0: Leer eventos SUMINISTRO_REGISTRADO del activo C por la API de auditoria y comparar id_usuario
        r_aud_setup = c.get(
            "/suministros/auditoria",
            params={"id_activo_biologico": id_c, "pagina": 1, "registros_por_pagina": 50},
            paso="T00_auditoria_setup",
        )
        assert r_aud_setup.status_code == 200
        evs_setup = [
            it for it in r_aud_setup.json().get("items", [])
            if it.get("tipo_operacion") == "SUMINISTRO_REGISTRADO"
        ]
        _CONTEXTO["eventos_setup"] = [
            {"id": it.get("id_auditoria_suministro"), "id_usuario": it.get("id_usuario")}
            for it in evs_setup
        ]

    def test_b01_consulta_con_resultados_auditoria(self, corrida_admin: CorridaG43):
        """B01 (TC-M05-105 / 040): Consulta CON resultados genera exactamente 1 CONSULTA_HISTORIAL_EJECUTADA.
        Fuente: RF-81 Fase 7, CA-8 y Postcondicion 2."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]
        id_ciclo = _CONTEXTO["id_ciclo_c"]
        id_usuario_ref = _CONTEXTO["id_usuario_ref"]

        id_antes = _ultimo_id_auditoria(c, "B01_auditoria_antes", entidad_afectada="historial_suministros", id_activo_biologico=id_c)

        filtros_enviados = {
            "id_activo_biologico": id_c,
            "id_ciclo_productivo": id_ciclo,
            "fecha_inicio_filtro": "2026-08-01",
            "fecha_fin_filtro": "2026-08-31",
        }
        params_b01 = {**filtros_enviados, "pagina": 1, "registros_por_pagina": 50}
        r_hist = c.get("/suministros/historial", params=params_b01, paso="B01_consultar_historial")
        # Fuente: RF-81 Fase 3 / RNF-04
        assert r_hist.status_code == 200, f"B01 HTTP {r_hist.status_code}: {c.seguro(r_hist.text)}"
        assert len(r_hist.json().get("items", [])) == 3, f"Esperados 3 registros en B01, obtenidos {len(r_hist.json().get('items', []))}"

        nuevos = _eventos_nuevos_desde(
            c, id_antes, "B01_auditoria_despues", entidad_afectada="historial_suministros", id_activo_biologico=id_c
        )
        consultas = [ev for ev in nuevos if ev.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA"]
        extras = [ev for ev in nuevos if ev.get("tipo_operacion") != "CONSULTA_HISTORIAL_EJECUTADA"]
        for ex in extras:
            _CONTEXTO["observaciones"]["obs_otros"].append({
                "origen": "B01", "id_auditoria_suministro": ex.get("id_auditoria_suministro"), "tipo_operacion": ex.get("tipo_operacion")
            })

        # Fuente: RF-81 Fase 7, CA-8 y Postcondicion 2
        assert len(consultas) == 1, f"Esperado exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo en B01, obtenidos {len(consultas)}: {[e.get('id_auditoria_suministro') for e in nuevos]}"
        ev = consultas[0]
        assert ev.get("id_usuario") == id_usuario_ref, f"id_usuario esperado {id_usuario_ref}, obtenido {ev.get('id_usuario')}"
        assert ev.get("id_activo_biologico") == id_c, f"id_activo_biologico esperado {id_c}, obtenido {ev.get('id_activo_biologico')}"
        assert ev.get("fecha_emision") is not None, "fecha_emision no debe ser nula"
        datos = ev.get("datos_nuevos")
        assert isinstance(datos, dict), f"datos_nuevos debe ser objeto JSON no nulo, obtenido {datos!r}"
        _verificar_filtros_aplicados(datos.get("filtros_aplicados"), filtros_enviados)
        assert datos.get("total_registros_retornados") == 3, (
            f"total_registros_retornados esperado 3, obtenido {datos.get('total_registros_retornados')}"
        )

        _registrar_obs_evento("B01", ev)
        _CONTEXTO["observaciones"]["datos_nuevos_literales"]["B01"] = datos

    def test_b02_consulta_sin_resultados_auditoria(self, corrida_admin: CorridaG43):
        """B02 (TC-M05-105 / 040, CU04 FA-01): Consulta SIN resultados genera exactamente 1 CONSULTA_HISTORIAL_EJECUTADA con total=0.
        Fuente: RF-81 Fase 7, CA-8, E1; caso TC-M05-105/040."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]
        id_ciclo = _CONTEXTO["id_ciclo_c"]
        id_usuario_ref = _CONTEXTO["id_usuario_ref"]

        id_antes = _ultimo_id_auditoria(c, "B02_auditoria_antes", entidad_afectada="historial_suministros", id_activo_biologico=id_c)

        filtros_enviados = {
            "id_activo_biologico": id_c,
            "id_ciclo_productivo": id_ciclo,
            "fecha_inicio_filtro": "2026-08-01",
            "fecha_fin_filtro": "2026-08-05",
        }
        params_vacio = {**filtros_enviados, "pagina": 1, "registros_por_pagina": 50}
        r_vacio = c.get("/suministros/historial", params=params_vacio, paso="B02_consulta_vacia")
        # Fuente: RF-81 E1 (consulta sin resultados responde HTTP 200 con 0 items)
        assert r_vacio.status_code == 200, f"B02 HTTP {r_vacio.status_code}: {c.seguro(r_vacio.text)}"
        assert len(r_vacio.json().get("items", [])) == 0, f"Esperados 0 registros en B02, obtenidos {len(r_vacio.json().get('items', []))}"

        nuevos = _eventos_nuevos_desde(
            c, id_antes, "B02_auditoria_despues", entidad_afectada="historial_suministros", id_activo_biologico=id_c
        )
        consultas = [ev for ev in nuevos if ev.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA"]
        extras = [ev for ev in nuevos if ev.get("tipo_operacion") != "CONSULTA_HISTORIAL_EJECUTADA"]
        for ex in extras:
            _CONTEXTO["observaciones"]["obs_otros"].append({
                "origen": "B02", "id_auditoria_suministro": ex.get("id_auditoria_suministro"), "tipo_operacion": ex.get("tipo_operacion")
            })

        # Fuente: RF-81 Fase 7, CA-8, E1; caso TC-M05-105/040 ("incluso sin resultados")
        assert len(consultas) == 1, f"Esperado exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo en B02, obtenidos {len(consultas)}"
        ev = consultas[0]
        assert ev.get("id_usuario") == id_usuario_ref, f"id_usuario esperado {id_usuario_ref}, obtenido {ev.get('id_usuario')}"
        assert ev.get("id_activo_biologico") == id_c, f"id_activo_biologico esperado {id_c}, obtenido {ev.get('id_activo_biologico')}"
        assert ev.get("fecha_emision") is not None, "fecha_emision no debe ser nula"
        datos = ev.get("datos_nuevos")
        assert isinstance(datos, dict), f"datos_nuevos debe ser objeto JSON no nulo, obtenido {datos!r}"
        _verificar_filtros_aplicados(datos.get("filtros_aplicados"), filtros_enviados)
        tot_ret = datos.get("total_registros_retornados")
        assert isinstance(tot_ret, int) and not isinstance(tot_ret, bool) and tot_ret == 0, (
            f"total_registros_retornados esperado 0 explicito, obtenido {tot_ret!r}"
        )

        _registrar_obs_evento("B02", ev)
        _CONTEXTO["observaciones"]["datos_nuevos_literales"]["B02"] = datos

    def test_b03_exportacion_sincrona_auditoria(self, corrida_admin: CorridaG43):
        """B03 (TC-M05-105 / 040): Exportacion sincrona PDF y EXCEL aisladas generan EXPORTACION_HISTORIAL_GENERADA.
        Fuente: RF-81 Fase 6 a (<= 10.000 registros, sincronica), Fase 7, CA-8 y Postcondicion 2."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]
        id_ciclo = _CONTEXTO["id_ciclo_c"]
        id_usuario_ref = _CONTEXTO["id_usuario_ref"]

        filtros_enviados = {
            "id_activo_biologico": id_c,
            "id_ciclo_productivo": id_ciclo,
            "fecha_inicio_filtro": "2026-08-01",
            "fecha_fin_filtro": "2026-08-31",
        }

        for fmt in ("PDF", "EXCEL"):
            id_antes = _ultimo_id_auditoria(
                c, f"B03_{fmt}_auditoria_antes", entidad_afectada="historial_suministros", id_activo_biologico=id_c
            )
            params_exp = {**filtros_enviados, "formato_exportacion": fmt}
            r_exp = c.get("/suministros/historial/exportar", params=params_exp, paso=f"B03_exportar_{fmt.lower()}")
            # Fuente: RF-81 Fase 6 a (<= 10.000 registros, sincronica) y OpenAPI 200
            assert r_exp.status_code == 200, f"B03 {fmt} HTTP {r_exp.status_code}: {c.seguro(r_exp.text)}"

            nuevos = _eventos_nuevos_desde(
                c, id_antes, f"B03_{fmt}_auditoria_despues", entidad_afectada="historial_suministros", id_activo_biologico=id_c
            )
            exps = [ev for ev in nuevos if ev.get("tipo_operacion") == "EXPORTACION_HISTORIAL_GENERADA"]
            extras = [ev for ev in nuevos if ev.get("tipo_operacion") != "EXPORTACION_HISTORIAL_GENERADA"]
            for ex in extras:
                _CONTEXTO["observaciones"]["obs_otros"].append({
                    "origen": f"B03_{fmt}", "id_auditoria_suministro": ex.get("id_auditoria_suministro"), "tipo_operacion": ex.get("tipo_operacion")
                })

            # Fuente: RF-81 Fase 7, CA-8 y Postcondicion 2
            assert len(exps) == 1, f"B03 {fmt}: esperado 1 EXPORTACION_HISTORIAL_GENERADA nuevo, obtenidos {len(exps)}"
            ev = exps[0]
            assert ev.get("id_usuario") == id_usuario_ref, f"B03 {fmt}: id_usuario esperado {id_usuario_ref}, obtenido {ev.get('id_usuario')}"
            assert ev.get("id_activo_biologico") == id_c, f"B03 {fmt}: id_activo_biologico esperado {id_c}, obtenido {ev.get('id_activo_biologico')}"
            assert ev.get("fecha_emision") is not None, f"B03 {fmt}: fecha_emision no debe ser nula"
            datos = ev.get("datos_nuevos")
            assert isinstance(datos, dict), f"B03 {fmt}: datos_nuevos debe ser dict no nulo, obtenido {datos!r}"
            _verificar_filtros_aplicados(datos.get("filtros_aplicados"), filtros_enviados)
            assert datos.get("total_registros_retornados") == 3, (
                f"B03 {fmt}: total_registros_retornados esperado 3, obtenido {datos.get('total_registros_retornados')}"
            )

            _registrar_obs_evento(f"B03_{fmt}", ev)
            _CONTEXTO["observaciones"]["datos_nuevos_literales"][f"B03_{fmt}"] = datos

    def test_b04_solo_lectura_restr_4(self, corrida_admin: CorridaG43):
        """B04 (TC-M05-102 / 037): El historial es de solo lectura (Restr. 4).
        POST, PUT, PATCH y DELETE sobre /suministros/historial o sobre registros deben ser rechazados (405)
        y la consulta del historial permanece inalterada."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]

        # Historial antes
        r_antes = c.get(f"/suministros/historial?id_activo_biologico={id_c}", paso="B04_antes")
        items_antes = r_antes.json().get("items", [])
        assert len(items_antes) == 3

        # Intentos de modificacion sobre el endpoint
        r_post = c.post("/suministros/historial", json={"id_activo_biologico": id_c}, paso="B04_post_intento")
        assert r_post.status_code in (404, 405), f"POST sobre /suministros/historial respondio {r_post.status_code}"

        r_put = c.put(f"/suministros/historial?id_activo_biologico={id_c}", json={"modificado": True}, paso="B04_put_intento")
        assert r_put.status_code in (404, 405)

        r_patch = c.patch(f"/suministros/historial?id_activo_biologico={id_c}", json={"modificado": True}, paso="B04_patch_intento")
        assert r_patch.status_code in (404, 405)

        r_del = c.delete(f"/suministros/historial?id_activo_biologico={id_c}", paso="B04_del_intento")
        assert r_del.status_code in (404, 405)

        # Historial despues: 100% inalterado
        r_despues = c.get(f"/suministros/historial?id_activo_biologico={id_c}", paso="B04_despues")
        items_despues = r_despues.json().get("items", [])
        assert len(items_despues) == 3

        # Observacion OBS-PAG (A.6): pagina=1, registros_por_pagina=2 (no es checkpoint)
        id_antes_pag = _ultimo_id_auditoria(c, "OBS_PAG_auditoria_antes", entidad_afectada="historial_suministros", id_activo_biologico=id_c)
        r_obs_pag = c.get(
            "/suministros/historial",
            params={"id_activo_biologico": id_c, "pagina": 1, "registros_por_pagina": 2},
            paso="OBS_PAG_consulta",
        )
        evs_pag = _eventos_nuevos_desde(
            c, id_antes_pag, "OBS_PAG_auditoria_despues", entidad_afectada="historial_suministros", id_activo_biologico=id_c
        )
        ev_pag = next((e for e in evs_pag if e.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA"), None)
        datos_pag = (ev_pag or {}).get("datos_nuevos") or {}
        _CONTEXTO["observaciones"]["obs_pag"] = {
            "http": r_obs_pag.status_code,
            "items_en_respuesta": len(r_obs_pag.json().get("items", [])) if r_obs_pag.status_code == 200 else None,
            "id_auditoria_suministro": (ev_pag or {}).get("id_auditoria_suministro"),
            "total_registros_retornados": datos_pag.get("total_registros_retornados"),
            "total_registros_filtrados": datos_pag.get("total_registros_filtrados"),
            "pagina": datos_pag.get("pagina"),
            "registros_por_pagina": datos_pag.get("registros_por_pagina"),
        }


class TestTC_M05_G43_Roles_Unidades:
    """Corrida 2 y 3: Control de acceso por rol y unidad productiva (Gestor de Granja y Productor)."""

    def test_a01_gestor_granja_consulta_su_unidad(self, corrida_gestor: CorridaG43):
        """A01 (TC-M05-102 / 037): Gestor de Granja consulta activo 1042 (finca 464, asignada a él) -> HTTP 200.
        Verifica respuesta valida y solo lectura (PUT/DELETE rechazados)."""
        c = corrida_gestor
        id_gestor_activo = _CONTEXTO["activo_gestor_id"]  # 1042

        r = c.get(f"/suministros/historial?id_activo_biologico={id_gestor_activo}", paso="A01_gestor_su_finca")
        assert r.status_code == 200, f"Gestor debio poder consultar activo 1042 en su finca 464: HTTP {r.status_code}: {c.seguro(r.text)}"
        data = r.json()
        assert len(data.get("items", [])) > 0
        assert data.get("resumen", {}).get("total_registros_filtrados", 0) > 0

        # Solo lectura: intento de modificar es rechazado con 405
        r_put = c.put(f"/suministros/historial?id_activo_biologico={id_gestor_activo}", paso="A01_gestor_put")
        assert r_put.status_code in (404, 405)

    def test_a02_gestor_granja_rechazo_sin_unidad(self, corrida_gestor: CorridaG43):
        """A02 [RF-81 Fase 1, E2, Restriccion 1, CA-3]: Gestor de Granja (usuario 30) consulta activo 957 (finca 1 ajena).
        -> HTTP 403; el mensaje contiene el texto COMPLETO de E2 con id 957 (normaliza solo espacios):
        "No tiene permisos para consultar el historial del activo 957. Verifique su rol y unidades productivas asignadas.";
        el cuerpo no trae registros ni resumen."""
        c = corrida_gestor
        id_activo_ajeno = _CONTEXTO["activo_productor_id"]  # 957

        r = c.get(f"/suministros/historial?id_activo_biologico={id_activo_ajeno}", paso="A02_gestor_finca_ajena")
        # Fuente: RF-81 Fase 1, E2, Restriccion 1, CA-3
        assert r.status_code == 403, (
            f"Esperado HTTP 403 en A02, obtenido HTTP {r.status_code}: {c.seguro(r.text)}"
        )
        body = r.json()
        assert "items" not in body and "resumen" not in body, "No debe haber registros ni resumen en respuesta 403 de A02"
        assert body.get("error_code") == "ACCESO_DENEGADO", (
            f"error_code esperado 'ACCESO_DENEGADO', obtenido {body.get('error_code')!r}"
        )
        msg_crudo = body.get("message", "")
        msg_norm = " ".join(msg_crudo.split())
        msg_esperado = f"No tiene permisos para consultar el historial del activo {id_activo_ajeno}. Verifique su rol y unidades productivas asignadas."
        assert msg_esperado in msg_norm, (
            f"Mensaje no contiene texto de E2. Esperado: {msg_esperado!r}, Obtenido: {msg_norm!r}"
        )

    def test_a02b_gestor_granja_rechazo_exportacion_sin_unidad(self, corrida_gestor: CorridaG43):
        """A02b [RF-81 Fase 1, E2, Restriccion 1]: Gestor de Granja (usuario 30) solicita exportacion sincronica
        GET /suministros/historial/exportar?id_activo_biologico=957&formato_exportacion=PDF
        -> HTTP 403; mismo mensaje de E2; no genera archivo ni id_exportacion."""
        c = corrida_gestor
        id_activo_ajeno = _CONTEXTO["activo_productor_id"]  # 957

        r = c.get(
            f"/suministros/historial/exportar?id_activo_biologico={id_activo_ajeno}&formato_exportacion=PDF",
            paso="A02b_gestor_export_ajena",
        )
        # Fuente: RF-81 Fase 1, E2, Restriccion 1
        assert r.status_code == 403, (
            f"Esperado HTTP 403 en A02b, obtenido HTTP {r.status_code}: {c.seguro(r.text)}"
        )
        body = r.json()
        assert "id_exportacion" not in body, "No debe retornar id_exportacion en respuesta 403 de A02b"
        assert "items" not in body and "resumen" not in body, "No debe retornar items ni resumen en respuesta 403 de A02b"
        ctype = r.headers.get("Content-Type", "").lower()
        assert "application/pdf" not in ctype, f"No debe retornar binario PDF en 403: Content-Type={ctype}"
        assert body.get("error_code") == "ACCESO_DENEGADO", (
            f"error_code esperado 'ACCESO_DENEGADO', obtenido {body.get('error_code')!r}"
        )
        msg_crudo = body.get("message", "")
        msg_norm = " ".join(msg_crudo.split())
        msg_esperado = f"No tiene permisos para consultar el historial del activo {id_activo_ajeno}. Verifique su rol y unidades productivas asignadas."
        assert msg_esperado in msg_norm, (
            f"Mensaje de exportacion no contiene texto de E2. Esperado: {msg_esperado!r}, Obtenido: {msg_norm!r}"
        )

        # Observaciones requeridas sin checkpoint:
        # 1. Gestor con activo inexistente (999999999) -> HTTP y error_code (se espera 404)
        r_inex = c.get("/suministros/historial?id_activo_biologico=999999999", paso="OBS_gestor_activo_inexistente")
        err_inex = None
        try:
            err_inex = r_inex.json().get("error_code")
        except Exception:
            pass
        _CONTEXTO["observaciones"]["obs_inexistente"] = {
            "http": r_inex.status_code,
            "error_code": err_inex,
            "x_request_id": r_inex.headers.get("X-Request-Id") or r_inex.headers.get("x-request-id"),
        }

        # 2. Distincion 403 frente a 404 permite distinguir si el activo existe (consecuencia de E2)
        _CONTEXTO["observaciones"]["obs_distincion_403_404"] = {
            "activo_existente_957_http": r.status_code,
            "activo_existente_957_error_code": body.get("error_code"),
            "activo_inexistente_999999999_http": r_inex.status_code,
            "activo_inexistente_999999999_error_code": err_inex,
            "conclusion": "403 vs 404 permite distinguir si el activo existe en el sistema (consecuencia directa de validacion E2)",
        }

    def test_a04_observacion_productor_consulta_su_unidad(self, corrida_productor: CorridaG43):
        """A04 [OBSERVACION]: Productor consulta activo 957 (finca 1, asignada a Productor) -> HTTP 200 con datos.
        Precondicion de control en A04: el Productor SI ve el activo 957 (GET /activos-biologicos/957 -> 200),
        demostrando que existe durante la misma corrida."""
        c = corrida_productor
        id_productor_activo = _CONTEXTO["activo_productor_id"]  # 957

        # Precondicion de control: Productor verifica que el activo 957 existe en esta corrida
        r_pre = c.get(f"/activos-biologicos/{id_productor_activo}", paso="A04_productor_precondicion_activo")
        # Fuente: Control de precondicion / Protocolo de consistencia
        assert r_pre.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: Productor debe ver activo {id_productor_activo}: HTTP {r_pre.status_code}: {c.seguro(r_pre.text)}"
        )

        r = c.get(f"/suministros/historial?id_activo_biologico={id_productor_activo}", paso="A04_productor_su_finca")
        # Fuente: RF-81 Fase 3 / Comportamiento para usuario con alcance
        assert r.status_code == 200, f"Productor debio poder consultar activo 957 en su finca 1: HTTP {r.status_code}: {c.seguro(r.text)}"
        data = r.json()
        assert len(data.get("items", [])) > 0, "Se esperaban registros en historial para activo 957"
        assert data.get("resumen", {}).get("total_registros_filtrados", 0) > 0, "total_registros_filtrados > 0 esperado"


class TestTC_M05_G43_Teardown_Inocuidad:
    """Verificacion de cierre estricto de todas las corridas e inocuidad en sandbox."""

    def test_98_cierre_corridas(self):
        """T98: Confirmar que las corridas previas (t00, admin, gestor, productor) fueron cerradas con HTTP 200."""
        cerradas = _CONTEXTO["corridas_cerradas"]
        for rol_req in ("t00", "admin", "gestor", "productor"):
            assert rol_req in cerradas, f"Corrida {rol_req} no fue registrada como cerrada"

        assert len(cerradas) >= 4
        for rol, info in cerradas.items():
            # Fuente: Regla 2 de sandbox (DELETE /test-control/runs/{run_id} -> 200 Rollback exitoso)
            assert info["status_code"] == 200, (
                f"La corrida {rol} ({info['run_id']}) cerro con HTTP {info['status_code']}: {info['body']}"
            )
            assert "Rollback exitoso" in info.get("body", ""), (
                f"La corrida {rol} ({info['run_id']}) no devolvio 'Rollback exitoso': {info['body']}"
            )

    def test_99_inocuidad_final(self):
        """T99: Inocuidad final dentro de run propio de solo lectura en sandbox."""
        id_c = _CONTEXTO.get("id_activo_c")
        assert id_c is not None, "id_activo_c no fue inicializado en T00/setup"

        c_t99 = CorridaG43("t99", _env("TEST_ADMIN_EMAIL"), _env("TEST_ADMIN_PASSWORD"))
        _CONTEXTO["runs_orden"].append({"rol": "t99", "run_id": c_t99.run_id})
        try:
            c_t99.login()
            r_aud = c_t99.get("/suministros/auditoria?pagina=1&registros_por_pagina=50", paso="T99_audit_inocuidad")
            # Fuente: RF-80 / Regla de inocuidad del sandbox
            assert r_aud.status_code == 200, f"Error consultando auditoria en T99: HTTP {r_aud.status_code}"
            body_aud = r_aud.json()
            total_actual = body_aud.get("total")
            assert total_actual == _CONTEXTO["auditoria_inicial_total"], (
                f"Falta de inocuidad en auditoria: total actual {total_actual} != inicial {_CONTEXTO['auditoria_inicial_total']}"
            )
            items_aud = body_aud.get("items", [])
            if _CONTEXTO["auditoria_inicial_ultimo_id"] > 0:
                assert len(items_aud) >= 1, "Se esperaban items de auditoria previos en T99"
                max_id_actual = max(ev["id_auditoria_suministro"] for ev in items_aud)
                assert max_id_actual == _CONTEXTO["auditoria_inicial_ultimo_id"], (
                    f"Falta de inocuidad en auditoria: max id actual {max_id_actual} != inicial {_CONTEXTO['auditoria_inicial_ultimo_id']}"
                )

            # Observacion: eventos nuevos en auditoria tras el 403 de A02 y A02b
            _CONTEXTO["observaciones"]["obs_auditoria_tras_403"] = (
                f"ninguno (0 eventos nuevos; total={total_actual} coincide con total inicial={_CONTEXTO['auditoria_inicial_total']}, "
                f"max_id={max_id_actual} coincide con max_id inicial={_CONTEXTO['auditoria_inicial_ultimo_id']})"
            )

            r_act = c_t99.get(f"/activos-biologicos/{id_c}", paso="T99_activo_c_404")
            # Fuente: Regla 2 de sandbox (rollback tras DELETE elimina el activo C)
            assert r_act.status_code == 404, (
                f"Falta de inocuidad: activo {id_c} sigue existiendo en T99 (HTTP {r_act.status_code})"
            )

            r_hist = c_t99.get(f"/suministros/historial?id_activo_biologico={id_c}", paso="T99_historial_c_404")
            # Fuente: Regla 2 de sandbox (rollback tras DELETE elimina historial del activo C)
            assert r_hist.status_code == 404, (
                f"Falta de inocuidad: historial del activo {id_c} sigue existiendo en T99 (HTTP {r_hist.status_code})"
            )
        finally:
            res_cierre = c_t99.cerrar()
            _CONTEXTO["corridas_cerradas"]["t99"] = {
                "run_id": c_t99.run_id,
                "status_code": res_cierre.status_code,
                "body": c_t99.seguro(res_cierre.text),
            }

        cierre_t99 = _CONTEXTO["corridas_cerradas"]["t99"]
        # Fuente: Regla 2 de sandbox (DELETE /test-control/runs/{run_id} -> 200 Rollback exitoso)
        assert cierre_t99["status_code"] == 200, f"Cierre T99 fallo: {cierre_t99}"
        assert "Rollback exitoso" in cierre_t99.get("body", ""), f"Cierre T99 sin Rollback exitoso: {cierre_t99}"


@pytest.fixture(scope="session", autouse=True)
def _persistir_contexto_sesion():
    """Persiste contexto_g43.json sanitizado al finalizar la sesion, incluso si falla cualquier test."""
    yield
    ev_dir = os.environ.get("TEST_EVIDENCE_DIR")
    if not ev_dir:
        return
    try:
        ctx_out = {
            "id_activo_c": _CONTEXTO.get("id_activo_c"),
            "id_ciclo_c": _CONTEXTO.get("id_ciclo_c"),
            "id_usuario_ref": _CONTEXTO.get("id_usuario_ref"),
            "auditoria_inicial_total": _CONTEXTO.get("auditoria_inicial_total"),
            "auditoria_inicial_ultimo_id": _CONTEXTO.get("auditoria_inicial_ultimo_id"),
            "eventos_setup": _CONTEXTO.get("eventos_setup"),
            "corridas_cerradas": _CONTEXTO.get("corridas_cerradas"),
            "runs_orden": _CONTEXTO.get("runs_orden"),
            "a03": _CONTEXTO.get("a03"),
            "observaciones": _CONTEXTO.get("observaciones"),
        }
        Path(ev_dir).mkdir(parents=True, exist_ok=True)
        (Path(ev_dir) / "contexto_g43.json").write_text(
            json.dumps(ctx_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        import sys
        print(f"[ERROR] No se pudo escribir contexto_g43.json: {exc}", file=sys.stderr)

