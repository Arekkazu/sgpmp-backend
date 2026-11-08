# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G38: Consulta de bitacora y cadena de custodia RF-80 (CU06)    |
"""Suite de pruebas para TC-M05-G38: Consulta de bitacora y cadena de custodia (RF-80).

Cubre los casos TC-M05-032 y TC-M05-044:
- Reconstruccion de cadena de custodia cronologica con doble timestamp (fecha_evento y fecha_emision).
- Exportacion filtrada por activo en CSV, XLSX y PDF; validacion de formato no soportado (400).
- Manejo de filtros invalidos (formato de fecha y fecha_desde > fecha_hasta).
- Consulta sin coincidencias y verificacion de auto-auditoria segun CU06 FA-02.
- Restriccion estricta RBAC para Veterinario (403 ACCESO_DENEGADO sin fuga de datos).
- Verificacion de registro de evento de seguridad ante intento denegado (caso 044.3).
- Cierres ordenados e inocuidad para corridas secuenciales de Administrador y Veterinario.
"""
from __future__ import annotations

import io
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

_CONTEXTO_ADMIN: dict[str, Any] = {
    "total_base": 0,
    "id_activo": None,
    "id_fase": None,
}

_CONTEXTO_VET: dict[str, Any] = {
    "total_seg_base": 0,
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


class CorridaSandboxRol:
    def __init__(self, prefijo_rol: str, email_env: str, pass_env: str) -> None:
        self.prefijo_rol = prefijo_rol
        self.email_env = email_env
        self.pass_env = pass_env
        self.run_id = f"tc-m05-g38-{prefijo_rol}-{uuid.uuid4().hex[:8]}"
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
        email = _env(self.email_env)
        pwd = _env(self.pass_env)
        r = self.post(
            "/sesiones/",
            {"correo_electronico": email, "contrasena": pwd},
            paso=f"login_{self.prefijo_rol}",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: login {self.prefijo_rol} HTTP {r.status_code}: {self.seguro(r.text)}"
        )
        token = r.json().get("token") or r.json().get("access_token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: login {self.prefijo_rol} sin token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"

    def cerrar(self) -> requests.Response | None:
        if self.cerrada:
            return None
        self.cerrada = True
        try:
            return self._enviar("DELETE", f"/test-control/runs/{self.run_id}", paso=f"teardown_{self.prefijo_rol}")
        finally:
            self.http.close()


@pytest.fixture(autouse=True)
def _marcar_test(request: pytest.FixtureRequest):
    global _TEST_ACTUAL
    _TEST_ACTUAL = request.node.name
    yield


_CORRIDA_ADMIN: CorridaSandboxRol | None = None
_CORRIDA_VET: CorridaSandboxRol | None = None


@pytest.fixture(scope="class")
def sandbox_admin():
    global _CORRIDA_ADMIN
    if _CORRIDA_ADMIN is None:
        _CORRIDA_ADMIN = CorridaSandboxRol("adm", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD")
        _CORRIDA_ADMIN.login()
    return _CORRIDA_ADMIN


@pytest.fixture(scope="class")
def sandbox_vet():
    global _CORRIDA_VET
    if _CORRIDA_VET is None:
        _CORRIDA_VET = CorridaSandboxRol("vet", "TEST_VET_EMAIL", "TEST_VET_PASSWORD")
        _CORRIDA_VET.login()
    return _CORRIDA_VET


class TestTCM05G38ConsultaYCadenaCustodia:
    """TC-M05-G38: Consulta de bitacora, cadena de custodia y control de accesos."""

    # =========================================================================
    # CORRIDA ADMIN
    # =========================================================================

    def test_t00_admin_setup(self, sandbox_admin: CorridaSandboxRol):
        """T00 Admin: Conteo inicial de eventos y creacion de activo con operaciones propias."""
        c = sandbox_admin

        # Conteo base
        r_ini = c.get("/suministros/auditoria", paso="t00_admin_conteo_base", params={"pagina": 1, "registros_por_pagina": 1})
        assert r_ini.status_code == 200, f"Error obteniendo conteo inicial: HTTP {r_ini.status_code}"
        _CONTEXTO_ADMIN["total_base"] = r_ini.json().get("total", 0)

        # Crear activo poblacional dedicado
        tag = uuid.uuid4().hex[:8]
        hoy = _hoy()
        fecha_ciclo = (hoy - timedelta(days=20)).isoformat()
        payload_activo = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G38-{tag}",
            "cantidad_inicial": 40,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
            "peso_actual": 18.0,
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="t00_admin_crear_activo")
        assert r_act.status_code == 201, f"Fallo creando activo: HTTP {r_act.status_code}: {c.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None
        _CONTEXTO_ADMIN["id_activo"] = id_activo

        # Abrir fase productiva
        payload_fase = {"id_ciclo_productiva": 1, "motivo_cambio": "Fase para prueba de cadena de custodia G38"}
        r_fase = c.post(f"/activos-biologicos/{id_activo}/fases", payload_fase, paso="t00_admin_abrir_fase")
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}"
        id_fase = r_fase.json().get("id_gestion_fases")
        _CONTEXTO_ADMIN["id_fase"] = id_fase

        # Registrar suministro directo 1
        r_s1 = c.post(
            "/suministros/costeo-directo",
            {
                "id_activo_biologico": id_activo,
                "tipo_suministro": "SERVICIO_VETERINARIO",
                "cantidad": 1.0,
                "unidad_medida": "UNIDAD",
                "precio_unitario": 55000.0,
                "fecha_aplicacion": hoy.isoformat(),
                "justificacion_precio": "Servicio veterinario preventivo",
                "id_idempotencia": str(uuid.uuid4()),
            },
            paso="t00_admin_suministro_1",
        )
        assert r_s1.status_code == 200, f"Fallo suministro 1: HTTP {r_s1.status_code}"

        # Registrar suministro directo 2
        r_s2 = c.post(
            "/suministros/costeo-directo",
            {
                "id_activo_biologico": id_activo,
                "tipo_suministro": "INSEMINACION",
                "cantidad": 1.0,
                "unidad_medida": "DOSIS",
                "precio_unitario": 75000.0,
                "fecha_aplicacion": hoy.isoformat(),
                "justificacion_precio": "Material reproductivo de alta genetica",
                "id_idempotencia": str(uuid.uuid4()),
            },
            paso="t00_admin_suministro_2",
        )
        assert r_s2.status_code == 200, f"Fallo suministro 2: HTTP {r_s2.status_code}"

    def test_a01_cadena_custodia_secuencia_completa(self, sandbox_admin: CorridaSandboxRol):
        """A01 (032.1): Cadena de custodia: eventos completos, cronologicos y con doble timestamp visible (CA-4, CA-13)."""
        c = sandbox_admin
        id_activo = _CONTEXTO_ADMIN["id_activo"]

        # Consultar la secuencia de auditoria filtrando por el activo de la corrida
        r_aud = c.get(
            "/suministros/auditoria",
            paso="a01_cadena_custodia",
            params={"id_activo_biologico": id_activo},
        )
        assert r_aud.status_code == 200, f"Error consultando auditoria: HTTP {r_aud.status_code}"
        items = r_aud.json().get("items", [])
        assert len(items) >= 4, f"Se esperaban al menos 4 eventos para la cadena de custodia del activo {id_activo}, obtenidos {len(items)}"

        # Verificar presencia de doble timestamp (fecha_evento y fecha_emision) en cada evento
        for ev in items:
            fe_ev = ev.get("fecha_evento")
            fe_em = ev.get("fecha_emision")
            assert fe_ev is not None, f"Evento {ev.get('id_auditoria_suministro')} carece de fecha_evento"
            assert fe_em is not None, f"Evento {ev.get('id_auditoria_suministro')} carece de fecha_emision (timestamp_emision)"
            assert ev.get("hash_integridad") is not None and len(ev["hash_integridad"]) == 64

        # Verificar orden cronologico (la API ordena por fecha_evento DESC)
        fechas = [ev["fecha_evento"] for ev in items]
        fechas_ordenadas = sorted(fechas, reverse=True)
        assert fechas == fechas_ordenadas, "Los eventos de auditoria no estan ordenados cronologicamente por fecha_evento descendente"

    def test_a02_exportacion_formatos_filtro_activo(self, sandbox_admin: CorridaSandboxRol):
        """A02 (032.2): Exportacion filtrada en CSV, XLSX y PDF; validacion de formato no soportado (400)."""
        c = sandbox_admin
        id_activo = _CONTEXTO_ADMIN["id_activo"]

        # 1. Exportacion CSV
        r_csv = c.get(
            "/suministros/auditoria/exportar",
            paso="a02_exportar_csv",
            params={"id_activo_biologico": id_activo, "formato": "csv"},
        )
        assert r_csv.status_code == 200, f"Error exportando CSV: HTTP {r_csv.status_code}"
        assert "text/csv" in r_csv.headers.get("content-type", "")
        texto_csv = r_csv.text
        assert "id_auditoria_suministro" in texto_csv
        assert "hash_integridad" in texto_csv
        lineas_csv = [l for l in texto_csv.strip().splitlines() if l.strip()]
        # Encabezado + al menos 4 registros
        assert len(lineas_csv) >= 5, f"CSV exportado contiene pocas lineas ({len(lineas_csv)})"

        # 2. Exportacion XLSX
        r_xlsx = c.get(
            "/suministros/auditoria/exportar",
            paso="a02_exportar_xlsx",
            params={"id_activo_biologico": id_activo, "formato": "xlsx"},
        )
        assert r_xlsx.status_code == 200, f"Error exportando XLSX: HTTP {r_xlsx.status_code}"
        assert "openxmlformats" in r_xlsx.headers.get("content-type", "")
        assert r_xlsx.content[:4] == b"PK\x03\x04", "El archivo XLSX no tiene la firma ZIP valida"

        # Validar estructura interna de XLSX con openpyxl
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content))
        assert "Auditoria Suministros" in wb.sheetnames
        ws = wb["Auditoria Suministros"]
        assert ws.max_row >= 5, f"La hoja de Excel contiene pocas filas ({ws.max_row})"

        # 3. Exportacion PDF
        r_pdf = c.get(
            "/suministros/auditoria/exportar",
            paso="a02_exportar_pdf",
            params={"id_activo_biologico": id_activo, "formato": "pdf"},
        )
        assert r_pdf.status_code == 200, f"Error exportando PDF: HTTP {r_pdf.status_code}"
        assert "application/pdf" in r_pdf.headers.get("content-type", "")
        assert r_pdf.content[:4] == b"%PDF", "El archivo PDF no tiene la firma PDF valida"

        # 4. Formato no soportado
        r_inv = c.get(
            "/suministros/auditoria/exportar",
            paso="a02_exportar_formato_invalido",
            params={"formato": "doc"},
        )
        assert r_inv.status_code in (400, 422), f"Se esperaba 400 ante formato invalido, obtenido HTTP {r_inv.status_code}"
        # Se documenta error_code sin hacerlo criterio estricto
        codigo_error = r_inv.json().get("error_code")
        assert codigo_error is not None

    def test_b01_filtros_invalidos(self, sandbox_admin: CorridaSandboxRol):
        """B01 (044.1): Filtros invalidos (formato de fecha y fecha_desde > fecha_hasta) deben retornar 4xx (CA-1 / TC-M05-044.1)."""
        c = sandbox_admin

        # Formato de fecha invalido -> 400 VAL_ENTRADA
        r_fmt = c.get(
            "/suministros/auditoria",
            paso="b01_fecha_formato_invalido",
            params={"fecha_desde": "fecha_invalida_no_iso"},
        )
        assert r_fmt.status_code in (400, 422), f"Se esperaba 400/422 ante formato de fecha invalido, obtenido HTTP {r_fmt.status_code}"

        # Rango invertido: fecha_desde > fecha_hasta -> la especificacion exige 4xx con mensaje de correccion
        r_rango = c.get(
            "/suministros/auditoria",
            paso="b01_rango_fechas_invertido",
            params={"fecha_desde": "2026-12-01T00:00:00Z", "fecha_hasta": "2026-11-01T00:00:00Z"},
        )
        # Defecto conocido de producto: el endpoint responde 200 con lista vacia en vez de validar el rango con 4xx
        assert r_rango.status_code in (400, 422), (
            "DEFECTO_PRODUCTO (TC-M05-044.1 / RNF Validacion): La especificacion requiere que la combinacion "
            f"invalida fecha_desde > fecha_hasta retorne HTTP 4xx con mensaje explicativo. Obtenido HTTP {r_rango.status_code} "
            f"(el endpoint retorno 200 con lista vacia sin validar la coherencia temporal de los filtros)."
        )

    def test_b02_consulta_sin_coincidencias_autoauditoria(self, sandbox_admin: CorridaSandboxRol):
        """B02 (044.2): Filtro valido sin coincidencias retorna 200 vacio y debe registrar la consulta (+1 evento) segun CU06 FA-02."""
        c = sandbox_admin

        # Conteo antes
        r_antes = c.get("/suministros/auditoria", paso="b02_conteo_antes", params={"pagina": 1, "registros_por_pagina": 1})
        total_antes = r_antes.json().get("total", 0)

        # Consulta con filtro valido sin coincidencias (activo inexistente en rango)
        r_vacia = c.get(
            "/suministros/auditoria",
            paso="b02_consulta_sin_coincidencias",
            params={"id_activo_biologico": 99999999},
        )
        assert r_vacia.status_code == 200, f"Error en consulta: HTTP {r_vacia.status_code}"
        data_vacia = r_vacia.json()
        assert data_vacia.get("total") == 0, f"Se esperaba total 0, obtenido: {data_vacia.get('total')}"
        assert data_vacia.get("items") == []

        # Conteo despues
        r_despues = c.get("/suministros/auditoria", paso="b02_conteo_despues", params={"pagina": 1, "registros_por_pagina": 1})
        total_despues = r_despues.json().get("total", 0)

        # Defecto conocido / Discrepancia de diseno: CU06 FA-02 estipula que la consulta de bitacora se auto-audita.
        # En la implementacion (consultar_auditoria_suministros_use_case.py), la consulta es de solo lectura y no se auto-audita.
        assert total_despues == total_antes + 1, (
            "DEFECTO_PRODUCTO / CONFLICTO DE DISENO (CU06 FA-02 vs Catalogo / TC-M05-044.2): "
            "La especificacion CU06 FA-02 establece que la ejecucion de consultas a la bitacora debe auditarse (+1 evento). "
            f"El conteo total se mantuvo en {total_despues} (sin incremento), ya que ConsultarAuditoriaSuministrosUseCase "
            "no implementa auto-auditoria al no haberse definido un evento de negocio para consultas a la bitacora de M05."
        )

    def test_t98_admin_cierre_sandbox(self, sandbox_admin: CorridaSandboxRol):
        """T98 Admin: Cierre ordenado de sandbox Administrador y confirmacion de rollback."""
        c = sandbox_admin
        r = c.cerrar()
        assert r is not None, "Cierre de sandbox ya ejecutado"
        assert r.status_code == 200, f"Error cerrando sandbox admin: HTTP {r.status_code}"
        data = r.json()
        mensaje = data.get("mensaje") or data.get("status") or ""
        assert "exitoso" in mensaje.lower(), f"Respuesta de rollback inesperada: {data}"

    def test_t99_admin_inocuidad(self):
        """T99 Admin: Inocuidad de la corrida Administrador fuera de sandbox."""
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
        assert total_fin == _CONTEXTO_ADMIN.get("total_base", 0), (
            f"Inocuidad fallida: el conteo de la bitacora cambio de {_CONTEXTO_ADMIN.get('total_base')} a {total_fin}"
        )

    # =========================================================================
    # CORRIDA VETERINARIO
    # =========================================================================

    def test_c01_vet_acceso_denegado_endpoints_auditoria(self, sandbox_vet: CorridaSandboxRol):
        """C01 Vet (044.3): Veterinario recibe HTTP 403 ACCESO_DENEGADO en lista, detalle y exportar sin fuga de datos."""
        c = sandbox_vet

        # 1. GET lista
        r_list = c.get("/suministros/auditoria", paso="c01_vet_get_lista")
        assert r_list.status_code == 403, f"Se esperaba 403 en GET lista, obtenido HTTP {r_list.status_code}"
        assert r_list.json().get("error_code") == "ACCESO_DENEGADO"
        assert "items" not in r_list.json(), "Fuga de datos: respuesta 403 contiene clave 'items'"

        # 2. GET detalle
        r_det = c.get("/suministros/auditoria/1", paso="c01_vet_get_detalle")
        assert r_det.status_code == 403, f"Se esperaba 403 en GET detalle, obtenido HTTP {r_det.status_code}"
        assert r_det.json().get("error_code") == "ACCESO_DENEGADO"

        # 3. GET exportar
        r_exp = c.get("/suministros/auditoria/exportar", paso="c01_vet_get_exportar", params={"formato": "csv"})
        assert r_exp.status_code == 403, f"Se esperaba 403 en GET exportar, obtenido HTTP {r_exp.status_code}"
        assert r_exp.json().get("error_code") == "ACCESO_DENEGADO"

    def test_c02_vet_intento_denegado_evento_seguridad(self, sandbox_vet: CorridaSandboxRol):
        """C02 Vet (044.3): Intento no autorizado debe generar un evento de seguridad (conteo +1)."""
        c = sandbox_vet

        # Consultar via /test-control/query eventos de auditoria o seguridad
        r_q_audit = c.post(
            "/test-control/query",
            {"query": "SELECT count(*) FROM modulo5.auditorias_suministros WHERE resultado = 'RECHAZADO'"},
            paso="c02_query_auditorias_rechazadas",
        )
        assert r_q_audit.status_code == 200, f"Error consultando test-control/query: HTTP {r_q_audit.status_code}"
        conteo_rechazados = r_q_audit.json().get("data", [{}])[0].get("count", 0)

        # Defecto conocido de producto: el middleware de autorizacion RBAC (src/shared/rbac.py) lanza
        # AuthorizationError(code='ACCESO_DENEGADO') sin escribir en ninguna bitacora de auditoria o seguridad.
        assert conteo_rechazados > 0, (
            "DEFECTO_PRODUCTO (RF-80 / TC-M05-044.3): La especificacion de seguridad requiere que los intentos de "
            "acceso denegados a la bitacora de auditoria registren un evento de seguridad. "
            f"El backend respondio HTTP 403 ACCESO_DENEGADO ante las 3 solicitudes del Veterinario pero registro 0 eventos "
            f"con resultado RECHAZADO en modulo5.auditorias_suministros."
        )

    def test_c98_vet_cierre_sandbox(self, sandbox_vet: CorridaSandboxRol):
        """C98 Vet: Cierre ordenado de sandbox Veterinario y confirmacion de rollback."""
        c = sandbox_vet
        r = c.cerrar()
        assert r is not None, "Cierre de sandbox Veterinario ya ejecutado"
        assert r.status_code == 200, f"Error cerrando sandbox vet: HTTP {r.status_code}"
        data = r.json()
        mensaje = data.get("mensaje") or data.get("status") or ""
        assert "exitoso" in mensaje.lower(), f"Respuesta de rollback inesperada: {data}"

    def test_c99_vet_inocuidad(self):
        """C99 Vet: Inocuidad de la corrida Veterinario fuera de sandbox."""
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
        assert total_fin == _CONTEXTO_ADMIN.get("total_base", 0), (
            f"Inocuidad fallida tras corrida Veterinario: total esperado {_CONTEXTO_ADMIN.get('total_base')}, obtenido {total_fin}"
        )

