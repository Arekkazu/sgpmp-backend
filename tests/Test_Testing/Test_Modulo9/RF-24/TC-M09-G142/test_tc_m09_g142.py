"""G142: preflight remoto, con OpenAPI y SELECT read-only de esquema TEST."""

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

import psycopg2


ROOT = Path(__file__).resolve().parent
BASE = "https://api.inmero.co/back-sigab-test"
M02_ROUTES = {
    "alta": ("/activos-biologicos", "post"),
    "cierre": ("/activos-biologicos/{id_activo}/cierre", "post"),
    "detalle": ("/activos-biologicos/{id_activo}", "get"),
    "auditoria": ("/auditoria/", "get"),
}

SQL_TABLES = """SELECT table_schema,table_name,table_type FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog','information_schema')
AND lower(table_name) ~ '(vision|vector|comportamiento|linea_base|baseline|observacion)'
ORDER BY table_schema,table_name"""
SQL_COLUMNS = """SELECT table_schema,table_name,column_name FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog','information_schema')
AND lower(column_name) ~ '(vector|comportamiento|origen_disparo|baseline|linea_base|ventana_observacion|id_camara)'
ORDER BY table_schema,table_name,column_name"""
SQL_SELECTED = """SELECT table_schema,table_name,column_name FROM information_schema.columns
WHERE (table_schema='modulo3' AND table_name IN
('paquetes_inferencia','eventos_edge_computing','telemetrias','telemetria_calidad'))
OR (table_schema='modulo9' AND table_name IN
('calibraciones','configuraciones_globales','infraestructuras','dispositivos_iot'))
ORDER BY table_schema,table_name,ordinal_position"""
SQL_META = "SELECT current_database(),current_user,current_setting('transaction_read_only')"


def fetch_openapi() -> tuple[int, bytes, dict]:
    request = urllib.request.Request(BASE + "/openapi.json", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        return response.status, raw, json.loads(raw)


def db_connection():
    required = ("TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_NAME", "TEST_DB_USER", "TEST_DB_PASSWORD")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("Faltan variables de conexión TEST read-only: " + ", ".join(missing))
    return psycopg2.connect(
        host=os.environ["TEST_DB_HOST"], port=os.environ["TEST_DB_PORT"],
        dbname=os.environ["TEST_DB_NAME"], user=os.environ["TEST_DB_USER"],
        password=os.environ["TEST_DB_PASSWORD"],
        options="-c default_transaction_read_only=on", connect_timeout=12,
    )


def db_discovery() -> dict:
    connection = db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(SQL_META)
            database, user, readonly = cursor.fetchone()
            if readonly != "on" or user != "member_qa" or database != "sgpmp_test":
                raise RuntimeError("La conexión no es member_qa read-only en sgpmp_test")
            cursor.execute(SQL_TABLES)
            tables = [{"schema": s, "table": t, "type": typ} for s, t, typ in cursor.fetchall()]
            cursor.execute(SQL_COLUMNS)
            columns = [{"schema": s, "table": t, "column": col} for s, t, col in cursor.fetchall()]
            cursor.execute(SQL_SELECTED)
            selected_rows = cursor.fetchall()
        selected: dict[str, list[str]] = {}
        for schema, table, column in selected_rows:
            selected.setdefault(f"{schema}.{table}", []).append(column)
        m03_candidates = [row for row in tables if row["schema"] == "modulo3"] + [
            row for row in columns if row["schema"] == "modulo3"]
        m09_candidates = [row for row in tables if row["schema"] == "modulo9"] + [
            row for row in columns if row["schema"] == "modulo9"]
        return {"database": database, "user": user, "transaction_read_only": readonly,
                "consultas": [SQL_META, SQL_TABLES, SQL_COLUMNS, SQL_SELECTED],
                "candidate_tables": tables, "candidate_columns": columns,
                "selected_columns": selected,
                "m03_semantic_candidates": m03_candidates,
                "m09_semantic_candidates": m09_candidates,
                "formal_m03_vision_source_identified": bool(m03_candidates),
                "formal_m09_vision_baseline_identified": bool(m09_candidates),
                "criterio": "No hay relación formal publicada cámara→vector VISION→área/tiempo/aptitud ni línea base VISION; telemetría/calidad genérica no prueba esa semántica."}
    finally:
        connection.close()


def openapi_discovery(doc: dict, raw: bytes) -> dict:
    text = raw.decode("utf-8")
    paths = doc.get("paths", {})
    components = doc.get("components", {}).get("schemas", {})
    routes = {}
    for name, (route, method) in M02_ROUTES.items():
        operation = paths.get(route, {}).get(method)
        routes[name] = {
            "present": bool(operation), "method": method.upper(), "path": route,
            "summary": operation.get("summary") if operation else None,
            "request_schema": operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema") if operation else None,
            "responses": list(operation.get("responses", {})) if operation else [],
        }
    related = [
        {"method": method.upper(), "path": route, "summary": operation.get("summary")}
        for route, methods in paths.items() for method, operation in methods.items()
        if method in {"get", "post", "put", "patch"}
        and re.search(r"\bvision\b|vector(es)?|linea.base|l[ií]nea.base", f"{route} {operation.get('summary', '')}", flags=re.IGNORECASE)
    ]
    terms = {term: len(re.findall(rf"\b{term}\b", text, flags=re.IGNORECASE))
             for term in ("VISION", "vector", "vector_comportamiento", "ventana_observacion",
                          "origen_disparo", "linea_base", "baseline", "apto_para_ia")}
    return {"routes": routes, "paths_totales": len(paths), "schemas_totales": len(components),
            "related_operations": related, "term_counts": terms,
            "manual_vision_published": bool([x for x in related if re.search(r"\bvision\b", x["path"] + " " + (x["summary"] or ""), flags=re.IGNORECASE)]),
            "dto_alta_m02": {"name": "RegistrarActivoBiologicoDTO",
                             "fields": list(components.get("RegistrarActivoBiologicoDTO", {}).get("properties", {})),
                             "required": components.get("RegistrarActivoBiologicoDTO", {}).get("required", [])},
            "dto_cierre_m02": {"name": "CerrarCicloDTO",
                               "fields": list(components.get("CerrarCicloDTO", {}).get("properties", {})),
                               "required": components.get("CerrarCicloDTO", {}).get("required", [])}}


def test_openapi_stable_with_m02_contracts():
    expected = os.environ.get("G142_OPENAPI_SHA")
    assert expected, "G142_OPENAPI_SHA debe provenir del GET oficial"
    status, raw, doc = fetch_openapi()
    assert status == 200
    assert hashlib.sha256(raw).hexdigest() == expected, "OpenAPI cambió durante el preflight"
    discovery = openapi_discovery(doc, raw)
    assert all(x["present"] for x in discovery["routes"].values())


def test_database_readonly_lacks_formal_vision_mapping():
    discovery = db_discovery()
    assert discovery["transaction_read_only"] == "on"
    assert not discovery["formal_m03_vision_source_identified"]
    assert not discovery["formal_m09_vision_baseline_identified"]
    assert any(x["schema"] == "modulo1" and x["table"] == "integridad_baseline"
               for x in discovery["candidate_tables"])
    assert not any(x["schema"] in {"modulo3", "modulo9"}
                   and re.search(r"vision|vector|comportamiento|linea_base|baseline", x["table"], flags=re.IGNORECASE)
                   for x in discovery["candidate_tables"])


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def git_snapshot() -> dict:
    return {"rama": git("branch", "--show-current"), "status_short": git("status", "--short"),
            "diff_stat": git("diff", "--stat"), "diff_cached_stat": git("diff", "--cached", "--stat"),
            "head": git("rev-parse", "HEAD"), "origin_test": git("rev-parse", "origin/test"),
            "divergencia": git("rev-list", "--left-right", "--count", "HEAD...origin/test")}


def write_outputs(out: Path, evidence: dict) -> None:
    out.joinpath("evidencia.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    api = evidence["openapi"]
    db = evidence["precondiciones_vision"]["discovery_db"]
    lines = [
        "# TC-M09-G142 — Resultado", "",
        f"**Resultado general: {evidence['resultado_general']}.** RUN_ID: {evidence['run_id']}. Ambiente: TEST; prueba local: NO.", "",
        "## Decisión general", "",
        "| Caso | Evento M02 previsto | Resultado | Motivo |", "|---|---|---|---|",
        "| TC-M09-288 | Alta de lote poblacional | BLOQUEADO / NO VERIFICABLE | No se identificó una fuente formal de observaciones VISION ni una línea base verificable. |",
        "| TC-M09-289 | Cierre de ciclo | BLOQUEADO / NO VERIFICABLE | La misma dependencia VISION falta; no se cerró un lote sin poder observar el efecto automático. |", "",
        "## Ejecutabilidad VISION/M03", "",
        f"Newman consultó `GET {BASE}/openapi.json` y verificó los cuatro contratos necesarios: POST de alta M02, POST de cierre M02, GET de detalle y GET de auditoría. El OpenAPI respondió HTTP {evidence['openapi_http']}; Pytest confirmó que el contrato no cambió durante el preflight. TEST publica {api['paths_totales']} rutas y {api['schemas_totales']} esquemas.", "",
        "La ausencia de un endpoint **manual** VISION se registra solo como contexto: un disparo M02→M09 podría ser interno. Por eso la decisión se apoya en las precondiciones de datos y verificación, no en esa ausencia aislada.", "",
        f"En la conexión `member_qa` a `sgpmp_test`, `transaction_read_only={db['transaction_read_only']}`, se ejecutaron únicamente cuatro SELECT de catálogo. En `modulo3` se observaron `telemetrias`, `telemetria_calidad`, `eventos_edge_computing` y `paquetes_inferencia`; las dos primeras incluyen `apto_para_ia`, pero ninguna de esas estructuras expone una relación formal de vector de comportamiento VISION con cámara, área, ventana y aptitud. El contrato API tampoco publica un recurso de vectores VISION.", "",
        "La búsqueda de tablas/vistas y columnas semánticas no identificó una persistencia de línea base VISION en M09. `modulo9.calibraciones` tiene campos de calibración SENSOR (`id_sensor`, `valor_referencia`, `id_usuario`) y no los campos de área/especie, origen automático, usuario nullable y vigencia exigidos para esta prueba. `modulo1.integridad_baseline` pertenece a RF-10 y no es la baseline VISION. Los nombres/columnas examinados y los SELECT exactos figuran en `evidencia.json`.", "",
        "**Conclusión de precondiciones:** no se encontró una fuente formal consultable que permita demostrar observaciones VISION aptas `>= N` ni una superficie para validar la baseline automática. No se inventó N: su fuente y valor quedan **no evaluados** porque falta antes la semántica de los vectores. Tampoco se evaluaron A1, especie y C1, que no resolverían esta dependencia global.", "",
        "## TC-M09-288 — nuevo lote", "",
        "**Escenario esperado.** Admin registra en A1 un lote POBLACIONAL de especie AVES. Sin llamar manualmente a VISION, la integración debería publicar una baseline para (A1, especie) con `origen_disparo=AUTOMATICO`, `usuario_id=null`, `vigente=true` y auditoría M09 EXITOSO. El usuario Admin del alta no debe atribuirse como autor del cálculo automático.", "",
        "**Qué se observó.** La ruta y el DTO de alta M02 sí están publicados. Sin embargo, antes de crear un lote no fue posible demostrar la fuente formal de vectores VISION, el umbral N ni dónde consultar la baseline resultante. No se envió POST `/activos-biologicos`: `id_activo`, timestamp del evento, señal de trigger, baseline y auditoría M09 son **no observables**, no fallos medidos. No existe un tiempo transcurrido que reportar.", "",
        "**Decisión: BLOQUEADO / NO VERIFICABLE.** Falta la precondición que permitiría alcanzar y evaluar la cadena automática. No se concluye que M02 haya omitido el disparo o que M09 haya fallado, porque el evento M02 nunca se produjo en este RUN.", "",
        "## TC-M09-289 — fin de ciclo", "",
        "**Escenario esperado.** Admin cierra un lote QA activo y cerrable de A1. El cierre M02 debe provocar un nuevo cálculo automático del mismo par, con origen AUTOMATICO, usuario nulo, baseline vigente y auditoría M09 EXITOSO; no se debe ejecutar VISION manualmente.", "",
        "**Qué se observó.** El POST de cierre está publicado, pero la misma fuente formal VISION y la verificación de baseline faltan. Además, no se preparó ni se cerró un lote: no se evaluaron sus fases, sensores o fecha de cierre, porque hacerlo ahora produciría un evento irreversible sin un oráculo M09 verificable. HTTP del cierre, señal de trigger, baseline posterior y auditoría son **no observables**.", "",
        "**Decisión: BLOQUEADO / NO VERIFICABLE.** No se confunde la falta de precondición con un defecto de integración. Tampoco se deduce nada de un timeout: no hubo evento y RF-24 no fija un SLA para el procesamiento automático.", "",
        "## Ejecución y trazabilidad", "",
        f"- Rama: `{evidence['git']['rama']}`; HEAD: `{evidence['git']['head']}`; origin/test: `{evidence['git']['origin_test']}`; divergencia: `{evidence['git']['divergencia']}`. Estado Git previo completo en `evidencia.json`.",
        "- POST alta M02: 0; POST cierre M02: 0; POST manual VISION: 0; setup: 0. STOP_ALL: NO. SQL: únicamente los SELECT indicados en la evidencia, en sesión read-only.",
        "- `newman.html` contiene el GET real y sus assertions. `pytest.xml` registra la segunda lectura del contrato y del esquema TEST. Ninguno ejecuta el oráculo funcional bloqueado.", "",
        "## Incidencias", "",
        "**INCIDENCIA REQUERIDA: SÍ, de aclaración de dependencia; no se declara bug de integración.** La evidencia de API y esquema no identifica una fuente formal de observaciones VISION ni una superficie verificable de baseline. Se requiere que el proyecto identifique el contrato/pipeline y la configuración N que habilitarían el RUN, o confirme que aún no están entregados.", "",
        "- **Grupo responsable:** Por determinar. **Componente a aclarar:** M03 (vector/cámara), M09 (baseline) e integración con M02. **Grupo de prueba:** TC-M09-G142. **Casos afectados:** TC-M09-288 y TC-M09-289. **Resultado:** BLOQUEADO / NO VERIFICABLE.",
        "- **Esperado:** fuente formal de vectores VISION aptos vinculados a C1/A1, mínimo N, baseline VISION consultable; luego eventos M02 y auditoría M09 automática.",
        "- **Obtenido:** rutas M02 disponibles, pero ninguna estructura/API formal identificada que permita montar `>= N` observaciones VISION ni verificar la baseline. No se ejecutaron los disparadores M02.",
        "- **Causa raíz:** por determinar: contrato de M03/M09 no publicado, implementación pendiente o despliegue/documentación no accesible. La inspección de esquema por sí sola no distingue esas posibilidades.",
        "- **Type:** question. **Severity:** Normal. **Priority:** Normal. **Evidencia:** `evidencia.json`, `newman.html`, `pytest.xml`. Si se confirma una entrega obligatoria ausente, reclasificar con evidencia al componente responsable.", "",
        "## Conclusión", "",
        "G142 queda **BLOQUEADO / NO VERIFICABLE**. Las rutas M02 están desplegadas, pero TEST no permite demostrar las precondiciones y la superficie de verificación de VISION automática. No se registró ni cerró un lote y no se adjudicó a M02/M09 un fallo de disparo no observado.", "",
    ]
    out.joinpath("TC-M09-G142_resultado.md").write_text("\n".join(lines), encoding="utf-8")
    html_report = (
        '<!doctype html><html lang="es"><meta charset="utf-8"><title>G142 Newman</title>'
        '<style>body{font:16px system-ui;max-width:70rem;margin:2rem;line-height:1.5}'
        'pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style>'
        f'<h1>G142 — Newman GET OpenAPI TEST</h1><p>RUN {html.escape(evidence["run_id"])} · '
        f'Newman exit {evidence["newman"]["exit_code"]} · POST M02: 0 · POST VISION: 0</p>'
        '<h2>GET y assertions</h2>'
        f'<pre>{html.escape(evidence["newman"]["stdout"][-5000:])}</pre>'
        '<h2>Rutas M02</h2>'
        f'<pre>{html.escape(json.dumps(api["routes"], ensure_ascii=False, indent=2))}</pre>'
        f'<p>OpenAPI SHA-256: {evidence["openapi_sha256"]}</p></html>'
    )
    out.joinpath("newman.html").write_text(html_report, encoding="utf-8")


def run() -> int:
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError("Ejecute desde TC-M09-G142")
    if os.environ.get("QA_BASE_URL", "").rstrip("/") != BASE:
        raise RuntimeError("QA_BASE_URL debe señalar TEST")
    run_id = os.environ.get("G142_RUN_ID", "")
    if not re.fullmatch(r"run-\d{8}-\d{6}", run_id):
        raise RuntimeError("G142_RUN_ID inválido")
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
        [exe, "run", str(ROOT / "TC-M09-G142.postman_collection.json"),
         "--env-var", f"base_url={BASE}", "--reporters", "cli"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=45, check=False,
    )
    if newman_run.returncode != 0:
        raise RuntimeError(f"Newman falló: {newman_run.stdout[-1000:]} {newman_run.stderr[-500:]}")
    status, raw, doc = fetch_openapi()
    if status != 200:
        raise RuntimeError(f"GET OpenAPI TEST HTTP {status}")
    api = openapi_discovery(doc, raw)
    if not all(x["present"] for x in api["routes"].values()):
        raise RuntimeError("Falta contrato M02/RF-10 esperado; revisar antes de decidir G142")
    db = db_discovery()
    if db["formal_m03_vision_source_identified"] or db["formal_m09_vision_baseline_identified"]:
        raise RuntimeError("Apareció estructura VISION candidata: revisar semántica antes de POST M02")
    digest = hashlib.sha256(raw).hexdigest()
    env = {**os.environ, "G142_OPENAPI_SHA": digest, "PYTHONDONTWRITEBYTECODE": "1"}
    pytest_run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--noconftest", "-p", "no:cacheprovider",
         str(ROOT / "test_tc_m09_g142.py"), f"--junitxml={out / 'pytest.xml'}"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    if pytest_run.returncode != 0:
        raise RuntimeError(f"Pytest no confirmó preflight: {pytest_run.stdout[-1000:]} {pytest_run.stderr[-500:]}")
    evidence = {
        "grupo": "TC-M09-G142", "casos": ["TC-M09-288", "TC-M09-289"], "run_id": run_id,
        "ambiente": "TEST", "prueba_local": False, "base_url": BASE, "git": snapshot,
        "openapi_http": status, "openapi_observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "openapi_sha256": digest, "openapi": api,
        "newman": {"exit_code": newman_run.returncode, "stdout": newman_run.stdout[-5000:],
                   "stderr": newman_run.stderr[-500:]},
        "pytest": {"exit_code": pytest_run.returncode, "resultado": pytest_run.stdout[-1000:]},
        "precondiciones_vision": {
            "fuente_vectores": {"estado": "NO IDENTIFICADA FORMALMENTE en API/esquema TEST",
                                "no_equivalencia": "apto_para_ia en telemetría no prueba vector de comportamiento VISION"},
            "N": None, "N_estado": "NO EVALUADO; sin fuente formal de vectores",
            "baseline": {"estado": "NO IDENTIFICADA FORMALMENTE en API/esquema TEST"},
            "area": {"estado": "NO EVALUADA tras bloqueo global"},
            "especie": {"estado": "NO EVALUADA tras bloqueo global"},
            "camara": {"estado": "NO EVALUADA tras bloqueo global"},
            "discovery_db": db,
        },
        "TC-M09-288": {
            "baseline_pre": None, "m02_request": None, "m02_response": None, "id_activo": None,
            "t_evento": None, "trigger_signal": None, "baseline_post": None, "elapsed": None,
            "auditoria_m09": None, "resultado": "BLOQUEADO / NO VERIFICABLE",
            "motivo": "Sin fuente formal de vectores VISION/N ni superficie baseline verificable; no se registró lote M02."},
        "TC-M09-289": {
            "activo": None, "precondiciones_cierre": None, "baseline_pre": None,
            "m02_request": None, "m02_response": None, "t_evento": None,
            "trigger_signal": None, "baseline_post": None, "auditoria_m09": None,
            "resultado": "BLOQUEADO / NO VERIFICABLE",
            "motivo": "La dependencia VISION no es montable/verificable; no se preparó ni cerró lote M02."},
        "post_alta_m02": 0, "post_cierre_m02": 0, "post_manual_vision": 0,
        "post_setup": 0, "sql_escritura": False, "stop_all": False,
        "resultado_general": "BLOQUEADO / NO VERIFICABLE",
        "motivo_general": "Rutas M02 disponibles, pero no hay fuente formal VISION/baseline verificable para evaluar la integración automática.",
        "incidencias": [{"incidencia_requerida": "SÍ", "grupo_responsable": "Por determinar",
                         "componente": "M03/M09 e integración M02", "grupo": "TC-M09-G142",
                         "casos": ["TC-M09-288", "TC-M09-289"], "resultado": "BLOQUEADO / NO VERIFICABLE",
                         "motivo": "Aclarar fuente formal de vectores VISION, N y superficie baseline antes de ejecutar triggers M02.",
                         "esperado": "Dependencias VISION montables y verificables; luego eventos M02 con baseline automática/auditoría.",
                         "obtenido": "M02 publicado, fuente VISION/baseline no identificada por API/SELECT de esquema.",
                         "causa_raiz": "Por determinar; contrato, implementación o despliegue/documentación no distinguibles.",
                         "type": "question", "severity": "Normal", "priority": "Normal",
                         "evidencia": "evidencia.json / newman.html / pytest.xml"}],
    }
    write_outputs(out, evidence)
    print(f"G142 BLOQUEADO / NO VERIFICABLE; TC-288/289 BLOQUEADOS; POST M02 0; "
          f"SQL escritura NO; {out}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--run"]:
        raise SystemExit("Uso: python test_tc_m09_g142.py --run")
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"ERROR G142: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
