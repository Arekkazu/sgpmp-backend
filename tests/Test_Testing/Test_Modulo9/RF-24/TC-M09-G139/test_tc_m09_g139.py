"""Preflight G139 en TEST y verificación independiente de estabilidad del OpenAPI."""

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
IDS = ("TC-M09-282", "TC-M09-283")


def fetch_openapi() -> tuple[int, bytes, dict]:
    request = urllib.request.Request(BASE + "/openapi.json", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        return response.status, raw, json.loads(raw)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def git_snapshot() -> dict:
    return {
        "rama": git("branch", "--show-current"),
        "status_short": git("status", "--short"),
        "diff_stat": git("diff", "--stat"),
        "diff_cached_stat": git("diff", "--cached", "--stat"),
        "head": git("rev-parse", "HEAD"),
        "origin_test": git("rev-parse", "origin/test"),
        "divergencia": git("rev-list", "--left-right", "--count", "HEAD...origin/test"),
    }


def discover(doc: dict, raw: bytes) -> dict:
    text = raw.decode("utf-8")
    operations = [
        (route, method, operation)
        for route, methods in doc.get("paths", {}).items()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    words = ("VISION", "modo_calibracion", "ventana_observacion", "origen_disparo", "linea_base", "baseline")
    term_counts = {word: len(re.findall(rf"\b{word}\b", text, flags=re.IGNORECASE)) for word in words}
    candidates = []
    for route, method, operation in operations:
        identity = f"{route} {operation.get('summary', '')} {operation.get('description', '')}"
        body = json.dumps(operation.get("requestBody", {}), ensure_ascii=False)
        if re.search(r"\bvision\b", identity, flags=re.IGNORECASE) or re.search(
            r"modo_calibracion|ventana_observacion", body, flags=re.IGNORECASE
        ):
            candidates.append((route, method, operation))
    vision = [
        (route, method, operation)
        for route, method, operation in candidates
        if method in {"post", "put", "patch"}
    ]
    sensor = doc.get("paths", {}).get("/configuracion/sensores/{id_sensor}/calibrar", {}).get("post")
    dto = doc.get("components", {}).get("schemas", {}).get("RegistrarCalibracionDTO", {})
    return {
        "encontrada": bool(vision),
        "method": vision[0][1].upper() if vision else None,
        "path": vision[0][0] if vision else None,
        "request_schema": vision[0][2].get("requestBody") if vision else None,
        "responses": list(vision[0][2].get("responses", {})) if vision else None,
        "security": vision[0][2].get("security") if vision else None,
        "busqueda": {
            "paths_totales": len(doc.get("paths", {})),
            "post_totales": sum(method == "post" for _, method, _ in operations),
            "schemas_totales": len(doc.get("components", {}).get("schemas", {})),
            "apariciones_exactas": term_counts,
            "candidatas": [
                {"method": method.upper(), "path": route, "summary": operation.get("summary")}
                for route, method, operation in candidates
            ],
        },
        "operacion_sensor_existente": {
            "method": "POST",
            "path": "/configuracion/sensores/{id_sensor}/calibrar",
            "summary": sensor.get("summary"),
            "request_schema": sensor.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema"),
            "campos_dto": list(dto.get("properties", {})),
            "campos_requeridos": dto.get("required", []),
        } if sensor else None,
    }


def test_openapi_remains_stable_and_without_vision():
    """Pytest detecta un cambio de despliegue entre Newman y el segundo GET."""
    expected_hash = os.environ.get("G139_VERIFY_SHA")
    assert expected_hash, "G139_VERIFY_SHA debe proceder del GET oficial"
    status, raw, doc = fetch_openapi()
    assert status == 200
    assert hashlib.sha256(raw).hexdigest() == expected_hash, "OpenAPI cambió durante el preflight"
    assert not discover(doc, raw)["encontrada"], "VISION apareció durante el preflight"


def write_outputs(out: Path, evidence: dict) -> None:
    out.joinpath("evidencia.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    vision = evidence["openapi_vision"]
    newman = evidence["newman"]
    report = [
        "# TC-M09-G139 — Resultado", "",
        f"**Resultado general: {evidence['resultado_general']}.** RUN_ID: {evidence['run_id']}. Ambiente decisorio: TEST. Prueba local: NO.", "",
        "## Decisión general", "",
        "| Caso | Condición | Resultado | Motivo |", "|---|---|---|---|",
        "| TC-M09-282 | 0 observaciones VISION aptas | BLOQUEADO / NO VERIFICABLE | Sin operación VISION no se puede montar ni ejecutar la ventana de 0 aptas. |",
        "| TC-M09-283, corrida N | Exactamente N aptas | BLOQUEADO / NO VERIFICABLE | Sin operación VISION no se ejecuta el umbral ni se conoce BASELINE_N. |",
        "| TC-M09-283, corrida N−1 | Exactamente N−1 aptas | BLOQUEADO / NO VERIFICABLE | Depende de N y de BASELINE_N; ninguna precondición llegó a ejecutarse. |", "",
        "## Ejecutabilidad VISION/M03", "",
        f"Newman consultó `GET {BASE}/openapi.json` y terminó con código {newman['exit_code']}. Un segundo GET en TEST devolvió HTTP {evidence['openapi_http']}; Pytest confirmó que el hash del OpenAPI permaneció igual entre consultas. Se revisaron {vision['busqueda']['paths_totales']} rutas, {vision['busqueda']['post_totales']} POST y {vision['busqueda']['schemas_totales']} esquemas. No hay operación formal VISION, ni `modo_calibracion` o `ventana_observacion` en el contrato.", "",
        "La única calibración publicada es `POST /configuracion/sensores/{id_sensor}/calibrar`, identificada como Flujo D SENSOR. Su `RegistrarCalibracionDTO` recibe dispositivo, infraestructura, valor y fecha; no define área y ventana VISION. Enviar campos extras a esa ruta no demostraría el proceso del Flujo F.", "",
        f"**Operación VISION publicada:** NO. Método/ruta/body/respuestas/security: no publicados. Hash SHA-256 de OpenAPI: `{evidence['openapi_sha256']}`.", "",
        "La fase 1 bloqueó las demás. La fuente formal de observaciones VISION, el vínculo cámara–observación, el flag de aptitud propio del proceso, N y la superficie de línea base figuran **NO EVALUADOS**. Esto no significa que se haya demostrado su ausencia: no se consultaron M03 ni BD después del bloqueo. La telemetría común no se trató como vector VISION.", "",
        "## Fixture", "",
        "No se prepararon A1/C1 ni ventanas. No hay IDs de observaciones, conteos ni snapshots PRE/POST. El valor de N no se leyó ni se supuso. No se ejecutó SQL ni se cambiaron flags o líneas base.", "",
        "## TC-M09-282 — cero observaciones aptas", "",
        "**Escenario esperado.** Con A1/C1 válidas y una ventana cerrada cuya cantidad de observaciones VISION aptas sea exactamente 0, el Ingeniero debe recibir HTTP 422. No debe aparecer una línea base nueva y la vigente previa debe permanecer intacta. Este caso no exige un mensaje literal único porque pueden aplicar dos rutas de rechazo.", "",
        "**Qué se pudo observar.** No existe una operación VISION publicada para enviar la ventana. Por eso el conteo de 0 aptas no fue medido, el POST no se envió y tampoco se pudo comparar la línea base PRE/POST. `HTTP obtenido` y `baseline conservada` quedan **no observables**, no se registran falsamente como 422 y SÍ.", "",
        "**Decisión: BLOQUEADO / NO VERIFICABLE.** Falta la primera precondición de ejecutabilidad; no hay evidencia de que la regla de 0 aptas funcione o falle.", "",
        "## TC-M09-283 — límite N y N−1", "",
        "### Corrida N", "",
        "**Escenario esperado.** Leer N desde una configuración real, construir una ventana con exactamente N observaciones VISION aptas y obtener 2xx y una BASELINE_N nueva y vigente. Una cantidad mayor a N no probaría el límite exacto.", "",
        "**Qué se pudo observar.** Sin operación VISION no se llegó a descubrir una fuente formal de vectores ni N, y no se preparó la ventana. La corrida N no se ejecutó. HTTP y BASELINE_N son **no observables**.", "",
        "### Corrida N−1", "",
        "**Escenario esperado.** En otra ventana cerrada y no solapada, exactamente N−1 aptas deben producir 422 y el mensaje contractual de datos insuficientes. Debe existir auditoría FALLIDA y BASELINE_N debe seguir vigente sin cambios.", "",
        "**Qué se pudo observar.** La corrida N−1 depende de BASELINE_N creada por la corrida N. Como esa primera corrida no fue posible, tampoco se ejecutó la segunda; no se consultó auditoría de un intento que no existió. HTTP, mensaje, auditoría y persistencia son **no observables**.", "",
        "**Decisión TC-M09-283: BLOQUEADO / NO VERIFICABLE.** Faltan operación VISION y, por la puerta del preflight, no se pudieron montar N, N−1 ni verificar las dos respuestas. No se afirma que N no exista en el sistema; simplemente no se alcanzó su descubrimiento.", "",
        "## Ejecución y trazabilidad", "",
        f"- Rama: `{evidence['git']['rama']}`; HEAD: `{evidence['git']['head']}`; origin/test: `{evidence['git']['origin_test']}`; divergencia: `{evidence['git']['divergencia']}`.",
        "- Estado Git previo y detalle de búsqueda contractual: `evidencia.json`.",
        "- POST VISION planificados tras preflight: 0; ejecutados: 0. POST de setup: 0. STOP_ALL: NO (no hubo escritura). SQL: ninguno.",
        "- `newman.html` contiene el GET real y sus assertions. `pytest.xml` registra la comprobación independiente de estabilidad del contrato. Ninguno ejecuta el oráculo funcional bloqueado.", "",
        "## Incidencias", "",
        "**INCIDENCIA REQUERIDA: NO, con la evidencia disponible.** Los dos casos están bloqueados antes de alcanzar su oráculo, y la matriz prevé el bloqueo hasta que se publiquen las dependencias VISION/M03. No se dispone de confirmación de que esa entrega ya fuera obligatoria en TEST; por eso no se registra un bug de Desarrollo ni de AIoT solo a partir de este preflight.", "",
        "Grupo: TC-M09-G139. Casos: TC-M09-282 y TC-M09-283. Resultado: BLOQUEADO / NO VERIFICABLE. Esperado: operación VISION y fuente formal de observaciones, N y baseline para probar 0, N y N−1. Obtenido: VISION no publicada; las fases siguientes no evaluadas. Grupo responsable de una eventual incidencia: Por determinar hasta confirmar el estado formal de entrega. Type/Severity/Priority: no aplican a una incidencia no abierta. Evidencia: `evidencia.json`, `newman.html` y `pytest.xml`.", "",
        "## Conclusión", "",
        "G139 permanece **BLOQUEADO / NO VERIFICABLE**. La ausencia de contrato VISION impidió alcanzar ambos oráculos. Una vez publicada la operación, habrá que demostrar la fuente formal de vectores, N y la línea base antes de enviar cualquiera de los tres POST previstos para la ejecución completa.", "",
    ]
    out.joinpath("TC-M09-G139_resultado.md").write_text("\n".join(report), encoding="utf-8")
    html_report = (
        '<!doctype html><html lang="es"><meta charset="utf-8"><title>G139 Newman</title>'
        '<style>body{font:16px system-ui;max-width:70rem;margin:2rem;line-height:1.5}'
        'pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style>'
        f'<h1>G139 — Newman GET OpenAPI TEST</h1><p>RUN {html.escape(evidence["run_id"])} · '
        f'Newman exit {newman["exit_code"]} · VISION: no · POST VISION: 0</p>'
        '<h2>Salida del GET y assertions</h2>'
        f'<pre>{html.escape(newman["stdout"][-5000:])}</pre>'
        '<h2>Discovery contractual</h2>'
        f'<pre>{html.escape(json.dumps(vision, ensure_ascii=False, indent=2))}</pre>'
        f'<p>OpenAPI SHA-256: {evidence["openapi_sha256"]}</p></html>'
    )
    out.joinpath("newman.html").write_text(html_report, encoding="utf-8")


def run() -> int:
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError("Ejecute desde la carpeta TC-M09-G139")
    if os.environ.get("QA_BASE_URL", "").rstrip("/") != BASE:
        raise RuntimeError("QA_BASE_URL debe señalar TEST")
    run_id = os.environ.get("G139_RUN_ID", "")
    if not re.fullmatch(r"run-\d{8}-\d{6}", run_id):
        raise RuntimeError("G139_RUN_ID inválido")
    out = ROOT / "RESULTADOS" / run_id
    if out.exists():
        raise RuntimeError("RUN_ID existente: no se sobrescribe")
    snapshot = git_snapshot()
    if snapshot["rama"] != "qa/juan-esteban-rf24-v2":
        raise RuntimeError(f"Rama inesperada: {snapshot['rama']}")
    out.mkdir(parents=True)
    newman_exe = shutil.which("newman.cmd" if os.name == "nt" else "newman")
    if not newman_exe:
        raise RuntimeError("No se encontró Newman en PATH")
    command = [newman_exe, "run", str(ROOT / "TC-M09-G139.postman_collection.json"),
               "--env-var", f"base_url={BASE}", "--reporters", "cli"]
    newman_result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=45, check=False)
    if newman_result.returncode != 0:
        raise RuntimeError(f"Newman falló (exit {newman_result.returncode}): {newman_result.stdout[-1000:]} {newman_result.stderr[-500:]}")
    status, raw, doc = fetch_openapi()
    if status != 200:
        raise RuntimeError(f"GET OpenAPI TEST HTTP {status}")
    contract = discover(doc, raw)
    if contract["encontrada"]:
        raise RuntimeError("VISION candidata publicada: verificar dependencias antes de POST; runner no escribe")
    digest = hashlib.sha256(raw).hexdigest()
    test_env = {**os.environ, "G139_VERIFY_SHA": digest, "PYTHONDONTWRITEBYTECODE": "1"}
    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--noconftest", "-p", "no:cacheprovider",
         str(ROOT / "test_tc_m09_g139.py"), f"--junitxml={out / 'pytest.xml'}"],
        cwd=ROOT, env=test_env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    if pytest_result.returncode != 0:
        raise RuntimeError(f"Pytest no confirmó estabilidad de OpenAPI: {pytest_result.stdout[-1000:]} {pytest_result.stderr[-500:]}")
    evidence = {
        "grupo": "TC-M09-G139", "casos": list(IDS), "run_id": run_id, "ambiente": "TEST",
        "prueba_local": False, "base_url": BASE, "git": snapshot,
        "openapi_http": status, "openapi_observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "openapi_sha256": digest, "openapi_vision": contract,
        "newman": {"exit_code": newman_result.returncode, "stdout": newman_result.stdout[-5000:],
                   "stderr": newman_result.stderr[-500:]},
        "pytest": {"exit_code": pytest_result.returncode, "resultado": pytest_result.stdout[-1000:]},
        "fuente_observaciones": {"estado": "NO EVALUADA", "motivo": "Fase 1: VISION no publicada"},
        "minimo": {"N": None, "fuente": None, "estado": "NO EVALUADO por bloqueo anterior"},
        "fixture": {"area": "NO PREPARADA", "especie": "NO PREPARADA", "camara": "NO PREPARADA"},
        "baseline_pre": {"estado": "NO CONSULTADO: sin operación VISION ni POST"},
        "TC-M09-282": {"ventana": None, "count_aptas": None, "response": None,
                       "baseline_post": None, "post_ejecutado": False,
                       "resultado": "BLOQUEADO / NO VERIFICABLE",
                       "motivo": "VISION no publicada en OpenAPI TEST: no se puede demostrar 0 aptas, ejecutar POST ni verificar baseline."},
        "TC-M09-283": {"N": {"ventana": None, "count_aptas": None, "response": None,
                             "baseline_id": None, "post_ejecutado": False},
                       "N_minus_1": {"ventana": None, "count_aptas": None, "response": None,
                                     "audit": None, "baseline_post": None, "post_ejecutado": False},
                       "resultado": "BLOQUEADO / NO VERIFICABLE",
                       "motivo": "VISION no publicada; N y N-1 no montados. N-1 requiere BASELINE_N de una primera corrida no ejecutada."},
        "post_vision_planificados": 0, "post_vision_ejecutados": 0, "post_setup_ejecutados": 0,
        "sql_ejecutado": "ninguno", "stop_all": False,
        "resultado_general": "BLOQUEADO / NO VERIFICABLE",
        "motivo_general": "La operación VISION necesaria para ambos oráculos no está publicada en TEST.",
        "incidencias": [],
        "decision_incidencias": {"incidencia_requerida": "NO con evidencia disponible",
                                  "grupo_responsable": "Por determinar si se confirma entrega obligatoria",
                                  "motivo": "La matriz prevé bloqueo hasta publicación; no se confirmó incumplimiento de un hito de entrega."},
    }
    write_outputs(out, evidence)
    print(f"G139 BLOQUEADO / NO VERIFICABLE; TC-282 y TC-283 BLOQUEADOS; VISION: NO; "
          f"POST VISION: 0; {out}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--run"]:
        raise SystemExit("Uso: python test_tc_m09_g139.py --run")
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"ERROR G139: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
