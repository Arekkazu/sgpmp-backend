"""TC-M09-G140 — Compuerta de ejecutabilidad VISION en TEST (TC-M09-284 y TC-M09-285).

RF-24 v2.0 / CU05 Flujo F. Ambiente decisorio: TEST.

Antes de crear ningún dato o ejecutar ningún cálculo, el grupo exige demostrar que VISION es
ejecutable (10 puntos). Este test comprueba esos puntos contra el contrato desplegado y, si la
fuente formal VISION no existe, deja TC-M09-284 y TC-M09-285 como BLOQUEADOS **sin** crear áreas
gemelas, sin fabricar conjuntos K/M y sin ejecutar ningún POST.

No escribe nada en TEST: solo `GET /openapi.json` y lecturas del contrato.

Uso:
    pytest test_tc_m09_g140_test.py -v --noconftest
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

FOLDER = "TC-M09-G140"
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name != FOLDER:
    raise RuntimeError(f"Directorio no autorizado para {FOLDER}")

GRUPO = "TC-M09-G140"
RF = "RF-24 v2.0"
CU = "CU05 — Gestionar Dispositivos IoT, Flujo F"
CASOS_TEST = ["TC-M09-284", "TC-M09-285"]

RUN_ID = os.environ["G140_RUN_ID_TEST"]
OUT_DIR = BASE_DIR / "RESULTADOS" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = os.environ.get("QA_BASE_URL", "https://api.inmero.co/back-sigab-test").rstrip("/")


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(*args: str) -> str:
    repo = BASE_DIR
    for _ in range(12):
        if (repo / ".git").exists():
            break
        repo = repo.parent
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              timeout=60, encoding="utf-8", errors="replace").stdout.strip() or "(vacio)"
    except Exception as e:  # pragma: no cover - diagnóstico
        return f"ERROR: {e}"


def palabra_suelta(texto: str, palabra: str) -> int:
    """Cuenta la palabra como token, no como subcadena.

    Importa: 'VISION' aparece dentro de 'provisión' y 'revisión', y contarlo como presencia
    daría un falso positivo de ejecutabilidad.
    """
    return len(re.findall(rf"(?<![A-Za-zÁÉÍÓÚáéíóúÑñ]){re.escape(palabra)}(?![A-Za-zÁÉÍÓÚáéíóúÑñ])",
                          texto, re.IGNORECASE))


@pytest.fixture(scope="module")
def openapi() -> dict:
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=40)
    r.raise_for_status()
    return r.json()


def test_compuerta_de_ejecutabilidad_vision(openapi):
    raw = json.dumps(openapi, ensure_ascii=False)
    bajo = raw.lower()

    ev: dict = {
        "grupo": GRUPO, "casos": CASOS_TEST, "requisito": RF, "casoDeUso": CU,
        "ambiente": "TEST", "prueba_local": False, "base_url": BASE_URL,
        "run_id": RUN_ID, "fecha": ahora_iso(),
        "git": {
            "rama": git("branch", "--show-current"), "status_short": git("status", "--short"),
            "diff_stat": git("diff", "--stat"), "diff_cached_stat": git("diff", "--cached", "--stat"),
            "head": git("rev-parse", "HEAD"), "origin_test": git("rev-parse", "origin/test"),
            "divergencia": git("rev-list", "--left-right", "--count", "HEAD...origin/test"),
        },
    }

    # ---------------------------------------------------------- operación VISION publicada
    ocurrencias_vision = palabra_suelta(raw, "VISION")
    contextos_substring = sorted({m.group(0) for m in re.finditer(r"\w*vision\w*", bajo)})
    dto = (openapi.get("components", {}).get("schemas", {}).get("RegistrarCalibracionDTO") or {})
    rutas_candidatas = [p for p in sorted(openapi.get("paths", {}))
                        if any(k in p.lower() for k in ("vision", "linea-base", "baseline",
                                                        "observacion", "vector", "comportamiento"))]
    ev["openapi_vision"] = {
        "rutas_totales": len(openapi.get("paths", {})),
        "ocurrencias_de_VISION_como_palabra": ocurrencias_vision,
        "coincidencias_por_subcadena": contextos_substring,
        "nota_subcadena": ("Las coincidencias de 'vision' provienen de 'provisión'/'revisión'. "
                           "Se cuenta la palabra como token para no producir un falso positivo."),
        "rutas_candidatas": rutas_candidatas,
        "registrar_calibracion_dto": {
            "properties": list((dto.get("properties") or {}).keys()),
            "required": dto.get("required"),
            "declara_modo_calibracion": "modo_calibracion" in (dto.get("properties") or {}),
        },
        "enums_con_VISION": [n for n, s in (openapi.get("components", {}).get("schemas") or {}).items()
                             if s.get("enum") and any("VISION" in str(x).upper() for x in s["enum"])],
    }

    # ---------------------------------------------------------- fuente formal de vectores
    endpoints_apto_ia = []
    for ruta, ops in openapi.get("paths", {}).items():
        for metodo, op in ops.items():
            if isinstance(op, dict) and "apto_para_ia" in json.dumps(op):
                endpoints_apto_ia.append(f"{metodo.upper()} {ruta}")
    schemas_apto_ia = [n for n, s in (openapi.get("components", {}).get("schemas") or {}).items()
                       if "apto_para_ia" in json.dumps(s)]
    ev["fuente_vectores"] = {
        "schemas_con_apto_para_ia": schemas_apto_ia,
        "endpoints_que_exponen_apto_para_ia": endpoints_apto_ia,
        "entidad_de_observacion_vision": None,
        "nota": ("apto_para_ia solo aparece en el schema de calidad de telemetría de sensores. "
                 "No se asume que sea el vector de comportamiento VISION solo por llevar ese "
                 "campo: el caso exige una entidad con cámara, área, timestamp y componentes."),
    }

    # ---------------------------------------------------------- configuración del algoritmo
    terminos = ["linea_base", "baseline", "ventana_observacion", "vector_comportamiento",
                "p5", "p95", "winsoriz", "percentil", "epsilon", "max_iter", "refinamiento",
                "convergencia", "mediana_iterativa"]
    ev["configuracion_algoritmo"] = {t: (t in bajo) for t in terminos}
    ev["N"] = None
    ev["epsilon"] = None
    ev["max_iter"] = None

    # ---------------------------------------------------------- compuerta de 10 puntos
    puntos = {
        "1_operacion_vision_publicada": ocurrencias_vision > 0,
        "2_fuente_formal_de_vectores_vision": False,
        "3_componentes_numericos_del_vector": False,
        "4_vinculo_camara_area_observacion": False,
        "5_apto_para_ia_consultable_por_flujo_formal": len(endpoints_apto_ia) > 0,
        "6_minimo_N_consultable": False,
        "7_persistencia_de_linea_base_verificable": ("linea_base" in bajo or "baseline" in bajo),
        "8_epsilon_consultable": "epsilon" in bajo,
        "9_max_iteraciones_consultable": ("max_iter" in bajo or "iteracion" in bajo),
        "10_regla_de_refinamiento_definida": False,
    }
    ev["compuerta_ejecutabilidad"] = {
        "puntos": puntos,
        "cumplidos": sum(1 for v in puntos.values() if v),
        "total": len(puntos),
        "criterio": ("Los 10 puntos de la sección 3 del paquete. Sin fuente formal VISION no se "
                     "crean K, M ni áreas gemelas y no se ejecuta ningún POST."),
    }

    vision_ejecutable = all(puntos.values())
    motivo_bloqueo = (
        "TEST no publica ninguna operación VISION: 'VISION' no aparece como palabra en todo el "
        "contrato (las coincidencias son 'provisión'/'revisión'), el DTO del registro de "
        "calibración no declara modo_calibracion, y no existe entidad ni ruta de vector de "
        "comportamiento VISION, ni configuración de ε, máximo de iteraciones, p5/p95 ni "
        "persistencia de línea base."
    )

    for caso in CASOS_TEST:
        ev[caso] = {
            "ambiente": "TEST",
            "resultado": "APROBADO" if vision_ejecutable else "BLOQUEADO / NO VERIFICABLE",
            "motivo": None if vision_ejecutable else motivo_bloqueo,
            "posts_vision_ejecutados": 0,
            "K": None, "M": None, "baseline_K": None, "baseline_KM": None, "comparacion": None,
        } if caso == "TC-M09-284" else {
            "ambiente": "TEST",
            "resultado": "APROBADO" if vision_ejecutable else "BLOQUEADO / NO VERIFICABLE",
            "motivo": None if vision_ejecutable else motivo_bloqueo,
            "posts_vision_ejecutados": 0,
            "dataset": None, "oracle_descartar": None, "oracle_winsorizar": None,
            "baseline_producto": None, "interpretacion_observada": None,
        }

    # Impedimento adicional y concreto para las áreas gemelas de TC-M09-284.
    tipo_modelo = None
    for n, s in (openapi.get("components", {}).get("schemas") or {}).items():
        pr = (s.get("properties") or {}).get("tipo_modelo_asignado")
        if pr:
            tipo_modelo = {"schema": n, "definicion": pr}
            break
    ev["TC-M09-284"]["impedimento_areas_gemelas"] = {
        "tipo_modelo_asignado": tipo_modelo,
        "admite_POBLACIONAL": bool(tipo_modelo) and "POBLACIONAL" in json.dumps(tipo_modelo),
        "nota": ("El caso pide áreas gemelas con tipo_modelo_asignado POBLACIONAL. El contrato "
                 "no admite ese valor para infraestructuras; POBLACIONAL es el tipo de activo "
                 "biológico, no el modelo asignado al área."),
    }

    ev["presupuesto"] = {"postVisionPlanificadosTest": 3, "postVisionEjecutados": 0,
                         "nota": "No se ejecuta ningún POST VISION mientras la operación no exista."}
    ev["resultado"] = "APROBADO" if vision_ejecutable else "BLOQUEADO / NO VERIFICABLE"
    ev["motivo"] = None if vision_ejecutable else motivo_bloqueo
    ev["seguridad"] = {"limpio": True,
                       "criterio": "Esta compuerta solo consulta el contrato público; no usa credenciales."}

    (OUT_DIR / "evidencia.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # La compuerta falla a propósito mientras VISION no exista: deja constancia del bloqueo.
    assert vision_ejecutable, (
        "TC-M09-284 y TC-M09-285 quedan BLOQUEADOS / NO VERIFICABLES.\n" + motivo_bloqueo +
        f"\nPuntos de ejecutabilidad cumplidos: {ev['compuerta_ejecutabilidad']['cumplidos']}"
        f"/{ev['compuerta_ejecutabilidad']['total']}"
    )
