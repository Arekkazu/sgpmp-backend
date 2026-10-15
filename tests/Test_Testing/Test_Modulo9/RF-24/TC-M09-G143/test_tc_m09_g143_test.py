"""TC-M09-G143 — Compuerta de ejecutabilidad VISION en TEST (TC-M09-290 y TC-M09-291).

RF-24 v2.0 / CU05 Flujo F. Ambiente decisorio: TEST.

Los dos casos de TEST dependen de VISION, pero con reglas de decisión distintas:

* **TC-M09-290** exige demostrar que la *fuente* de observaciones VISION existe y que, para el par
  (C1, A1), la ventana relevante tiene `count = 0`. El paquete es explícito (§11): si la fuente no
  existe en absoluto, no puede demostrarse que el sistema alcanzó la etapa de filtrado, y el caso
  queda **BLOQUEADO / NO VERIFICABLE**. La ausencia de una ruta *manual* VISION no basta para
  bloquearlo (§12), porque M02→M09 podría ser una integración interna; por eso aquí se busca la
  fuente de datos, no el endpoint.
* **TC-M09-291** sí exige una **operación manual VISION**. Su propia matriz (§22 y §56) indica que
  la ausencia de esa operación se trata como fallo con evidencia OpenAPI: **RECHAZADO**.

Este módulo ejecuta la colección Newman (un único GET público) y revalida el contrato desde Pytest.
No autentica, no usa credenciales y no envía ningún POST: ni el lote M02 de TC-290 (§14) ni el
manual de TC-291 (§22). Sobre TEST, solo lectura.

Uso:
    pytest test_tc_m09_g143_test.py -v --noconftest
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

FOLDER = "TC-M09-G143"
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name != FOLDER:
    raise RuntimeError(f"Directorio no autorizado para {FOLDER}")

GRUPO = "TC-M09-G143"
RF = "RF-24 v2.0"
CU = "CU05 — Gestionar Dispositivos IoT, Flujo F"
CASOS = ["TC-M09-290", "TC-M09-291"]

RUN_ID = os.environ["G143_RUN_ID_TEST"]
OUT_DIR = BASE_DIR / "RESULTADOS" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = os.environ.get("QA_BASE_URL", "https://api.inmero.co/back-sigab-test").rstrip("/")
COLECCION = BASE_DIR / "TC-M09-G143.postman_collection.json"


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root() -> Path:
    d = BASE_DIR
    for _ in range(12):
        if (d / ".git").exists():
            return d
        d = d.parent
    return BASE_DIR


def git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo_root()), *args], capture_output=True,
                           text=True, timeout=60, encoding="utf-8", errors="replace")
        return r.stdout.strip() or "(vacio)"
    except Exception as e:  # pragma: no cover - diagnóstico
        return f"ERROR: {e}"


def palabra_suelta(texto: str, palabra: str) -> int:
    """Cuenta la palabra como token, no como subcadena.

    Importa: 'VISION' está dentro de 'provisión' y 'revisión', y contarlo como presencia daría un
    falso positivo de ejecutabilidad que llevaría a crear datos en TEST para nada.
    """
    borde = "[A-Za-zÁÉÍÓÚáéíóúÑñ]"
    return len(re.findall(rf"(?<!{borde}){re.escape(palabra)}(?!{borde})", texto, re.IGNORECASE))


def ejecutar_newman() -> dict:
    """Ejecuta la colección y devuelve el resumen; deja `newman.html` en la carpeta del RUN."""
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return {"ejecutado": False, "motivo": "npx no disponible en PATH"}
    salida_json = OUT_DIR / "newman-summary.json"
    cmd = [npx, "--no-install", "newman", "run", str(COLECCION),
           "--env-var", f"base_url={BASE_URL}",
           "--reporters", "cli,htmlextra,json",
           "--reporter-htmlextra-export", str(OUT_DIR / "newman.html"),
           "--reporter-htmlextra-omitHeaders",
           "--reporter-htmlextra-showEnvironmentData", "false",
           "--reporter-htmlextra-title", f"{GRUPO} — compuerta VISION en TEST",
           "--reporter-json-export", str(salida_json)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                          encoding="utf-8", errors="replace")
    resumen: dict = {"ejecutado": True, "exit_code": proc.returncode,
                     "html": "newman.html"}
    if salida_json.exists():
        datos = json.loads(salida_json.read_text(encoding="utf-8"))
        ejec = datos.get("run", {}).get("executions", [])
        aserciones = []
        for e in ejec:
            for a in e.get("assertions", []) or []:
                aserciones.append({"nombre": a.get("assertion"),
                                   "fallo": bool(a.get("error"))})
        resumen["assertions"] = aserciones
        resumen["totales"] = datos.get("run", {}).get("stats", {}).get("assertions", {})
        # El resumen JSON de Newman reproduce el cuerpo completo del contrato; no aporta nada que
        # no esté ya en la evidencia y abulta el RUN, así que no se conserva.
        salida_json.unlink()
    return resumen


@pytest.fixture(scope="module")
def openapi() -> dict:
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=60)
    r.raise_for_status()
    return r.json()


def test_compuerta_vision_en_test(openapi):
    raw = json.dumps(openapi, ensure_ascii=False)
    bajo = raw.lower()
    paths = openapi.get("paths", {}) or {}
    schemas = (openapi.get("components", {}) or {}).get("schemas", {}) or {}

    ev: dict = {
        "grupo": GRUPO, "casos": CASOS, "requisito": RF, "casoDeUso": CU,
        "ambiente": "TEST", "prueba_local": False, "base_url": BASE_URL,
        "run_id": RUN_ID, "fecha": ahora_iso(),
        "git": {
            "rama": git("branch", "--show-current"),
            "status_short": git("status", "--short"),
            "diff_stat": git("diff", "--stat"),
            "diff_cached_stat": git("diff", "--cached", "--stat"),
            "head": git("rev-parse", "HEAD"),
            "origin_test": git("rev-parse", "origin/test"),
            "divergencia": git("rev-list", "--left-right", "--count", "HEAD...origin/test"),
        },
    }

    # ------------------------------------------------ ¿existe una operación VISION publicada?
    ocurrencias = palabra_suelta(raw, "VISION")
    subcadenas = sorted({m.group(0) for m in re.finditer(r"[a-z0-9_]*vision[a-z0-9_]*", bajo)})

    ops_calibracion = []
    for ruta, ops in paths.items():
        for metodo, op in ops.items():
            if isinstance(op, dict) and re.search(r"calibrac", ruta + json.dumps(op), re.I):
                ops_calibracion.append(f"{metodo.upper()} {ruta}")
    dto = schemas.get("RegistrarCalibracionDTO", {}) or {}
    props_dto = list((dto.get("properties") or {}).keys())

    ev["openapi_vision"] = {
        "rutas_totales": len(paths),
        "esquemas_totales": len(schemas),
        "ocurrencias_de_VISION_como_palabra": ocurrencias,
        "coincidencias_por_subcadena": subcadenas,
        "nota_subcadena": ("Todas las coincidencias de 'vision' provienen de 'provisión' "
                           "(suministros NIC-41). Se cuenta la palabra como token para no "
                           "producir un falso positivo de operación VISION."),
        "operaciones_de_calibracion_publicadas": sorted(ops_calibracion),
        "registrar_calibracion_dto": {
            "properties": props_dto,
            "required": dto.get("required"),
            "declara_modo_calibracion": "modo_calibracion" in props_dto,
        },
        "enums_con_VISION_o_CAMARA": [
            n for n, s in schemas.items()
            if s.get("enum") and any(k in str(s["enum"]).upper() for k in ("VISION", "CAMARA"))
        ],
    }

    # ------------------------------------------------ ¿existe una fuente formal de observaciones?
    terminos = ["vector_comportamiento", "ventana_observacion", "linea_base", "baseline",
                "epsilon", "max_iter", "winsoriz", "percentil", "p95", "refinamiento",
                "convergencia", "camara", "modo_calibracion"]
    conteo = {t: bajo.count(t) for t in terminos}
    schemas_apto_ia = [n for n, s in schemas.items() if "apto_para_ia" in json.dumps(s)]
    ev["fuente_observaciones_vision"] = {
        "terminos_en_contrato": conteo,
        "schemas_con_apto_para_ia": schemas_apto_ia,
        "entidad_de_observacion_vision": None,
        "nota": ("apto_para_ia solo aparece en el esquema de calidad de telemetría de SENSORES. "
                 "No se asume que sea el vector de comportamiento VISION por llevar ese campo: "
                 "el caso exige una entidad con cámara, área, ventana y aptitud."),
    }
    hay_fuente = any(v > 0 for v in conteo.values())

    # ------------------------------------------------ fixture de TC-290 (área + cámara + modelo)
    tipo_modelo = None
    for n, s in schemas.items():
        pr = (s.get("properties") or {}).get("tipo_modelo_asignado")
        if pr and pr.get("anyOf"):
            tipo_modelo = {"schema": n, "valores": next(
                (x.get("enum") for x in pr["anyOf"] if x.get("enum")), None)}
            break
    ev["fixture_tc290"] = {
        "tipo_modelo_asignado_del_area": tipo_modelo,
        "admite_MODELO_AVES": bool(tipo_modelo) and "MODELO_AVES" in str(tipo_modelo),
        "admite_POBLACIONAL_como_modelo_de_area": bool(tipo_modelo) and "POBLACIONAL" in str(tipo_modelo),
        "nota": ("El área sí admite MODELO_AVES. POBLACIONAL no es un modelo de área sino el tipo "
                 "de activo biológico del lote, y eso no es el impedimento: el impedimento es que "
                 "no existe fuente de observaciones VISION que pueda tener count=0 demostrable."),
        "ruta_disparador_m02": "POST /activos-biologicos" if "/activos-biologicos" in paths else None,
    }

    ev["newman"] = ejecutar_newman()

    # ------------------------------------------------ decisión por caso
    vision_manual = ocurrencias > 0
    fuente_vision = hay_fuente

    motivo_290 = (
        "No existe en TEST ninguna fuente formal de observaciones VISION: el contrato no publica "
        "vector de comportamiento, ventana de observación, línea base, ε, máximo de iteraciones, "
        "p5/p95 ni refinamiento, y el único apto_para_ia pertenece a la calidad de telemetría de "
        "sensores. Sin esa fuente no puede demostrarse que la ventana relevante de (C1, A1) tiene "
        "count = 0, que es la condición intencional del caso: ausencia de estructura no es cero "
        "observaciones funcionales (§11). Tampoco existe una superficie de línea base donde "
        "comprobar que no se publicó ninguna, ni un evento M09 de calibración VISION que pudiera "
        "quedar en FALLIDO. Por eso no se registró el lote M02: hacerlo crearía un activo "
        "biológico real en TEST sin ningún oráculo que observar (§14)."
    )
    motivo_291 = (
        "TEST no publica ninguna operación manual VISION. 'VISION' no aparece como palabra en todo "
        "el contrato — las coincidencias de 'vision' son 'provisión' de suministros NIC-41 — y la "
        "única operación de calibración publicada es POST /configuracion/sensores/{id_sensor}/"
        "calibrar, que es de SENSOR: exige id_sensor en la ruta, su DTO no declara "
        "modo_calibracion y no admite un disparo por área. Sin operación manual VISION no puede "
        "obtenerse el 422 ni el evento RF-10 asociado. La propia matriz del caso trata esta "
        "ausencia como incumplimiento con evidencia OpenAPI (§22 y §56), no como bloqueo."
    )

    ev["TC-M09-290"] = {
        "ambiente": "TEST", "prueba_local": False,
        "resultado": "APROBADO" if fuente_vision else "BLOQUEADO / NO VERIFICABLE",
        "motivo": None if fuente_vision else motivo_290,
        "fixture": ev["fixture_tc290"],
        "observaciones_count": None,
        "nota_observaciones_count": ("No es 0: es NO DETERMINABLE. No existe fuente consultable "
                                     "cuyo conteo pudiera ser cero."),
        "m02_request": None, "m02_response": None, "trigger_signal": None,
        "baseline_pre": None, "baseline_post": None, "audit_m09": None,
        "posts_ejecutados": 0,
    }
    ev["TC-M09-291"] = {
        "ambiente": "TEST", "prueba_local": False,
        "resultado": "APROBADO" if vision_manual else "RECHAZADO",
        "motivo": None if vision_manual else motivo_291,
        "openapi_vision": ev["openapi_vision"],
        "fixture": {"A2": None, "nota": "No se creó A2: la operación VISION ya se confirmó ausente (§22)."},
        "request_window": None, "response": None,
        "http_esperado": 422, "http_obtenido": None,
        "audit_m09": None, "ip_registrada": None,
        "posts_ejecutados": 0,
    }

    ev["presupuesto"] = {
        "postActivosBiologicosPlanificados": 1, "postActivosBiologicosEjecutados": 0,
        "postVisionManualPlanificados": 1, "postVisionManualEjecutados": 0,
        "escrituras_en_test": 0,
        "sql_en_test": "ninguno; la decisión se resuelve con el contrato público",
    }
    ev["stop_all"] = {"activado": False,
                      "motivo": "No se envió ningún POST VISION, así que no pudo generarse una "
                                "línea base inesperada."}
    ev["resultado"] = "RECHAZADO" if not vision_manual else (
        "APROBADO" if fuente_vision else "BLOQUEADO / NO VERIFICABLE")
    ev["seguridad"] = {
        "limpio": True,
        "criterio": ("La colección y este módulo solo consultan el contrato público. No hay login, "
                     "ni token, ni cookie, ni cabecera Authorization que pudiera quedar en los "
                     "artefactos."),
    }

    (OUT_DIR / "evidencia.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # La compuerta falla a propósito mientras VISION no exista: ese fallo es la constancia.
    assert vision_manual and fuente_vision, (
        "TC-M09-291 queda RECHAZADO y TC-M09-290 queda BLOQUEADO / NO VERIFICABLE.\n"
        f"- TC-M09-291: {motivo_291}\n"
        f"- TC-M09-290: {motivo_290}"
    )
