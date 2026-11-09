# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G42 RF-81: filtros, paginacion y limites (100, 101 / 035, 036) |
"""
TC-M05-G42 — RF-81 CU04, GET /suministros/historial.
Validacion de filtros, paginacion y niveles de volumen.
Hoja plana: TC-M05-100 y TC-M05-101. Hoja agrupada: 035 y 036.

Checkpoints normativos:
  - test_00_setup_linea_base_y_activos: Setup de dos activos (A y B) con ciclo y 3 registros en A; captura de linea base.
  - test_a01_combinaciones_invalidas_filtros: (100 / 035) Combinaciones invalidas:
      (a) fecha_fin_filtro < fecha_inicio_filtro -> HTTP 422 con mensaje especifico.
      (b) costo_max < costo_min -> HTTP 422 con mensaje especifico.
      (c) id_ciclo_productivo no perteneciente al activo -> HTTP 422 con mensaje especifico.
      Verificacion de mensajes descriptivos distintos y ausencia de datos/resumen.
  - test_a02_fechas_caso_cu04_fa02: (100 / 035, fuente: caso/CU04 FA-02; RF-81 NO lo define)
      (d) fecha_fin_filtro futura (hoy+1 America/Bogota) -> Esperado del caso: HTTP 422.
      (e) fecha_inicio_filtro anterior al inicio del ciclo del activo -> Esperado del caso: HTTP 422.
  - test_b01_paginacion_activo_con_mas_de_205_registros: (101 / 036) Paginacion sobre activo 1042 (263 registros):
      registros_por_pagina=200 -> HTTP 200 con 200 items;
      registros_por_pagina=201 -> HTTP 200 con 200 items (aplica tope maximo 200);
      metadatos coherentes; orden fecha_aplicacion DESC;
      monto_total_filtrado = suma de costo_registro de todos los registros;
      pagina 2 no repite items de pagina 1.
  - test_98_cierre_sandbox: DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso'.
  - test_99_inocuidad_final: Verificacion fuera de sandbox: 0 efectos persistidos.
"""
from __future__ import annotations

import json
import math
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
    "id_activo_a": None,
    "id_activo_b": None,
    "id_ciclo_a": 5,
    "id_ciclo_b": 5,
    "activo_grande_id": 1042,
    "activo_grande_total": 0,
    "auditoria_inicial": 0,
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


class CorridaSandboxG42:
    """Gestiona la transaccion sandbox para TC-M05-G42 (Administrador)."""

    def __init__(self) -> None:
        self.run_id = f"tc-m05-g42-adm-{uuid.uuid4().hex[:12]}"
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
def corrida_g42() -> CorridaSandboxG42:
    c = CorridaSandboxG42()
    c.login()
    try:
        yield c
    finally:
        c.cerrar()


class TestTC_M05_G42_Filtros_Paginacion:
    """Suite TC-M05-G42: Validacion de filtros, paginacion y niveles (RF-81, 100/101 plano, 035/036 agrupado)."""

    def test_00_setup_linea_base_y_activos(self, corrida_g42: CorridaSandboxG42):
        """T00: Setup de activos A y B con ciclo, 3 registros en A y captura de linea base."""
        c = corrida_g42

        # 1. Crear activo A (Individual Holstein)
        id_unico_a = f"QA-G42-A-{uuid.uuid4().hex[:6]}"
        r_act_a = c.post(
            "/activos-biologicos",
            {
                "tipo_activo": "INDIVIDUAL",
                "id_especie": 5,
                "id_infraestructura": 389,
                "identificador": id_unico_a,
                "raza": "Holstein",
                "sexo": "Hembra",
                "fecha_inicio_ciclo": "2026-08-01",
                "origen_financiero": "nacimiento",
            },
            paso="T00_crear_activo_a",
        )
        assert r_act_a.status_code == 201, f"Error creando activo A: HTTP {r_act_a.status_code}: {c.seguro(r_act_a.text)}"
        id_a = r_act_a.json().get("id_activo_biologico")
        assert id_a is not None, "Respuesta sin id_activo_biologico"
        _CONTEXTO["id_activo_a"] = id_a

        # Abrir fase en A
        r_fase_a = c.post(
            f"/activos-biologicos/{id_a}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase QA G42 A", "fecha_inicio": "2026-08-01T05:00:00Z"},
            paso="T00_abrir_fase_a",
        )
        assert r_fase_a.status_code in (200, 201), f"Error fase A: HTTP {r_fase_a.status_code}: {c.seguro(r_fase_a.text)}"

        # 2. Crear activo B (Individual Holstein)
        id_unico_b = f"QA-G42-B-{uuid.uuid4().hex[:6]}"
        r_act_b = c.post(
            "/activos-biologicos",
            {
                "tipo_activo": "INDIVIDUAL",
                "id_especie": 5,
                "id_infraestructura": 389,
                "identificador": id_unico_b,
                "raza": "Holstein",
                "sexo": "Macho",
                "fecha_inicio_ciclo": "2026-08-01",
                "origen_financiero": "nacimiento",
            },
            paso="T00_crear_activo_b",
        )
        assert r_act_b.status_code == 201, f"Error creando activo B: HTTP {r_act_b.status_code}: {c.seguro(r_act_b.text)}"
        id_b = r_act_b.json().get("id_activo_biologico")
        assert id_b is not None
        _CONTEXTO["id_activo_b"] = id_b

        r_fase_b = c.post(
            f"/activos-biologicos/{id_b}/fases",
            {"id_ciclo_productiva": 5, "motivo_cambio": "Apertura fase QA G42 B", "fecha_inicio": "2026-08-01T05:00:00Z"},
            paso="T00_abrir_fase_b",
        )
        assert r_fase_b.status_code in (200, 201)

        # 3. Registrar 3 suministros en A (2 alimentos y 1 medicamento)
        r_c1 = c.post(
            "/suministros/consumo-alimentos",
            {
                "id_activo_biologico": id_a,
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
                "id_activo_biologico": id_a,
                "id_tipo_alimento": 1,
                "fecha_consumo": "2026-08-15",
                "hora_suministro": "08:00:00",
                "cantidad_alimento": 25.0,
                "costo_unitario": 1200.0,
            },
            paso="T00_consumo_2",
        )
        assert r_c2.status_code == 201

        r_m1 = c.post(
            "/suministros/medicamentos",
            {
                "id_activo_biologico": id_a,
                "nombre_medicamento": "Ivermectina 1%",
                "fecha_aplicacion": "2026-08-18",
                "hora_aplicacion": "09:00:00",
                "via_administracion": "SUBCUTANEA",
                "dosis_aplicada": 5.0,
                "unidad_dosis": "ML",
                "periodo_retiro_dias": 0,
                "motivo_aplicacion": "Desparasitacion preventiva obligatoria de lote",
                "costo_unitario": 2000.0,
                "nombre_veterinario": "Dr. Carlos Veterinario",
            },
            paso="T00_medicamento_1",
        )
        assert r_m1.status_code == 201, f"Error creando medicamento en setup: HTTP {r_m1.status_code}: {c.seguro(r_m1.text)}"

        # 4. Verificar consulta exitosa del activo A con 3 registros
        r_hist_a = c.get(f"/suministros/historial?id_activo_biologico={id_a}", paso="T00_historial_a")
        assert r_hist_a.status_code == 200
        data_a = r_hist_a.json()
        assert len(data_a.get("items", [])) == 3
        assert data_a.get("resumen", {}).get("total_registros_filtrados") == 3

    def test_a01_combinaciones_invalidas_filtros(self, corrida_g42: CorridaSandboxG42):
        """A01 (TC-M05-100 / 035): Validacion de combinaciones invalidas (Restr. 7 / E5 / CA-10).
        (a) fecha_fin_filtro < fecha_inicio_filtro
        (b) costo_max < costo_min
        (c) id_ciclo_productivo no perteneciente al activo.
        Esperado: HTTP 422 en cada una con mensaje del conflicto especifico; la consulta no devuelve datos."""
        c = corrida_g42
        id_a = _CONTEXTO["id_activo_a"]
        mensajes_observados = []

        # (a) fecha_fin_filtro < fecha_inicio_filtro
        params_a = {
            "id_activo_biologico": id_a,
            "fecha_inicio_filtro": "2026-08-20",
            "fecha_fin_filtro": "2026-08-10",
        }
        r_a = c.get("/suministros/historial", params=params_a, paso="A01_fecha_fin_menor_inicio")
        assert r_a.status_code == 422, f"Esperado 422 para fecha_fin < fecha_inicio, obtenido HTTP {r_a.status_code}: {c.seguro(r_a.text)}"
        body_a = r_a.json()
        assert "items" not in body_a and "resumen" not in body_a, "La respuesta 422 no debe incluir datos de items o resumen"
        msg_a = body_a.get("message", "")
        assert "fecha_fin_filtro" in msg_a or "fecha_inicio_filtro" in msg_a or "anterior" in msg_a.lower(), (
            f"El mensaje 422 debe identificar el conflicto de fechas: {msg_a}"
        )
        mensajes_observados.append(msg_a)

        # (b) costo_max < costo_min
        params_b = {
            "id_activo_biologico": id_a,
            "costo_min": "10000.00",
            "costo_max": "1000.00",
        }
        r_b = c.get("/suministros/historial", params=params_b, paso="A01_costo_max_menor_min")
        assert r_b.status_code == 422, f"Esperado 422 para costo_max < costo_min, obtenido HTTP {r_b.status_code}: {c.seguro(r_b.text)}"
        body_b = r_b.json()
        assert "items" not in body_b and "resumen" not in body_b
        msg_b = body_b.get("message", "")
        assert "costo_max" in msg_b or "costo_min" in msg_b or "menor" in msg_b.lower(), (
            f"El mensaje 422 debe identificar el conflicto de costos: {msg_b}"
        )
        mensajes_observados.append(msg_b)

        # (c) id_ciclo_productivo ajeno (ciclo 1 que pertenece a tilapia, no al activo A de Mojarra Plateada id 5)
        params_c = {
            "id_activo_biologico": id_a,
            "id_ciclo_productivo": 1,
        }
        r_c = c.get("/suministros/historial", params=params_c, paso="A01_ciclo_real_ajeno")
        assert r_c.status_code == 422, f"Esperado 422 para ciclo real ajeno (1), obtenido HTTP {r_c.status_code}: {c.seguro(r_c.text)}"
        body_c = r_c.json()
        assert "items" not in body_c and "resumen" not in body_c
        msg_c = body_c.get("message", "")
        assert "ciclo" in msg_c.lower() or "pertenece" in msg_c.lower(), (
            f"El mensaje 422 debe identificar el conflicto del ciclo: {msg_c}"
        )
        mensajes_observados.append(msg_c)

        # Probar tambien ciclo inexistente (999999)
        r_c_inex = c.get("/suministros/historial", params={"id_activo_biologico": id_a, "id_ciclo_productivo": 999999}, paso="A01_ciclo_inexistente")
        assert r_c_inex.status_code == 422

        # Verificar que los tres mensajes de conflicto son distintos y descriptivos
        assert len(set(mensajes_observados)) == 3, f"Los mensajes de conflicto deben diferir entre si: {mensajes_observados}"

    def test_a02a_fecha_fin_futura(self, corrida_g42: CorridaSandboxG42):
        """A02a (TC-M05-100 / 035, fuente: caso/CU04 FA-02; RF-81 NO lo define):
        fecha_fin_filtro futura (hoy + 1 dia en America/Bogota).
        Esperado del caso (CU04 FA-02): HTTP 422 con conflicto especifico.
        Hecho observado: la API responde HTTP 200, reportado como omision / especificacion ambigua."""
        c = corrida_g42
        id_a = _CONTEXTO["id_activo_a"]

        manana = (datetime.now(ZONA_USUARIO).date() + timedelta(days=1)).isoformat()
        params_d = {
            "id_activo_biologico": id_a,
            "fecha_fin_filtro": manana,
        }
        r_d = c.get("/suministros/historial", params=params_d, paso="A02a_fecha_fin_futura")
        assert r_d.status_code == 422, (
            f"DEFECTO / OMISION SEGUN CASO CU04 FA-02: fecha_fin_filtro futura ({manana}) "
            f"respondio HTTP {r_d.status_code} en lugar de 422 ({c.seguro(r_d.text)})"
        )

    def test_a02b_fecha_inicio_anterior_ciclo(self, corrida_g42: CorridaSandboxG42):
        """A02b (TC-M05-100 / 035, fuente: caso/CU04 FA-02; RF-81 NO lo define):
        fecha_inicio_filtro anterior al inicio del ciclo del activo (2026-08-01 vs 2026-01-01).
        Esperado del caso (CU04 FA-02): HTTP 422 con conflicto especifico.
        Hecho observado: la API responde HTTP 200, reportado como omision / especificacion ambigua."""
        c = corrida_g42
        id_a = _CONTEXTO["id_activo_a"]

        params_e = {
            "id_activo_biologico": id_a,
            "fecha_inicio_filtro": "2026-01-01",
        }
        r_e = c.get("/suministros/historial", params=params_e, paso="A02b_fecha_inicio_anterior_ciclo")
        assert r_e.status_code == 422, (
            f"DEFECTO / OMISION SEGUN CASO CU04 FA-02: fecha_inicio_filtro anterior al ciclo (2026-01-01) "
            f"respondio HTTP {r_e.status_code} en lugar de 422 ({c.seguro(r_e.text)})"
        )

    def test_b01a_paginacion_activo_con_mas_de_205_registros(self, corrida_g42: CorridaSandboxG42):
        """B01a (TC-M05-101 / 036): Paginacion obligatoria (Restr. 5 / RNF-04 / CA-6).
        Se ejecuta en solo lectura dentro de la sandbox sobre activo 1042 (500 registros commiteados):
        - registros_por_pagina=200 -> HTTP 200 con 200 items.
        - Recorrido completo de todas las paginas sin duplicados.
        - Metadatos coherentes: total_registros_filtrados, total_paginas, pagina_actual.
        - Orden fecha_aplicacion DESC.
        - monto_total_filtrado = suma de costo_registro de todos los registros consultando todas las paginas.
        - Observacion de registros_por_pagina=0 y pagina=0 registradas en trazas."""
        c = corrida_g42
        id_grande = _CONTEXTO["activo_grande_id"]  # 1042

        # 1. Peticion con registros_por_pagina=200 (Pagina 1)
        r_200 = c.get(
            "/suministros/historial",
            params={"id_activo_biologico": id_grande, "pagina": 1, "registros_por_pagina": 200},
            paso="B01a_tamano_200_p1",
        )
        assert r_200.status_code == 200, f"Error paginacion 200: HTTP {r_200.status_code}: {c.seguro(r_200.text)}"
        data_200 = r_200.json()
        items_p1 = data_200.get("items", [])
        resumen_200 = data_200.get("resumen", {})

        assert len(items_p1) == 200, f"Se esperaban exactamente 200 items en pagina 1, obtenidos {len(items_p1)}"
        total_filtrados = resumen_200.get("total_registros_filtrados", 0)
        assert total_filtrados >= 205, f"El activo debe tener >= 205 registros, observados {total_filtrados}"
        _CONTEXTO["activo_grande_total"] = total_filtrados

        paginas_esperadas = math.ceil(total_filtrados / 200)
        assert resumen_200.get("total_paginas") == paginas_esperadas, (
            f"total_paginas esperado {paginas_esperadas}, obtenido {resumen_200.get('total_paginas')}"
        )
        assert resumen_200.get("pagina_actual") == 1

        # 2. Recorrido completo de todas las paginas
        todas_filas = list(items_p1)
        ids_vistos = {it["id_registro_suministro"] for it in items_p1}

        for pag in range(2, paginas_esperadas + 1):
            r_pag = c.get(
                "/suministros/historial",
                params={"id_activo_biologico": id_grande, "pagina": pag, "registros_por_pagina": 200},
                paso=f"B01a_pagina_{pag}",
            )
            assert r_pag.status_code == 200
            items_pag = r_pag.json().get("items", [])
            for it in items_pag:
                it_id = it["id_registro_suministro"]
                assert it_id not in ids_vistos, f"ID duplicado en pagina {pag}: {it_id}"
                ids_vistos.add(it_id)
            todas_filas.extend(items_pag)

        assert len(todas_filas) == total_filtrados, (
            f"Se esperaban {total_filtrados} items en total recorriendo todas las paginas, obtenidos {len(todas_filas)}"
        )

        # 3. Validar orden fecha_aplicacion DESC
        fechas = [it["fecha_aplicacion"] for it in todas_filas]
        assert fechas == sorted(fechas, reverse=True), "El orden de los registros debe ser fecha_aplicacion DESC"

        # 4. Validar monto_total_filtrado = suma de costo_registro de TODOS los registros
        monto_resumen = Decimal(str(resumen_200.get("monto_total_filtrado", "0")))
        suma_calculada = sum(Decimal(str(it.get("costo_registro", "0"))) for it in todas_filas)
        assert monto_resumen == suma_calculada, (
            f"monto_total_filtrado ({monto_resumen}) no coincide con suma de registros ({suma_calculada})"
        )

        # 5. Observacion sobre limites no definidos: registros_por_pagina=0 y pagina=0
        r_p0 = c.get(
            "/suministros/historial",
            params={"id_activo_biologico": id_grande, "pagina": 0, "registros_por_pagina": 50},
            paso="B01a_obs_pagina_cero",
        )
        r_t0 = c.get(
            "/suministros/historial",
            params={"id_activo_biologico": id_grande, "pagina": 1, "registros_por_pagina": 0},
            paso="B01a_obs_tamano_cero",
        )

    def test_b01b_tope_maximo_registros_por_pagina(self, corrida_g42: CorridaSandboxG42):
        """B01b (TC-M05-101 / 036): Validación de límite superior excedido (Tabla Entradas 'registros_por_pagina').
        Especificación: 'El sistema aplica el límite máximo si se excede' -> esperado HTTP 200 con 200 items.
        Hecho observado: el backend responde HTTP 400 (FastAPI query validation), reportado como defecto de producto."""
        c = corrida_g42
        id_grande = _CONTEXTO["activo_grande_id"]  # 1042

        r_201 = c.get(
            "/suministros/historial",
            params={"id_activo_biologico": id_grande, "pagina": 1, "registros_por_pagina": 201},
            paso="B01b_tamano_201_aplica_tope",
        )
        assert r_201.status_code == 200, (
            f"DEFECTO DE PRODUCTO (Tabla Entradas 'registros_por_pagina'): Se esperaba HTTP 200 aplicando tope máximo de 200 items, "
            f"pero el backend respondió HTTP {r_201.status_code} ({c.seguro(r_201.text)})"
        )
        data_201 = r_201.json()
        items_201 = data_201.get("items", [])
        assert len(items_201) == 200, f"El sistema debio aplicar el limite de 200 items ante param=201, pero retorno {len(items_201)}"
        # Solo se registran en trazas_http.jsonl como observacion del ambiente

    def test_98_cierre_sandbox(self, corrida_g42: CorridaSandboxG42):
        """T98: Cierre estricto del sandbox con DELETE /test-control/runs/{run_id} -> 200."""
        c = corrida_g42
        resp = c.cerrar()
        assert resp is not None, "El sandbox ya habia sido cerrado"
        assert resp.status_code == 200, f"Error cerrando sandbox: HTTP {resp.status_code}: {resp.text}"
        cuerpo = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        assert "Rollback exitoso" in resp.text or cuerpo.get("status") == "Rollback exitoso", (
            f"Respuesta inesperada al cerrar sandbox: {resp.text}"
        )

    def test_99_inocuidad_final(self):
        """T99: Inocuidad final sin sandbox: confirmar que no quedaron activos creados del test."""
        id_a = _CONTEXTO.get("id_activo_a")
        if not id_a:
            return
        base_url = _env("TEST_BASE_URL").rstrip("/")
        # Login normal fuera de sandbox
        r_login = requests.post(
            f"{base_url}/sesiones/",
            json={"correo_electronico": _env("TEST_ADMIN_EMAIL"), "contrasena": _env("TEST_ADMIN_PASSWORD")},
            timeout=TIMEOUT_S,
        )
        assert r_login.status_code == 200
        token = r_login.json().get("token") or r_login.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        # Consultar activo A fuera de sandbox: debe retornar 404 (revertido en BD)
        r_check = requests.get(f"{base_url}/suministros/historial?id_activo_biologico={id_a}", headers=headers, timeout=TIMEOUT_S)
        assert r_check.status_code == 404, (
            f"Falta de inocuidad: el activo {id_a} sigue existiendo fuera de sandbox (HTTP {r_check.status_code})"
        )
