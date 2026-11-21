# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G14 RF-76: rechazo de campos y valores límite (sandbox HTTP)  |
"""
TC-M05-G14 — RF-76 CU03, POST /suministros/medicamentos (requests + sandbox transaccional).

Subcasos:
  (a) A01–A16: rechazo por campos obligatorios ausentes o inválidos → 400.
  (b) B01–B09: valores límite de dosis, motivo y fecha sobre un activo ACTIVO.

ADVERTENCIA — ORDEN DE EJECUCIÓN OBLIGATORIO:
  Este archivo DEBE ejecutarse completo y en el orden en que están escritos los tests:
  línea base de inocuidad → preparación → A01–A16 → B01–B09 (sin B03) → cierre de la
  corrida principal → B03 → inocuidad final. Ejecutar con ``-p no:randomly`` y sin
  seleccionar tests sueltos (``-k`` / ``::nodeid``). ``test_00_inocuidad_linea_base``
  falla si detecta que otro test de este archivo corrió antes que él.

Diseño:
- Cliente: requests.Session contra el backend desplegado ($TEST_BASE_URL de .env.test).
  No usa la fixture sandbox_client (esa levanta la app local con BD local).
- Corridas (cada una con su run_id, UN solo login — DEF-04 — y su teardown):
    1. Inocuidad inicial: conteo base de medicamentos del activo.
    2. Principal (fixture de módulo): preparación + A01–A16 + B01–B09 salvo B03.
    3. B03 (dosis 0.0001): corrida propia, al final; un error de BD no contamina la principal.
    4. Inocuidad final: el conteo debe coincidir con el base (rollback total).
- La fase del ciclo productivo se abre DENTRO del sandbox (RF-37) con un ciclo de la
  especie del activo (el listado de ciclos del activo ya viene filtrado por especie);
  el rollback la revierte.
- periodo_retiro_dias = 0 en todos los payloads: con retiro > 0 se invoca RF-44 y se envía
  un correo real que el rollback no deshace.
- "Hoy" se calcula en America/Bogota, la misma zona que viaja en X-Zona-Horaria.
- Traza de evidencia: si $TEST_EVIDENCE_DIR está definida, cada request agrega una línea
  JSON a <TEST_EVIDENCE_DIR>/trazas_http.jsonl (sin cabeceras, tokens, secretos ni bodies).
- Los esperados son los de la ESPECIFICACIÓN RF-76 (RN-R05-EXT): si el backend no los
  cumple, el test falla. Sin skip, sin xfail, sin defaults aprobados.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZONA_USUARIO = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        # Windows sin paquete tzdata: Colombia es UTC-05:00 fijo (sin horario de verano desde 1993).
        ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:  # pragma: no cover - Python < 3.9
    ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")

NOMBRE_ZONA = "America/Bogota"
TIMEOUT_S = 45
REINTENTOS_GET = 2
ID_ACTIVO_POR_DEFECTO = "930"
ESTADO_ACTIVO = 1
ARCHIVO_TRAZA = "trazas_http.jsonl"

_RAIZ_REPO = Path(__file__).resolve().parents[5]
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

# Conteos compartidos entre las corridas de inocuidad (inicial y final).
_INOCUIDAD: dict[str, int] = {}
# Tests de este archivo ya ejecutados, en orden (guardia de orden de test_00).
_EJECUTADOS: list[str] = []


# --------------------------------------------------------------------------- utilidades


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    """Lee la variable del entorno del proceso y, si falta, de .env.test. Nunca la imprime."""
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"PRECONDICION_NO_CUMPLIDA: falta la variable de entorno {nombre}")
    return valor or ""


def _hoy() -> date:
    return datetime.now(ZONA_USUARIO).date()


def _secretos() -> list[str]:
    return [s for s in (_env("TEST_SANDBOX_SECRET", False), _env("TEST_ADMIN_PASSWORD", False)) if s]


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    """Recorta el texto y enmascara cualquier secreto, contraseña o token que contenga."""
    texto = (texto or "")[:300]
    for s in [*_secretos(), *extra]:
        if s:
            texto = texto.replace(s, "***")
    return texto


def _json_o_vacio(resp: requests.Response) -> dict:
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _error_code(resp: requests.Response) -> str | None:
    return _json_o_vacio(resp).get("error_code")


def _campos_error(resp: requests.Response) -> list[str]:
    return [f.get("field") for f in _json_o_vacio(resp).get("fields") or [] if isinstance(f, dict)]


def _mensajes_error(resp: requests.Response) -> str:
    body = _json_o_vacio(resp)
    if not body:
        return resp.text or ""
    partes = [str(body.get("message") or "")]
    partes += [str(f.get("message") or "") for f in body.get("fields") or [] if isinstance(f, dict)]
    return " | ".join(partes)


class ErrorConexion(Exception):
    """Fallo de red saneado: sin body, cabeceras ni frames de urllib3 en el traceback."""

    def __init__(self, paso: str, ruta: str, excepcion: BaseException) -> None:
        self.reintentable = isinstance(excepcion, requests.ConnectionError)
        super().__init__(f"paso={paso} ruta={ruta} excepcion={type(excepcion).__name__}")


class _CuerpoSensible(dict):
    """Body con credenciales: su repr no expone valores si pytest muestra argumentos de frames."""

    def __repr__(self) -> str:
        return "<cuerpo sensible omitido>"

    __str__ = __repr__


def _causa(exc: BaseException) -> str:
    """Resumen de la excepción original para combinarla con el fallo del teardown."""
    return f"{type(exc).__name__}: {_seguro(str(exc))}"


def _test_actual() -> str:
    """Id del test en curso según pytest (``archivo::test[param] (call)`` → ``test[param]``)."""
    actual = os.environ.get("PYTEST_CURRENT_TEST", "")
    return actual.split("::")[-1].split(" ")[0] if actual else "-"


def _trazar(metodo: str, ruta: str, resp: requests.Response | None, inicio: float, error: str | None = None) -> None:
    """Una línea JSON por request en $TEST_EVIDENCE_DIR/trazas_http.jsonl. Sin cabeceras ni bodies."""
    carpeta = os.environ.get("TEST_EVIDENCE_DIR")
    if not carpeta:
        return
    body = _json_o_vacio(resp) if resp is not None else {}
    linea = {
        "tipo": "http",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test": _test_actual(),
        "metodo": metodo,
        "ruta": ruta,
        "http": resp.status_code if resp is not None else None,
        "error_code": body.get("error_code"),
        "fields": [
            {"field": f.get("field"), "type": f.get("type")}
            for f in body.get("fields") or []
            if isinstance(f, dict)
        ],
        "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
    }
    if error is not None:
        linea["error_conexion"] = error
    _escribir_traza(carpeta, linea)


def _trazar_conteo(momento: str, id_activo: int, total: int) -> None:
    """Registro de tipo 'conteo' (base / final) para dejar constancia de la inocuidad."""
    carpeta = os.environ.get("TEST_EVIDENCE_DIR")
    if not carpeta:
        return
    _escribir_traza(
        carpeta,
        {
            "tipo": "conteo",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test": _test_actual(),
            "momento": momento,
            "id_activo": id_activo,
            "total_medicamentos": total,
        },
    )


def _escribir_traza(carpeta: str, linea: dict) -> None:
    destino = Path(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    with open(destino / ARCHIVO_TRAZA, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False) + "\n")


class Corrida:
    """Una corrida del sandbox: run_id propio, un solo login y teardown con rollback.

    Todas las rutas son relativas y se resuelven SOLO contra $TEST_BASE_URL.
    """

    def __init__(self, prefijo: str) -> None:
        self.base = _env("TEST_BASE_URL").rstrip("/")
        self.run_id = f"{prefijo}-{uuid.uuid4()}"
        self.token: str | None = None
        self.cerrada = False
        self.preparacion: dict = {}
        self.http = requests.Session()
        self.http.headers.update(
            {
                "X-Test-Run-Id": self.run_id,
                "X-Sandbox-Secret": _env("TEST_SANDBOX_SECRET"),
                "X-Zona-Horaria": NOMBRE_ZONA,
            }
        )

    def seguro(self, texto: str) -> str:
        return _seguro(texto, (self.token,) if self.token else ())

    def _enviar(self, metodo: str, ruta: str, paso: str | None = None, **kw) -> requests.Response:
        assert ruta.startswith("/"), f"Ruta relativa esperada; recibido {ruta!r}"
        inicio = time.perf_counter()
        try:
            resp = self.http.request(metodo, self.base + ruta, timeout=TIMEOUT_S, **kw)
        except requests.RequestException as exc:
            _trazar(metodo, ruta, None, inicio, error=type(exc).__name__)
            # from None: el traceback no arrastra los frames de urllib3 (body y cabeceras).
            raise ErrorConexion(paso or _test_actual(), ruta, exc) from None
        _trazar(metodo, ruta, resp, inicio)
        return resp

    def get(self, ruta: str, paso: str | None = None, **kw) -> requests.Response:
        """GET con reintento solo ante errores de conexión (máx. REINTENTOS_GET)."""
        for intento in range(REINTENTOS_GET + 1):
            try:
                return self._enviar("GET", ruta, paso=paso, **kw)
            except ErrorConexion as exc:
                if not exc.reintentable or intento == REINTENTOS_GET:
                    raise
        raise AssertionError("inalcanzable")

    def post(self, ruta: str, json: dict, paso: str | None = None) -> requests.Response:
        """POST sin reintentos: un reintento podría duplicar una escritura."""
        return self._enviar("POST", ruta, paso=paso, json=json)

    def login(self) -> None:
        assert self.token is None, "DEF-04: solo se permite un login por run_id"
        r = self.post(
            "/sesiones/",
            _CuerpoSensible(
                correo_electronico=_env("TEST_ADMIN_EMAIL"), contrasena=_env("TEST_ADMIN_PASSWORD")
            ),
            paso="login",
        )
        assert r.status_code == 200, (
            f"PRECONDICION_NO_CUMPLIDA: paso=login admin HTTP {r.status_code}, error_code={_error_code(r)}"
        )
        token = _json_o_vacio(r).get("token")
        assert token, f"PRECONDICION_NO_CUMPLIDA: paso=login sin token (claves {sorted(_json_o_vacio(r).keys())})"
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


def _assert_teardown(resp: requests.Response | None, corrida: Corrida) -> None:
    assert resp is not None, "Teardown ya ejecutado antes; no se pudo verificar el rollback"
    assert resp.status_code == 200, (
        f"Teardown DELETE /test-control/runs/<run_id> HTTP {resp.status_code}: {corrida.seguro(resp.text)}"
    )
    status = _json_o_vacio(resp).get("status", "")
    assert "Rollback exitoso" in status, f"Teardown sin 'Rollback exitoso': status={status!r}"


def _cerrar_tras_error(corrida: Corrida, original: BaseException) -> None:
    """Teardown inmediato tras un fallo: si también falla, el mensaje lleva ambas causas.

    Si el teardown sale bien no lanza nada: el llamador re-lanza la excepción original intacta.
    """
    try:
        resp = corrida.cerrar()
    except Exception as exc_td:  # ErrorConexion u otro fallo del propio DELETE
        raise AssertionError(f"{_causa(original)} | teardown: {type(exc_td).__name__}") from None
    if resp is None:
        return
    status = _json_o_vacio(resp).get("status", "")
    if resp.status_code != 200 or "Rollback exitoso" not in status:
        raise AssertionError(f"{_causa(original)} | teardown: HTTP {resp.status_code}") from None


def _cerrar_ok(corrida: Corrida) -> None:
    """Teardown sin error previo: exige 200 + 'Rollback exitoso'."""
    try:
        resp = corrida.cerrar()
    except ErrorConexion as exc_td:
        raise AssertionError(f"teardown: {exc_td}") from None
    _assert_teardown(resp, corrida)


def _id_activo() -> int:
    valor = _env("TEST_M05_ACTIVO_ID", obligatoria=False, defecto=ID_ACTIVO_POR_DEFECTO)
    assert valor.isdigit(), f"PRECONDICION_NO_CUMPLIDA: TEST_M05_ACTIVO_ID no es un entero ({valor!r})"
    return int(valor)


def _contar_medicamentos(c: Corrida, id_activo: int) -> int:
    r = c.get("/suministros/medicamentos", params={"id_activo_biologico": id_activo})
    assert r.status_code == 200, (
        f"GET /suministros/medicamentos?id_activo_biologico={id_activo} HTTP {r.status_code}, "
        f"error_code={_error_code(r)}: {c.seguro(r.text)}"
    )
    body = _json_o_vacio(r)
    assert isinstance(body.get("total"), int), f"Respuesta de listado sin 'total' entero: {sorted(body.keys())}"
    return body["total"]


def _leer_activo(c: Corrida, id_activo: int, paso: str = "leer activo") -> dict:
    r = c.get(f"/activos-biologicos/{id_activo}")
    assert r.status_code == 200, (
        f"PRECONDICION_NO_CUMPLIDA: paso={paso} GET /activos-biologicos/{id_activo} "
        f"HTTP {r.status_code}, error_code={_error_code(r)}"
    )
    return _json_o_vacio(r)


def _fases_activas(c: Corrida, id_activo: int, paso: str) -> list[dict]:
    r = c.get(f"/activos-biologicos/{id_activo}/fases")
    assert r.status_code == 200, (
        f"PRECONDICION_NO_CUMPLIDA: paso={paso} GET /activos-biologicos/{id_activo}/fases "
        f"HTTP {r.status_code}, error_code={_error_code(r)}"
    )
    return [f for f in _json_o_vacio(r).get("fases") or [] if f.get("es_activa") is True]


def _fecha_iso(valor) -> date | None:
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _elegir_ciclo(c: Corrida, id_activo: int) -> dict:
    """Ciclo productivo compatible con la especie del activo.

    ``GET /activos-biologicos/{id}/ciclos-productivos`` devuelve SOLO los ciclos de la
    especie del activo (``ciclo_productivo_m09_adapter.listar_por_especie``: filtro
    ``cb.id_especie = :id_especie``). De esos se toma, de forma determinista, el de menor
    ``id_ciclo_productivo`` que tenga fases configuradas (un ciclo sin fases da
    ``CICLO_SIN_FASES``). ``POST /fases`` vuelve a validar la especie en el servidor
    (``CICLO_ESPECIE_INCOMPATIBLE``); si ocurriera, la preparación falla con ese error_code.
    """
    r = c.get(f"/activos-biologicos/{id_activo}/ciclos-productivos")
    assert r.status_code == 200, (
        f"PRECONDICION_NO_CUMPLIDA: paso=listar ciclos de la especie GET "
        f"/activos-biologicos/{id_activo}/ciclos-productivos HTTP {r.status_code}, error_code={_error_code(r)}"
    )
    body = _json_o_vacio(r)
    assert body.get("id_activo_biologico") == id_activo, (
        f"PRECONDICION_NO_CUMPLIDA: paso=listar ciclos devolvió el activo {body.get('id_activo_biologico')}, "
        f"esperado {id_activo}"
    )
    con_fases = sorted(
        (ci for ci in body.get("items") or [] if ci.get("fases")),
        key=lambda ci: ci["id_ciclo_productivo"],
    )
    assert con_fases, (
        f"PRECONDICION_NO_CUMPLIDA: paso=listar ciclos: la especie del activo {id_activo} no tiene ciclos "
        f"productivos con fases (total={body.get('total')})"
    )
    return con_fases[0]


def _preparar(c: Corrida, id_activo: int) -> dict:
    """Verifica el activo y abre una fase del ciclo productivo si no hay ninguna abierta."""
    activo = _leer_activo(c, id_activo, paso="verificar activo")
    p = "PRECONDICION_NO_CUMPLIDA: paso=verificar activo"
    assert activo.get("tipo") == "INDIVIDUAL", f"{p}: tipo={activo.get('tipo')!r}, se requiere INDIVIDUAL"
    assert activo.get("id_estado") == ESTADO_ACTIVO, (
        f"{p}: id_estado={activo.get('id_estado')} ({activo.get('nombre_estado')}), se requiere {ESTADO_ACTIVO}"
    )
    fecha_previa = _fecha_iso(activo.get("fecha_inicio_ciclo"))
    assert fecha_previa is not None, f"{p}: el activo {id_activo} no tiene fecha_inicio_ciclo (E3 no verificable)"

    ciclo_usado = None
    fase_abierta_por_prueba = False
    if not _fases_activas(c, id_activo, paso="consultar fases antes de abrir"):
        ciclo_usado = _elegir_ciclo(c, id_activo)
        id_ciclo = ciclo_usado["id_ciclo_productivo"]
        rf = c.post(
            f"/activos-biologicos/{id_activo}/fases",
            {"id_ciclo_productiva": id_ciclo, "motivo_cambio": "TC-M05-G14: apertura de fase en sandbox"},
        )
        assert rf.status_code == 201, (
            f"PRECONDICION_NO_CUMPLIDA: paso=abrir fase POST /activos-biologicos/{id_activo}/fases "
            f"(id_ciclo_productiva={id_ciclo}) HTTP {rf.status_code}, error_code={_error_code(rf)}"
        )
        creada = _json_o_vacio(rf)
        assert creada.get("es_activa") is True and creada.get("id_ciclo_productiva") == id_ciclo, (
            f"PRECONDICION_NO_CUMPLIDA: paso=abrir fase HTTP 201 pero es_activa={creada.get('es_activa')!r}, "
            f"id_ciclo_productiva={creada.get('id_ciclo_productiva')!r} (esperado {id_ciclo})"
        )
        fase_abierta_por_prueba = True

    # Relectura posterior a la preparación: estado, fase abierta y fecha_inicio_ciclo.
    activo_post = _leer_activo(c, id_activo, paso="releer activo tras preparar")
    activas = _fases_activas(c, id_activo, paso="releer fases tras preparar")
    assert activas, (
        f"PRECONDICION_NO_CUMPLIDA: paso=releer fases tras preparar: el activo {id_activo} sigue sin fase es_activa"
    )
    assert activo_post.get("id_estado") == ESTADO_ACTIVO, (
        f"PRECONDICION_NO_CUMPLIDA: paso=releer activo tras preparar: id_estado={activo_post.get('id_estado')}, "
        f"se requiere {ESTADO_ACTIVO}"
    )
    fecha_post = _fecha_iso(activo_post.get("fecha_inicio_ciclo"))
    assert fecha_post is not None and fecha_post == fecha_previa, (
        f"PRECONDICION_NO_CUMPLIDA: paso=releer activo tras preparar: fecha_inicio_ciclo cambió o es nula "
        f"(antes={fecha_previa}, después={fecha_post})"
    )
    return {
        "id_activo": id_activo,
        "activo": activo_post,
        "fecha_inicio_ciclo": fecha_post,  # B08/B09 usan SIEMPRE el valor releído
        "fases_activas": activas,
        "ciclo_usado": ciclo_usado,
        "fase_abierta_por_prueba": fase_abierta_por_prueba,
    }


def _payload(id_activo: int, hora: str, **cambios) -> dict:
    """Payload base de la ficha; ``fecha_aplicacion`` = hoy en America/Bogota al momento de la llamada."""
    base = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": _hoy().isoformat(),
        "hora_aplicacion": hora,
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 10,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": "Tratamiento de infección respiratoria",
        "costo_unitario": 500,
        "nombre_veterinario": "Dr. Pérez",
    }
    base.update(cambios)
    return base


def _describir(payload: dict, campo_variado: str | None) -> str:
    if campo_variado is None:
        return "payload base"
    if campo_variado not in payload:
        return f"sin '{campo_variado}'"
    valor = payload[campo_variado]
    if isinstance(valor, str) and len(valor) > 30:
        return f"{campo_variado}=<{len(valor)} caracteres>"
    return f"{campo_variado}={valor!r}"


def _assert_registro_valido(c: Corrida, resp: requests.Response, enviado: str, antes: int, id_activo: int) -> dict:
    """Comprobaciones comunes de un 201 de la especificación: VALIDADO, sin retiro, +1, activo sigue ACTIVO."""
    assert resp.status_code == 201, (
        f"[{enviado}] esperado HTTP 201; recibido {resp.status_code}, error_code={_error_code(resp)}: "
        f"{c.seguro(resp.text)}"
    )
    medicamento = _json_o_vacio(resp).get("medicamento") or {}
    assert medicamento.get("estado_registro") == "VALIDADO", (
        f"[{enviado}] HTTP 201: estado_registro esperado 'VALIDADO'; obtenido {medicamento.get('estado_registro')!r}"
    )
    assert medicamento.get("fecha_fin_retiro") is None, (
        f"[{enviado}] HTTP 201: con periodo_retiro_dias=0 no debe haber fecha_fin_retiro; "
        f"obtenido {medicamento.get('fecha_fin_retiro')!r}"
    )
    despues = _contar_medicamentos(c, id_activo)
    assert despues == antes + 1, (
        f"[{enviado}] HTTP 201 pero el conteo de registros del activo pasó de {antes} a {despues} (esperado +1)"
    )
    estado = _leer_activo(c, id_activo).get("id_estado")
    assert estado == ESTADO_ACTIVO, (
        f"[{enviado}] HTTP 201: con retiro 0 el activo debe seguir en id_estado={ESTADO_ACTIVO}; obtenido {estado} "
        "(RF-44 no debía invocarse)"
    )
    return medicamento


def _assert_rechazo(
    c: Corrida,
    resp: requests.Response,
    enviado: str,
    antes: int,
    id_activo: int,
    error_code: str | None = None,
    campo: str | None = None,
    texto: str | None = None,
) -> None:
    """HTTP 400; error_code / campo en fields[] / texto exigidos (si se piden); y nada persistido.

    Si se piden ``campo`` y ``texto`` a la vez, basta con que se cumpla UNO de los dos.
    """
    code = _error_code(resp)
    assert resp.status_code == 400, (
        f"[{enviado}] esperado HTTP 400; recibido {resp.status_code}, error_code={code}: {c.seguro(resp.text)}"
    )
    if error_code is not None:
        assert code == error_code, f"[{enviado}] HTTP 400 con error_code esperado {error_code!r}; obtenido {code!r}"
    campos = _campos_error(resp)
    mensajes = _mensajes_error(resp)
    if campo is not None and texto is not None:
        assert campo in campos or texto in mensajes, (
            f"[{enviado}] HTTP 400 error_code={code}: se esperaba {campo!r} en fields[] o {texto!r} en el mensaje; "
            f"fields={campos}, mensaje={c.seguro(mensajes)!r}"
        )
    elif campo is not None:
        assert campo in campos, (
            f"[{enviado}] HTTP 400 error_code={code}: fields[] debe incluir {campo!r}; obtenido {campos}"
        )
    elif texto is not None:
        assert texto in mensajes, (
            f"[{enviado}] HTTP 400 error_code={code}: el mensaje debe contener {texto!r}; "
            f"obtenido {c.seguro(mensajes)!r}"
        )
    despues = _contar_medicamentos(c, id_activo)
    assert despues == antes, (
        f"[{enviado}] HTTP {resp.status_code} error_code={code}: no debía persistir; "
        f"conteo de registros del activo pasó de {antes} a {despues}"
    )


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _registrar_orden(request):
    """Anota cada test ejecutado de este archivo (guardia de orden de test_00)."""
    yield
    _EJECUTADOS.append(request.node.name)


@pytest.fixture(scope="module")
def corrida_principal(request):
    """Corrida principal: 1 login + preparación; el teardown se verifica en test_zz y aquí como red.

    A1: si el login o la preparación fallan, la corrida se cierra EN ESE MOMENTO (antes de
    propagar el error), para que ninguna corrida quede abierta mientras otra hace login.
    """
    c = Corrida("test-m05-g14")
    try:
        c.login()
        c.preparacion = _preparar(c, _id_activo())
    except BaseException as exc:
        _cerrar_tras_error(c, exc)
        raise

    def _finalizar() -> None:
        if not c.cerrada:
            _cerrar_ok(c)

    request.addfinalizer(_finalizar)
    return c


# --------------------------------------------------------------------------- 1. inocuidad inicial


def test_00_inocuidad_linea_base():
    """Corrida aparte: conteo base de medicamentos del activo antes de cualquier caso."""
    assert not _EJECUTADOS, (
        "ORDEN_INVALIDO: test_00_inocuidad_linea_base debe ser el primer test del archivo; ya se ejecutaron "
        f"{_EJECUTADOS}. Ejecute el archivo completo, en orden y con -p no:randomly."
    )
    c = Corrida("test-m05-g14-inocuidad-ini")
    try:
        c.login()
        id_activo = _id_activo()
        total = _contar_medicamentos(c, id_activo)
    except BaseException as exc:
        _cerrar_tras_error(c, exc)
        raise
    _cerrar_ok(c)
    _INOCUIDAD["inicial"] = total
    _trazar_conteo("base", id_activo, total)


# --------------------------------------------------------------------------- 2. corrida principal


def test_01_preparacion(corrida_principal):
    prep = corrida_principal.preparacion
    activo = prep["activo"]
    p = "PRECONDICION_NO_CUMPLIDA"
    assert activo.get("id_activo_biologico") == prep["id_activo"], (
        f"{p}: el activo leído ({activo.get('id_activo_biologico')}) no es el configurado ({prep['id_activo']})"
    )
    assert activo.get("tipo") == "INDIVIDUAL", f"{p}: tipo={activo.get('tipo')!r}, se requiere INDIVIDUAL"
    assert activo.get("id_estado") == ESTADO_ACTIVO, f"{p}: id_estado={activo.get('id_estado')}, se requiere 1"
    assert prep["fecha_inicio_ciclo"] <= _hoy(), (
        f"{p}: fecha_inicio_ciclo={prep['fecha_inicio_ciclo']} es posterior a hoy ({_hoy()}); B08/B09 no aplican"
    )
    assert len(prep["fases_activas"]) >= 1, f"{p}: el activo debe tener una fase abierta tras la preparación"
    r = corrida_principal.get(f"/activos-biologicos/{prep['id_activo']}")
    assert r.status_code == 200, f"{p}: GET /activos-biologicos/{prep['id_activo']} HTTP {r.status_code}"
    estado = _json_o_vacio(r).get("id_estado")
    assert estado == ESTADO_ACTIVO, f"{p}: tras abrir la fase el activo debe seguir en id_estado=1; obtenido {estado}"


# Subcaso (a): (id, campo omitido o variado, valor | _OMITIR, hora, error_code esperado)
_OMITIR = object()
_CASOS_A = [
    ("A01", "id_activo_biologico", _OMITIR, "08:01", "VAL_ENTRADA"),
    ("A02", "nombre_medicamento", _OMITIR, "08:02", "VAL_ENTRADA"),
    ("A03", "fecha_aplicacion", _OMITIR, "08:03", "VAL_ENTRADA"),
    ("A04", "hora_aplicacion", _OMITIR, "08:04", "VAL_ENTRADA"),
    ("A05", "via_administracion", _OMITIR, "08:05", "VAL_ENTRADA"),
    ("A06", "dosis_aplicada", _OMITIR, "08:06", "VAL_ENTRADA"),
    ("A07", "unidad_dosis", _OMITIR, "08:07", "VAL_ENTRADA"),
    ("A08", "motivo_aplicacion", _OMITIR, "08:08", "VAL_ENTRADA"),
    ("A09", "costo_unitario", _OMITIR, "08:09", "VAL_ENTRADA"),
    ("A10", "nombre_veterinario", _OMITIR, "08:10", "VAL_ENTRADA"),
    ("A11", "via_administracion", "ORAL2", "08:11", "VIA_ADMINISTRACION_INVALIDA"),
    ("A12", "nombre_veterinario", None, "08:12", "VAL_ENTRADA"),
    ("A13", "unidad_dosis", "", "08:13", "VAL_ENTRADA"),
    ("A14", "hora_aplicacion", "25:99", "08:14", "VAL_ENTRADA"),
    ("A15", "fecha_aplicacion", "15-09-2026", "08:15", "VAL_ENTRADA"),
    ("A16", "nombre_medicamento", "M" * 51, "08:16", "VAL_ENTRADA"),
]


@pytest.mark.parametrize(
    "campo,valor,hora,error_code",
    [pytest.param(c, v, h, e, id=f"{i}-{c}-{'omitido' if v is _OMITIR else 'invalido'}") for i, c, v, h, e in _CASOS_A],
)
def test_a_rechazo_campos(corrida_principal, campo, valor, hora, error_code):
    c = corrida_principal
    id_activo = c.preparacion["id_activo"]
    payload = _payload(id_activo, hora)
    if valor is _OMITIR:
        payload.pop(campo)
    else:
        payload[campo] = valor
    enviado = _describir(payload, campo)

    antes = _contar_medicamentos(c, id_activo)
    resp = c.post("/suministros/medicamentos", payload)
    _assert_rechazo(c, resp, enviado, antes, id_activo, error_code=error_code, campo=campo)


def test_a17_estado_activo_tras_grupo_a(corrida_principal):
    """Al final del subcaso (a) el activo sigue ACTIVO: RF-44 no se invocó."""
    id_activo = corrida_principal.preparacion["id_activo"]
    r = corrida_principal.get(f"/activos-biologicos/{id_activo}")
    assert r.status_code == 200, f"GET /activos-biologicos/{id_activo} HTTP {r.status_code}, error_code={_error_code(r)}"
    estado = _json_o_vacio(r).get("id_estado")
    assert estado == ESTADO_ACTIVO, f"Tras el subcaso (a) el activo debe seguir en id_estado=1; obtenido {estado}"


# Subcaso (b) en la corrida principal: (id, cambios, hora, esperado, error_code, campo, texto)
# Las fechas relativas se resuelven en tiempo de ejecución con "hoy" y la fecha_inicio_ciclo
# RELEÍDA tras la preparación. B04 acepta campo en fields[] O el texto de E6.
_CASOS_B = [
    ("B01", {"dosis_aplicada": 0}, "09:01", 400, None, None, "mayor a cero"),
    ("B02", {"dosis_aplicada": -1}, "09:02", 400, None, None, "mayor a cero"),
    ("B04", {"motivo_aplicacion": "Preventiv"}, "09:04", 400, None, "motivo_aplicacion", "10 caracteres"),
    ("B05", {"motivo_aplicacion": "Preventiva"}, "09:05", 201, None, None, None),
    ("B06", {"fecha_aplicacion": "HOY"}, "09:06", 201, None, None, None),
    ("B07", {"fecha_aplicacion": "HOY+1"}, "09:07", 400, "FECHA_FUTURA", None, None),
    ("B08", {"fecha_aplicacion": "INICIO-1"}, "09:08", 400, "FECHA_ANTERIOR_A_CICLO", None, None),
    ("B09", {"fecha_aplicacion": "INICIO"}, "09:09", 201, None, None, None),
]

_IDS_B = {
    "B01": "B01-dosis_0",
    "B02": "B02-dosis_negativa",
    "B04": "B04-motivo_9_caracteres",
    "B05": "B05-motivo_10_caracteres",
    "B06": "B06-fecha_hoy",
    "B07": "B07-fecha_manana",
    "B08": "B08-fecha_inicio_ciclo_menos_1",
    "B09": "B09-fecha_inicio_ciclo",
}


def _resolver_fecha(simbolo: str, fecha_inicio: date) -> str:
    return {
        "HOY": _hoy(),
        "HOY+1": _hoy() + timedelta(days=1),
        "INICIO-1": fecha_inicio - timedelta(days=1),
        "INICIO": fecha_inicio,
    }[simbolo].isoformat()


@pytest.mark.parametrize(
    "cambios,hora,esperado,error_code,campo,texto",
    [pytest.param(cb, h, e, ec, ca, t, id=_IDS_B[i]) for i, cb, h, e, ec, ca, t in _CASOS_B],
)
def test_b_valores_limite(corrida_principal, cambios, hora, esperado, error_code, campo, texto):
    c = corrida_principal
    id_activo = c.preparacion["id_activo"]
    cambios = dict(cambios)
    if "fecha_aplicacion" in cambios:
        cambios["fecha_aplicacion"] = _resolver_fecha(cambios["fecha_aplicacion"], c.preparacion["fecha_inicio_ciclo"])
    payload = _payload(id_activo, hora, **cambios)
    enviado = ", ".join(_describir(payload, k) for k in cambios)

    antes = _contar_medicamentos(c, id_activo)
    resp = c.post("/suministros/medicamentos", payload)
    if esperado == 201:
        _assert_registro_valido(c, resp, enviado, antes, id_activo)
    else:
        _assert_rechazo(c, resp, enviado, antes, id_activo, error_code=error_code, campo=campo, texto=texto)


def test_zz_cierre_corrida_principal(corrida_principal):
    """Teardown explícito de la corrida principal antes de B03 y de la inocuidad final."""
    _cerrar_ok(corrida_principal)


# --------------------------------------------------------------------------- 3. B03, corrida propia


@pytest.mark.parametrize("dosis", [pytest.param(0.0001, id="B03-dosis_0.0001")])
def test_zz_b03_dosis_minima(dosis):
    """dosis_aplicada=0.0001 (decimal 10,4) → 201 y persistido. Corrida aislada por riesgo de error de BD."""
    c = Corrida("test-m05-g14-b03")
    try:
        c.login()
        prep = _preparar(c, _id_activo())
        id_activo = prep["id_activo"]
        payload = _payload(id_activo, "09:03", dosis_aplicada=dosis)
        enviado = _describir(payload, "dosis_aplicada")

        antes = _contar_medicamentos(c, id_activo)
        resp = c.post("/suministros/medicamentos", payload)
        medicamento = _assert_registro_valido(c, resp, enviado, antes, id_activo)
        recibido = medicamento.get("cantidad")
        assert recibido is not None, f"[{enviado}] HTTP 201 sin 'cantidad' en la respuesta"
        try:
            cantidad = Decimal(str(recibido))
        except InvalidOperation:
            raise AssertionError(f"[{enviado}] HTTP 201: 'cantidad' no es decimal ({recibido!r})") from None
        assert cantidad == Decimal("0.0001"), (
            f"[{enviado}] HTTP 201: la dosis persistida debe conservar 4 decimales (Decimal('0.0001')); "
            f"obtenido {recibido!r}"
        )
    except BaseException as exc:
        _cerrar_tras_error(c, exc)
        raise
    _cerrar_ok(c)


# --------------------------------------------------------------------------- 4. inocuidad final


def test_zz_inocuidad_final():
    """Corrida aparte tras todos los teardown: el conteo debe igualar la línea base (cero contaminación)."""
    c = Corrida("test-m05-g14-inocuidad-fin")
    try:
        c.login()
        id_activo = _id_activo()
        final = _contar_medicamentos(c, id_activo)
    except BaseException as exc:
        _cerrar_tras_error(c, exc)
        raise
    _cerrar_ok(c)
    _trazar_conteo("final", id_activo, final)
    assert "inicial" in _INOCUIDAD, (
        "No hay línea base: test_00_inocuidad_linea_base no llegó a registrar el conteo inicial"
    )
    assert final == _INOCUIDAD["inicial"], (
        f"Contaminación: el activo tenía {_INOCUIDAD['inicial']} registros antes de la suite y {final} después"
    )
