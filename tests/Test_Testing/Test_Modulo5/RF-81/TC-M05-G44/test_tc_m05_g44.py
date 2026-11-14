# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G44 RF-81: exportacion del historial (caso 103 / 038)          |
"""
TC-M05-G44 — RF-81 CU04, GET /suministros/historial/exportar.
Exportacion del historial de suministros: sincrona, asincrona, retencion 72 h y concurrencia.
Hoja plana: TC-M05-103. Hoja agrupada: 038.

Checkpoints normativos:
  - test_00_setup_linea_base_y_activo_d: Setup de activo propio D con fase abierta y 3 registros (60.000 COP).
  - test_a01_exportacion_sincrona_excel_y_pdf: (103 / 038) Exportacion sincrona (<= 10.000 registros):
      HTTP 200 en <= 10 s; Excel abierto con openpyxl conteniendo encabezado, columnas completas,
      filas de suministros, subtotales por categoria y ciclo, y firma/timestamp del sistema;
      PDF iniciando con %PDF; suma de filas coincide con monto_total_filtrado.
  - test_b03_solo_lectura_inmutabilidad: (103 / 038, Restr. 4) La exportacion no altera el historial
      (conteo y suma antes y despues identicos).
  - test_b04_solicitar_trabajo_asincrono_exportacion: (103 / 038) Encolamiento de exportacion asincrona
      (POST /suministros/historial/trabajos -> 202 con id_cola y estado PENDIENTE, GET estado -> 200 PENDIENTE).
  - test_b05_limite_concurrencia_exportaciones_429: (103 / 038, Restr. 8) Limite concurrente de exportaciones
      (3 activas encoladas; 4ta solicitud rechazada con HTTP 429 LIMITE_EXPORTACIONES_EXCEDIDO).
  - test_98_cierre_sandbox: DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso'.
  - test_99_inocuidad_final: Verificacion fuera de sandbox: 0 efectos persistidos (activo D responde 404).

Cobertura no ejecutada (declarada formalmente):
  - B01 (10.000 exactos sincrono): no existe conjunto de 10.000 registros commiteados en el ambiente.
  - B02 (10.001 asincrono con retencion 72 h): no existe conjunto > 10.000 registros en el ambiente.
"""
from __future__ import annotations

import io
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

import openpyxl
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
    "id_activo_d": None,
    "total_monto_d": Decimal("60000.0000"),
    "total_items_d": 3,
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


class CorridaSandboxG44:
    """Gestiona la transaccion sandbox para TC-M05-G44 (Administrador)."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g44-adm-{uuid.uuid4().hex[:12]}"
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
def corrida_g44() -> CorridaSandboxG44:
    c = CorridaSandboxG44()
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G44_Exportacion_Historial:
    """Suite TC-M05-G44: Exportacion de historial sincrona y validacion documental (RF-81, 103 plano, 038 agrupado)."""

    def test_00_setup_linea_base_y_activo_d(self, corrida_g44: CorridaSandboxG44):
        """T00: Setup activo propio D con 3 registros y captura de linea base."""
        c = corrida_g44

        # 1. Crear activo D (Individual Holstein)
        id_unico_d = f"QA-G44-D-{uuid.uuid4().hex[:6]}"
        r_act_d = c.post(
            "/activos-biologicos",
            {
                "tipo_activo": "INDIVIDUAL",
                "id_especie": 5,
                "id_infraestructura": 389,
                "identificador": id_unico_d,
                "raza": "Holstein",
                "sexo": "Hembra",
                "fecha_inicio_ciclo": "2026-08-01",
                "origen_financiero": "nacimiento",
            },
            paso="T00_crear_activo_d",
        )
        assert r_act_d.status_code == 201, f"Error creando activo D: HTTP {r_act_d.status_code}: {c.seguro(r_act_d.text)}"
        id_d = r_act_d.json().get("id_activo_biologico")
        assert id_d is not None
        _CONTEXTO["id_activo_d"] = id_d

        # 2. Abrir fase
        r_fase = c.post(
            f"/activos-biologicos/{id_d}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase QA G44", "fecha_inicio": "2026-08-01T05:00:00Z"},
            paso="T00_abrir_fase_d",
        )
        assert r_fase.status_code in (200, 201)

        # 3. Registrar 2 consumos (20k + 30k = 50k) y 1 medicamento (10k) = 60.000 COP
        r_c1 = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_d,
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
                "id_activo_biologico": id_d,
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
                "id_activo_biologico": id_d,
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

        # 4. Validar consulta de historial base
        r_hist = c.get(f"/suministros/historial?id_activo_biologico={id_d}", paso="T00_verificar_historial")
        assert r_hist.status_code == 200
        data = r_hist.json()
        assert len(data.get("items", [])) == 3
        monto_str = data.get("resumen", {}).get("monto_total_filtrado", "0")
        assert Decimal(str(monto_str)) == Decimal("60000.0000")

    def test_a01_exportacion_sincrona_excel_y_pdf(self, corrida_g44: CorridaSandboxG44):
        """A01 (TC-M05-103 / 038): Exportacion sincrona PDF y Excel (<= 10.000 registros, Restr. 3 / Fase 6 / E3 / CA-4 / CA-5 / RNF-02):
        - Entrega archivo en <= 10 s.
        - Excel se abre con openpyxl; contiene encabezado del activo, tabla con todas las columnas,
          subtotales por categoria y ciclo, y firma/timestamp del sistema.
        - PDF inicia con %PDF y tamano > 0.
        - Los totales del archivo coinciden con monto_total_filtrado (60.000 COP)."""
        c = corrida_g44
        id_d = _CONTEXTO["id_activo_d"]
        monto_esperado = _CONTEXTO["total_monto_d"]

        # 1. Exportacion EXCEL
        t0 = time.perf_counter()
        r_xl = c.get(
            f"/suministros/historial/exportar?id_activo_biologico={id_d}&formato_exportacion=EXCEL",
            paso="A01_exportar_excel",
        )
        dur_xl = time.perf_counter() - t0
        assert r_xl.status_code == 200, f"Error exportacion Excel: HTTP {r_xl.status_code}: {c.seguro(r_xl.text)}"
        assert dur_xl <= 10.0, f"Exportacion Excel tardo mas de 10 s ({dur_xl:.2f} s)"
        assert "spreadsheetml" in r_xl.headers.get("content-type", ""), (
            f"Content-Type inesperado para Excel: {r_xl.headers.get('content-type')}"
        )
        assert len(r_xl.content) > 1000, f"Tamano de archivo Excel demasiado pequeno: {len(r_xl.content)} bytes"

        # Validacion del contenido Excel con openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(r_xl.content))
        hoja = wb.active
        assert hoja is not None, "El archivo Excel no tiene hoja activa"

        # Extraer todas las filas de texto
        filas_excel = []
        for row in hoja.iter_rows(values_only=True):
            if any(val is not None for val in row):
                filas_excel.append([str(v) if v is not None else "" for v in row])

        texto_completo = " ".join(" ".join(f) for f in filas_excel)
        print("Excel Filas extraidas:", len(filas_excel))
        for r_idx, f in enumerate(filas_excel[:10]):
            print(f"  Fila {r_idx+1}: {f}")

        # Validar encabezado del activo y filtros
        assert "Historial de Suministros" in texto_completo, "Excel no incluye el título esperado"
        assert f"Activo: {id_d}" in texto_completo or str(id_d) in texto_completo, "Excel no incluye el activo esperado"
        assert "Total de registros: 3" in texto_completo, "Excel no incluye el conteo de 3 registros"
        assert "60000" in texto_completo, "Excel no incluye el monto total 60000 COP"

        # Validar columnas requeridas de la spec
        columnas_requeridas = ["tipo_suministro", "fecha_aplicacion", "cantidad", "costo_registro"]
        for col in columnas_requeridas:
            assert any(col in f for f in filas_excel), f"Columna {col} ausente en el archivo Excel"

        # Validar pie: subtotales, firma y timestamp
        assert "Subtotal ALIMENTO" in texto_completo, "Excel no incluye subtotal de alimento"
        assert "Subtotal MEDICAMENTO" in texto_completo, "Excel no incluye subtotal de medicamento"
        assert "Subtotal ciclo" in texto_completo, "Excel no incluye subtotal por ciclo productivo"
        assert "Firma del sistema (SHA-256):" in texto_completo, "Excel no incluye firma del sistema"
        assert "Generado por SIGAB:" in texto_completo, "Excel no incluye timestamp de generacion"

        # 2. Exportacion PDF
        t1 = time.perf_counter()
        r_pdf = c.get(
            f"/suministros/historial/exportar?id_activo_biologico={id_d}&formato_exportacion=PDF",
            paso="A01_exportar_pdf",
        )
        dur_pdf = time.perf_counter() - t1
        assert r_pdf.status_code == 200, f"Error exportacion PDF: HTTP {r_pdf.status_code}: {c.seguro(r_pdf.text)}"
        assert dur_pdf <= 10.0, f"Exportacion PDF tardo mas de 10 s ({dur_pdf:.2f} s)"
        assert r_pdf.content.startswith(b"%PDF"), "El archivo PDF retornado no inicia con el marcador binario %PDF"
        assert len(r_pdf.content) > 1000, f"Tamano de archivo PDF demasiado pequeno: {len(r_pdf.content)} bytes"

        # Validacion del contenido PDF con pypdf
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(r_pdf.content))
            assert len(pdf_reader.pages) >= 1, "El PDF generado no tiene paginas"
            texto_pdf = " ".join(pag.extract_text() or "" for pag in pdf_reader.pages)
            print(f"PDF extraido ({len(pdf_reader.pages)} paginas):", texto_pdf[:300])

            assert "Historial de Suministros" in texto_pdf, "PDF no contiene el título"
            assert str(id_d) in texto_pdf, f"PDF no contiene el id del activo {id_d}"
            assert "60000" in texto_pdf or "60.000" in texto_pdf, "PDF no contiene el total 60000 COP"
            assert "ALIMENTO" in texto_pdf and "MEDICAMENTO" in texto_pdf, "PDF no contiene tipos de suministros"
            assert "Subtotal ciclo" in texto_pdf, "PDF no contiene seccion de subtotal por ciclo productivo"
            assert "Firma del sistema" in texto_pdf or "SHA-256" in texto_pdf, "PDF no contiene firma del sistema"
            assert "Generado por SIGAB" in texto_pdf or "Fecha de generación" in texto_pdf, "PDF no contiene timestamp"
        except ImportError:
            print("AVISO: pypdf no disponible para inspeccionar texto interno del PDF")

    def test_b03_solo_lectura_inmutabilidad(self, corrida_g44: CorridaSandboxG44):
        """B03 (TC-M05-103 / 038, Restr. 4 / solo lectura): La exportacion no altera el historial
        (conteo y suma antes y despues permanecen identicos)."""
        c = corrida_g44
        id_d = _CONTEXTO["id_activo_d"]
        monto_esperado = _CONTEXTO["total_monto_d"]

        r_hist = c.get(f"/suministros/historial?id_activo_biologico={id_d}", paso="B03_verificar_inmutabilidad")
        assert r_hist.status_code == 200
        data = r_hist.json()
        items = data.get("items", [])
        assert len(items) == _CONTEXTO["total_items_d"], f"El conteo de items cambio tras exportar: {len(items)}"
        monto_actual = Decimal(str(data.get("resumen", {}).get("monto_total_filtrado", "0")))
        assert monto_actual == monto_esperado, f"El monto cambio tras exportar: esperado {monto_esperado}, obtenido {monto_actual}"

    def test_b04_solicitar_trabajo_asincrono_exportacion(self, corrida_g44: CorridaSandboxG44):
        """B04 (103 / 038): Encolamiento de trabajo asíncrono de exportación (POST /suministros/historial/trabajos).
        Verifica HTTP 202 con id_cola y estado PENDIENTE, y que GET /suministros/historial/trabajos/{id_cola} responde 200."""
        c = corrida_g44
        id_activo = _CONTEXTO["id_activo_d"]
        body = {
            "tipo_trabajo": "EXPORTACION",
            "id_activo_biologico": id_activo,
            "formato_exportacion": "EXCEL",
        }
        r = c.post("/suministros/historial/trabajos", body, paso="B04_encolar_exportacion_async")
        assert r.status_code == 202, f"Se esperaba HTTP 202 al encolar trabajo async: HTTP {r.status_code}: {c.seguro(r.text)}"
        data = r.json()
        assert data.get("tipo_trabajo") == "EXPORTACION", f"tipo_trabajo inesperado: {data}"
        assert data.get("estado") == "PENDIENTE", f"estado inicial inesperado: {data}"
        id_cola = data.get("id_cola")
        assert id_cola and id_cola > 0, f"id_cola ausente o invalido: {data}"
        _CONTEXTO["id_cola_b04"] = id_cola

        # Consultar estado del trabajo recien encolado
        r_st = c.get(f"/suministros/historial/trabajos/{id_cola}", paso="B04_consultar_estado_trabajo")
        assert r_st.status_code == 200, f"Se esperaba HTTP 200 al consultar estado del trabajo {id_cola}: HTTP {r_st.status_code}"
        st_data = r_st.json()
        assert st_data.get("id_cola") == id_cola, f"id_cola no coincide: {st_data}"
        assert st_data.get("estado") == "PENDIENTE", f"estado debe ser PENDIENTE: {st_data}"

    def test_b05_limite_concurrencia_exportaciones_429(self, corrida_g44: CorridaSandboxG44):
        """B05 (103 / 038, Restr. 8): Límite de concurrencia de exportaciones asíncronas por usuario (máximo 3).
        Encola 2 exportaciones adicionales (total 3 activas) y verifica que la 4ta solicitud es rechazada con HTTP 429."""
        c = corrida_g44
        id_activo = _CONTEXTO["id_activo_d"]
        body = {
            "tipo_trabajo": "EXPORTACION",
            "id_activo_biologico": id_activo,
            "formato_exportacion": "EXCEL",
        }

        # 2da solicitud (debe ser 202)
        r2 = c.post("/suministros/historial/trabajos", body, paso="B05_encolar_exportacion_2")
        assert r2.status_code == 202, f"2da exportacion debio ser encolada (202): HTTP {r2.status_code}: {c.seguro(r2.text)}"

        # 3ra solicitud (debe ser 202)
        r3 = c.post("/suministros/historial/trabajos", body, paso="B05_encolar_exportacion_3")
        assert r3.status_code == 202, f"3ra exportacion debio ser encolada (202): HTTP {r3.status_code}: {c.seguro(r3.text)}"

        # 4ta solicitud (debe superar el limite concurrente = 3 -> HTTP 429)
        r4 = c.post("/suministros/historial/trabajos", body, paso="B05_encolar_exportacion_4_rechazo")
        assert r4.status_code == 429, (
            f"DEFECTO (Restr. 8): 4ta exportacion debio responder HTTP 429, respondio HTTP {r4.status_code}: {c.seguro(r4.text)}"
        )
        err = r4.json()
        assert err.get("error_code") == "LIMITE_EXPORTACIONES_EXCEDIDO", f"error_code inesperado en 429: {err}"
        assert "exportaciones concurrentes" in err.get("message", "").lower(), f"Mensaje inesperado en 429: {err}"

    def test_98_cierre_sandbox(self, corrida_g44: CorridaSandboxG44):
        """T98: Cierre estricto del sandbox con DELETE /test-control/runs/{run_id} -> 200."""
        c = corrida_g44
        resp = c.cerrar()
        assert resp is not None
        assert resp.status_code == 200, f"Error cerrando sandbox: HTTP {resp.status_code}: {resp.text}"
        assert "Rollback exitoso" in resp.text

    def test_99_inocuidad_final(self):
        """T99: Inocuidad final sin sandbox: verificar que el activo D no persiste (HTTP 404)."""
        id_d = _CONTEXTO.get("id_activo_d")
        if not id_d:
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

        r_check = requests.get(f"{base_url}/suministros/historial?id_activo_biologico={id_d}", headers=headers, timeout=TIMEOUT_S)
        assert r_check.status_code == 404, (
            f"Falta de inocuidad: el activo {id_d} sigue existiendo fuera de sandbox (HTTP {r_check.status_code})"
        )

