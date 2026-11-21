"""Preflight de TC-M09-287: contrato VISION y dependencia de L1 del RUN TC-275."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE = "https://api.inmero.co/back-sigab-test"
G137_RESULTS = ROOT.parent / "TC-M09-G137" / "RESULTADOS"


def fetch_openapi() -> tuple[int, bytes, dict]:
    request = urllib.request.Request(BASE + "/openapi.json", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        return response.status, raw, json.loads(raw)


def discover(doc: dict, raw: bytes) -> dict:
    text = raw.decode("utf-8")
    ops = [(route, method, operation)
           for route, methods in doc.get("paths", {}).items()
           for method, operation in methods.items()
           if method in {"get", "post", "put", "patch", "delete"}]
    terms = {name: len(re.findall(rf"\b{name}\b", text, flags=re.IGNORECASE))
             for name in ("VISION", "modo_calibracion", "ventana_observacion", "origen_disparo")}
    candidates = []
    for route, method, operation in ops:
        label = f"{route} {operation.get('summary', '')} {operation.get('description', '')}"
        body = json.dumps(operation.get("requestBody", {}), ensure_ascii=False)
        if re.search(r"\bvision\b", label, flags=re.IGNORECASE) or re.search(
                r"modo_calibracion|ventana_observacion", body, flags=re.IGNORECASE):
            candidates.append((route, method, operation))
    vision = [(route, method, operation) for route, method, operation in candidates
              if method in {"post", "put", "patch"}]
    sensor = doc.get("paths", {}).get("/configuracion/sensores/{id_sensor}/calibrar", {}).get("post")
    dto = doc.get("components", {}).get("schemas", {}).get("RegistrarCalibracionDTO", {})
    return {
        "encontrada": bool(vision),
        "method": vision[0][1].upper() if vision else None,
        "path": vision[0][0] if vision else None,
        "request_schema": vision[0][2].get("requestBody") if vision else None,
        "responses": list(vision[0][2].get("responses", {})) if vision else None,
        "security": vision[0][2].get("security") if vision else None,
        "busqueda": {"paths_totales": len(doc.get("paths", {})),
                     "post_totales": sum(method == "post" for _, method, _ in ops),
                     "schemas_totales": len(doc.get("components", {}).get("schemas", {})),
                     "apariciones_exactas": terms,
                     "candidatas": [{"method": method.upper(), "path": route,
                                     "summary": operation.get("summary")}
                                    for route, method, operation in candidates]},
        "operacion_sensor_existente": {
            "method": "POST", "path": "/configuracion/sensores/{id_sensor}/calibrar",
            "summary": sensor.get("summary"),
            "request_schema": sensor.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema"),
            "campos_dto": list(dto.get("properties", {})),
        } if sensor else None,
    }


def previous_tc275() -> dict:
    runs = []
    for evidence_path in sorted(G137_RESULTS.glob("*/evidencia.json")):
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        case = evidence.get("TC-M09-275", {})
        runs.append({
            "run_id": evidence.get("run_id"),
            "fuente": str(evidence_path.relative_to(ROOT.parent)).replace("\\", "/"),
            "resultado": case.get("resultado"),
            "post_ejecutado": case.get("post_ejecutado"),
            "post_vision_total": evidence.get("post_vision_ejecutados"),
            "vision_publicada": evidence.get("openapi_vision", {}).get("encontrada"),
            "baseline_publicada": case.get("baseline_id") or case.get("linea_base_id"),
        })
    valid = [run for run in runs if run["resultado"] == "APROBADO" and run["post_ejecutado"]
             and run["baseline_publicada"]]
    return {"fuente_preferida": "TC-M09-275", "runs_encontrados": runs,
            "run_valido_con_L1": valid[0] if valid else None,
            "conclusion": "No hay RUN válido de TC-275 que demuestre L1 vigente" if not valid
                          else "Hay candidato TC-275; reconfirmar L1 por API/SELECT antes del POST"}


def test_openapi_stable_without_vision():
    """Consulta independiente para detectar un despliegue nuevo durante el RUN."""
    expected_hash = os.environ.get("G141_OPENAPI_SHA")
    assert expected_hash, "G141_OPENAPI_SHA debe venir del GET oficial"
    status, raw, doc = fetch_openapi()
    assert status == 200
    assert hashlib.sha256(raw).hexdigest() == expected_hash, "OpenAPI cambió durante el preflight"
    assert not discover(doc, raw)["encontrada"], "VISION apareció durante el preflight"


def test_tc275_has_no_valid_l1_run():
    """Verifica la dependencia oficial TC-275 sin afirmar el estado de BD TEST."""
    prior = previous_tc275()
    assert prior["runs_encontrados"], "No se encontró evidencia TC-275 para evaluar la dependencia"
    assert prior["run_valido_con_L1"] is None, "Apareció un RUN TC-275 válido; revisar antes de decidir G141"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def git_snapshot() -> dict:
    return {"rama": git("branch", "--show-current"), "status_short": git("status", "--short"),
            "diff_stat": git("diff", "--stat"), "diff_cached_stat": git("diff", "--cached", "--stat"),
            "head": git("rev-parse", "HEAD"), "origin_test": git("rev-parse", "origin/test"),
            "divergencia": git("rev-list", "--left-right", "--count", "HEAD...origin/test")}


def write_outputs(out: Path, evidence: dict) -> None:
    out.joinpath("evidencia.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    prior = evidence["L1"]["trazabilidad_tc275"]
    vision = evidence["openapi_vision"]
    lines = [
        "# TC-M09-G141 — Resultado", "",
        f"**TC-M09-287 y TC-M09-G141: {evidence['resultado']}.** RUN_ID: {evidence['run_id']}. Ambiente: TEST; prueba local: NO.", "",
        "## Decisión", "",
        "El segundo cálculo VISION no se ejecutó. Faltan dos precondiciones comprobadas: TEST no publica una operación VISION y el RUN disponible de TC-M09-275 no creó una L1 verificable. Por eso no se alcanzó el oráculo de reemplazo de vigencia.", "",
        "## Entorno y contrato", "",
        f"Newman consultó `GET {BASE}/openapi.json` y terminó correctamente; un GET Python obtuvo HTTP {evidence['openapi_http']}. Pytest confirmó que el OpenAPI permaneció estable en la lectura posterior. Se examinaron {vision['busqueda']['paths_totales']} rutas, {vision['busqueda']['post_totales']} POST y {vision['busqueda']['schemas_totales']} esquemas. Ninguna operación declara VISION, `modo_calibracion` o `ventana_observacion`.", "",
        "El `POST /configuracion/sensores/{id_sensor}/calibrar` existente corresponde a **SENSOR, Flujo D**. Su body no describe una calibración VISION con área y ventana; usarlo cambiaría el caso bajo prueba. Método/ruta/schema/security/respuestas VISION: **no publicados**.", "",
        f"Hash SHA-256 del OpenAPI: `{evidence['openapi_sha256']}`. Rama: `{evidence['git']['rama']}`; HEAD: `{evidence['git']['head']}`; origin/test: `{evidence['git']['origin_test']}`; divergencia: `{evidence['git']['divergencia']}`. Estado Git previo completo en `evidencia.json`.", "",
        "## Precondición L1", "",
        f"La fuente preferida es TC-M09-275. Se revisaron {len(prior['runs_encontrados'])} RUN(s) con evidencia de ese caso. El RUN `{prior['runs_encontrados'][0]['run_id'] if prior['runs_encontrados'] else 'ninguno'}` quedó `{prior['runs_encontrados'][0]['resultado'] if prior['runs_encontrados'] else 'sin evidencia'}` y no ejecutó un POST VISION. No hay en esa fuente una L1 creada y vigente que pueda usarse aquí.", "",
        "Esto **no prueba que en la BD TEST no exista ninguna línea base**: no se consultó la persistencia porque la operación VISION ya faltaba. Tampoco se sustituyó silenciosamente TC-275 por otra supuesta L1. A1, especie, identificador de L1 y su vigencia PRE quedan **no verificados**. La matriz pide revaluar primero TC-275 cuando VISION esté disponible.", "",
        "## Ventana posterior W2", "",
        "La prueba requería una ventana posterior a la de L1, cerrada, con al menos N observaciones VISION aptas de una cámara activa asociada al área. Sin contrato VISION ni L1 validada, no se descubrió N, no se creó W2 y no se contaron observaciones. Inicio/fin, IDs y cantidad apta: **no evaluados**, no cero medido.", "",
        "## Segundo disparo", "",
        "El actor previsto era el Ingeniero de Campo. Como no había ruta VISION ni precondiciones de L1/W2, no se inició sesión para ejecutar este caso y no se envió POST. HTTP esperado cuando el escenario sea válido: cualquier **2xx**. HTTP obtenido ahora: **no observable**. No se hicieron escrituras de setup ni SQL.", "",
        "## Reemplazo de vigencia", "",
        "El oráculo principal sería observar **L1 vigente antes** y, tras el cálculo W2, **L2/W2 vigente y L1 ya no vigente** para el mismo par área/especie. Aquí no existe snapshot PRE/POST de una ejecución VISION, así que L1 sigue vigente: **no verificable**; L2 vigente: **no verificable**; correlación con W2: **no verificable**.", "",
        "RF-24 no exige que L1 permanezca físicamente como historial ni que L2 tenga un ID distinto si la implementación reemplaza in-place. Esos aspectos no se convierten en fallos de este RUN.", "",
        "## Incidencia", "",
        "**INCIDENCIA REQUERIDA: NO, con la evidencia disponible.** El caso está bloqueado antes del segundo cálculo y no hay confirmación de que VISION/M03 ya debiera estar entregado en TEST. No se observó un reemplazo incorrecto que justifique un bug de Desarrollo, AIoT o DBA.", "",
        "Grupo: TC-M09-G141. Caso: TC-M09-287. Resultado: BLOQUEADO / NO VERIFICABLE. Esperado: operación VISION, L1 vigente de TC-275, W2 posterior con observaciones suficientes y segundo cálculo 2xx que deja L2 vigente. Obtenido: operación VISION no publicada y TC-275 previo bloqueado sin L1 publicada. Causa de una eventual incidencia de entrega: por determinar hasta conocer el hito formal. Grupo responsable, Type, Severity y Priority: no se asignan a una incidencia no abierta. Evidencia: `evidencia.json`, `newman.html`, `pytest.xml`.", "",
        "## Conclusión", "",
        "TC-M09-287 y G141 quedan **BLOQUEADOS / NO VERIFICABLES**. Primero debe existir VISION en TEST y revaluarse TC-M09-275 para obtener una L1 vigente trazable; después podrán construirse W2 y comprobarse el reemplazo de vigencia. No se evaluó conservación histórica de L1.", "",
    ]
    out.joinpath("TC-M09-G141_resultado.md").write_text("\n".join(lines), encoding="utf-8")
    html_report = (
        '<!doctype html><html lang="es"><meta charset="utf-8"><title>G141 Newman</title>'
        '<style>body{font:16px system-ui;max-width:70rem;margin:2rem;line-height:1.5}'
        'pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style>'
        f'<h1>G141 — Newman GET OpenAPI TEST</h1><p>RUN {html.escape(evidence["run_id"])} · '
        f'Newman exit {evidence["newman"]["exit_code"]} · VISION: no · POST VISION: 0</p>'
        '<h2>GET y assertions</h2>'
        f'<pre>{html.escape(evidence["newman"]["stdout"][-5000:])}</pre>'
        '<h2>Contrato encontrado</h2>'
        f'<pre>{html.escape(json.dumps(vision, ensure_ascii=False, indent=2))}</pre>'
        f'<p>OpenAPI SHA-256: {evidence["openapi_sha256"]}</p></html>'
    )
    out.joinpath("newman.html").write_text(html_report, encoding="utf-8")


def run() -> int:
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError("Ejecute desde TC-M09-G141")
    if os.environ.get("QA_BASE_URL", "").rstrip("/") != BASE:
        raise RuntimeError("QA_BASE_URL debe señalar TEST")
    run_id = os.environ.get("G141_RUN_ID", "")
    if not re.fullmatch(r"run-\d{8}-\d{6}", run_id):
        raise RuntimeError("G141_RUN_ID inválido")
    out = ROOT / "RESULTADOS" / run_id
    if out.exists():
        raise RuntimeError("RUN_ID existente: no se sobrescribe")
    snapshot = git_snapshot()
    if snapshot["rama"] != "qa/juan-esteban-rf24-v2":
        raise RuntimeError("Rama QA requerida no está activa")
    out.mkdir(parents=True)
    exe = shutil.which("newman.cmd" if os.name == "nt" else "newman")
    if not exe:
        raise RuntimeError("Newman no está en PATH")
    newman_run = subprocess.run(
        [exe, "run", str(ROOT / "TC-M09-G141.postman_collection.json"),
         "--env-var", f"base_url={BASE}", "--reporters", "cli"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=45, check=False,
    )
    if newman_run.returncode != 0:
        raise RuntimeError(f"Newman falló: {newman_run.stdout[-1000:]} {newman_run.stderr[-500:]}")
    status, raw, doc = fetch_openapi()
    if status != 200:
        raise RuntimeError(f"GET OpenAPI TEST HTTP {status}")
    vision = discover(doc, raw)
    if vision["encontrada"]:
        raise RuntimeError("VISION candidata apareció: verificar L1, W2 y N antes de POST. Runner no escribe")
    prior = previous_tc275()
    digest = hashlib.sha256(raw).hexdigest()
    env = {**os.environ, "G141_OPENAPI_SHA": digest, "PYTHONDONTWRITEBYTECODE": "1"}
    pytest_run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--noconftest", "-p", "no:cacheprovider",
         str(ROOT / "test_tc_m09_287.py"), f"--junitxml={out / 'pytest.xml'}"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    if pytest_run.returncode != 0:
        raise RuntimeError(f"Pytest no confirmó precondiciones: {pytest_run.stdout[-1000:]} {pytest_run.stderr[-500:]}")
    evidence = {
        "grupo": "TC-M09-G141", "caso": "TC-M09-287", "run_id": run_id,
        "ambiente": "TEST", "prueba_local": False, "base_url": BASE, "git": snapshot,
        "openapi_http": status, "openapi_observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "openapi_sha256": digest, "openapi_vision": vision,
        "newman": {"exit_code": newman_run.returncode, "stdout": newman_run.stdout[-5000:],
                   "stderr": newman_run.stderr[-500:]},
        "pytest": {"exit_code": pytest_run.returncode, "resultado": pytest_run.stdout[-1000:]},
        "actor": {"estado": "NO CONSULTADO: caso bloqueado antes de POST"},
        "fixture": {"area": None, "especie": None, "camara": None, "N": None,
                    "estado": "NO PREPARADO: no hay operación VISION"},
        "L1": {"fuente": "TC-M09-275", "trazabilidad_tc275": prior,
               "snapshot_pre": None, "vigente_pre": None, "motivo": "TC-275 bloqueado; L1 no demostrada"},
        "W2": {"inicio": None, "fin": None, "count_aptas": None, "ids": [],
               "estado": "NO PREPARADA"},
        "request": None, "response": None, "baseline_post": None,
        "comparacion_vigencia": {"L1_sigue_vigente": None, "L2_vigente": None,
                                 "corresponde_a_W2": None, "estado": "NO VERIFICABLE sin segundo POST"},
        "post_vision_planificados": 0, "post_vision_ejecutados": 0,
        "post_setup_ejecutados": 0, "sql_ejecutado": "ninguno",
        "resultado": "BLOQUEADO / NO VERIFICABLE",
        "motivo": "VISION no publicada en TEST y TC-275 previo bloqueado sin una L1 vigente trazable.",
        "incidencia": {"incidencia_requerida": "NO con evidencia disponible",
                       "grupo_responsable": "No asignado; por determinar si se confirma entrega obligatoria",
                       "grupo": "TC-M09-G141", "caso": "TC-M09-287",
                       "causa": "Faltan contrato VISION y L1 proveniente de TC-275; no se probó el reemplazo."},
    }
    write_outputs(out, evidence)
    print(f"G141 BLOQUEADO / NO VERIFICABLE; TC-287 BLOQUEADO; VISION: NO; "
          f"L1 de TC-275: NO DEMOSTRADA; POST VISION: 0; {out}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--run"]:
        raise SystemExit("Uso: python test_tc_m09_287.py --run")
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"ERROR G141: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
