# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G40 (JSON, repro, MD, TXT)  |
# | 2026-11-12 | Juan Sebastian Gutierrez | TC-M05-G40 rediseno v2.0: checkpoints T00..T99, obtenido real desde observaciones |
"""Generador de artefactos de corrida para TC-M05-G40 (RF-80 v2.0, RFC-025 C25.1).

Lee JUnit XML, trazas_http.jsonl y observaciones_g40.json del staging de la corrida y genera:
- resultado_TC-M05-G40[_reintentoN].json
- TC-M05-G40[_reintentoN]_resultado.md
- INFORME_FASE234_TC-M05-G40[_reintentoN].txt
- Inyecta data-jsonblob en resultado_TC-M05-G40[_reintentoN].html
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ZONA_USUARIO = timezone(timedelta(hours=-5))


TEST_METADATA = {
    "test_t00_linea_base": {
        "paso": "T00 Linea base de modulo5.auditorias_suministros (corrida aparte solo lectura)",
        "esperado": "GET /suministros/auditoria 200 con total y ultimo_id base; DELETE -> 200 Rollback exitoso",
        "fuente": "Testing Harness / Inocuidad",
    },
    "test_a01_atomicidad_commit_rf78": {
        "paso": "A01 Atomicidad en commit RF-78 (POST /suministros/costeo-directo)",
        "esperado": "HTTP 200 (RF-78 CA-14/E8); exactamente 1 SUMINISTRO_REGISTRADO, 1 PRECIO_MANUAL_INGRESADO y 1 ACUMULADO_ACTUALIZADO con hash_integridad (64 hex), version in {1,2} y <= 2.0 s",
        "fuente": "RF-80 v2.0 Auditoria local / CA-1 / TC-M05-031 v2.0 / RF-78 CA-14 y E8",
    },
    "test_a02_atomicidad_commit_rf79": {
        "paso": "A02 Atomicidad en commit RF-79 (POST /activos-biologicos/{id}/cierre)",
        "esperado": "HTTP 200 (OpenAPI); exactamente 1 CICLO_CONSOLIDADO y 1 REPORTE_COSTOS_GENERADO (entidad_afectada='provision_nic41') en secuencia y con hash <= 2.0 s; clave 'versiones' == 1 CONSOLIDADO; resultado_ica solo conteo",
        "fuente": "RF-80 v2.0 Auditoria local / CA-1 / TC-M05-031 v2.0 / ListaVersionesProvisionResponse",
    },
    "test_a03_atomicidad_commit_rf81": {
        "paso": "A03 Atomicidad en commit RF-81 (GET /suministros/historial)",
        "esperado": "HTTP 200 (OpenAPI); exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo del Admin (entidad_afectada='historial_suministros', EXITOSO) con hash <= 2.0 s",
        "fuente": "RF-80 v2.0 Auditoria local / CA-1 / TC-M05-031 v2.0 / OpenAPI",
    },
    "test_b01_rollback_errores_api": {
        "paso": "B01 Rollback / no persistencia parcial en errores RF-78, RF-79 y RF-81",
        "esperado": "(a) RF-78 sin fase -> 409 (anota error_code), 0 SUMINISTRO_REGISTRADO/ACUMULADO_ACTUALIZADO; (b) RF-79 cierre repetido -> 4xx (anota codigo y error_code), 0 CICLO_CONSOLIDADO/REPORTE_COSTOS_GENERADO, versiones=1; (c) RF-81 rango invertido -> 422 COMBINACION_FILTROS_INVALIDA y 0 CONSULTA_HISTORIAL_EJECUTADA EXITOSO",
        "fuente": "RF-80 v2.0 RNF-02 / TC-M05-031 v2.0 / RF-78 / RF-79 / RF-81 R7-E5",
    },
    "test_t98_cierre_sandbox_principal": {
        "paso": "T98 Cierre de corrida sandbox principal",
        "esperado": "DELETE /test-control/runs/{run_id} -> HTTP 200 Rollback exitoso",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_c01_rollback_tecnico_sandbox": {
        "paso": "C01 Rollback tecnico en corrida sandbox aparte y verificacion 404 por ID",
        "esperado": "RF-78/RF-79/RF-81 -> 200 (>=1 evento/op); DELETE -> 200; en corrida aparte solo lectura: GET /suministros/auditoria/{id} -> 404 para cada id, GET /activos-biologicos/{id} -> 404, total y ultimo_id iguales a previos a C01",
        "fuente": "RF-80 v2.0 RNF-02 / TC-M05-031 v2.0 / Testing Harness",
    },
    "test_t99_inocuidad_post_rollback": {
        "paso": "T99 Inocuidad post-rollback en corrida sandbox aparte de solo lectura",
        "esperado": "total y ultimo_id iguales a T00; todos los activos creados (incluido C01) y sus acumulados -> HTTP 404; DELETE -> 200",
        "fuente": "Testing Harness / Inocuidad / RF-80 v2.0 RNF-02",
    },
}


def _cargar_trazas_por_test(ruta_trazas: Path) -> dict[str, list[dict[str, Any]]]:
    por_test: dict[str, list[dict[str, Any]]] = {}
    if not ruta_trazas.exists():
        return por_test
    for linea in ruta_trazas.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            reg = json.loads(linea)
        except Exception:
            continue
        tname = reg.get("test") or "init"
        por_test.setdefault(tname, []).append(reg)
    return por_test


def _resumir_trazas(trazas: list[dict[str, Any]], max_items: int = 8) -> str:
    if not trazas:
        return "Sin llamadas HTTP registradas"
    partes: list[str] = []
    for r in trazas[:max_items]:
        metodo = r.get("metodo", "?")
        ruta = r.get("ruta", "?")
        st = r.get("status_code")
        ec = r.get("error_code")
        xid = r.get("x_request_id") or ""
        ec_str = f" {ec}" if ec else ""
        xid_str = f" [X-Request-Id={xid}]" if xid else ""
        partes.append(f"{metodo} {ruta} -> HTTP {st}{ec_str}{xid_str}")
    if len(trazas) > max_items:
        partes.append(f"(+{len(trazas) - max_items} requests)")
    return "; ".join(partes)


def extraer_latencia_a01_a03(
    obs_data: dict[str, Any],
    trazas_por_test: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    res = obs_data.get("latencia_a01_a03_resumen")
    if isinstance(res, dict) and res.get("muestras"):
        return res
    latencias: list[float] = []
    objetivos = (
        ("test_a01_atomicidad_commit_rf78", "POST", "/suministros/costeo-directo"),
        ("test_a02_atomicidad_commit_rf79", "POST", "/cierre"),
        ("test_a03_atomicidad_commit_rf81", "GET", "/suministros/historial"),
    )
    for tname, metodo, seg in objetivos:
        for d in trazas_por_test.get(tname, []):
            ruta = str(d.get("ruta") or "")
            if d.get("metodo") == metodo and (ruta == seg or ruta.endswith(seg)):
                dur = d.get("duracion_ms")
                if dur is not None:
                    latencias.append(float(dur))
                    break
    if not latencias:
        return {"muestras": 0, "min_ms": 0.0, "p50_ms": 0.0, "max_ms": 0.0}
    s = sorted(latencias)
    n = len(s)
    return {
        "muestras": n,
        "min_ms": round(s[0], 2),
        "p50_ms": round(s[n // 2], 2),
        "max_ms": round(s[-1], 2),
    }


def _construir_obtenido(
    nombre: str,
    obs_cp: dict[str, Any],
    resumen_http: str,
    msg_fallo: str | None = None,
    msg_skip: str | None = None,
) -> str:
    texto_obs = (obs_cp.get("obtenido_texto") or "").strip()
    if msg_fallo is not None:
        base = f"{msg_fallo} | {texto_obs}" if texto_obs else msg_fallo
        return f"{base} | HTTP: {resumen_http}"
    if msg_skip is not None:
        return f"SKIPPED: {msg_skip} | HTTP: {resumen_http}"
    if texto_obs:
        return f"{texto_obs} | HTTP: {resumen_http}"
    return f"HTTP: {resumen_http}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G40")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (0 para corrida inicial)")
    args = parser.parse_args()

    staging = Path(args.staging)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    xml_path = staging / f"resultado_TC-M05-G40{sufijo}.xml"
    if not xml_path.exists():
        xml_path = staging / "resultado_TC-M05-G40.xml"
    if not xml_path.exists():
        print(f"ERROR: No existe archivo XML en {staging}")
        return

    trazas_por_test = _cargar_trazas_por_test(staging / "trazas_http.jsonl")
    obs_path = staging / "observaciones_g40.json"
    obs_data: dict[str, Any] = {}
    if obs_path.exists():
        try:
            obs_data = json.loads(obs_path.read_text(encoding="utf-8"))
        except Exception:
            obs_data = {}
    detalle_cps = obs_data.get("checkpoints_detalle") if isinstance(obs_data.get("checkpoints_detalle"), dict) else {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    checkpoints: list[dict[str, str]] = []
    fallos_detalle: list[dict[str, str]] = []
    ok = 0
    falla = 0

    testcase_elements = root.findall(".//testcase")
    total = len(testcase_elements)

    for tc in testcase_elements:
        nombre = tc.attrib.get("name", "")
        meta = TEST_METADATA.get(
            nombre,
            {
                "paso": nombre,
                "esperado": "Comportamiento segun especificacion RF-80 v2.0",
                "fuente": "RF-80 v2.0 / TC-M05-G40",
            },
        )
        trazas = trazas_por_test.get(nombre, [])
        resumen_http = _resumir_trazas(trazas)
        obs_cp = detalle_cps.get(nombre) if isinstance(detalle_cps.get(nombre), dict) else {}

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")

        if failure is not None or error is not None:
            nodo = failure if failure is not None else error
            estado = "FALLA"
            falla += 1
            msg_raw = (nodo.attrib.get("message") or nodo.text or "Fallo de aserto").strip()
            msg_primera_linea = msg_raw.splitlines()[0]
            obtenido = _construir_obtenido(nombre, obs_cp, resumen_http, msg_fallo=msg_primera_linea)
            fallos_detalle.append({
                "test": nombre,
                "paso": meta["paso"],
                "fuente": meta["fuente"],
                "mensaje": msg_primera_linea,
                "http": resumen_http,
            })
        elif skipped is not None:
            estado = "OMITIDO"
            msg_raw = (skipped.attrib.get("message") or skipped.text or "Omitido").strip()
            obtenido = _construir_obtenido(nombre, obs_cp, resumen_http, msg_skip=msg_raw)
        else:
            estado = "OK"
            ok += 1
            obtenido = _construir_obtenido(nombre, obs_cp, resumen_http)

        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": obtenido,
            "estado": estado,
        })

    veredicto = "Aprobado" if falla == 0 and total > 0 else "Rechazado"

    resultado_json = {
        "tc": "TC-M05-G40",
        "summary": {
            "total": total,
            "ok": ok,
            "falla": falla,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
    }

    json_path = staging / f"resultado_TC-M05-G40{sufijo}.json"
    json_path.write_text(json.dumps(resultado_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generado: {json_path.name}")

    html_path = staging / f"resultado_TC-M05-G40{sufijo}.html"
    if not html_path.exists():
        html_path = staging / "resultado_TC-M05-G40.html"
    if html_path.exists():
        try:
            html_content = html_path.read_text(encoding="utf-8")
            blob_script = (
                '<script id="data-jsonblob" type="application/json">'
                + json.dumps(resultado_json, ensure_ascii=False)
                + "</script>"
            )
            if 'id="data-jsonblob"' not in html_content:
                if "</body>" in html_content:
                    html_content = html_content.replace("</body>", f"{blob_script}</body>")
                else:
                    html_content += blob_script
                html_path.write_text(html_content, encoding="utf-8")
                print(f"Inyectado data-jsonblob en {html_path.name}")
        except Exception as e:
            print(f"Aviso: no se pudo inyectar data-jsonblob en HTML: {e}")

    stats_lat = extraer_latencia_a01_a03(obs_data, trazas_por_test)
    ahora_str = datetime.now(ZONA_USUARIO).strftime("%Y-%m-%d %H:%M:%S")
    md_lines = [
        "# Resultado de Prueba: TC-M05-G40",
        "## Atomicidad de Auditoria y Rollback (RF-80 v2.0, RFC-025 C25.1)",
        "",
        f"- **ID Caso:** TC-M05-G40 (TC-M05-031 v2.0 / Plano: TC-M05-095){' - Reintento ' + str(args.reintento) if args.reintento > 0 else ''}",
        f"- **Veredicto:** {veredicto} ({ok}/{total} OK, {falla} Fallas)",
        f"- **Fecha:** {ahora_str} (America/Bogota)",
        f"- **Duracion:** {args.duracion_s:.2f} s",
        "",
        "### Latencia Observada A01-A03 (solo observacion, sin asercion)",
        f"- Muestras registradas: {stats_lat.get('muestras', 0)}",
        f"- Minima: {stats_lat.get('min_ms', 0.0)} ms | Mediana p50: {stats_lat.get('p50_ms', 0.0)} ms | Maxima: {stats_lat.get('max_ms', 0.0)} ms",
        "",
        "### Resumen de Checkpoints",
        "| # | Paso | Esperado | Obtenido | Estado |",
        "|---|------|----------|----------|--------|",
    ]
    for idx, cp in enumerate(checkpoints, 1):
        md_lines.append(
            f"| {idx} | {cp['paso'].replace('|', '/')} | {cp['esperado'].replace('|', '/')} "
            f"| {cp['obtenido'].replace('|', '/')} | {cp['estado']} |"
        )

    md_lines.append("")
    md_lines.append("### Fallos Detectados")
    if not fallos_detalle:
        md_lines.append("- Sin fallos en esta ejecucion.")
    else:
        for fd in fallos_detalle:
            md_lines.append(f"- **{fd['paso']}** ({fd['fuente']})")
            md_lines.append(f"  - Detalle: `{fd['mensaje']}`")
            md_lines.append(f"  - Trazas: `{fd['http']}`")

    md_lines.append("")
    md_lines.append("### Cobertura no ejecutable por API")
    md_lines.append(f"- **C02:** {obs_data.get('c02_analisis', 'No ejecutable por API; cubierto atomicamente por C01.')}")
    md_lines.append(
        "- **Retirado por RFC-025 C25.1:** Cola persistente M05->M12 100.000 eventos, alertas 90%/100%, FIFO 48h y degradacion <=50 ms sin auditoria."
    )

    md_path = staging / f"TC-M05-G40{sufijo}_resultado.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Generado: {md_path.name}")

    txt_lines = [
        "================================================================================",
        f"INFORME DE EJECUCION: TC-M05-G40{' (REINTENTO ' + str(args.reintento) + ')' if args.reintento > 0 else ''}",
        'RF-80 v2.0 (RFC-025 C25.1) "Atomicidad de Auditoria y Rollback"',
        "================================================================================",
        f"Fecha/Hora: {ahora_str} (America/Bogota)",
        f"Total tests: {total} | Aprobados: {ok} | Fallidos: {falla}",
        f"Veredicto: {veredicto} | Duracion: {args.duracion_s:.2f} s",
        "",
        "CHECKPOINTS:",
        "--------------------------------------------------------------------------------",
    ]
    for idx, cp in enumerate(checkpoints, 1):
        txt_lines.extend([
            f"[{idx:02d}] {cp['paso']} -> {cp['estado']}",
            f"     Esperado: {cp['esperado']}",
            f"     Obtenido: {cp['obtenido']}",
            "",
        ])

    txt_lines.extend([
        "LATENCIA OBSERVADA A01-A03 (solo observacion, sin asercion):",
        f"  muestras={stats_lat.get('muestras', 0)} min={stats_lat.get('min_ms', 0.0)}ms p50={stats_lat.get('p50_ms', 0.0)}ms max={stats_lat.get('max_ms', 0.0)}ms",
        "",
        "RESULTADO JSON:",
        json.dumps(resultado_json, indent=2, ensure_ascii=False),
    ])

    txt_path = staging / f"INFORME_FASE234_TC-M05-G40{sufijo}.txt"
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()
