"""TC-M09-G29 — REEVALUACIÓN V3 (RF-17): propagación de umbrales hacia el Nodo Edge.

TC-M09-62 (propagación exitosa) y TC-M09-63 (fallo de sincronización). Ambiente decisorio:
DEV, porque la integración MQTT/AIoT del proyecto vive allí.

Por qué existe este archivo y no se reejecuta ``EvaluacionV2/test_tc_m09_g29.py``: aquel
fija por aserción la rama de V2 (``qa/juan-esteban-re-evaluacion-M02``) y escribe su
evidencia dentro de ``EvaluacionV2/RESULTADOS/``, que es inmutable. Este archivo conserva la
misma naturaleza y los mismos oráculos de V2 —verificación de implementación en SOLO
LECTURA— y añade el oráculo decisorio de V3: identificar qué adaptador Edge está realmente
inyectado en el flujo desplegado.

Sin escrituras: ningún POST/PATCH de umbral, ningún SQL, ninguna conexión MQTT, ningún
cambio en el índice de Git. Los ``test_oraculo_*`` codifican lo que exige RF-17/matriz; si
fallan, documentan la ausencia del flujo y no se ajustan para que pasen.
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
RUN_ID = os.environ.get("G29_REEVAL_V3_RUN_ID", "")
RESULTADOS = AQUI / "RESULTADOS" / RUN_ID

DEV = "https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp"
TEST_HTTPS = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
DEV_ADMIN = "admin.general@pecuaria.co"

PATRON_SYNC = re.compile(r"sincroniz|sync|pendient|pending|edge|mqtt|propag|ack", re.I)
PATRON_INTEGRACION = re.compile(r"mqtt|MqttPort|MqttHttpAdapter|broker|nodo.?edge|NodoEdge|edge_port|EdgeSincronizacion|publicar|publish|/v1/commands|sincroniz", re.I)

ARCHIVOS_RF17 = [
    "src/configuration/application/use_cases/umbrales/registrar_umbral_use_case.py",
    "src/configuration/application/use_cases/umbrales/editar_umbral_use_case.py",
    "src/configuration/infrastructure/routers/umbral_router.py",
    "src/configuration/domain/repositories/edge_sincronizacion_port.py",
    "src/configuration/infrastructure/adapters/edge_sincronizacion_stub_adapter.py",
]

EVIDENCIA: dict = {}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=BACKEND, capture_output=True, text=True, check=True, encoding="utf-8").stdout


def _http(url: str, *, metodo: str = "GET", cuerpo: dict | None = None, token: str | None = None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo,
                                 headers={"Accept": "application/json", "Content-Type": "application/json"})
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
    for secreto in filter(None, [os.environ.get("DEV_ADMIN_PASSWORD"), os.environ.get("MQTT_PASSWORD")]):
        texto = texto.replace(secreto, "[REDACTED]")
    texto = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[JWT REDACTED]", texto)
    return json.loads(texto)


def _guardar(nombre: str, datos) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / nombre).write_text(json.dumps(_limpio(datos), indent=2, ensure_ascii=False), encoding="utf-8")


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
        "umbralAmbientalResponse": sorted(schemas.get("UmbralAmbientalResponse", {}).get("properties", {}).keys()),
        "rutasUmbrales": sorted(p for p in rutas if "umbral" in p.lower()),
        "rutasSincronizacionEdgeMqtt": sorted(p for p in rutas if re.search(r"edge|mqtt|sincron|sync|pendient|broker|nodo", p, re.I)),
    })
    return res


@pytest.fixture(scope="session", autouse=True)
def evidencia():
    assert RUN_ID and re.fullmatch(r"[\w-]+", RUN_ID), "G29_REEVAL_V3_RUN_ID requerido"
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    destino = RESULTADOS / "TC-M09-G29-evidencia-v3.json"
    assert not destino.exists(), "No sobrescribir evidencia existente"
    EVIDENCIA.update({
        "grupo": "TC-M09-G29", "casos": ["TC-M09-62", "TC-M09-63"], "rf": "RF-17", "cu": "CU-03",
        "tipo": "REEVALUACION V3", "runId": RUN_ID,
        "fechaInicio": datetime.now(timezone.utc).isoformat(), "ambienteDecisorio": "DEV",
        "naturaleza": "verificacion de implementacion read-only (contrato desplegado + codigo origin/dev + "
                      "identificacion del adaptador inyectado); sin escrituras, sin SQL, sin MQTT",
        "escriturasEjecutadas": 0,
        "git": {
            "rama": _git("branch", "--show-current").strip(),
            "head": _git("rev-parse", "HEAD").strip(),
            "originDev": _git("rev-parse", "origin/dev").strip(),
            "originDevUltimoCommit": _git("log", "-1", "--format=%h %cs %s", "origin/dev").strip(),
            "diffSrcHeadVsOriginDev": _git("diff", "--stat", "HEAD", "origin/dev", "--", "src").strip() or "(sin diferencias)",
            "indiceIntacto": _git("diff", "--cached", "--stat").strip() == "",
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
    c = {"DEV": _contrato(DEV), "TEST_https": _contrato(TEST_HTTPS)}
    EVIDENCIA["contratos"] = c
    _guardar("openapi-v3.json", c)
    return c


@pytest.fixture(scope="session")
def codigo_dev():
    """Qué adaptador Edge está realmente inyectado en el flujo RF-17 desplegado."""
    fuentes = {r: _git("show", f"origin/dev:{r}") for r in ARCHIVOS_RF17}
    router = fuentes["src/configuration/infrastructure/routers/umbral_router.py"]
    inyecciones = [l.strip() for l in router.splitlines() if "edge_port=" in l]
    adaptador_stub = any("EdgeSincronizacionStubAdapter()" in l for l in inyecciones)
    stub_src = fuentes["src/configuration/infrastructure/adapters/edge_sincronizacion_stub_adapter.py"]
    devuelve_siempre = [l.strip() for l in stub_src.splitlines() if "ResultadoEnvioMqtt(" in l]
    consumidores_mqtt = [l for l in _git("grep", "-n", "-E", "MqttPort|MqttHttpAdapter", "origin/dev", "--", "src").splitlines()
                         if "mqtt_port.py" not in l and "mqtt_http_adapter.py" not in l
                         and "edge_sincronizacion_port.py" not in l and "edge_sincronizacion_stub_adapter.py" not in l]
    publica_umbral = [l for l in consumidores_mqtt if "umbral" in l.lower()]
    info = {
        "inyeccionesEdgePortEnRouterRF17": inyecciones,
        "adaptadorInyectado": "EdgeSincronizacionStubAdapter" if adaptador_stub else "otro/real",
        "esStub": adaptador_stub,
        "stubDevuelve": devuelve_siempre,
        "consumidoresMqttPortFueraDeUmbrales": consumidores_mqtt,
        "consumidoresMqttPortEnFlujoDeUmbrales": publica_umbral,
        "rf17InvocaPuertoEdge": "edge_port.propagar_umbral" in fuentes[
            "src/configuration/application/use_cases/umbrales/registrar_umbral_use_case.py"],
        "rf17DeclaraFalloEdge": "FALLO_SINCRONIZACION_EDGE" in fuentes[
            "src/configuration/application/use_cases/umbrales/registrar_umbral_use_case.py"],
        "referenciasIntegracionEnRF17": {r: [l.strip() for l in s.splitlines() if PATRON_INTEGRACION.search(l)][:12]
                                         for r, s in fuentes.items() if "use_cases" in r},
    }
    EVIDENCIA["codigoOriginDev"] = info
    return info


@pytest.fixture(scope="session")
def dev_runtime():
    """GET autenticados en DEV. Requiere DEV_ADMIN_PASSWORD; si falta, se omite sin sustituir actor."""
    password = os.environ.get("DEV_ADMIN_PASSWORD")
    if not password:
        EVIDENCIA["devRuntime"] = {"ejecutado": False,
                                   "motivo": "DEV_ADMIN_PASSWORD no disponible en el proceso; no se sustituye el actor"}
        pytest.skip("DEV_ADMIN_PASSWORD no disponible")
    estado, login = _http(DEV + "/sesiones/", metodo="POST",
                          cuerpo={"correo_electronico": DEV_ADMIN, "contrasena": password})
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
            muestras.append({"id_especie": e["id_especie"], "especie": e["nombre"], "status": st,
                             "total": len(items), "camposItem": sorted(items[0].keys()),
                             "estadoSincronizacionObservado": [i.get("estado_sincronizacion") for i in items[:5]]})
        if len(muestras) >= 2:
            break
    rt = {"ejecutado": True,
          "actor": {"correo": me.get("correo_electronico") if me else None,
                    "rol": me.get("nombre_rol") if me else None,
                    "estado": me.get("estado_cuenta") if me else None,
                    "permisosRecurso20": sorted(p["id_accion"] for p in (perms or {}).get("permisos", []) if p["id_recurso"] == 20)},
          "especiesActivas": len(activas), "muestrasUmbrales": muestras, "tokenPersistido": False}
    EVIDENCIA["devRuntime"] = rt
    return rt


# ── Precondiciones ────────────────────────────────────────────────────────────

def test_rama_obligatoria():
    assert EVIDENCIA["git"]["rama"] == "qa/juan-esteban-tercera-evaluacion-M09"


def test_indice_git_intacto():
    assert EVIDENCIA["git"]["indiceIntacto"], "El índice de Git no debe modificarse"


def test_codigo_local_equivale_a_origin_dev():
    assert EVIDENCIA["git"]["diffSrcHeadVsOriginDev"] == "(sin diferencias)"


def test_dev_accesible_y_rf17_rest_desplegado(contratos):
    dev = contratos["DEV"]
    assert dev["health"] == 200 and dev["openapi"] == 200
    assert "POST /configuracion/umbrales" in dev["operacionesRF17"]
    assert "PATCH /configuracion/umbrales/{id_umbral_ambiental}" in dev["operacionesRF17"]


# ── Oráculo TC-M09-62 / TC-M09-63 ─────────────────────────────────────────────

def test_oraculo_rf17_invoca_la_propagacion_hacia_el_edge(codigo_dev):
    """TC-62/63: guardar un umbral debe disparar la propagación. (V2: no existía.)"""
    EVIDENCIA.setdefault("oraculo", {})["rf17InvocaIntegracion"] = codigo_dev["rf17InvocaPuertoEdge"]
    assert codigo_dev["rf17InvocaPuertoEdge"], "RF-17 no invoca ningún puerto de propagación al Edge"


def test_oraculo_umbral_expone_estado_de_sincronizacion(contratos):
    """TC-63: la configuración debe poder quedar 'Pendiente de Sincronización'."""
    campos = [c for c in contratos["DEV"]["umbralAmbientalResponse"] if PATRON_SYNC.search(c)]
    EVIDENCIA.setdefault("oraculo", {})["estadoSincronizacion"] = campos
    assert campos, f"UmbralAmbientalResponse DEV sin estado de sincronización: {contratos['DEV']['umbralAmbientalResponse']}"


def test_oraculo_adaptador_edge_es_real_no_stub(codigo_dev):
    """TC-62: la propagación debe llegar a un medio real (MQTT/Edge), no a un stub."""
    EVIDENCIA.setdefault("oraculo", {})["adaptadorReal"] = not codigo_dev["esStub"]
    assert not codigo_dev["esStub"], (
        "El flujo RF-17 desplegado inyecta EdgeSincronizacionStubAdapter: "
        f"{codigo_dev['inyeccionesEdgePortEnRouterRF17']}; el stub devuelve {codigo_dev['stubDevuelve']}. "
        "No existe publicación real hacia MQTT/Nodo Edge.")


def test_oraculo_existe_publicacion_mqtt_para_umbrales(codigo_dev):
    """TC-62: debe existir un publish real del umbral hacia el broker/Edge."""
    EVIDENCIA.setdefault("oraculo", {})["publishUmbral"] = codigo_dev["consumidoresMqttPortEnFlujoDeUmbrales"]
    assert codigo_dev["consumidoresMqttPortEnFlujoDeUmbrales"], (
        "Ningún flujo de umbrales consume MqttPort/MqttHttpAdapter; MQTT sigue siendo exclusivo de RF-23")


def test_oraculo_contrato_declara_500_por_fallo_de_sincronizacion(contratos):
    """TC-63: RF-17 exige HTTP 500 con la configuración central guardada."""
    ops = contratos["DEV"]["operacionesRF17"]
    con_500 = {k: v for k, v in ops.items() if k.split()[0] in ("POST", "PATCH") and "500" in v}
    EVIDENCIA.setdefault("oraculo", {})["operacionesCon500"] = con_500
    assert con_500, f"Ninguna escritura RF-17 declara 500 en el contrato DEV: {ops}"


def test_oraculo_edge_observable_para_umbrales(contratos):
    """TC-62/63: debe existir una vía para observar la configuración efectiva del Edge."""
    rutas = [r for r in contratos["DEV"]["rutasSincronizacionEdgeMqtt"] if "umbral" in r.lower() or "sincron" in r.lower()]
    EVIDENCIA.setdefault("oraculo", {})["edgeObservable"] = {
        "rutasUmbralEdge": rutas, "rutasEdgeDeclaradas": contratos["DEV"]["rutasSincronizacionEdgeMqtt"]}
    assert rutas, (f"Sin ruta para consultar la configuración efectiva del Edge para umbrales. "
                   f"Rutas edge en DEV: {contratos['DEV']['rutasSincronizacionEdgeMqtt']}")


def test_oraculo_dev_runtime_expone_estado_sincronizacion(dev_runtime):
    """Confirmación en runtime de DEV (se omite sin credencial; no cambia el veredicto)."""
    campos = sorted({c for m in dev_runtime["muestrasUmbrales"] for c in m["camposItem"] if PATRON_SYNC.search(c)})
    EVIDENCIA.setdefault("oraculo", {})["estadoSincronizacionRuntime"] = campos
    assert campos, "El recurso de umbrales en DEV no expone estado de sincronización en runtime"


# ── Resultados por caso ───────────────────────────────────────────────────────

def test_resultado_tc62_y_tc63(contratos, codigo_dev):
    """Consolida el resultado de los dos originales; no introduce criterios nuevos."""
    stub = codigo_dev["esStub"]
    tc62 = {
        "caso": "TC-M09-62", "ambiente": "DEV", "escrituras": 0,
        "backendIntentaPropagar": codigo_dev["rf17InvocaPuertoEdge"],
        "publicacionRealMqtt": bool(codigo_dev["consumidoresMqttPortEnFlujoDeUmbrales"]),
        "adaptadorInyectado": codigo_dev["adaptadorInyectado"],
        "edgeRecibe": "no verificable — el flujo desplegado no contacta ningún Edge",
        "edgeAplica": "no verificable — sin propagación real",
        "ack": "inexistente — el contrato de ACK está pendiente de definición con IoT",
        "estadoSincronizacionRegistrado": True,
        "configuracionEfectivaEdgeConsultable": False,
        "resultado": "RECHAZADO" if stub else "PENDIENTE DE EJECUCION",
        "motivo": "El backend registra un estado de sincronización pero no propaga: el adaptador inyectado "
                  "es un stub que siempre degrada a PENDIENTE. No hay publish, ni topic, ni ACK, ni Edge destino.",
    }
    tc63 = {
        "caso": "TC-M09-63", "ambiente": "DEV", "escrituras": 0,
        "edgeOfflineControlado": "no aplica — no existe Edge en el flujo desplegado",
        "configuracionCentralConservada": "no ejecutado (sin escrituras); el código la conserva antes de propagar",
        "httpEsperadoRF17": 500,
        "httpDeclaradoEnContratoDev": False,
        "estadoPendiente": "implementado en código y expuesto en el contrato DEV",
        "edgeConservaConfiguracionAnterior": "no verificable — el Edge nunca recibe configuración",
        "advertenciaAlUsuario": "existe motivo_fallo_sincronizacion en el contrato",
        "resultado": "RECHAZADO" if stub else "PENDIENTE DE EJECUCION",
        "motivo": "El flujo alterno de fallo de sincronización no puede demostrarse: no hay integración real "
                  "que pueda fallar. La parte central (estado PENDIENTE) existe, pero la verificación del "
                  "comportamiento del Edge real es imposible con el stub.",
    }
    _guardar("tc62-result.json", tc62)
    _guardar("tc63-result.json", tc63)
    EVIDENCIA["resultados"] = {"TC-M09-62": tc62["resultado"], "TC-M09-63": tc63["resultado"]}
    _guardar("preflight-v3.json", {k: EVIDENCIA[k] for k in ("git", "clienteMqtt", "codigoOriginDev", "contratos")})
    _guardar("plan-v3.json", {
        "runId": RUN_ID, "ambienteDecisorio": "DEV", "base": DEV,
        "escriturasPlanificadas": 0,
        "motivoSinEscrituras": "Escenario A (stub): ejecutar POST/PATCH solo demostraría persistencia central y un "
                               "estado PENDIENTE simulado; no probaría propagación ni comportamiento del Edge real. "
                               "Ademas DEV_ADMIN_PASSWORD no esta disponible en el proceso.",
        "raspberry": {"requeridoPorElFlujoDesplegado": False, "limitante": False,
                      "justificacion": "El backend desplegado no intenta comunicarse con el hardware: el puerto "
                                       "EdgeSincronizacionPort esta cubierto por EdgeSincronizacionStubAdapter."},
        "mqtt": {"flujoReal": False, "broker": "no utilizado por RF-17", "topic": "inexistente para umbrales",
                 "cliente": EVIDENCIA["clienteMqtt"]},
    })
    assert not stub, "Escenario A: integración Edge sustituida por stub; TC-62 y TC-63 no pueden aprobarse"
