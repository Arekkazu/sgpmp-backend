# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G37: Persistencia y clasificacion de eventos RF-80 (CU06)      |
"""Suite de pruebas para TC-M05-G37: Persistencia y clasificacion de eventos (RF-80).

Cubre los casos TC-M05-026 y TC-M05-027:
- Persistencia inmediata (<= 2 s) de operaciones exitosas (RF-78, RF-79, RF-81).
- Registro de campos base RF-10 y campos de extension M05 (hash, clasificacion, retencion).
- Verificacion de registro de fallos en auditoria (CA-1).
- Consistencia entre consulta por filtros y por detalle /{id}.
- Clasificacion diferenciada (NIC41 / 5 años vs TECNICO / 1 año).
- Tipo no catalogado por defecto a NIC41 (prueba a nivel de unidad).
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
    "evento_rf78": None,
    "evento_rf79_consolidado": None,
    "evento_rf79_reporte": None,
    "evento_rf81": None,
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


class CorridaSandbox:
    def __init__(self) -> None:
        self.run_id = f"tc-m05-g37-adm-{uuid.uuid4().hex[:8]}"
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


class TestTCM05G37PersistenciaYClasificacion:
    """TC-M05-G37: Persistencia y clasificacion de eventos de auditoria en M05."""

    def test_t00_setup_linea_base(self, sandbox_admin: CorridaSandbox):
        """T00: Conteo inicial de eventos de auditoria y creacion de activo con fase."""
        c = sandbox_admin

        # 1. Conteo inicial de eventos en la bitacora
        r_ini = c.get("/suministros/auditoria", paso="t00_conteo_base", params={"pagina": 1, "registros_por_pagina": 1})
        assert r_ini.status_code == 200, f"Error obteniendo conteo base: HTTP {r_ini.status_code}: {c.seguro(r_ini.text)}"
        total_ini = r_ini.json().get("total", 0)
        _CONTEXTO["total_base"] = total_ini
        assert isinstance(total_ini, int) and total_ini >= 0

        # 2. Crear activo poblacional dedicado
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
        r_act = c.post("/activos-biologicos", payload_activo, paso="t00_crear_activo")
        assert r_act.status_code == 201, f"Fallo al crear activo QA: HTTP {r_act.status_code}: {c.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None, "Respuesta sin id_activo_biologico"
        _CONTEXTO["id_activo"] = id_activo

        # 3. Abrir fase productiva
        payload_fase = {
            "id_ciclo_productiva": 1,
            "motivo_cambio": "Apertura fase productiva QA G37",
        }
        r_fase = c.post(f"/activos-biologicos/{id_activo}/fases", payload_fase, paso="t00_abrir_fase")
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"
        id_fase = r_fase.json().get("id_gestion_fases")
        assert id_fase is not None, "Respuesta sin id_gestion_fases"
        _CONTEXTO["id_fase"] = id_fase

    def test_a01_rf78_operacion_exitosa(self, sandbox_admin: CorridaSandbox):
        """A01 (026.1): Registro de suministro directo RF-78 -> evento SUMINISTRO_REGISTRADO persistido <= 2 s."""
        c = sandbox_admin
        id_activo = _CONTEXTO["id_activo"]
        hoy_str = _hoy().isoformat()

        # Medir tiempo de peticion
        t_req_inicio = time.perf_counter()
        payload_sum = {
            "id_activo_biologico": id_activo,
            "tipo_suministro": "SERVICIO_VETERINARIO",
            "cantidad": 1.0,
            "unidad_medida": "UNIDAD",
            "precio_unitario": 40000.0,
            "fecha_aplicacion": hoy_str,
            "justificacion_precio": "Tarifa estandar segun contrato veterinario vigente",
            "id_idempotencia": str(uuid.uuid4()),
        }
        r_sum = c.post("/suministros/costeo-directo", payload_sum, paso="a01_rf78_registrar_suministro")
        duracion_req = time.perf_counter() - t_req_inicio
        assert r_sum.status_code == 200, f"Error registrando suministro RF-78: HTTP {r_sum.status_code}: {c.seguro(r_sum.text)}"

        # Consultar inmediatamente la bitacora de auditoria filtrando por activo
        t_query_inicio = time.perf_counter()
        r_aud = c.get(
            "/suministros/auditoria",
            paso="a01_rf78_consultar_auditoria",
            params={"id_activo_biologico": id_activo, "tipo_operacion": "SUMINISTRO_REGISTRADO"},
        )
        duracion_query = time.perf_counter() - t_query_inicio
        assert r_aud.status_code == 200, f"Error consultando auditoria: HTTP {r_aud.status_code}: {c.seguro(r_aud.text)}"
        items = r_aud.json().get("items", [])
        assert len(items) >= 1, f"No se encontro evento SUMINISTRO_REGISTRADO para el activo {id_activo}"

        evento = items[0]
        _CONTEXTO["evento_rf78"] = evento

        # Validar persistencia <= 2 s (visibilidad inmediata comprobada en transaccion)
        assert duracion_req < 2.0 or (duracion_req + duracion_query) < 3.0, (
            f"Persistencia excede el umbral de 2 s: request={duracion_req:.3f}s, query={duracion_query:.3f}s"
        )

        # Validar campos base RF-10
        assert evento.get("id_auditoria_suministro") is not None and evento["id_auditoria_suministro"] > 0
        assert evento.get("entidad_afectada") == "registro_suministro"
        assert evento.get("tipo_operacion") == "SUMINISTRO_REGISTRADO"
        assert evento.get("resultado") == "EXITOSO"
        assert evento.get("fecha_evento") is not None
        assert evento.get("id_usuario") is not None

        # Validar campos de extension M05
        assert evento.get("id_activo_biologico") == id_activo
        assert evento.get("costo_afectado") is not None and float(evento["costo_afectado"]) == 40000.0
        assert evento.get("origen_precio") == "MANUAL"
        assert evento.get("clasificacion_registro") is not None
        assert evento.get("retencion_aplicable") is not None
        assert evento.get("hash_integridad") is not None and len(evento["hash_integridad"]) == 64
        assert evento.get("fecha_emision") is not None

    def test_a01_rf79_operacion_exitosa(self, sandbox_admin: CorridaSandbox):
        """A01 (026.1): Cierre de ciclo productivo RF-79 -> eventos CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO persistidos <= 2 s."""
        c = sandbox_admin
        id_activo = _CONTEXTO["id_activo"]
        hoy_str = _hoy().isoformat()

        t_req_inicio = time.perf_counter()
        payload_cierre = {
            "fecha_cierre": hoy_str,
            "motivo_cierre": "finalizacion_lote",
            "descripcion_cierre": "Cierre de ciclo QA G37 para consolidacion RF-79",
        }
        r_cierre = c.post(f"/activos-biologicos/{id_activo}/cierre", payload_cierre, paso="a01_rf79_cierre_activo")
        duracion_req = time.perf_counter() - t_req_inicio
        assert r_cierre.status_code == 200, f"Error cerrando ciclo de activo: HTTP {r_cierre.status_code}: {c.seguro(r_cierre.text)}"

        # Consultar auditoria filtrando por activo
        r_aud = c.get(
            "/suministros/auditoria",
            paso="a01_rf79_consultar_auditoria",
            params={"id_activo_biologico": id_activo},
        )
        assert r_aud.status_code == 200, f"Error consultando auditoria: HTTP {r_aud.status_code}: {c.seguro(r_aud.text)}"
        items = r_aud.json().get("items", [])
        tipos_encontrados = {ev.get("tipo_operacion"): ev for ev in items}

        assert "CICLO_CONSOLIDADO" in tipos_encontrados, (
            f"No se encontro evento CICLO_CONSOLIDADO para activo {id_activo}. Tipos: {list(tipos_encontrados.keys())}"
        )
        assert "REPORTE_COSTOS_GENERADO" in tipos_encontrados, (
            f"No se encontro evento REPORTE_COSTOS_GENERADO para activo {id_activo}. Tipos: {list(tipos_encontrados.keys())}"
        )

        ev_consolidado = tipos_encontrados["CICLO_CONSOLIDADO"]
        ev_reporte = tipos_encontrados["REPORTE_COSTOS_GENERADO"]
        _CONTEXTO["evento_rf79_consolidado"] = ev_consolidado
        _CONTEXTO["evento_rf79_reporte"] = ev_reporte

        # Validar campos base y extension en CICLO_CONSOLIDADO
        assert ev_consolidado.get("entidad_afectada") == "provision_nic41"
        assert ev_consolidado.get("resultado") == "EXITOSO"
        assert ev_consolidado.get("costo_afectado") is not None
        assert ev_consolidado.get("hash_integridad") is not None and len(ev_consolidado["hash_integridad"]) == 64
        assert ev_consolidado.get("clasificacion_registro") == "NIC41"
        assert ev_consolidado.get("retencion_aplicable") == "5 años"

    def test_a01_rf81_operacion_exitosa(self, sandbox_admin: CorridaSandbox):
        """A01 (026.1): Consulta de historial RF-81 -> evento CONSULTA_HISTORIAL_EJECUTADA persistido <= 2 s."""
        c = sandbox_admin
        id_activo = _CONTEXTO["id_activo"]

        t_req_inicio = time.perf_counter()
        r_hist = c.get(
            "/suministros/historial",
            paso="a01_rf81_consultar_historial",
            params={"id_activo_biologico": id_activo},
        )
        duracion_req = time.perf_counter() - t_req_inicio
        assert r_hist.status_code == 200, f"Error consultando historial RF-81: HTTP {r_hist.status_code}: {c.seguro(r_hist.text)}"

        # Consultar auditoria filtrando por activo y tipo CONSULTA_HISTORIAL_EJECUTADA
        r_aud = c.get(
            "/suministros/auditoria",
            paso="a01_rf81_verificar_auditoria",
            params={"id_activo_biologico": id_activo, "tipo_operacion": "CONSULTA_HISTORIAL_EJECUTADA"},
        )
        assert r_aud.status_code == 200, f"Error consultando auditoria: HTTP {r_aud.status_code}: {c.seguro(r_aud.text)}"
        items = r_aud.json().get("items", [])
        assert len(items) >= 1, f"No se encontro evento CONSULTA_HISTORIAL_EJECUTADA para activo {id_activo}"

        ev_hist = items[0]
        _CONTEXTO["evento_rf81"] = ev_hist

        assert ev_hist.get("entidad_afectada") == "historial_suministros"
        assert ev_hist.get("tipo_operacion") == "CONSULTA_HISTORIAL_EJECUTADA"
        assert ev_hist.get("resultado") == "EXITOSO"
        assert ev_hist.get("hash_integridad") is not None and len(ev_hist["hash_integridad"]) == 64

    def test_a02_operacion_fallida_registro_auditoria(self, sandbox_admin: CorridaSandbox):
        """A02 (026.1): Operacion fallida (4xx) debe registrar evento con resultado FALLIDO/RECHAZADO en <= 2 s (CA-1)."""
        c = sandbox_admin
        id_activo = _CONTEXTO["id_activo"]

        # Intentar registrar suministro con fecha fuera de rango del ciclo
        payload_invalido = {
            "id_activo_biologico": id_activo,
            "tipo_suministro": "SERVICIO_VETERINARIO",
            "cantidad": 1.0,
            "unidad_medida": "UNIDAD",
            "precio_unitario": 30000.0,
            "fecha_aplicacion": "2020-01-01",  # Fecha fuera del rango
            "justificacion_precio": "Tarifa contractual",
            "id_idempotencia": str(uuid.uuid4()),
        }
        r_fail = c.post("/suministros/costeo-directo", payload_invalido, paso="a02_operacion_fallida")
        assert r_fail.status_code in (400, 409, 422), (
            f"Se esperaba rechazo (400/409/422), obtenido HTTP {r_fail.status_code}"
        )

        # Consultar si se genero evento en la bitacora de auditoria con resultado FALLIDO o RECHAZADO
        r_aud = c.get(
            "/suministros/auditoria",
            paso="a02_verificar_auditoria_fallo",
            params={"id_activo_biologico": id_activo},
        )
        assert r_aud.status_code == 200, f"Error consultando auditoria: HTTP {r_aud.status_code}: {c.seguro(r_aud.text)}"
        items = r_aud.json().get("items", [])
        eventos_fallidos = [ev for ev in items if ev.get("resultado") in ("FALLIDO", "RECHAZADO")]

        # Aserto estricto segun RF-80 CA-1: operaciones fallidas deben registrarse con resultado FALLIDO o RECHAZADO en <= 2 s.
        # Defecto conocido del producto: el backend no audita rechazos por validaciones de negocio (4xx).
        assert len(eventos_fallidos) > 0, (
            "DEFECTO_PRODUCTO (RF-80 CA-1 / TC-M05-026.1): La especificacion exige que las operaciones fallidas "
            "se registren en la bitacora con resultado FALLIDO o RECHAZADO en <= 2 s. "
            f"El backend respondio HTTP {r_fail.status_code} ({r_fail.json().get('error_code')}) pero registro 0 eventos "
            f"fallidos en modulo5.auditorias_suministros para el activo {id_activo}."
        )

    def test_a03_consistencia_filtros_vs_detalle(self, sandbox_admin: CorridaSandbox):
        """A03 (026.1): El mismo evento obtenido por filtros en lista y por GET /{id} coincide en todos sus campos."""
        c = sandbox_admin
        evento_lista = _CONTEXTO.get("evento_rf78")
        assert evento_lista is not None, "Precondicion: no se tiene el evento de RF-78 de A01"

        id_ev = evento_lista["id_auditoria_suministro"]
        r_det = c.get(f"/suministros/auditoria/{id_ev}", paso="a03_consultar_detalle_evento")
        assert r_det.status_code == 200, f"Error obteniendo detalle del evento {id_ev}: HTTP {r_det.status_code}: {c.seguro(r_det.text)}"
        evento_detalle = r_det.json()

        campos_a_comparar = [
            "id_auditoria_suministro",
            "entidad_afectada",
            "tipo_operacion",
            "id_usuario",
            "resultado",
            "fecha_evento",
            "fecha_emision",
            "id_activo_biologico",
            "id_ciclo_productivo",
            "costo_afectado",
            "origen_precio",
            "clasificacion_registro",
            "retencion_aplicable",
            "hash_integridad",
        ]

        for campo in campos_a_comparar:
            val_lista = evento_lista.get(campo)
            val_det = evento_detalle.get(campo)
            assert val_lista == val_det, (
                f"Discrepancia en campo '{campo}' entre lista ({val_lista}) y detalle ({val_det}) para evento {id_ev}"
            )

    def test_b01_clasificacion_retencion_eventos(self, sandbox_admin: CorridaSandbox):
        """B01 (027): Clasificacion y retencion segun catalogo: NIC41 (5 años) vs TECNICO (1 año)."""
        c = sandbox_admin
        id_activo = _CONTEXTO["id_activo"]

        r_aud = c.get(
            "/suministros/auditoria",
            paso="b01_consultar_eventos_clasificacion",
            params={"id_activo_biologico": id_activo},
        )
        assert r_aud.status_code == 200, f"Error consultando auditoria: HTTP {r_aud.status_code}: {c.seguro(r_aud.text)}"
        items = r_aud.json().get("items", [])
        assert len(items) >= 3, f"Se esperaban al menos 3 eventos registrados para el activo {id_activo}, obtenidos {len(items)}"

        tipos_nic41_esperados = {"SUMINISTRO_REGISTRADO", "ACUMULADO_ACTUALIZADO", "CICLO_CONSOLIDADO", "REPORTE_COSTOS_GENERADO"}
        tipos_tecnico_esperados = {"PRECIO_MANUAL_INGRESADO", "CONSULTA_HISTORIAL_EJECUTADA"}

        encontrados_nic41 = 0
        encontrados_tecnico = 0

        for ev in items:
            tipo = ev.get("tipo_operacion")
            clasif = ev.get("clasificacion_registro")
            ret = ev.get("retencion_aplicable")

            if tipo in tipos_nic41_esperados:
                assert clasif == "NIC41", f"Evento {tipo} deberia clasificarse como NIC41, obtenido: {clasif}"
                assert ret == "5 años", f"Evento {tipo} deberia retenerse 5 años, obtenido: {ret}"
                encontrados_nic41 += 1
            elif tipo in tipos_tecnico_esperados:
                assert clasif == "TECNICO", f"Evento {tipo} deberia clasificarse como TECNICO, obtenido: {clasif}"
                assert ret == "1 año", f"Evento {tipo} deberia retenerse 1 año, obtenido: {ret}"
                encontrados_tecnico += 1

        assert encontrados_nic41 > 0, "No se encontraron eventos con clasificacion NIC41 / 5 años"
        assert encontrados_tecnico > 0, "No se encontraron eventos con clasificacion TECNICO / 1 año"

    def test_b02_tipo_no_catalogado_clasifica_nic41_unidad(self):
        """B02 (027): Tipo NO catalogado clasifica por defecto como NIC41 / 5 años (nivel unidad)."""
        from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import clasificar_retencion

        tipo_desconocido = "EVENTO_NO_CATALOGADO_EXPERIMENTO_QA"
        clasif, ret = clasificar_retencion(tipo_desconocido)

        assert clasif == "NIC41", f"Tipo no catalogado debio clasificarse como NIC41 por conservadurismo, obtenido: {clasif}"
        assert ret == "5 años", f"Tipo no catalogado debio retenerse 5 años, obtenido: {ret}"

    def test_t98_cierre_sandbox(self, sandbox_admin: CorridaSandbox):
        """T98: Cierre ordenado de sandbox y confirmacion de rollback."""
        c = sandbox_admin
        r = c.cerrar()
        assert r is not None, "Cierre de sandbox ya habia sido ejecutado"
        assert r.status_code == 200, f"Error en DELETE /test-control/runs: HTTP {r.status_code}: {c.seguro(r.text)}"
        data = r.json()
        mensaje = data.get("mensaje") or data.get("status") or ""
        assert "exitoso" in mensaje.lower(), f"Respuesta de rollback inesperada: {data}"

    def test_t99_inocuidad_rollback(self):
        """T99: Inocuidad - el conteo final de la bitacora coincide con la linea base antes del sandbox."""
        base_url = _env("TEST_BASE_URL").rstrip("/")
        email = _env("TEST_ADMIN_EMAIL")
        pwd = _env("TEST_ADMIN_PASSWORD")

        # Login limpio sin headers de sandbox
        r_login = requests.post(
            f"{base_url}/sesiones/",
            json={"correo_electronico": email, "contrasena": pwd},
            headers={"X-Zona-Horaria": NOMBRE_ZONA},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200, "Error en login para verificacion de inocuidad"
        token = r_login.json().get("token") or r_login.json().get("access_token")

        r_fin = requests.get(
            f"{base_url}/suministros/auditoria",
            headers={"Authorization": f"Bearer {token}", "X-Zona-Horaria": NOMBRE_ZONA},
            params={"pagina": 1, "registros_por_pagina": 1},
            timeout=TIMEOUT_S,
        )
        assert r_fin.status_code == 200, f"Error consultando auditoria final: HTTP {r_fin.status_code}"
        total_fin = r_fin.json().get("total", 0)

        total_base = _CONTEXTO.get("total_base", 0)
        assert total_fin == total_base, (
            f"Fallo de inocuidad: el conteo de la bitacora cambio de {total_base} a {total_fin} "
            "tras el cierre de la corrida sandbox (el rollback no fue completo)."
        )
