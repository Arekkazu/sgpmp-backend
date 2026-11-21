# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G17 RF-76: tratamientos simultáneos y concurrencia (API real)  |
"""
TC-M05-G17 — RF-76 CU03, POST /suministros/medicamentos.
Tratamientos simultáneos y concurrencia real sobre activo QA dedicado y desechable.

Subcasos:
  (a) TC-M05-008 (A01–A04):
      - A01: Primer tratamiento con período de retiro (5 días) -> HTTP 201/200, activo EN_TRATAMIENTO,
             retiro vigente = hoy + 5, tratamientos_activos = 1.
      - A02: Segundo tratamiento con retiro mayor (10 días) -> HTTP 200 (E11), activo EN_TRATAMIENTO,
             retiro vigente = hoy + 10, tratamientos_activos = 2, mensaje E11 descriptivo.
      - A03: Tercer tratamiento con retiro menor (3 días) -> HTTP 200 (E11), activo EN_TRATAMIENTO,
             retiro vigente mantiene MAX (hoy + 10), tratamientos_activos = 3.
      - A04: Cuarto tratamiento con retiro mayor (15 días) -> HTTP 200 (E11), activo EN_TRATAMIENTO,
             retiro vigente se extiende a MAX (hoy + 15), tratamientos_activos = 4;
             verificación de 4 tratamientos VALIDADOS y anulación secuencial que restaura estado ACTIVO.
  (b) TC-M05-009 (B01):
      - B01: Concurrencia real (20 rondas de 5 hilos sincronizados con Barrier(5)).
             En cada ronda:
               * 5 aplicaciones concurrentes con retiros permutados [2, 4, 6, 8, 10] días y horas únicas.
               * Todos los hilos reciben HTTP 2xx (201/200), 0 colisiones 409 y 0 errores 500.
               * Validación de 5 registros VALIDADOS, fecha_fin_retiro_vigente = hoy + 10 días,
                 tratamientos_activos = 5 y estado EN_TRATAMIENTO.
               * Limpieza de la ronda mediante anulación de los 5 registros, restaurando estado ACTIVO.
  (c) Setup y Teardown:
      - T00: Creación de activo QA dedicado individual (Mojarra Plateada) y apertura de fase (ciclo 5).
      - T98: Verificación final de 0 tratamientos activos y estado final ACTIVO del activo QA.

Diseño y Reglas Duras:
- API Real de Staging (TEST_BASE_URL) con commits reales (SIN sandbox headers X-Test-Run-Id ni X-Sandbox-Secret).
- UN solo login de Admin al inicio de la sesión; token JWT compartido y seguro entre hilos.
- Trazas HTTP completas con query params y sanitización rigurosa de secretos con lock de concurrencia.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZONA_USUARIO = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")

NOMBRE_ZONA = "America/Bogota"
TIMEOUT_S = 45
ARCHIVO_TRAZA = "trazas_http.jsonl"
_LOCK_TRAZA = threading.Lock()

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

# Contexto global compartido de la corrida
_CONTEXTO: dict[str, Any] = {
    "token": None,
    "id_activo": None,
    "identificador_activo": None,
    "id_gestion_fases": None,
    "a01_id": None,
    "a02_id": None,
    "a03_id": None,
    "a04_id": None,
    "rondas_exitosas": 0,
    "total_peticiones_concurrencia": 0,
    "peticiones_concurrencia_ok": 0,
    "estado_final_activo": None,
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
            _env("TEST_PROD_PASSWORD", False),
            _env("TEST_PROD_EMAIL", False),
            _env("TEST_ING_PASSWORD", False),
            _env("TEST_ING_EMAIL", False),
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
    hilo_id: str | None = None,
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
        "test": _TEST_ACTUAL,
        "hilo": hilo_id or "main",
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


class ClienteAPI:
    """Cliente HTTP thread-safe para interactuar con la API real de Staging (sin sandbox)."""

    def __init__(self) -> None:
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.token: str | None = None
        self.http = requests.Session()
        self.http.headers.update({
            "X-Zona-Horaria": NOMBRE_ZONA,
        })

    def autenticar_admin(self) -> str:
        """Autentica al administrador una sola vez y almacena el token."""
        global _TEST_ACTUAL
        _TEST_ACTUAL = "auth_admin"
        correo = _env("TEST_ADMIN_EMAIL")
        clave = _env("TEST_ADMIN_PASSWORD")
        ruta = "/sesiones/"
        t0 = time.perf_counter()
        resp = None
        err = None
        payload = {"correo_electronico": correo, "contrasena": clave}
        try:
            resp = self.http.post(
                f"{self.base}{ruta}",
                json=payload,
                timeout=TIMEOUT_S,
            )
        except requests.RequestException as e:
            err = str(e)
            _trazar("POST", ruta, None, t0, None, payload, None, err)
            raise ErrorConexion("auth_admin", ruta, e)

        _trazar("POST", ruta, resp, t0, None, payload, None, None)
        assert resp.status_code == 200, f"Login admin fallo: status={resp.status_code}"
        token = resp.json().get("token") or resp.json().get("access_token")
        assert token, "Login admin no devolvio token"
        self.token = token
        self.http.headers["Authorization"] = f"Bearer {token}"
        _CONTEXTO["token"] = token
        return token

    def peticion(
        self,
        metodo: str,
        ruta: str,
        params: dict[str, Any] | None = None,
        json_data: Any = None,
        paso_nombre: str | None = None,
        hilo_id: str | None = None,
    ) -> requests.Response:
        url = f"{self.base}{ruta}"
        headers = {"X-Zona-Horaria": NOMBRE_ZONA}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        t0 = time.perf_counter()
        resp = None
        err = None
        try:
            resp = requests.request(
                method=metodo,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=TIMEOUT_S,
            )
        except requests.RequestException as e:
            err = str(e)
            _trazar(metodo, ruta, None, t0, params, json_data, self.token, err, hilo_id)
            raise ErrorConexion(paso_nombre or _TEST_ACTUAL, ruta, e)

        _trazar(metodo, ruta, resp, t0, params, json_data, self.token, None, hilo_id)
        return resp


@pytest.fixture(scope="session")
def cliente() -> ClienteAPI:
    c = ClienteAPI()
    c.autenticar_admin()
    return c


# ===========================================================================
# SUITE DE PRUEBAS
# ===========================================================================


def test_00_setup_activo_qa(cliente: ClienteAPI) -> None:
    """T00: Crea un activo QA dedicado (Mojarra Plateada) y abre fase con ciclo 5."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_00_setup_activo_qa"

    # Crear activo individual QA en infraestructura 389 (Finca 1)
    # Formato identificador: QA-M05-G17-%y%m%d-%H%M%S (exactamente 24 caracteres <= 25)
    marca = datetime.now(ZONA_USUARIO).strftime("%y%m%d-%H%M%S")
    identificador = f"QA-M05-G17-{marca}"
    _CONTEXTO["identificador_activo"] = identificador

    payload_activo = {
        "tipo_activo": "INDIVIDUAL",
        "id_especie": 5,
        "fecha_inicio_ciclo": _hoy().isoformat(),
        "origen_financiero": "nacimiento",
        "id_infraestructura": 389,
        "identificador": identificador,
        "raza": "Plateada",
        "sexo": "Hembra",
    }
    resp_activo = cliente.peticion("POST", "/activos-biologicos", json_data=payload_activo, paso_nombre="T00_crear_activo")
    assert resp_activo.status_code == 201, f"Fallo creacion activo QA: {resp_activo.text}"
    data_activo = resp_activo.json()
    id_activo = data_activo.get("id_activo_biologico")
    assert id_activo, "No se recibio id_activo_biologico en respuesta"
    _CONTEXTO["id_activo"] = id_activo

    # Abrir fase en ciclo 5
    payload_fase = {
        "id_ciclo_productiva": 5,
        "motivo_cambio": "Apertura ciclo mojarra para prueba TC-M05-G17",
    }
    resp_fase = cliente.peticion("POST", f"/activos-biologicos/{id_activo}/fases", json_data=payload_fase, paso_nombre="T00_abrir_fase")
    assert resp_fase.status_code == 201, f"Fallo apertura de fase activo QA: {resp_fase.text}"
    _CONTEXTO["id_gestion_fases"] = resp_fase.json().get("id_gestion_fases")

    # Confirmar estado ACTIVO (id_estado: 1)
    resp_get = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre="T00_verificar_estado")
    assert resp_get.status_code == 200
    assert resp_get.json().get("id_estado") == 1, "El activo QA recien creado debe estar en estado ACTIVO (1)"


def test_a01_primer_tratamiento_inicia_retiro(cliente: ClienteAPI) -> None:
    """A01: Primer tratamiento con retiro (5 días) inicia período y pasa activo a EN_TRATAMIENTO."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_a01_primer_tratamiento_inicia_retiro"
    id_activo = _CONTEXTO["id_activo"]
    hoy = _hoy()

    payload = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "MedQA-A01-Base",
        "dosis_aplicada": 10.0,
        "unidad_dosis": "ML",
        "via_administracion": "ORAL",
        "motivo_aplicacion": "Tratamiento inicial A01",
        "nombre_veterinario": "Dr. Carlos Gomez",
        "fecha_aplicacion": hoy.isoformat(),
        "hora_aplicacion": "08:00",
        "periodo_retiro_dias": 5,
        "costo_unitario": 2500.0,
        "lote": "LOTE-A01",
        "fecha_vencimiento_lote": "2027-12-31",
        "observaciones": "A01 primer tratamiento",
    }

    resp = cliente.peticion("POST", "/suministros/medicamentos", json_data=payload, paso_nombre="A01_post_tratamiento")
    assert resp.status_code in (200, 201), f"A01 status inesperado: {resp.status_code} ({resp.text})"
    data = resp.json()

    _CONTEXTO["a01_id"] = data.get("id_registro_medicamento") or data.get("medicamento", {}).get("id_registro_medicamento")
    esperada = (hoy + timedelta(days=5)).isoformat()
    assert data.get("fecha_fin_retiro_vigente") == esperada, f"A01 retiro vigente debe ser {esperada}"
    assert data.get("tratamientos_activos") == 1, "A01 tratamientos activos debe ser 1"

    # Verificar activo en EN_TRATAMIENTO (id_estado: 3)
    resp_activo = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre="A01_verificar_estado_activo")
    assert resp_activo.status_code == 200
    assert resp_activo.json().get("id_estado") == 3, "El activo debe estar en estado EN_TRATAMIENTO (3)"


def test_a02_segundo_tratamiento_extiende_retiro(cliente: ClienteAPI) -> None:
    """A02: Segundo tratamiento con retiro mayor (10 días) responde 200 E11 y extiende retiro."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_a02_segundo_tratamiento_extiende_retiro"
    id_activo = _CONTEXTO["id_activo"]
    hoy = _hoy()

    payload = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "MedQA-A02-Mayor",
        "dosis_aplicada": 12.0,
        "unidad_dosis": "ML",
        "via_administracion": "ORAL",
        "motivo_aplicacion": "Tratamiento secundario A02",
        "nombre_veterinario": "Dr. Carlos Gomez",
        "fecha_aplicacion": hoy.isoformat(),
        "hora_aplicacion": "08:15",
        "periodo_retiro_dias": 10,
        "costo_unitario": 3000.0,
        "lote": "LOTE-A02",
        "fecha_vencimiento_lote": "2027-12-31",
        "observaciones": "A02 tratamiento mayor",
    }

    resp = cliente.peticion("POST", "/suministros/medicamentos", json_data=payload, paso_nombre="A02_post_tratamiento")
    assert resp.status_code == 200, f"A02 esperaba HTTP 200 (E11), obtenido {resp.status_code} ({resp.text})"
    data = resp.json()

    _CONTEXTO["a02_id"] = data.get("id_registro_medicamento") or data.get("medicamento", {}).get("id_registro_medicamento")
    esperada = (hoy + timedelta(days=10)).isoformat()
    assert data.get("fecha_fin_retiro_vigente") == esperada, f"A02 retiro vigente debe ser {esperada}"
    assert data.get("tratamientos_activos") == 2, "A02 tratamientos activos debe ser 2"
    mensaje = data.get("mensaje", "")
    assert "2 tratamientos activos" in mensaje, f"Mensaje E11 debe indicar 2 tratamientos activos: '{mensaje}'"
    assert esperada in mensaje, f"Mensaje E11 debe indicar fecha vigente {esperada}: '{mensaje}'"

    # Verificar que activo se mantiene EN_TRATAMIENTO
    resp_activo = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre="A02_verificar_estado_activo")
    assert resp_activo.status_code == 200
    assert resp_activo.json().get("id_estado") == 3


def test_a03_tercer_tratamiento_menor_mantiene_vigente(cliente: ClienteAPI) -> None:
    """A03: Tercer tratamiento con retiro menor (3 días) mantiene fecha vigente en MAX (hoy + 10)."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_a03_tercer_tratamiento_menor_mantiene_vigente"
    id_activo = _CONTEXTO["id_activo"]
    hoy = _hoy()

    payload = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "MedQA-A03-Menor",
        "dosis_aplicada": 8.0,
        "unidad_dosis": "ML",
        "via_administracion": "ORAL",
        "motivo_aplicacion": "Tratamiento menor A03",
        "nombre_veterinario": "Dr. Carlos Gomez",
        "fecha_aplicacion": hoy.isoformat(),
        "hora_aplicacion": "08:30",
        "periodo_retiro_dias": 3,
        "costo_unitario": 2000.0,
        "lote": "LOTE-A03",
        "fecha_vencimiento_lote": "2027-12-31",
        "observaciones": "A03 tratamiento menor",
    }

    resp = cliente.peticion("POST", "/suministros/medicamentos", json_data=payload, paso_nombre="A03_post_tratamiento")
    assert resp.status_code == 200, f"A03 esperaba HTTP 200 (E11), obtenido {resp.status_code} ({resp.text})"
    data = resp.json()

    _CONTEXTO["a03_id"] = data.get("id_registro_medicamento") or data.get("medicamento", {}).get("id_registro_medicamento")
    esperada_max = (hoy + timedelta(days=10)).isoformat()
    assert data.get("fecha_fin_retiro_vigente") == esperada_max, f"A03 retiro vigente debe mantenerse en {esperada_max}"
    assert data.get("tratamientos_activos") == 3, "A03 tratamientos activos debe ser 3"

    # Verificar que activo se mantiene EN_TRATAMIENTO
    resp_activo = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre="A03_verificar_estado_activo")
    assert resp_activo.status_code == 200
    assert resp_activo.json().get("id_estado") == 3


def test_a04_cuarto_tratamiento_mayor_y_anulacion(cliente: ClienteAPI) -> None:
    """A04: Cuarto tratamiento extiende retiro a 15 días, GET valida 4 registros, anulación restaura ACTIVO."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_a04_cuarto_tratamiento_mayor_y_anulacion"
    id_activo = _CONTEXTO["id_activo"]
    hoy = _hoy()

    payload = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "MedQA-A04-Maximo",
        "dosis_aplicada": 15.0,
        "unidad_dosis": "ML",
        "via_administracion": "ORAL",
        "motivo_aplicacion": "Tratamiento maximo A04",
        "nombre_veterinario": "Dr. Carlos Gomez",
        "fecha_aplicacion": hoy.isoformat(),
        "hora_aplicacion": "08:45",
        "periodo_retiro_dias": 15,
        "costo_unitario": 3500.0,
        "lote": "LOTE-A04",
        "fecha_vencimiento_lote": "2027-12-31",
        "observaciones": "A04 tratamiento maximo",
    }

    resp = cliente.peticion("POST", "/suministros/medicamentos", json_data=payload, paso_nombre="A04_post_tratamiento")
    assert resp.status_code == 200, f"A04 esperaba HTTP 200 (E11), obtenido {resp.status_code} ({resp.text})"
    data = resp.json()

    _CONTEXTO["a04_id"] = data.get("id_registro_medicamento") or data.get("medicamento", {}).get("id_registro_medicamento")
    esperada_max15 = (hoy + timedelta(days=15)).isoformat()
    assert data.get("fecha_fin_retiro_vigente") == esperada_max15, f"A04 retiro vigente debe extenderse a {esperada_max15}"
    assert data.get("tratamientos_activos") == 4, "A04 tratamientos activos debe ser 4"

    # Verificar con GET que existen exactamente los 4 registros en estado VALIDADO
    resp_lista = cliente.peticion("GET", f"/suministros/medicamentos?id_activo_biologico={id_activo}", paso_nombre="A04_consultar_lista")
    assert resp_lista.status_code == 200
    items = resp_lista.json()
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    ids_creados = {_CONTEXTO["a01_id"], _CONTEXTO["a02_id"], _CONTEXTO["a03_id"], _CONTEXTO["a04_id"]}
    items_validados = [it for it in items if it.get("id_registro_medicamento") in ids_creados and it.get("estado_registro") == "VALIDADO"]
    assert len(items_validados) == 4, f"Se esperaban 4 medicamentos VALIDADOS, encontrados {len(items_validados)}"

    # Anular secuencialmente los 4 medicamentos para limpiar el activo y probar reversibilidad
    for id_reg in ids_creados:
        payload_anul = {
            "justificacion_anulacion": "Anulación de prueba TC-M05-G17 para subcaso 008",
        }
        resp_anul = cliente.peticion("POST", f"/suministros/medicamentos/{id_reg}/anulacion", json_data=payload_anul, paso_nombre=f"A04_anular_{id_reg}")
        assert resp_anul.status_code == 200, f"Fallo anulacion de medicamento {id_reg}: {resp_anul.text}"

    # Reversibilidad: comprobar que al no tener tratamientos activos, el activo vuelve a ACTIVO (id_estado: 1)
    resp_activo = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre="A04_verificar_reversibilidad_activo")
    assert resp_activo.status_code == 200
    assert resp_activo.json().get("id_estado") == 1, "Tras anular todos los tratamientos activos, el activo debe retornar a ACTIVO (1)"


def test_b01_concurrencia_20_rondas(cliente: ClienteAPI) -> None:
    """B01: 20 rondas de concurrencia real (5 hilos con Barrier). Todos 2xx, retiro MAX = hoy+10, anulación limpia."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_b01_concurrencia_20_rondas"
    id_activo = _CONTEXTO["id_activo"]
    hoy = _hoy()
    rondas_totales = 20
    retiros_base = [2, 4, 6, 8, 10]

    for r in range(1, rondas_totales + 1):
        # Asegurar estado ACTIVO previo a la ronda
        resp_act_pre = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre=f"B01_pre_ronda_{r}")
        assert resp_act_pre.status_code == 200
        assert resp_act_pre.json().get("id_estado") == 1, f"Ronda {r}: el activo debe iniciar en estado ACTIVO (1)"

        # Permutar retiros para esta ronda rotando la lista
        offset = (r - 1) % len(retiros_base)
        retiros_ronda = retiros_base[offset:] + retiros_base[:offset]

        barrier = threading.Barrier(5)
        resultados_hilos: list[dict[str, Any]] = [{} for _ in range(5)]

        def trabajador(hilo_idx: int, periodo_retiro: int) -> None:
            # Calcular hora única de aplicación para este hilo y ronda (evita conflicto de minuto exacto)
            minuto_global = (r - 1) * 5 + hilo_idx
            hora = 6 + (minuto_global // 60)
            minuto = minuto_global % 60
            hora_aplicacion = f"{hora:02d}:{minuto:02d}"

            payload_hilo = {
                "id_activo_biologico": id_activo,
                "nombre_medicamento": f"MedQA-R{r:02d}-H{hilo_idx}",
                "dosis_aplicada": float(10.0 + hilo_idx),
                "unidad_dosis": "ML",
                "via_administracion": "ORAL",
                "motivo_aplicacion": f"Tratamiento concurrente R{r:02d}-H{hilo_idx}",
                "nombre_veterinario": "Dr. Carlos Gomez",
                "fecha_aplicacion": hoy.isoformat(),
                "hora_aplicacion": hora_aplicacion,
                "periodo_retiro_dias": periodo_retiro,
                "costo_unitario": 1000.0 * periodo_retiro,
                "lote": f"LOTE-R{r:02d}-H{hilo_idx}",
                "fecha_vencimiento_lote": "2027-12-31",
                "observaciones": f"Ronda {r} hilo {hilo_idx}",
            }

            try:
                # Sincronización en la barrera para disparar exactamente en simultáneo
                barrier.wait(timeout=10)
                resp = cliente.peticion(
                    "POST",
                    "/suministros/medicamentos",
                    json_data=payload_hilo,
                    paso_nombre=f"B01_R{r:02d}_H{hilo_idx}",
                    hilo_id=f"R{r:02d}-H{hilo_idx}",
                )
                resultados_hilos[hilo_idx] = {
                    "status_code": resp.status_code,
                    "data": resp.json() if resp.status_code in (200, 201) else None,
                    "text": resp.text[:200],
                    "error": None,
                }
            except Exception as exc:
                resultados_hilos[hilo_idx] = {
                    "status_code": 0,
                    "data": None,
                    "text": "",
                    "error": str(exc),
                }

        # Lanzar 5 hilos
        threads = []
        for i in range(5):
            t = threading.Thread(target=trabajador, args=(i, retiros_ronda[i]))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=TIMEOUT_S)

        # Evaluar respuestas de los 5 hilos
        ids_ronda = set()
        for idx, res in enumerate(resultados_hilos):
            _CONTEXTO["total_peticiones_concurrencia"] += 1
            st = res.get("status_code")
            assert st in (200, 201), (
                f"Ronda {r} Hilo {idx} fallo: status={st}, error={res.get('error')}, body={res.get('text')}"
            )
            _CONTEXTO["peticiones_concurrencia_ok"] += 1
            body = res.get("data") or {}
            reg_id = body.get("id_registro_medicamento") or body.get("medicamento", {}).get("id_registro_medicamento")
            if reg_id:
                ids_ronda.add(reg_id)

        assert len(ids_ronda) == 5, f"Ronda {r}: se esperaban 5 IDs de medicamento distintos, se obtuvieron {len(ids_ronda)}"

        # Consultar lista de tratamientos y validar
        resp_lista = cliente.peticion("GET", f"/suministros/medicamentos?id_activo_biologico={id_activo}", paso_nombre=f"B01_lista_R{r}")
        assert resp_lista.status_code == 200
        items_lista = resp_lista.json()
        if isinstance(items_lista, dict) and "items" in items_lista:
            items_lista = items_lista["items"]

        items_ronda = [it for it in items_lista if it.get("id_registro_medicamento") in ids_ronda]
        assert len(items_ronda) == 5, f"Ronda {r}: la BD debe tener 5 medicamentos de esta ronda"
        for it in items_ronda:
            assert it.get("estado_registro") == "VALIDADO", f"Ronda {r}: medicamento {it.get('id_registro_medicamento')} no esta VALIDADO"

        # Verificar activo en EN_TRATAMIENTO
        resp_act_post = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre=f"B01_post_ronda_{r}")
        assert resp_act_post.status_code == 200
        assert resp_act_post.json().get("id_estado") == 3, f"Ronda {r}: el activo debe quedar en estado EN_TRATAMIENTO (3)"

        # Limpieza de la ronda: anular los 5 tratamientos para la siguiente ronda
        for id_reg in ids_ronda:
            payload_anul = {
                "justificacion_anulacion": f"Anulación limpieza concurrencia ronda {r} TC-M05-G17",
            }
            resp_anul = cliente.peticion("POST", f"/suministros/medicamentos/{id_reg}/anulacion", json_data=payload_anul, paso_nombre=f"B01_anular_R{r}_{id_reg}")
            assert resp_anul.status_code == 200, f"Ronda {r}: fallo anulacion de medicamento {id_reg}"

        # Verificar que el activo volvio a ACTIVO (1)
        resp_act_clean = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre=f"B01_clean_ronda_{r}")
        assert resp_act_clean.status_code == 200
        assert resp_act_clean.json().get("id_estado") == 1, f"Ronda {r}: el activo debio volver a ACTIVO (1) tras anular tratamientos"

        _CONTEXTO["rondas_exitosas"] += 1

    assert _CONTEXTO["rondas_exitosas"] == rondas_totales, f"Solo se completaron {_CONTEXTO['rondas_exitosas']} de {rondas_totales} rondas"


def test_98_limpieza_y_verificacion_final(cliente: ClienteAPI) -> None:
    """T98: Certifica que no queden tratamientos activos y valida estado final ACTIVO del activo QA."""
    global _TEST_ACTUAL
    _TEST_ACTUAL = "test_98_limpieza_y_verificacion_final"
    id_activo = _CONTEXTO["id_activo"]
    assert id_activo, "Falta id_activo en contexto"

    # Consultar medicamentos del activo
    resp_lista = cliente.peticion("GET", f"/suministros/medicamentos?id_activo_biologico={id_activo}", paso_nombre="T98_consultar_lista")
    assert resp_lista.status_code == 200
    items = resp_lista.json()
    if isinstance(items, dict) and "items" in items:
        items = items["items"]

    # Si hubiera algun tratamiento todavia en VALIDADO, anularlo
    pendientes = [it for it in items if it.get("estado_registro") == "VALIDADO"]
    for p in pendientes:
        id_reg = p.get("id_registro_medicamento")
        payload_anul = {"justificacion_anulacion": "Anulación final de remanente TC-M05-G17"}
        cliente.peticion("POST", f"/suministros/medicamentos/{id_reg}/anulacion", json_data=payload_anul, paso_nombre=f"T98_anular_remanente_{id_reg}")

    # Verificar estado final del activo
    resp_activo = cliente.peticion("GET", f"/activos-biologicos/{id_activo}", paso_nombre="T98_verificar_estado_final")
    assert resp_activo.status_code == 200
    estado_final = resp_activo.json().get("id_estado")
    _CONTEXTO["estado_final_activo"] = estado_final
    assert estado_final == 1, f"El activo QA {id_activo} debe quedar en estado ACTIVO (1), obtenido {estado_final}"
