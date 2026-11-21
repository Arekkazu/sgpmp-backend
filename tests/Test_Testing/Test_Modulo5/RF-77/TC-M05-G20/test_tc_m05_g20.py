# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G20 RF-77: Consolidado y promedio por individuo (014 y 015)    |
"""
TC-M05-G20 — RF-77, POST /suministros/reportes-gastos.
Consolidado y promedio por individuo (casos TC-M05-014 y TC-M05-015).

Checkpoints:
  - test_00_setup_linea_base:
      Línea base previa del historial de reportes del Administrador.
  - test_a01_consolidado_y_anulacion:
      Activo INDIVIDUAL con 3 consumos y 2 medicamentos validados (75.000 + 25.000 = 100.000 COP)
      y 1 consumo anulado (10.000 COP).
      Reporte HTTP 200: total 100.000 COP, ALIMENTACION 75.000 (3 reg, 75%), MEDICACION 25.000 (2 reg, 25%).
      El consumo anulado queda excluido (CA-1, CA-2).
  - test_a02_filtro_categorias_incluidas:
      Reporte filtrado con categorias_incluidas=['ALIMENTACION']: total 75.000 COP y solo dicha categoría.
  - test_b01_lote_poblacional_promedio_y_bajas:
      Lote POBLACIONAL P1 inicial 110, baja de 10 (actual 100), gasto 1.000.000 COP.
      Reporte HTTP 200: gasto_promedio_individuo = 10.000 COP y nota de bajas con N=10 (CA-6, Restr. 6).
  - test_b02_lote_poblacional_baja_total_no_calculable:
      Lote POBLACIONAL P2 con gasto > 0 y baja total (cantidad_actual=0, estado BAJA).
      Reporte HTTP 200: gasto_promedio_individuo None/'NO_CALCULABLE' con causa de la spec (Restr. 6).
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
    "id_lote_p1": None,
    "id_lote_p2": None,
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


class CorridaSandboxG20:
    """Gestiona la transacción sandbox (X-Test-Run-Id) de Administrador para TC-M05-G20."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g20-adm-{uuid.uuid4().hex[:12]}"
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
def corrida_g20() -> CorridaSandboxG20:
    c = CorridaSandboxG20()
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G20_Consolidado_Promedio:
    """Suite TC-M05-G20: Consolidado y promedio por individuo (RF-77, TC-M05-014 y 015)."""

    def test_00_setup_linea_base(self, corrida_g20: CorridaSandboxG20):
        """T00: Captura de línea base del historial de reportes del Administrador."""
        c = corrida_g20
        r_hist = c.get("/suministros/reportes-gastos/historial", paso="T00_historial_linea_base")
        assert r_hist.status_code == 200, (
            f"Error capturando línea base: HTTP {r_hist.status_code}: {c.seguro(r_hist.text)}"
        )
        datos = r_hist.json()
        total_base = len(datos) if isinstance(datos, list) else len(datos.get("items", []))
        _CONTEXTO["historial_base_total"] = total_base

    def test_a01_consolidado_y_anulacion(self, corrida_g20: CorridaSandboxG20):
        """A01 (TC-M05-014): Activo INDIVIDUAL con consumos, medicamentos y anulación.
        Gasto total consolidado, subtotales por categoría, porcentajes y exclusión de anulados."""
        c = corrida_g20

        # 1. Crear activo individual (Especie 5, Infraestructura 389)
        fecha_ciclo = "2026-08-01"
        id_unico = f"QA-G20-IND-{uuid.uuid4().hex[:6]}"
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
        r_act = c.post("/activos-biologicos", payload_activo, paso="A01_crear_activo_individual")
        assert r_act.status_code == 201, f"Fallo creando activo INDIVIDUAL: HTTP {r_act.status_code}: {c.seguro(r_act.text)}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None, "Respuesta sin id_activo_biologico"
        _CONTEXTO["id_activo_ind"] = id_activo

        # 2. Abrir fase productiva con fecha en el pasado correspondiente
        r_fase = c.post(
            f"/activos-biologicos/{id_activo}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase productiva QA G20", "fecha_inicio": "2026-08-01T05:00:00Z"},
            paso="A01_abrir_fase_individual",
        )
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"

        # 3. Registrar 3 consumos de alimento VALIDADOS (25k + 25k + 25k = 75.000 COP)
        consumos_datos = [
            ("2026-08-10", "08:00:00", Decimal("25"), Decimal("1000")),  # 25.000 COP
            ("2026-08-15", "09:00:00", Decimal("20"), Decimal("1250")),  # 25.000 COP
            ("2026-08-20", "10:00:00", Decimal("25"), Decimal("1000")),  # 25.000 COP
        ]
        total_alim_esperado = Decimal("0")
        for fecha_c, hora_c, cant, costo in consumos_datos:
            sub = cant * costo
            total_alim_esperado += sub
            r_c = c.post(
                "/suministros/consumo-alimentos",
                {
                    "id_activo_biologico": id_activo,
                    "id_tipo_alimento": 1,
                    "fecha_consumo": fecha_c,
                    "hora_suministro": hora_c,
                    "cantidad_alimento": float(cant),
                    "costo_unitario": float(costo),
                },
                paso="A01_consumo_validado",
            )
            assert r_c.status_code == 201, f"Fallo consumo validado: HTTP {r_c.status_code}: {c.seguro(r_c.text)}"

        # 4. Registrar 2 aplicaciones de medicamento VALIDADOS (15k + 10k = 25.000 COP)
        meds_datos = [
            ("2026-08-12", "08:30:00", Decimal("5"), Decimal("3000")),  # 15.000 COP
            ("2026-08-18", "09:30:00", Decimal("5"), Decimal("2000")),  # 10.000 COP
        ]
        total_med_esperado = Decimal("0")
        for fecha_m, hora_m, dosis, costo in meds_datos:
            sub = dosis * costo
            total_med_esperado += sub
            r_m = c.post(
                "/suministros/medicamentos",
                {
                    "id_activo_biologico": id_activo,
                    "nombre_medicamento": "Oxitetraciclina QA",
                    "via_administracion": "INTRAMUSCULAR",
                    "dosis_aplicada": float(dosis),
                    "unidad_dosis": "ml",
                    "fecha_aplicacion": fecha_m,
                    "hora_aplicacion": hora_m,
                    "costo_unitario": float(costo),
                    "periodo_retiro_dias": 0,
                    "motivo_aplicacion": "Tratamiento sanitario preventivo QA G20",
                    "nombre_veterinario": "Dr. QA Veterinario",
                },
                paso="A01_medicamento_validado",
            )
            assert r_m.status_code == 201, f"Fallo medicamento validado: HTTP {r_m.status_code}: {c.seguro(r_m.text)}"

        # 5. Registrar 1 consumo adicional para ANULARLO (10.000 COP)
        r_c4 = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_activo,
                "id_tipo_alimento": 1,
                "fecha_consumo": "2026-08-25",
                "hora_suministro": "11:00:00",
                "cantidad_alimento": 10.0,
                "costo_unitario": 1000.0,
            },
            paso="A01_consumo_para_anular",
        )
        assert r_c4.status_code == 201, f"Fallo creando consumo 4: HTTP {r_c4.status_code}: {c.seguro(r_c4.text)}"
        c4_id = r_c4.json().get("id_consumo_alimento") or r_c4.json().get("id_consumo_alimeto")
        assert c4_id is not None, "Respuesta sin id_consumo_alimento"

        # 6. Anular consumo C4 (exige >= 50 caracteres según spec/RF-75)
        justificacion_anulacion = "Anulacion por error en pesaje de racion durante prueba automatizada QA G20"
        r_anul = c.post(
            f"/suministros/consumo-alimentos/{c4_id}/anulacion",
            {"justificacion_anulacion": justificacion_anulacion},
            paso="A01_anular_consumo",
        )
        assert r_anul.status_code == 200, f"Fallo anulando consumo C4: HTTP {r_anul.status_code}: {c.seguro(r_anul.text)}"

        # 7. Generar reporte consolidado para el mes de agosto 2026
        payload_rep = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": "2026-08-31",
            "tipo_periodo": "MENSUAL",
        }
        r_rep = c.post("/suministros/reportes-gastos", payload_rep, paso="A01_generar_reporte_consolidado")
        assert r_rep.status_code == 200, f"Reporte respondió HTTP {r_rep.status_code}: {c.seguro(r_rep.text)}"
        rep = r_rep.json()

        # Verificaciones de totales (Aritmética Decimal calculada)
        total_esperado = total_alim_esperado + total_med_esperado  # 75.000 + 25.000 = 100.000 COP
        total_obtenido = Decimal(str(rep["gasto_total_acumulado"]))
        assert total_obtenido == total_esperado, (
            f"Gasto total acumulado incorrecto: esperado {total_esperado}, obtenido {total_obtenido}"
        )

        # Verificación de desglose por categorías
        desglose = {d["categoria"]: d for d in rep.get("desglose_categorias", [])}
        assert "ALIMENTACION" in desglose, "Categoría ALIMENTACION no presente en el desglose"
        assert "MEDICACION" in desglose, "Categoría MEDICACION no presente en el desglose"

        cat_alim = desglose["ALIMENTACION"]
        assert Decimal(str(cat_alim["subtotal"])) == total_alim_esperado, (
            f"Subtotal alimentación: esperado {total_alim_esperado}, obtenido {cat_alim['subtotal']}"
        )
        assert cat_alim["num_registros"] == 3, f"Num registros alimentación: esperado 3, obtenido {cat_alim['num_registros']}"
        pct_alim = Decimal(str(cat_alim["porcentaje"]))
        assert abs(pct_alim - Decimal("75.00")) <= Decimal("0.01"), f"Porcentaje alimentación: esperado 75%, obtenido {pct_alim}%"

        cat_med = desglose["MEDICACION"]
        assert Decimal(str(cat_med["subtotal"])) == total_med_esperado, (
            f"Subtotal medicación: esperado {total_med_esperado}, obtenido {cat_med['subtotal']}"
        )
        assert cat_med["num_registros"] == 2, f"Num registros medicación: esperado 2, obtenido {cat_med['num_registros']}"
        pct_med = Decimal(str(cat_med["porcentaje"]))
        assert abs(pct_med - Decimal("25.00")) <= Decimal("0.01"), f"Porcentaje medicación: esperado 25%, obtenido {pct_med}%"

        # Verificación de exclusión del registro ANULADO (los 10.000 COP no deben figurar)
        assert total_obtenido == Decimal("100000.0000"), "El registro anulado sumó al total acumulado (debe excluirse)"

    def test_a02_filtro_categorias_incluidas(self, corrida_g20: CorridaSandboxG20):
        """A02 (TC-M05-014): Filtro categorias_incluidas=['ALIMENTACION'].
        El reporte incluye solo dicha categoría y el total coincide exactamente con su subtotal."""
        c = corrida_g20
        id_activo = _CONTEXTO["id_activo_ind"]
        assert id_activo is not None, "Precondición no cumplida: id_activo_ind es None"

        payload_rep = {
            "activo_biologico_id": id_activo,
            "fecha_inicio_reporte": "2026-08-01",
            "fecha_fin_reporte": "2026-08-31",
            "tipo_periodo": "MENSUAL",
            "categorias_incluidas": ["ALIMENTACION"],
        }
        r_rep = c.post("/suministros/reportes-gastos", payload_rep, paso="A02_filtro_categoria_alimentacion")
        assert r_rep.status_code == 200, f"Reporte filtrado respondió HTTP {r_rep.status_code}: {c.seguro(r_rep.text)}"
        rep = r_rep.json()

        total_obtenido = Decimal(str(rep["gasto_total_acumulado"]))
        assert total_obtenido == Decimal("75000.0000"), (
            f"Total acumulado filtrado incorrecto: esperado 75000, obtenido {total_obtenido}"
        )
        desglose = rep.get("desglose_categorias", [])
        assert len(desglose) == 1, f"Se esperaba 1 categoría en el desglose, se obtuvieron {len(desglose)}"
        assert desglose[0]["categoria"] == "ALIMENTACION", f"Categoría incorrecta: {desglose[0]['categoria']}"
        assert Decimal(str(desglose[0]["subtotal"])) == Decimal("75000.0000")
        assert desglose[0]["num_registros"] == 3

    def test_b01_lote_poblacional_promedio_y_bajas(self, corrida_g20: CorridaSandboxG20):
        """B01 (TC-M05-015): Lote POBLACIONAL P1 con cantidad_inicial=110, baja de 10 (actual=100)
        y gasto total 1.000.000 COP. Promedio = 10.000 COP y nota de bajas con N=10 (Restr. 6)."""
        c = corrida_g20
        fecha_ciclo = "2026-11-01"
        fecha_hoy = datetime.now(ZONA_USUARIO).date().isoformat()
        id_unico = f"QA-G20-LOTE1-{uuid.uuid4().hex[:6]}"

        # 1. Crear lote poblacional P1
        payload_p1 = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": id_unico,
            "cantidad_inicial": 110,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_p1 = c.post("/activos-biologicos", payload_p1, paso="B01_crear_lote_p1")
        assert r_p1.status_code == 201, f"Fallo creando lote P1: HTTP {r_p1.status_code}: {c.seguro(r_p1.text)}"
        id_lote1 = r_p1.json().get("id_activo_biologico")
        _CONTEXTO["id_lote_p1"] = id_lote1

        # 2. Abrir fase
        r_fase = c.post(
            f"/activos-biologicos/{id_lote1}/fases",
            {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase P1 QA G20", "fecha_inicio": "2026-11-01T05:00:00Z"},
            paso="B01_abrir_fase_p1",
        )
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase P1: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"

        # 3. Registrar gasto: Alimento 750.000 COP + Medicamento 250.000 COP = 1.000.000 COP
        r_c = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_lote1,
                "id_tipo_alimento": 1,
                "fecha_consumo": fecha_hoy,
                "hora_suministro": "08:00:00",
                "cantidad_alimento": 500.0,
                "costo_unitario": 1500.0,
            },
            paso="B01_consumo_p1",
        )
        assert r_c.status_code == 201, f"Fallo consumo P1: HTTP {r_c.status_code}: {c.seguro(r_c.text)}"

        r_m = c.post(
            "/suministros/medicamentos",
            {
                "id_activo_biologico": id_lote1,
                "nombre_medicamento": "Oxitetraciclina Lote QA",
                "via_administracion": "INTRAMUSCULAR",
                "dosis_aplicada": 50.0,
                "unidad_dosis": "ml",
                "fecha_aplicacion": fecha_hoy,
                "hora_aplicacion": "08:00:00",
                "costo_unitario": 5000.0,
                "periodo_retiro_dias": 0,
                "motivo_aplicacion": "Tratamiento sanitario lote P1 QA G20",
                "nombre_veterinario": "Dr. QA Veterinario",
            },
            paso="B01_medicamento_p1",
        )
        assert r_m.status_code == 201, f"Fallo medicamento P1: HTTP {r_m.status_code}: {c.seguro(r_m.text)}"

        # 4. Registrar baja de 10 individuos (fecha_baja = hoy para respetar fecha_creacion del activo)
        r_baja = c.post(
            f"/activos-biologicos/{id_lote1}/eventos/baja",
            {
                "tipo_baja": "muerte",
                "fecha_baja": fecha_hoy,
                "motivo_baja": "Mortalidad por adaptacion lote QA G20",
                "cantidad_afectada": 10,
            },
            paso="B01_registrar_baja_10",
        )
        assert r_baja.status_code == 201, f"Fallo registrando baja: HTTP {r_baja.status_code}: {c.seguro(r_baja.text)}"

        # 5. Generar reporte para P1
        payload_rep = {
            "activo_biologico_id": id_lote1,
            "fecha_inicio_reporte": fecha_ciclo,
            "fecha_fin_reporte": fecha_hoy,
            "tipo_periodo": "MENSUAL",
        }
        r_rep = c.post("/suministros/reportes-gastos", payload_rep, paso="B01_reporte_lote_p1")
        assert r_rep.status_code == 200, f"Reporte P1 respondió HTTP {r_rep.status_code}: {c.seguro(r_rep.text)}"
        rep = r_rep.json()

        # Validaciones de totales y promedio
        total_obtenido = Decimal(str(rep["gasto_total_acumulado"]))
        assert total_obtenido == Decimal("1000000.0000"), f"Total P1 esperado 1000000, obtenido {total_obtenido}"

        promedio_obtenido = Decimal(str(rep["gasto_promedio_individuo"]))
        promedio_esperado = Decimal("1000000") / Decimal("100")  # 10.000 COP
        assert promedio_obtenido == promedio_esperado, (
            f"Promedio por individuo incorrecto: esperado {promedio_esperado}, obtenido {promedio_obtenido}"
        )

        # Nota de bajas
        nota_bajas = rep.get("nota_bajas") or ""
        assert "10 bajas" in nota_bajas, f"Nota de bajas no contiene '10 bajas': {nota_bajas!r}"
        assert "usa la cantidad actual del lote y no la cantidad promedio del período" in nota_bajas, (
            f"Texto de nota de bajas no conforme con spec: {nota_bajas!r}"
        )

    def test_b02_lote_poblacional_baja_total_no_calculable(self, corrida_g20: CorridaSandboxG20):
        """B02 (TC-M05-015): Lote POBLACIONAL P2 con gasto > 0 y baja total (cantidad_actual=0).
        gasto_promedio_individuo = 'NO_CALCULABLE' (None en JSON) con causa de la spec (Restr. 6)."""
        c = corrida_g20
        fecha_ciclo = "2026-11-01"
        fecha_hoy = datetime.now(ZONA_USUARIO).date().isoformat()
        id_unico = f"QA-G20-LOTE2-{uuid.uuid4().hex[:6]}"

        # 1. Crear lote poblacional P2
        payload_p2 = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": id_unico,
            "cantidad_inicial": 50,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
        }
        r_p2 = c.post("/activos-biologicos", payload_p2, paso="B02_crear_lote_p2")
        assert r_p2.status_code == 201, f"Fallo creando lote P2: HTTP {r_p2.status_code}: {c.seguro(r_p2.text)}"
        id_lote2 = r_p2.json().get("id_activo_biologico")
        _CONTEXTO["id_lote_p2"] = id_lote2

        # 2. Abrir fase
        r_fase = c.post(
            f"/activos-biologicos/{id_lote2}/fases",
            {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase P2 QA G20", "fecha_inicio": "2026-11-01T05:00:00Z"},
            paso="B02_abrir_fase_p2",
        )
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase P2: HTTP {r_fase.status_code}: {c.seguro(r_fase.text)}"

        # 3. Registrar gasto de alimento (50.000 COP)
        r_c = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_lote2,
                "id_tipo_alimento": 1,
                "fecha_consumo": fecha_hoy,
                "hora_suministro": "08:00:00",
                "cantidad_alimento": 50.0,
                "costo_unitario": 1000.0,
            },
            paso="B02_consumo_p2",
        )
        assert r_c.status_code == 201, f"Fallo consumo P2: HTTP {r_c.status_code}: {c.seguro(r_c.text)}"

        # 4. Registrar baja TOTAL de los 50 individuos (fecha_baja = hoy)
        r_baja = c.post(
            f"/activos-biologicos/{id_lote2}/eventos/baja",
            {
                "tipo_baja": "muerte",
                "fecha_baja": fecha_hoy,
                "motivo_baja": "Muerte total accidental lote QA G20",
                "cantidad_afectada": 50,
            },
            paso="B02_baja_total_p2",
        )
        assert r_baja.status_code == 201, f"Fallo registrando baja total: HTTP {r_baja.status_code}: {c.seguro(r_baja.text)}"

        # 5. Generar reporte para P2
        payload_rep = {
            "activo_biologico_id": id_lote2,
            "fecha_inicio_reporte": fecha_ciclo,
            "fecha_fin_reporte": fecha_hoy,
            "tipo_periodo": "MENSUAL",
        }
        r_rep = c.post("/suministros/reportes-gastos", payload_rep, paso="B02_reporte_lote_p2")
        assert r_rep.status_code == 200, f"Reporte P2 respondió HTTP {r_rep.status_code}: {c.seguro(r_rep.text)}"
        rep = r_rep.json()

        total_obtenido = Decimal(str(rep["gasto_total_acumulado"]))
        assert total_obtenido == Decimal("50000.0000"), f"Total P2 esperado 50000, obtenido {total_obtenido}"

        promedio_obtenido = rep.get("gasto_promedio_individuo")
        assert promedio_obtenido == "NO_CALCULABLE", (
            f"DEFECTO_PRODUCTO (RF-77 Restr. 6 / CA-6 / TC-M05-015): gasto_promedio_individuo debe ser 'NO_CALCULABLE' "
            f"cuando cantidad_actual=0. Obtenido: {promedio_obtenido!r}"
        )

        causa_obtenida = rep.get("causa_no_calculable_promedio") or ""
        causa_esperada = "La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."
        assert causa_obtenida == causa_esperada, (
            f"Causa no calculable no coincide con spec: esperada {causa_esperada!r}, obtenida {causa_obtenida!r}"
        )

        causa_obtenida = rep.get("causa_no_calculable_promedio") or ""
        causa_esperada = "La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."
        assert causa_obtenida == causa_esperada, (
            f"Causa no calculable no coincide con spec: esperada {causa_esperada!r}, obtenida {causa_obtenida!r}"
        )

    def test_98_cierre_sandbox(self, corrida_g20: CorridaSandboxG20):
        """T98: Cierre ordenado de la sesión sandbox y verificación de rollback atómico."""
        c = corrida_g20
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

