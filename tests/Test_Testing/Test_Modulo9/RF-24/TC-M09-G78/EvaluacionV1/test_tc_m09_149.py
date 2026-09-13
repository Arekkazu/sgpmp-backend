"""TC-M09-G78 / TC-M09-149 — Mantener calibración pendiente cuando falla la propagación al firmware.

Primera evaluación (RF-24, CU-05). Verificación de implementación de SOLO LECTURA:

- DEV es el ambiente decisorio (MQTT solo existe allí); TEST solo se consulta para
  comparar el despliegue del componente REST.
- Se leen los contratos OpenAPI desplegados (GET sin autenticación) y el código de
  ``origin/dev`` con ``git show`` / ``git grep`` (sin checkout ni fetch).
- No se ejecuta ningún POST, login, SQL ni conexión MQTT: el checklist previo al POST
  no se cumple (no hay flujo MQTT, pending ni retry identificables para calibraciones).

Las pruebas del bloque "oráculo TC-149" codifican lo que exige la matriz. Si fallan,
documentan la ausencia del flujo en el producto; no se ajustan para que pasen.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parents[5]  # .../sgpmp-backend
RUN_ID = os.environ.get("G78_RUN_ID", "")
RESULTADOS = AQUI / "RESULTADOS" / RUN_ID

DEV = "https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp"
TEST_SUMINISTRADA = "http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
TEST_HTTPS = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"

RUTA_CALIBRAR = "/configuracion/sensores/{id_sensor}/calibrar"
# Nomenclatura semántica aceptable para el estado/propagación (no se falla por nombre).
PATRON_ESTADO = re.compile(r"estado|pend|sync|sincron|propag|retry|reintent|ack|firmware|mqtt", re.I)
PATRON_MQTT = re.compile(r"mqtt|MqttPort|MqttHttpAdapter|enviar_configuracion|broker|firmware|/v1/commands", re.I)
PATRON_RETRY = re.compile(r"retry|reintent|next_retry|scheduler|poller|worker", re.I)

ARCHIVOS_CALIBRACION = [
    "src/configuration/application/use_cases/sensores/registrar_calibracion_use_case.py",
    "src/configuration/domain/entities/calibracion.py",
    "src/configuration/infrastructure/models/calibracion_model.py",
    "src/configuration/infrastructure/schema/calibracion_schema.py",
    "src/configuration/infrastructure/dto/registrar_calibracion_dto.py",
    "src/configuration/infrastructure/routers/sensor_router.py",
]

EVIDENCIA: dict = {}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=BACKEND, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            cuerpo = r.read().decode("utf-8")
            return r.status, (json.loads(cuerpo) if cuerpo.strip().startswith(("{", "[")) else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def _resumen_contrato(base: str) -> dict:
    salud, _ = _get_json(base + "/health")
    estado, api = _get_json(base + "/openapi.json")
    res = {"base": base, "health": salud, "openapi": estado}
    if estado != 200 or not api:
        return res
    schemas = api.get("components", {}).get("schemas", {})
    op = api["paths"].get(RUTA_CALIBRAR, {}).get("post")
    rutas = list(api["paths"].keys())
    res.update(
        {
            "endpointCalibrar": op is not None,
            "respuestasCalibrar": sorted((op or {}).get("responses", {}).keys()),
            "calibracionResponse": list(schemas.get("CalibracionResponse", {}).get("properties", {}).keys()),
            "registrarCalibracionDTO": list(schemas.get("RegistrarCalibracionDTO", {}).get("properties", {}).keys()),
            "rutasCalibracion": [p for p in rutas if "calibr" in p.lower()],
            "rutasPropagacionORetryDeCalibracion": [
                p for p in rutas if "calibr" in p.lower() and PATRON_ESTADO.search(p)
            ],
            "rutasMqttExistentes": [p for p in rutas if re.search(r"configurar|configuraciones", p)],
            "schemasEstadoCalibracion": [s for s in schemas if "calibr" in s.lower() and PATRON_ESTADO.search(s)],
        }
    )
    return res


@pytest.fixture(scope="session", autouse=True)
def evidencia():
    assert RUN_ID and re.fullmatch(r"[\w-]+", RUN_ID), "G78_RUN_ID requerido"
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    destino = RESULTADOS / "TC-M09-149-evidencia.json"
    assert not destino.exists(), "No sobrescribir evidencia existente"

    EVIDENCIA.update(
        {
            "caso": "TC-M09-149",
            "grupo": "TC-M09-G78",
            "rf": "RF-24",
            "cu": "CU-05",
            "tipo": "PRIMERA EVALUACION",
            "runId": RUN_ID,
            "fechaInicio": datetime.now(timezone.utc).isoformat(),
            "ambienteDecisorio": "DEV",
            "naturalezaEvidencia": "verificacion de implementacion read-only (contrato desplegado + codigo origin/dev); sin POST",
            "git": {
                "rama": _git("branch", "--show-current").strip(),
                "head": _git("rev-parse", "HEAD").strip(),
                "originDev": _git("rev-parse", "origin/dev").strip(),
                "originDevUltimoCommit": _git("log", "-1", "--format=%h %cs %s", "origin/dev").strip(),
                "diffSrcHeadVsOriginDev": _git("diff", "--stat", "HEAD", "origin/dev", "--", "src").strip() or "(sin diferencias)",
            },
        }
    )
    yield EVIDENCIA
    EVIDENCIA["fechaFin"] = datetime.now(timezone.utc).isoformat()
    destino.write_text(json.dumps(EVIDENCIA, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="session")
def contratos():
    c = {"DEV": _resumen_contrato(DEV), "TEST_suministrada": _resumen_contrato(TEST_SUMINISTRADA), "TEST_https": _resumen_contrato(TEST_HTTPS)}
    EVIDENCIA["contratos"] = c
    return c


@pytest.fixture(scope="session")
def codigo_dev():
    fuentes = {ruta: _git("show", f"origin/dev:{ruta}") for ruta in ARCHIVOS_CALIBRACION}
    usos_mqtt = [
        linea for linea in _git("grep", "-n", "-E", "MqttPort|MqttHttpAdapter|enviar_configuracion", "origin/dev", "--", "src").splitlines()
        if "mqtt_port.py" not in linea and "mqtt_http_adapter.py" not in linea
    ]
    calib_con_retry = [
        linea for linea in _git("grep", "-n", "-i", "-E", "calibr", "origin/dev", "--", "src").splitlines()
        if PATRON_RETRY.search(linea)
    ]
    EVIDENCIA["codigoOriginDev"] = {
        "archivosRevisados": ARCHIVOS_CALIBRACION,
        "referenciasMqttEnArchivosDeCalibracion": {
            ruta: [l.strip() for l in src.splitlines() if PATRON_MQTT.search(l)] for ruta, src in fuentes.items()
        },
        "consumidoresDeMqttPort": usos_mqtt,
        "lineasCalibracionConRetry": calib_con_retry,
        "columnasModeloCalibracion": re.findall(r"^\s+(\w+): Mapped", fuentes[ARCHIVOS_CALIBRACION[2]], re.M),
    }
    return fuentes, usos_mqtt, calib_con_retry


# ── Precondiciones de la evaluación ──────────────────────────────────────────

def test_rama_obligatoria():
    assert EVIDENCIA["git"]["rama"] == "qa/juan-esteban-re-evaluacion-M02"


def test_dev_backend_accesible(contratos):
    assert contratos["DEV"]["health"] == 200
    assert contratos["DEV"]["openapi"] == 200


def test_dev_endpoint_calibracion_desplegado(contratos):
    assert contratos["DEV"]["endpointCalibrar"] is True


def test_codigo_local_equivale_a_origin_dev():
    assert EVIDENCIA["git"]["diffSrcHeadVsOriginDev"] == "(sin diferencias)"


def test_test_y_dev_comparten_contrato_de_calibracion(contratos):
    dev, test = contratos["DEV"], contratos["TEST_https"]
    claves = ["endpointCalibrar", "respuestasCalibrar", "calibracionResponse", "registrarCalibracionDTO", "rutasCalibracion"]
    EVIDENCIA["desfaseTestDev"] = {k: dev.get(k) != test.get(k) for k in claves}
    assert all(dev.get(k) == test.get(k) for k in claves)


# ── Oráculo TC-M09-149 (matriz G78) ──────────────────────────────────────────

def test_oraculo_contrato_dev_expone_estado_de_propagacion(contratos):
    """CALIBRACIÓN_PENDIENTE debe ser observable en el contrato (nombre semántico libre)."""
    dev = contratos["DEV"]
    campos = [c for c in dev["calibracionResponse"] + dev["registrarCalibracionDTO"] if PATRON_ESTADO.search(c)]
    EVIDENCIA.setdefault("oraculo", {})["camposEstadoEnContrato"] = campos
    assert campos, f"CalibracionResponse/DTO en DEV no exponen estado de propagación: {dev['calibracionResponse']}"


def test_oraculo_calibracion_propaga_al_firmware_via_mqtt(codigo_dev):
    fuentes, usos_mqtt, _ = codigo_dev
    uso_caso = fuentes[ARCHIVOS_CALIBRACION[0]]
    router = fuentes[ARCHIVOS_CALIBRACION[5]]
    propaga = bool(PATRON_MQTT.search(uso_caso)) or bool(PATRON_MQTT.search(router))
    EVIDENCIA.setdefault("oraculo", {})["calibracionInvocaMqtt"] = propaga
    assert propaga, (
        "RegistrarCalibracionUseCase y sensor_router no invocan MqttPort/broker; "
        f"únicos consumidores de MqttPort: {usos_mqtt}"
    )


def test_oraculo_calibracion_persiste_estado_pendiente(codigo_dev):
    fuentes, _, _ = codigo_dev
    columnas = EVIDENCIA["codigoOriginDev"]["columnasModeloCalibracion"]
    entidad = fuentes[ARCHIVOS_CALIBRACION[1]]
    estado = [c for c in columnas if PATRON_ESTADO.search(c)] or re.findall(r"PENDIENTE|PENDING", entidad)
    EVIDENCIA.setdefault("oraculo", {})["estadoPendienteEnModelo"] = estado
    assert estado, f"modulo9.calibraciones no tiene columna/estado de propagación: {columnas}"


def test_oraculo_existe_reintento_automatico_de_calibraciones(contratos, codigo_dev):
    _, _, calib_con_retry = codigo_dev
    rutas = contratos["DEV"]["rutasPropagacionORetryDeCalibracion"]
    EVIDENCIA.setdefault("oraculo", {})["retryCalibracion"] = {"rutas": rutas, "codigo": calib_con_retry}
    assert rutas or calib_con_retry, "No existe ruta, worker ni scheduler de reintento para calibraciones en DEV"
