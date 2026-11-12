# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G39: Campos minimos, inmutabilidad y hash RF-80 (CU06)        |
"""Suite de pruebas para TC-M05-G39: Campos minimos, inmutabilidad, hash e idempotencia (RF-80).

Cubre los casos TC-M05-092, 093 y 094 (agrupados 028, 029 y 030):
- Consulta de eventos incompletos y presencia de detalle_causa (TC-M05-092 / 028).
- Verificacion de superficie de escritura exclusiva GET via OpenAPI (TC-M05-093 / 029).
- Rechazo HTTP 405 de metodos de modificacion (PUT/PATCH/DELETE) e inalterabilidad del hash (TC-M05-093 / 029).
- Verificacion de auditoria de seguridad ante intentos de modificacion (TC-M05-093 / 029).
- Recalculo determinista de hash_integridad SHA-256 segun formula de BD y comparacion (TC-M05-093 / 029).
- Verificacion de presencia de id_evento_m05 para deduplicacion (TC-M05-094 / 030).
- Cierre ordenado e inocuidad del sandbox.
"""
from __future__ import annotations

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
_LOCK_TRAZA = threading.Lock()

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

_CONTEXTO: dict[str, Any] = {
    "total_base": 0,
    "id_activo": None,
    "id_fase": None,
    "id_evento_propio": None,
    "hash_evento_propio": None,
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
        self.run_id = f"tc-m05-g39-adm-{uuid.uuid4().hex[:8]}"
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

    def request(self, metodo: str, ruta: str, paso: str | None = None, json: Any = None, **kw) -> requests.Response:
        return self._enviar(metodo, ruta, paso=paso, json_body=json, **kw)

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


class TestTCM05G39CamposMinimosEInmutabilidad:
    """TC-M05-G39: Campos minimos, inmutabilidad, hash e idempotencia de la bitacora."""

    def test_t00_setup_linea_base(self, sandbox_admin: CorridaSandbox):
        """T00: Conteo inicial, activo propio, ciclo y creacion de evento propio RF-78."""
        c = sandbox_admin

        # Conteo base
        r_ini = c.get("/suministros/auditoria", paso="t00_conteo_base", params={"pagina": 1, "registros_por_pagina": 1})
        assert r_ini.status_code == 200, f"Error obteniendo conteo inicial: HTTP {r_ini.status_code}"
        _CONTEXTO["total_base"] = r_ini.json().get("total", 0)

        # Crear activo poblacional dedicado
        tag = uuid.uuid4().hex[:8]
        hoy = _hoy()
        fecha_ciclo = (hoy - timedelta(days=15)).isoformat()
        payload_activo = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "id_infraestructura": 2,
            "identificador_unico": f"QA-G39-{tag}",
            "cantidad_inicial": 50,
            "fecha_ingreso": fecha_ciclo,
            "fecha_inicio_ciclo": fecha_ciclo,
            "origen_financiero": "nacimiento",
            "peso_actual": 20.0,
        }
        r_act = c.post("/activos-biologicos", payload_activo, paso="t00_crear_activo")
        assert r_act.status_code == 201, f"Fallo creando activo: HTTP {r_act.status_code}"
        id_activo = r_act.json().get("id_activo_biologico")
        assert id_activo is not None
        _CONTEXTO["id_activo"] = id_activo

        # Abrir fase
        payload_fase = {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase QA G39"}
        r_fase = c.post(f"/activos-biologicos/{id_activo}/fases", payload_fase, paso="t00_abrir_fase")
        assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: HTTP {r_fase.status_code}"
        _CONTEXTO["id_fase"] = r_fase.json().get("id_gestion_fases")

        # Registrar suministro directo RF-78
        r_sum = c.post(
            "/suministros/costeo-directo",
            {
                "id_activo_biologico": id_activo,
                "tipo_suministro": "SERVICIO_VETERINARIO",
                "cantidad": 1.0,
                "unidad_medida": "UNIDAD",
                "precio_unitario": 60000.0,
                "fecha_aplicacion": hoy.isoformat(),
                "justificacion_precio": "Control veterinario de rutina",
                "id_idempotencia": str(uuid.uuid4()),
            },
            paso="t00_crear_evento_suministro",
        )
        assert r_sum.status_code == 200, f"Fallo suministro RF-78: HTTP {r_sum.status_code}"

        # Obtener id de auditoria del evento propio creado
        r_aud = c.get("/suministros/auditoria", paso="t00_obtener_evento_propio", params={"id_activo_biologico": id_activo, "tipo_operacion": "SUMINISTRO_REGISTRADO"})
        assert r_aud.status_code == 200
        items = r_aud.json().get("items", [])
        assert len(items) >= 1, "No se encontro el evento propio registrado en auditoria"
        _CONTEXTO["id_evento_propio"] = items[0]["id_auditoria_suministro"]
        _CONTEXTO["hash_evento_propio"] = items[0]["hash_integridad"]

    def test_a02_consulta_evento_incompleto_detalle_causa(self, sandbox_admin: CorridaSandbox):
        """A02 (TC-M05-092 / 028): Los eventos con registro_incompleto=true deben mostrar detalle_causa con campos faltantes (CA-12 / CU06 FA-05)."""
        c = sandbox_admin

        # Consultar evento real conocido con registro_incompleto=true (fila 87)
        r_det = c.get("/suministros/auditoria/87", paso="a02_consultar_evento_incompleto")
        assert r_det.status_code == 200, f"Error obteniendo evento 87: HTTP {r_det.status_code}"
        evento = r_det.json()

        assert evento.get("registro_incompleto") is True, f"Se esperaba registro_incompleto=True en evento 87, obtenido: {evento.get('registro_incompleto')}"

        # Defecto conocido de producto (RF-80 CA-12 / CU06 FA-05): detalle_causa debe detallar la lista de campos faltantes.
        # En la BD y API, detalle_causa es None / null en todos los eventos incompletos.
        detalle_causa = evento.get("detalle_causa")
        assert detalle_causa is not None and len(detalle_causa.strip()) > 0, (
            "DEFECTO_PRODUCTO (RF-80 CA-12 / CU06 FA-05 / TC-M05-092 / 028): La especificacion requiere que "
            "los eventos con registro_incompleto=true incluyan en detalle_causa la lista de campos faltantes "
            "(ej. 'Campos faltantes: ...'). El evento 87 tiene registro_incompleto=true pero detalle_causa es null."
        )

    def test_b01_superficie_escritura_openapi(self, sandbox_admin: CorridaSandbox):
        """B01 (TC-M05-093 / 029): Superficie de escritura: el OpenAPI confirma solo metodos GET bajo /suministros/auditoria*."""
        c = sandbox_admin
        base_url = _env("TEST_BASE_URL").rstrip("/")

        r_openapi = requests.get(f"{base_url}/openapi.json", timeout=15)
        assert r_openapi.status_code == 200, f"Error descargando openapi.json: HTTP {r_openapi.status_code}"
        schema = r_openapi.json()
        paths = schema.get("paths", {})

        rutas_auditoria_m05 = {p: list(methods.keys()) for p, methods in paths.items() if p.startswith("/suministros/auditoria")}
        assert len(rutas_auditoria_m05) > 0, "No se encontraron rutas bajo /suministros/auditoria en OpenAPI"

        metodos_escritura = {"post", "put", "patch", "delete"}
        escrituras_encontradas = {}
        for ruta, metodos in rutas_auditoria_m05.items():
            for m in metodos:
                if m.lower() in metodos_escritura:
                    escrituras_encontradas[f"{m.upper()} {ruta}"] = True

        assert len(escrituras_encontradas) == 0, (
            f"VULNERABILIDAD/FALLA: Se encontraron metodos de modificacion expuestos en OpenAPI: {list(escrituras_encontradas.keys())}"
        )

    def test_b02_inmutabilidad_rechazo_405_y_auditoria_seguridad(self, sandbox_admin: CorridaSandbox):
        """B02 (TC-M05-093 / 029): PUT/PATCH/DELETE a la bitacora retornan 405, fila/hash intactos y registran evento de seguridad (CA-2)."""
        c = sandbox_admin
        id_ev = _CONTEXTO["id_evento_propio"]
        hash_antes = _CONTEXTO["hash_evento_propio"]
        assert id_ev is not None and hash_antes is not None

        # 1. Probar rechazo HTTP 405 en raiz y sobre el evento propio
        for metodo in ["PUT", "PATCH", "DELETE"]:
            r_root = c.request(metodo, "/suministros/auditoria", paso=f"b02_intento_{metodo}_raiz")
            assert r_root.status_code == 405, f"Se esperaba 405 en {metodo} /suministros/auditoria, obtenido HTTP {r_root.status_code}"

            r_item = c.request(metodo, f"/suministros/auditoria/{id_ev}", paso=f"b02_intento_{metodo}_item")
            assert r_item.status_code == 405, f"Se esperaba 405 en {metodo} /suministros/auditoria/{id_ev}, obtenido HTTP {r_item.status_code}"

        # 2. Verificar que el evento propio y su hash permanezcan intactos
        r_verif = c.get(f"/suministros/auditoria/{id_ev}", paso="b02_verificar_evento_intacto")
        assert r_verif.status_code == 200
        assert r_verif.json().get("hash_integridad") == hash_antes, "El hash de integridad cambio tras los intentos de modificacion!"

        # 3. Verificar si el intento no autorizado genero un evento de seguridad (RF-80 CA-2 / RNF-05)
        # Consultar conteo en modulo5.auditorias_suministros (resultado = 'RECHAZADO')
        r_q_seg = c.post(
            "/test-control/query",
            {"query": "SELECT count(*) FROM modulo5.auditorias_suministros WHERE resultado = 'RECHAZADO'"},
            paso="b02_consultar_eventos_seguridad_m05",
        )
        assert r_q_seg.status_code == 200
        conteo_m05 = r_q_seg.json().get("data", [{}])[0].get("count", 0)

        # Consultar conteo en modulo1.eventos
        r_q_m01 = c.post(
            "/test-control/query",
            {"query": "SELECT count(*) FROM modulo1.eventos"},
            paso="b02_consultar_eventos_seguridad_m01",
        )
        assert r_q_m01.status_code == 200
        conteo_m01 = r_q_m01.json().get("data", [{}])[0].get("count", 0)

        # Defecto conocido: el router rechaza con 405 pero no persiste traza de seguridad en ninguna tabla
        assert conteo_m05 > 0 or conteo_m01 > 0, (
            "DEFECTO_PRODUCTO (RF-80 Restr. 1 / CA-2 / RNF-05 / TC-M05-093 / 029): La especificacion de inmutabilidad "
            "exige que todo intento de modificacion no permitido (PUT/PATCH/DELETE) sea rechazado y registrado como "
            "evento de seguridad en la bitacora. El sistema respondio HTTP 405 pero registro 0 eventos con resultado "
            f"RECHAZADO en modulo5.auditorias_suministros (conteo={conteo_m05}) y 0 eventos en modulo1.eventos (conteo={conteo_m01})."
        )

    def test_b03_verificacion_integridad_hash_sha256(self, sandbox_admin: CorridaSandbox):
        """B03 (TC-M05-093 / 029): Recálculo determinista de hash SHA-256 sobre todas las columnas reales (CA-6 / Restr. 5)."""
        c = sandbox_admin
        id_propio = _CONTEXTO["id_evento_propio"]

        # Recalcular hash para el evento propio y eventos reales de la base (87, 88)
        ids_a_evaluar = [87, 88, id_propio]
        ids_str = ", ".join(str(i) for i in ids_a_evaluar if i is not None)

        # El conjunto normativo comprende la totalidad de columnas reales de modulo5.auditorias_suministros
        # excluyendo ÚNICAMENTE hash_integridad. Como creado_en e id_registro_suministro no existen en la tabla,
        # to_jsonb(a) - 'hash_integridad' abarca todas las 22 columnas reales restantes.
        q_sql = f"""
        SELECT 
          id_auditoria_suministro,
          hash_integridad,
          (SELECT string_agg(format('%I=%L', key, value), ' & ' ORDER BY key)
           FROM jsonb_each_text(to_jsonb(a) - 'hash_integridad')) as canonical_str
        FROM modulo5.auditorias_suministros a
        WHERE id_auditoria_suministro IN ({ids_str})
        """
        r_q = c.post("/test-control/query", {"query": q_sql}, paso="b03_recalcular_hash_integridad")
        assert r_q.status_code == 200
        rows = r_q.json().get("data", [])
        assert len(rows) >= 2, f"Se esperaban filas evaluadas para hash, obtenidas {len(rows)}"

        for row in rows:
            stored_hash = row.get("hash_integridad")
            canon_str = row.get("canonical_str")
            id_aud = row.get("id_auditoria_suministro")
            assert stored_hash is not None and len(stored_hash) == 64
            assert canon_str is not None

            # Calcular SHA-256 en proceso y contrastar contra hash almacenado
            calc_hash = hashlib.sha256(canon_str.encode("utf-8")).hexdigest()
            assert calc_hash == stored_hash, (
                f"Discrepancia en hash SHA-256 para evento {id_aud}: almacenado={stored_hash}, calculado={calc_hash}"
            )

    def test_c01_id_evento_m05_presente_en_registros(self, sandbox_admin: CorridaSandbox):
        """C01 (TC-M05-094 / 030): Cada registro de auditoria debe incluir id_evento_m05 (UUID de deduplicacion) (Restr. 9 / CA-14)."""
        c = sandbox_admin
        id_ev = _CONTEXTO["id_evento_propio"]

        r_det = c.get(f"/suministros/auditoria/{id_ev}", paso="c01_verificar_id_evento_m05")
        assert r_det.status_code == 200
        evento = r_det.json()

        # Defecto conocido de producto: id_evento_m05 (UUID emitido por M05 antes de publicar para deduplicacion en M12)
        # no existe en la arquitectura actual. La clave primaria es id_auditoria_suministro (entero autoincremental).
        assert "id_evento_m05" in evento, (
            "DEFECTO_PRODUCTO (RF-80 Restr. 9 / CA-14 / RNF-09 / TC-M05-094 / 030): La especificacion de deduplicacion "
            "exige que cada registro de auditoria contenga el campo 'id_evento_m05' (UUID unico emitido por el componente "
            "de M05 antes de publicar). La API y la tabla modulo5.auditorias_suministros carecen de esta columna/propiedad "
            "(solo disponen de id_auditoria_suministro de tipo entero)."
        )

    def test_t98_cierre_sandbox(self, sandbox_admin: CorridaSandbox):
        """T98: Cierre ordenado de sandbox Administrador y confirmacion de rollback."""
        c = sandbox_admin
        r = c.cerrar()
        assert r is not None, "Cierre de sandbox ya ejecutado"
        assert r.status_code == 200, f"Error cerrando sandbox: HTTP {r.status_code}"
        data = r.json()
        mensaje = data.get("mensaje") or data.get("status") or ""
        assert "exitoso" in mensaje.lower(), f"Respuesta de rollback inesperada: {data}"

    def test_t99_inocuidad_rollback(self):
        """T99: Inocuidad - el conteo final de la bitacora coincide con la linea base."""
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
        total_base = _CONTEXTO.get("total_base", 0)
        assert total_fin == total_base, (
            f"Fallo de inocuidad: el conteo de la bitacora cambio de {total_base} a {total_fin}"
        )

