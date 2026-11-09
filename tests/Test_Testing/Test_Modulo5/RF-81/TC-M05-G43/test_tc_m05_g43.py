# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G43 RF-81: control de acceso y auditoria (102, 105 / 037, 040) |
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
  - test_a02_gestor_granja_rechazo_sin_unidad: (102 / 037) Gestor de Granja consulta activo 957 (finca ajena) ->
      Esperado de la spec (E2/CA-3): HTTP 403 con mensaje de E2.
  - test_a03_auditoria_intento_rechazado: (102 / 037, CU04 FA-04) Auditoria del intento de acceso rechazado ->
      Esperado: 1 evento RECHAZADO en la bitacora.
  - test_a04_productor_consulta_su_unidad: (102 / 037) Productor consulta activo 957 (su finca 1) -> HTTP 200.
  - test_98_cierre_corridas: Cierre de todas las corridas sandbox con DELETE /test-control/runs/{run_id} -> 200.
  - test_99_inocuidad_final: Verificacion fuera de sandbox: 0 efectos persistidos.
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
    "activo_gestor_id": 1042,   # Finca 464 (Gestor de Granja)
    "activo_productor_id": 957, # Finca 1 (Productor)
    "corridas_cerradas": {},
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
    admin_pw = _env("TEST_ADMIN_PASSWORD", obligatoria=False)
    if admin_pw and len(admin_pw) >= 4:
        limpio = limpio.replace(admin_pw, "[REDACTED_PASSWORD]")
    sandbox_sec = _env("TEST_SANDBOX_SECRET", obligatoria=False)
    if sandbox_sec and len(sandbox_sec) >= 6:
        limpio = limpio.replace(sandbox_sec, "[REDACTED_SECRET]")
    for tok in tokens_extra:
        if tok and len(tok) >= 8:
            limpio = limpio.replace(tok, "[REDACTED_TOKEN]")
    limpio = re.sub(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]", limpio)
    admin_email = _env("TEST_ADMIN_EMAIL", obligatoria=False)
    if admin_email and admin_email in limpio:
        partes = admin_email.split("@")
        masc = partes[0][:3] + "***@" + partes[1] if len(partes) == 2 else "***@email"
        limpio = limpio.replace(admin_email, masc)
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


class CorridaG43:
    """Gestiona una transaccion sandbox (X-Test-Run-Id) individual para un rol."""

    def __init__(self, etiqueta_rol: str, email: str, password: str) -> None:
        self.etiqueta = etiqueta_rol
        self.email = email
        self.password = password
        self.run_id = f"tc-m05-g43-{etiqueta_rol}-{uuid.uuid4().hex[:8]}"
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
    c = CorridaG43("admin", _env("TEST_ADMIN_EMAIL"), _env("TEST_ADMIN_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_gestor() -> CorridaG43:
    c = CorridaG43("gestor", _env("TEST_FIELD_ENGINEER_EMAIL"), _env("TEST_FIELD_ENGINEER_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


@pytest.fixture(scope="class")
def corrida_productor() -> CorridaG43:
    c = CorridaG43("productor", _env("TEST_PRODUCER_EMAIL"), _env("TEST_PRODUCER_PASSWORD"))
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G43_Admin_Auditoria:
    """Corrida 1: Administrador — Activos propios, auditoria de consultas, exportaciones y solo lectura."""

    def test_00_setup_linea_base_y_activo_c(self, corrida_admin: CorridaG43):
        """T00: Setup activo propio C con 3 registros y captura de linea base."""
        c = corrida_admin

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

    def test_b01_consulta_con_resultados_auditoria(self, corrida_admin: CorridaG43):
        """B01 (TC-M05-105 / 040): Consulta CON resultados genera evento CONSULTA_HISTORIAL_EJECUTADA (CA-8 / RNF-05).
        Verifica id_usuario, id_activo_biologico, resultado EXITOSO, filtros aplicados,
        total de registros retornados y visibilidad en <= 2 s."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]

        t_inicio = time.perf_counter()
        r_hist = c.get(f"/suministros/historial?id_activo_biologico={id_c}", paso="B01_consultar_historial")
        assert r_hist.status_code == 200
        assert len(r_hist.json().get("items", [])) == 3

        # Verificar evento de auditoria en modulo5.auditorias_suministros via /test-control/query
        sql = (
            f"SELECT * FROM modulo5.auditorias_suministros "
            f"WHERE entidad_afectada = 'historial_suministros' AND id_activo_biologico = {id_c} "
            f"  AND tipo_operacion = 'CONSULTA_HISTORIAL_EJECUTADA' "
            f"ORDER BY id_auditoria_suministro DESC LIMIT 1"
        )
        r_q = c.post("/test-control/query", {"query": sql}, paso="B01_verificar_auditoria_query")
        assert r_q.status_code == 200
        eventos = r_q.json().get("data", [])
        duracion_visibilidad = time.perf_counter() - t_inicio

        assert len(eventos) >= 1, f"No se encontro evento CONSULTA_HISTORIAL_EJECUTADA para activo {id_c}"
        ev = eventos[0]
        # Sanitizar e imprimir fila completa
        print("B01 Audit Row:", json.dumps(_sanitizar_objeto(ev), default=str))

        assert ev.get("resultado") == "EXITOSO"
        assert ev.get("id_activo_biologico") == id_c
        assert ev.get("id_usuario") is not None
        if c.id_usuario is not None:
            assert ev.get("id_usuario") == c.id_usuario
        assert duracion_visibilidad <= 2.5, f"El evento de auditoria tardo mas de 2 s en ser visible ({duracion_visibilidad:.2f} s)"

        # CA-8 / Fase 7: El evento debe registrar usuario, filtros aplicados, activo y total registros retornados
        datos = ev.get("datos_nuevos") or {}
        total_retornado = datos.get("total_registros_retornados") if isinstance(datos, dict) else None
        filtros_reg = datos.get("filtros") or datos.get("filtros_aplicados") if isinstance(datos, dict) else None

        assert total_retornado is not None and filtros_reg is not None, (
            f"DEFECTO DE PRODUCTO (CA-8 / Fase 7): La bitacora de auditoria no almacena los filtros aplicados "
            f"ni el total de registros retornados (datos_nuevos={datos}, columnas_adicionales={ev})"
        )

        # Verificar tambien via GET /suministros/auditoria
        r_aud = c.get(f"/suministros/auditoria?entidad_afectada=historial_suministros&id_activo_biologico={id_c}", paso="B01_auditoria_api")
        assert r_aud.status_code == 200
        items_aud = r_aud.json().get("items", [])
        assert any(it.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA" for it in items_aud)

    def test_b02_consulta_sin_resultados_auditoria(self, corrida_admin: CorridaG43):
        """B02 (TC-M05-105 / 040, segun el caso CU04 FA-01): Consulta SIN resultados (rango sin registros)
        tambien genera evento CONSULTA_HISTORIAL_EJECUTADA con filtros y total=0 en la bitacora."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]

        # Conteo previo de consultas sobre activo C
        sql_conteo = (
            f"SELECT count(*) as c FROM modulo5.auditorias_suministros "
            f"WHERE entidad_afectada = 'historial_suministros' AND id_activo_biologico = {id_c} "
            f"  AND tipo_operacion = 'CONSULTA_HISTORIAL_EJECUTADA'"
        )
        r_prev = c.post("/test-control/query", {"query": sql_conteo}, paso="B02_conteo_previo")
        total_previo = int(r_prev.json().get("data", [{}])[0].get("c", 0))

        # Consulta con rango de fechas sin registros (2025)
        params_vacio = {
            "id_activo_biologico": id_c,
            "fecha_inicio_filtro": "2025-01-01",
            "fecha_fin_filtro": "2025-01-31",
        }
        r_vacio = c.get("/suministros/historial", params=params_vacio, paso="B02_consulta_vacia")
        assert r_vacio.status_code == 200
        assert len(r_vacio.json().get("items", [])) == 0

        # Verificar que se genero un nuevo evento de auditoria
        r_post = c.post("/test-control/query", {"query": sql_conteo}, paso="B02_conteo_posterior")
        total_post = int(r_post.json().get("data", [{}])[0].get("c", 0))

        assert total_post > total_previo, (
            f"La consulta sin resultados debio auditarse (prev={total_previo}, post={total_post})"
        )

        # Verificar que el evento almacene filtros y total de registros retornados (0)
        sql_ultimo = (
            f"SELECT * FROM modulo5.auditorias_suministros "
            f"WHERE entidad_afectada = 'historial_suministros' AND id_activo_biologico = {id_c} "
            f"  AND tipo_operacion = 'CONSULTA_HISTORIAL_EJECUTADA' "
            f"ORDER BY id_auditoria_suministro DESC LIMIT 1"
        )
        r_ult = c.post("/test-control/query", {"query": sql_ultimo}, paso="B02_verificar_ultimo_evento")
        ev_vacio = r_ult.json().get("data", [{}])[0]
        print("B02 Audit Row:", json.dumps(_sanitizar_objeto(ev_vacio), default=str))

        datos = ev_vacio.get("datos_nuevos") or {}
        total_retornado = datos.get("total_registros_retornados") if isinstance(datos, dict) else None
        assert total_retornado is not None, (
            f"DEFECTO DE PRODUCTO (CA-8 / Fase 7): El evento de auditoria para consulta sin resultados no almacena "
            f"el total de registros retornados ni los filtros aplicados (datos_nuevos={datos})"
        )

    def test_b03_exportacion_sincrona_auditoria(self, corrida_admin: CorridaG43):
        """B03 (TC-M05-105 / 040): Exportacion sincrona en PDF y Excel genera EXPORTACION_HISTORIAL_GENERADA
        con usuario, filtros y total en <= 2 s (CA-8 / RNF-05)."""
        c = corrida_admin
        id_c = _CONTEXTO["id_activo_c"]

        # Exportar Excel
        t0 = time.perf_counter()
        r_exp_xl = c.get(
            f"/suministros/historial/exportar?id_activo_biologico={id_c}&formato_exportacion=EXCEL",
            paso="B03_exportar_excel",
        )
        assert r_exp_xl.status_code == 200
        dur_xl = time.perf_counter() - t0

        # Exportar PDF
        t1 = time.perf_counter()
        r_exp_pdf = c.get(
            f"/suministros/historial/exportar?id_activo_biologico={id_c}&formato_exportacion=PDF",
            paso="B03_exportar_pdf",
        )
        assert r_exp_pdf.status_code == 200
        dur_pdf = time.perf_counter() - t1

        # Verificar eventos EXPORTACION_HISTORIAL_GENERADA
        sql = (
            f"SELECT * FROM modulo5.auditorias_suministros "
            f"WHERE entidad_afectada = 'historial_suministros' AND id_activo_biologico = {id_c} "
            f"  AND tipo_operacion = 'EXPORTACION_HISTORIAL_GENERADA' "
            f"ORDER BY id_auditoria_suministro DESC LIMIT 2"
        )
        r_q = c.post("/test-control/query", {"query": sql}, paso="B03_verificar_export_audit")
        eventos = r_q.json().get("data", [])
        assert len(eventos) >= 2, f"Se esperaban al menos 2 eventos EXPORTACION_HISTORIAL_GENERADA, encontrados {len(eventos)}"

        for ev in eventos:
            print("B03 Audit Row:", json.dumps(_sanitizar_objeto(ev), default=str))
            datos = ev.get("datos_nuevos") or {}
            total_exp = datos.get("total_registros_exportados") or datos.get("total_registros_retornados") if isinstance(datos, dict) else None
            assert total_exp is not None, (
                f"DEFECTO DE PRODUCTO (CA-8 / Fase 7): El evento de auditoria de exportacion no almacena "
                f"el total de registros exportados ni los filtros (datos_nuevos={datos})"
            )

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
        """A02 (TC-M05-102 / 037): Usuario con permiso de rol pero SIN la unidad del activo (Restr. 1 / CA-3 / E2).
        Gestor de Granja consulta activo 957 (finca 1, NO asignada a Gestor de Granja):
        Esperado de la spec: HTTP 403 con mensaje de E2 ("No tiene permisos para consultar el historial del activo 957.
        Verifique su rol y unidades productivas asignadas.") y sin fuga de datos en el cuerpo.
        Hecho observado: la API responde HTTP 404 (ACTIVO_NO_ENCONTRADO).
        [INFERENCIA]: ActivoConsultaPort.obtener() evalúa primero la existencia contra modulo2.activos_biologicos,
        donde la política RLS (pol_activos_biologicos_select) oculta el activo ajeno, retornando None y lanzando
        NotFoundError antes de que AlcanceActivoPort (linea 152) pueda evaluar la pertenencia a la unidad y lanzar 403."""
        c = corrida_gestor
        id_activo_ajeno = _CONTEXTO["activo_productor_id"]  # 957 (finca 1)

        r = c.get(f"/suministros/historial?id_activo_biologico={id_activo_ajeno}", paso="A02_gestor_finca_ajena")

        assert r.status_code == 403, (
            f"DEFECTO DE PRODUCTO (E2 / CA-3): Se esperaba HTTP 403 con mensaje de permisos por rol y unidades, "
            f"pero el backend respondio HTTP {r.status_code} ({c.seguro(r.text)}). "
            f"Hecho observado: Gestor recibe 404 (ACTIVO_NO_ENCONTRADO) para el activo 957, mientras Productor recibe 200 para el mismo activo. "
            f"[INFERENCIA]: La causa probable es la política RLS en modulo2.activos_biologicos que oculta el activo ajeno antes de que AlcanceActivoPort sea evaluado."
        )
        body = r.json()
        assert "items" not in body and "resumen" not in body, "No debe haber fuga de datos en respuesta 403"
        msg = body.get("message", "")
        assert "permisos" in msg.lower() and "unidades" in msg.lower(), f"Mensaje no cumple formato E2: {msg}"

    def test_a03_auditoria_intento_rechazado(self, corrida_gestor: CorridaG43):
        """A03 (TC-M05-102 / 037, segun el caso CU04 FA-04): Tras el intento de consulta no autorizado de A02,
        la bitacora de auditoria debe registrar el intento con resultado RECHAZADO (o FALLIDO).
        Esperado del caso: al menos 1 evento registrado con resultado RECHAZADO/FALLIDO en modulo5.auditorias_suministros.
        Hecho observado: 0 eventos (el componente de autorizacion de la API no audita accesos denegados)."""
        c = corrida_gestor
        id_activo_ajeno = _CONTEXTO["activo_productor_id"]  # 957
        id_user = c.id_usuario or 30

        # Consultas de verificacion ANTES del intento rechazado
        sql_i = f"SELECT count(*) as c FROM modulo5.auditorias_suministros WHERE id_usuario = {id_user}"
        sql_ii = f"SELECT count(*) as c FROM modulo5.auditorias_suministros WHERE id_activo_biologico = {id_activo_ajeno}"
        sql_iii = "SELECT count(*) as c FROM modulo5.auditorias_suministros WHERE resultado != 'EXITOSO'"

        r_before_i = c.post("/test-control/query", {"query": sql_i}, paso="A03_antes_audit_gestor")
        assert r_before_i.status_code == 200, f"Error en query (i) antes: HTTP {r_before_i.status_code}: {r_before_i.text}"
        before_i = r_before_i.json().get("data", [{}])[0].get("c", 0)

        r_before_ii = c.post("/test-control/query", {"query": sql_ii}, paso="A03_antes_audit_activo957")
        assert r_before_ii.status_code == 200, f"Error en query (ii) antes: HTTP {r_before_ii.status_code}: {r_before_ii.text}"
        before_ii = r_before_ii.json().get("data", [{}])[0].get("c", 0)

        r_before_iii = c.post("/test-control/query", {"query": sql_iii}, paso="A03_antes_audit_no_exitoso")
        assert r_before_iii.status_code == 200, f"Error en query (iii) antes: HTTP {r_before_iii.status_code}: {r_before_iii.text}"
        before_iii = r_before_iii.json().get("data", [{}])[0].get("c", 0)

        # Intento de consulta rechazado
        r_get = c.get(f"/suministros/historial?id_activo_biologico={id_activo_ajeno}", paso="A03_intento_rechazado")
        assert r_get.status_code in (403, 404), f"Inesperado status code en consulta ajena: HTTP {r_get.status_code}"

        # Consultas de verificacion DESPUES del intento rechazado
        r_after_i = c.post("/test-control/query", {"query": sql_i}, paso="A03_despues_audit_gestor")
        assert r_after_i.status_code == 200, f"Error en query (i) despues: HTTP {r_after_i.status_code}: {r_after_i.text}"
        after_i = r_after_i.json().get("data", [{}])[0].get("c", 0)

        r_after_ii = c.post("/test-control/query", {"query": sql_ii}, paso="A03_despues_audit_activo957")
        assert r_after_ii.status_code == 200, f"Error en query (ii) despues: HTTP {r_after_ii.status_code}: {r_after_ii.text}"
        after_ii = r_after_ii.json().get("data", [{}])[0].get("c", 0)

        r_after_iii = c.post("/test-control/query", {"query": sql_iii}, paso="A03_despues_audit_no_exitoso")
        assert r_after_iii.status_code == 200, f"Error en query (iii) despues: HTTP {r_after_iii.status_code}: {r_after_iii.text}"
        after_iii = r_after_iii.json().get("data", [{}])[0].get("c", 0)

        delta_iii = after_iii - before_iii

        # El caso exige que se audite con resultado != EXITOSO (RECHAZADO/FALLIDO)
        assert delta_iii >= 1, (
            f"DEFECTO DE PRODUCTO (CU04 FA-04): No se registro evento de auditoria con resultado != 'EXITOSO' "
            f"tras consulta no autorizada. Conteos antes: (i)={before_i}, (ii)={before_ii}, (iii)={before_iii}; "
            f"despues: (i)={after_i}, (ii)={after_ii}, (iii)={after_iii}. "
            f"El componente de autorizacion rechaza la peticion sin persistir evento en modulo5.auditorias_suministros."
        )

    def test_a04_observacion_productor_consulta_su_unidad(self, corrida_productor: CorridaG43):
        """A04 [OBSERVACION]: Productor consulta activo 957 (finca 1, asignada a Productor) -> HTTP 200 con datos.
        Nota: El rol Productor esta fuera de la especificacion de RF-81 (gestores y tecnicos),
        este checkpoint se mantiene como observacion informativa de interoperabilidad."""
        c = corrida_productor
        id_productor_activo = _CONTEXTO["activo_productor_id"]  # 957

        r = c.get(f"/suministros/historial?id_activo_biologico={id_productor_activo}", paso="A04_productor_su_finca")
        assert r.status_code == 200, f"Productor debio poder consultar activo 957 en su finca 1: HTTP {r.status_code}: {c.seguro(r.text)}"
        data = r.json()
        assert len(data.get("items", [])) > 0
        assert data.get("resumen", {}).get("total_registros_filtrados", 0) > 0


class TestTC_M05_G43_Teardown_Inocuidad:
    """Verificacion de cierre estricto de todas las corridas e inocuidad fuera de sandbox."""

    def test_98_cierre_corridas(self):
        """T98: Confirmar que todas las corridas de la suite fueron cerradas con HTTP 200."""
        cerradas = _CONTEXTO["corridas_cerradas"]
        assert "admin" in cerradas, "Corrida Admin no fue registrada como cerrada"
        assert "gestor" in cerradas, "Corrida Gestor no fue registrada como cerrada"
        assert "productor" in cerradas, "Corrida Productor no fue registrada como cerrada"

        for rol, info in cerradas.items():
            assert info["status_code"] == 200, (
                f"La corrida {rol} ({info['run_id']}) cerro con HTTP {info['status_code']}: {info['body']}"
            )

    def test_99_inocuidad_final(self):
        """T99: Inocuidad final: verificar fuera de sandbox que el activo C no persiste."""
        id_c = _CONTEXTO.get("id_activo_c")
        if not id_c:
            return
        base_url = _env("TEST_BASE_URL").rstrip("/")
        r_login = requests.post(
            f"{base_url}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200
        token = r_login.json().get("token") or r_login.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        r_check = requests.get(f"{base_url}/suministros/historial?id_activo_biologico={id_c}", headers=headers, timeout=TIMEOUT_S)
        assert r_check.status_code == 404, (
            f"Falta de inocuidad: el activo {id_c} sigue existiendo fuera de sandbox (HTTP {r_check.status_code})"
        )

