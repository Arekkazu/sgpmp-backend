"""TC-M09-G29 — REEVALUACIÓN V2 (RF-17): propagación de umbrales hacia Nodo Edge.

TC-M09-62 (propagación exitosa) y TC-M09-63 (fallo de sincronización).

Verificación de implementación de SOLO LECTURA en DEV, el ambiente decisorio porque
MQTT solo existe allí:
- contrato OpenAPI desplegado en DEV y TEST (GET sin autenticación);
- código de ``origin/dev`` con ``git show`` / ``git grep`` (sin checkout ni fetch);
- en tiempo de ejecución, login del Administrador DEV y GET de umbrales reales para
  comprobar si el recurso expone estado de sincronización.

No se ejecuta ningún POST ni PATCH de umbral, ni SQL, ni conexión MQTT. Las pruebas
``test_oraculo_*`` codifican lo que exige RF-17/matriz; si fallan, documentan la
ausencia del flujo y no se ajustan para que pasen.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parents[5]
RUN_ID = os.environ.get("G29_REEVAL_V2_RUN_ID", "")
RESULTADOS = AQUI / "RESULTADOS" / RUN_ID

DEV = "https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp"
TEST_SUMINISTRADA = "http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
TEST_HTTPS = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
DEV_ADMIN = "admin.general@pecuaria.co"

PATRON_SYNC = re.compile(r"sincroniz|sync|pendient|pending|edge|mqtt|propag|ack", re.I)
PATRON_INTEGRACION = re.compile(r"mqtt|MqttPort|MqttHttpAdapter|broker|nodo.?edge|NodoEdge|publicar|publish|/v1/commands|sincroniz", re.I)

ARCHIVOS_RF17 = [
    "src/configuration/application/use_cases/umbrales/registrar_umbral_use_case.py",
    "src/configuration/application/use_cases/umbrales/editar_umbral_use_case.py",
    "src/configuration/infrastructure/routers/umbral_router.py",
    "src/configuration/infrastructure/schema/umbral_schema.py",
    "src/configuration/domain/entities/umbral_ambiental.py",
]

EVIDENCIA: dict = {}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=BACKEND, capture_output=True, text=True, check=True, encoding="utf-8").stdout


def _http(url: str, *, metodo: str = "GET", cuerpo: dict | None = None, token: str | None = None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"Accept": "application/json", "Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            texto = r.read().decode("utf-8")
            return r.status, (json.loads(texto) if texto.strip().startswith(("{", "[")) else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def _limpio(obj):
    texto = json.dumps(obj, ensure_ascii=False)
    for secreto in filter(None, [os.environ.get("DEV_ADMIN_PASSWORD")]):
        texto = texto.replace(secreto, "[REDACTED]")
    texto = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[JWT REDACTED]", texto)
    return json.loads(texto)


def _contrato(base: str) -> dict:
    salud, _ = _http(base + "/health")
    estado, api = _http(base + "/openapi.json")
    res = {"base": base, "health": salud, "openapi": estado}
    if estado != 200 or not api:
        return res
    rutas = api["paths"]
    schemas = api.get("components", {}).get("schemas", {})
    ops = {}
    for ruta in ("/configuracion/umbrales", "/configuracion/umbrales/{id_umbral_ambiental}"):
        for metodo, op in rutas.get(ruta, {}).items():
            ops[f"{metodo.upper()} {ruta}"] = sorted(op.get("responses", {}).keys())
    res.update({
        "operacionesRF17": ops,
        "umbralAmbientalResponse": list(schemas.get("UmbralAmbientalResponse", {}).get("properties", {}).keys()),
        "rutasUmbrales": [p for p in rutas if "umbral" in p.lower()],
        "rutasSincronizacionEdgeMqtt": [p for p in rutas if re.search(r"edge|mqtt|sincron|sync|pendient|broker|nodo", p, re.I)],
    })
    return res


@pytest.fixture(scope="session", autouse=True)
def evidencia():
    assert RUN_ID and re.fullmatch(r"[\w-]+", RUN_ID), "G29_REEVAL_V2_RUN_ID requerido"
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    destino = RESULTADOS / "TC-M09-G29-evidencia-v2.json"
    assert not destino.exists(), "No sobrescribir evidencia existente"
    EVIDENCIA.update({
        "grupo": "TC-M09-G29", "casos": ["TC-M09-62", "TC-M09-63"], "rf": "RF-17", "tipo": "REEVALUACION V2",
        "runId": RUN_ID, "fechaInicio": datetime.now(timezone.utc).isoformat(), "ambienteDecisorio": "DEV",
        "naturaleza": "verificacion de implementacion read-only (contrato desplegado + codigo origin/dev + GET autenticado DEV); sin escrituras",
        "git": {
            "rama": _git("branch", "--show-current").strip(), "head": _git("rev-parse", "HEAD").strip(),
            "originDev": _git("rev-parse", "origin/dev").strip(),
            "originDevUltimoCommit": _git("log", "-1", "--format=%h %cs %s", "origin/dev").strip(),
            "diffSrcHeadVsOriginDev": _git("diff", "--stat", "HEAD", "origin/dev", "--", "src").strip() or "(sin diferencias)",
        },
        "clienteMqtt": {
            "paho_mqtt": importlib.util.find_spec("paho") is not None,
            "mosquitto_sub": shutil.which("mosquitto_sub") is not None,
            "mosquitto_pub": shutil.which("mosquitto_pub") is not None,
            "mqttx": shutil.which("mqttx") is not None,
            "mqtt_cli": shutil.which("mqtt") is not None,
        },
    })
    yield EVIDENCIA
    EVIDENCIA["fechaFin"] = datetime.now(timezone.utc).isoformat()
    destino.write_text(json.dumps(_limpio(EVIDENCIA), indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="session")
def contratos():
    c = {"DEV": _contrato(DEV), "TEST_suministrada": _contrato(TEST_SUMINISTRADA), "TEST_https": _contrato(TEST_HTTPS)}
    EVIDENCIA["contratos"] = c
    return c


@pytest.fixture(scope="session")
def dev_runtime():
    password = os.environ.get("DEV_ADMIN_PASSWORD")
    assert password, "DEV_ADMIN_PASSWORD requerida (solo en proceso)"
    estado, login = _http(DEV + "/sesiones/", metodo="POST", cuerpo={"correo_electronico": DEV_ADMIN, "contrasena": password})
    assert estado == 200 and login and login.get("token"), f"login DEV HTTP {estado}"
    token = login["token"]
    _, me = _http(DEV + "/usuarios/me", token=token)
    _, perms = _http(DEV + "/sesiones/me/permisos", token=token)
    _, especies = _http(DEV + "/configuracion/especies", token=token)
    activas = [e for e in (especies or {}).get("items", []) if e.get("es_activo")]
    muestras = []
    for e in activas:
        st, umb = _http(DEV + f"/configuracion/umbrales?id_especie={e['id_especie']}", token=token)
        items = (umb or {}).get("items", [])
        if items:
            muestras.append({"id_especie": e["id_especie"], "especie": e["nombre"], "status": st, "total": len(items),
                             "camposItem": sorted(items[0].keys()), "ejemplo": {k: items[0][k] for k in ("id_umbral_ambiental", "id_variable_ambiental", "valor_min", "valor_max", "es_activo", "fecha_actualizacion")}})
        if len(muestras) >= 2:
            break
    st_aud = None
    if muestras:
        st_aud, aud = _http(DEV + f"/configuracion/umbrales/{muestras[0]['ejemplo']['id_umbral_ambiental']}/auditoria", token=token)
        muestras[0]["auditoriaStatus"] = st_aud
        if isinstance(aud, dict):
            muestras[0]["auditoriaCampos"] = sorted((aud.get("items") or [{}])[0].keys()) if aud.get("items") else sorted(aud.keys())
    rt = {
        "actor": {"correo": me.get("correo_electronico") if me else None, "rol": me.get("nombre_rol") if me else None, "estado": me.get("estado_cuenta") if me else None,
                  "permisosRecurso20": sorted(p["id_accion"] for p in (perms or {}).get("permisos", []) if p["id_recurso"] == 20)},
        "especiesActivas": len(activas), "muestrasUmbrales": muestras, "tokenPersistido": False,
    }
    EVIDENCIA["devRuntime"] = rt
    return rt


@pytest.fixture(scope="session")
def codigo_dev():
    fuentes = {r: _git("show", f"origin/dev:{r}") for r in ARCHIVOS_RF17}
    consumidores_mqtt = [l for l in _git("grep", "-n", "-E", "MqttPort|MqttHttpAdapter|enviar_configuracion", "origin/dev", "--", "src").splitlines()
                         if "mqtt_port.py" not in l and "mqtt_http_adapter.py" not in l]
    usos_nodo_edge = _git("grep", "-n", "-E", "NodoEdgePort|NodoEdgeStubAdapter", "origin/dev", "--", "src").splitlines()
    stub = _git("show", "origin/dev:src/prediction/infrastructure/adapters/nodo_edge_stub_adapter.py")
    EVIDENCIA["codigoOriginDev"] = {
        "archivosRF17": ARCHIVOS_RF17,
        "referenciasIntegracionEnRF17": {r: [l.strip() for l in s.splitlines() if PATRON_INTEGRACION.search(l)] for r, s in fuentes.items()},
        "consumidoresMqttPort": consumidores_mqtt,
        "usosNodoEdgePort": usos_nodo_edge,
        "nodoEdgeStub": [l.strip() for l in stub.splitlines() if l.strip()],
    }
    return fuentes, consumidores_mqtt, usos_nodo_edge


# ── Precondiciones ────────────────────────────────────────────────────────────

def test_rama_obligatoria():
    assert EVIDENCIA["git"]["rama"] == "qa/juan-esteban-re-evaluacion-M02"


def test_codigo_local_equivale_a_origin_dev():
    assert EVIDENCIA["git"]["diffSrcHeadVsOriginDev"] == "(sin diferencias)"


def test_dev_accesible_y_rf17_rest_desplegado(contratos):
    dev = contratos["DEV"]
    assert dev["health"] == 200 and dev["openapi"] == 200
    assert "POST /configuracion/umbrales" in dev["operacionesRF17"]
    assert "PATCH /configuracion/umbrales/{id_umbral_ambiental}" in dev["operacionesRF17"]


def test_actor_dev_autorizado_rf17(dev_runtime):
    a = dev_runtime["actor"]
    assert a["rol"] in ("Administrador", "Veterinario") and a["estado"] == "Activo"
    assert {1, 2, 3}.issubset(set(a["permisosRecurso20"]))


def test_test_rest_rf17_equivalente_a_dev(contratos):
    dev, test = contratos["DEV"], contratos["TEST_https"]
    claves = ["operacionesRF17", "umbralAmbientalResponse", "rutasUmbrales"]
    EVIDENCIA["desfaseTestDev"] = {k: dev.get(k) != test.get(k) for k in claves}
    assert all(dev.get(k) == test.get(k) for k in claves)


# ── Oráculo TC-M09-62 / TC-M09-63 ─────────────────────────────────────────────

def test_oraculo_rf17_publica_hacia_mqtt_o_nodo_edge(codigo_dev):
    """TC-62/63: guardar un umbral debe disparar la propagación hacia el Edge."""
    fuentes, consumidores, usos_edge = codigo_dev
    refs = {r: [l for l in s.splitlines() if PATRON_INTEGRACION.search(l)] for r, s in fuentes.items() if "umbral" in r}
    EVIDENCIA.setdefault("oraculo", {})["rf17InvocaIntegracion"] = any(refs.values())
    assert any(refs.values()), f"Crear/editar umbral no invoca MQTT/Edge. Consumidores MqttPort: {consumidores}; NodoEdgePort: {usos_edge}"


def test_oraculo_umbral_expone_estado_de_sincronizacion(contratos, dev_runtime):
    """TC-63: la configuración debe poder quedar 'Pendiente de Sincronización'."""
    campos_contrato = [c for c in contratos["DEV"]["umbralAmbientalResponse"] if PATRON_SYNC.search(c)]
    campos_runtime = sorted({c for m in dev_runtime["muestrasUmbrales"] for c in m["camposItem"] if PATRON_SYNC.search(c)})
    EVIDENCIA.setdefault("oraculo", {})["estadoSincronizacion"] = {"contrato": campos_contrato, "runtime": campos_runtime}
    assert campos_contrato or campos_runtime, f"UmbralAmbientalResponse DEV sin estado de sincronizacion: {contratos['DEV']['umbralAmbientalResponse']}"


def test_oraculo_contrato_declara_500_por_fallo_de_sincronizacion(contratos):
    """TC-63: RF-17 exige HTTP 500 con la configuración central guardada."""
    ops = contratos["DEV"]["operacionesRF17"]
    con_500 = {k: v for k, v in ops.items() if k.split()[0] in ("POST", "PATCH") and "500" in v}
    EVIDENCIA.setdefault("oraculo", {})["operacionesCon500"] = con_500
    assert con_500, f"Ninguna escritura RF-17 declara 500: {ops}"


def test_oraculo_edge_observable_para_umbrales(contratos, codigo_dev):
    """TC-62/63: debe existir una vía para observar la configuración efectiva del Edge."""
    _, _, usos_edge = codigo_dev
    rutas = [r for r in contratos["DEV"]["rutasSincronizacionEdgeMqtt"] if "umbral" in r.lower() or "sincron" in r.lower()]
    stub = EVIDENCIA["codigoOriginDev"]["nodoEdgeStub"]
    EVIDENCIA.setdefault("oraculo", {})["edgeObservable"] = {"rutas": rutas, "nodoEdgeEsStub": any("Stub temporal" in l for l in stub)}
    assert rutas, f"Sin ruta de estado/ACK del Edge para umbrales. Rutas edge DEV: {contratos['DEV']['rutasSincronizacionEdgeMqtt']}"
