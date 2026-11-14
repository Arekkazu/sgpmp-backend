# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G39 (Evaluación Oficial)     |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G39 reevaluacion v2.0: --reintento, obtenido real por trazas, sin diagnosticos fijos |
"""Generador de artefactos de corrida para TC-M05-G39 (RF-80 v2.0, RFC-025).

Lee JUnit XML, trazas_http.jsonl y observaciones_g39.json del staging de la corrida y genera:
- resultado_TC-M05-G39[_reintentoN].json
- TC-M05-G39[_reintentoN]_resultado.md
- INFORME_FASE234_TC-M05-G39[_reintentoN].txt
- Inyecta data-jsonblob en resultado_TC-M05-G39[_reintentoN].html
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
    "test_a01_incompletos_con_causa": {
        "paso": "A01 Eventos incompletos nuevos con detalle_causa y consolidacion RF-79",
        "esperado": "Costeo sin fase -> 409 REGISTRO_FALLIDO; cierre RF-79; todos los registro_incompleto=true tienen detalle_causa no nulo ni vacio y consolidacion sin marca falsa por conciliacion pendiente",
        "fuente": "TC-M05-092 / RF-80 v2.0 CA-12, R8, E2 / INC-M05-278-G39 defecto 1",
    },
    "test_a02_campos_base_presentes": {
        "paso": "A02 Campos base presentes en TODOS los eventos nuevos (CA-11)",
        "esperado": "Todo evento nuevo (incluido INSERT) tiene tipo_operacion, resultado y fecha_emision no nulos ni vacios",
        "fuente": "TC-M05-092 / RF-80 v2.0 CA-11, R8",
    },
    "test_b01_inmutabilidad_api": {
        "paso": "B01 Inmutabilidad por API (PUT/PATCH/DELETE/POST como Admin)",
        "esperado": "Cada metodo -> HTTP 405 Allow: GET, GET objetivo intacto (incluido hash) y 1 evento RECHAZADO de Admin en <=2 s sin cuerpo enviado",
        "fuente": "TC-M05-093 / RF-80 v2.0 Restriccion 1, CA-2, RNF-05 / INC-M05-278-G39 defecto 2",
    },
    "test_b02_intentos_otros_actores": {
        "paso": "B02 Intentos de otros actores (Productor, ID inexistente 999999999, sin token)",
        "esperado": "Productor PUT -> 405 sin fuga + 1 RECHAZADO de Productor; Admin ID 999999999 -> 405 + 1 RECHAZADO; sin token -> 401",
        "fuente": "TC-M05-093 / RF-80 v2.0 CA-2, RNF-05 / INC-M05-278-G39",
    },
    "test_b03_recalculo_hash": {
        "paso": "B03 Recalculo SHA-256 (nuevos v2 e historicos v1) + simulacion local alterada",
        "esperado": "Recalculo desde GET /{id} igual a hash_integridad en nuevos v2 e historicos v1 (87/88/89); simulacion alterada difiere",
        "fuente": "TC-M05-093 / RF-80 v2.0 C25.3, ADR-M05-02",
    },
    "test_b04_sin_endpoints_escritura": {
        "paso": "B04 Ausencia de endpoints de escritura en /openapi.json",
        "esperado": "GET /openapi.json no declara POST/PUT/PATCH/DELETE bajo /suministros/auditoria*",
        "fuente": "TC-M05-093, nota ZAP / RF-80 v2.0 CA-2",
    },
    "test_t98_cierre_corrida_principal": {
        "paso": "T98 Cierre de la corrida sandbox principal",
        "esperado": "DELETE /test-control/runs/{run_id} -> HTTP 200 Rollback exitoso",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_t99_inocuidad": {
        "paso": "T99 Inocuidad post-rollback en corrida sandbox aparte de solo lectura",
        "esperado": "total y ultimo_id iguales a T00; GET de activos creados -> HTTP 404; DELETE -> 200",
        "fuente": "Testing Harness / Inocuidad",
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
        return "Sin llamadas HTTP registradas (fallo previo en precondicion)"
    partes: list[str] = []
    for r in trazas[:max_items]:
        metodo = r.get("metodo", "?")
        ruta = r.get("ruta", "?")
        st = r.get("status_code")
        ec = r.get("error_code")
        xid = r.get("x_request_id") or ""
        allow = r.get("allow_header") or ""
        extra_bits: list[str] = []
        if allow:
            extra_bits.append(f"Allow={allow}")
        rb = r.get("response_body")
        if isinstance(rb, dict):
            if "total" in rb and isinstance(rb.get("total"), int):
                extra_bits.append(f"total={rb['total']}")
            if isinstance(rb.get("items"), list):
                ids = [x.get("id_auditoria_suministro") for x in rb["items"] if isinstance(x, dict) and x.get("id_auditoria_suministro") is not None]
                if ids:
                    extra_bits.append(f"ids={ids[:6]}")
            if rb.get("id_activo_biologico") is not None:
                extra_bits.append(f"id_activo={rb['id_activo_biologico']}")
        ec_str = f" {ec}" if ec else ""
        xid_str = f" [X-Request-Id={xid}]" if xid else ""
        det_str = f" ({', '.join(extra_bits)})" if extra_bits else ""
        partes.append(f"{metodo} {ruta} -> HTTP {st}{ec_str}{det_str}{xid_str}")
    if len(trazas) > max_items:
        partes.append(f"(+{len(trazas) - max_items} requests)")
    return "; ".join(partes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G39")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (0 para corrida inicial)")
    args = parser.parse_args()

    staging = Path(args.staging)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    xml_path = staging / f"resultado_TC-M05-G39{sufijo}.xml"
    if not xml_path.exists():
        xml_path = staging / "resultado_TC-M05-G39.xml"
    if not xml_path.exists():
        print(f"ERROR: No existe archivo XML en {staging}")
        return

    trazas_por_test = _cargar_trazas_por_test(staging / "trazas_http.jsonl")

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
                "fuente": "RF-80 v2.0 / TC-M05-G39",
            },
        )
        trazas = trazas_por_test.get(nombre, [])
        resumen_http = _resumir_trazas(trazas)

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")

        if failure is not None or error is not None:
            nodo = failure if failure is not None else error
            estado = "FALLA"
            falla += 1
            msg_raw = (nodo.attrib.get("message") or nodo.text or "Fallo de aserto").strip()
            msg_primera_linea = msg_raw.splitlines()[0]
            obtenido = f"{msg_primera_linea} | HTTP: {resumen_http}"
            fallos_detalle.append({
                "test": nombre,
                "paso": meta["paso"],
                "fuente": meta["fuente"],
                "mensaje": msg_primera_linea,
                "http": resumen_http,
                "clasificacion": "PENDIENTE_DIAGNOSTICO",
            })
        elif skipped is not None:
            estado = "OMITIDO"
            msg_raw = (skipped.attrib.get("message") or skipped.text or "Omitido").strip()
            obtenido = f"SKIPPED: {msg_raw} | HTTP: {resumen_http}"
        else:
            estado = "OK"
            ok += 1
            obtenido = f"HTTP: {resumen_http}"

        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": obtenido,
            "estado": estado,
        })

    veredicto = "Aprobado" if falla == 0 and total > 0 else "Rechazado"

    resultado_json = {
        "tc": "TC-M05-G39",
        "summary": {
            "total": total,
            "ok": ok,
            "falla": falla,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
    }

    json_path = staging / f"resultado_TC-M05-G39{sufijo}.json"
    json_path.write_text(json.dumps(resultado_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generado: {json_path.name}")

    html_path = staging / f"resultado_TC-M05-G39{sufijo}.html"
    if not html_path.exists():
        html_path = staging / "resultado_TC-M05-G39.html"
    if html_path.exists():
        try:
            html_content = html_path.read_text(encoding="utf-8")
            blob_script = (
                f'<script id="data-jsonblob" type="application/json">'
                f"{json.dumps(resultado_json, ensure_ascii=False)}</script>"
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

    ahora_str = datetime.now(ZONA_USUARIO).strftime("%Y-%m-%d %H:%M:%S")
    md_lines = [
        "# Resultado de Prueba: TC-M05-G39",
        "## Campos Minimos, Inmutabilidad y Hash de Integridad (RF-80 v2.0, RFC-025)",
        "",
        f"- **ID Caso:** TC-M05-G39 (TC-M05-092 y TC-M05-093; TC-M05-094 retirado por RFC-025){' — Reintento ' + str(args.reintento) if args.reintento > 0 else ''}",
        f"- **Veredicto:** {veredicto} ({ok}/{total} OK, {falla} Fallas)",
        f"- **Fecha:** {ahora_str} (America/Bogota)",
        f"- **Duración:** {args.duracion_s:.2f} s",
        "",
        "### Resumen de Checkpoints",
        "| # | Paso | Esperado | Obtenido | Estado |",
        "|---|------|----------|----------|--------|",
    ]
    for idx, cp in enumerate(checkpoints, 1):
        paso_esc = cp["paso"].replace("|", "/")
        esp_esc = cp["esperado"].replace("|", "/")
        obt_esc = cp["obtenido"].replace("|", "/")
        md_lines.append(f"| {idx} | {paso_esc} | {esp_esc} | {obt_esc} | {cp['estado']} |")

    md_lines.append("")
    md_lines.append("### Fallos Detectados")
    if not fallos_detalle:
        md_lines.append("- Sin fallos en esta ejecucion.")
    else:
        for fd in fallos_detalle:
            md_lines.append(f"- **{fd['paso']}** ({fd['fuente']}) — `{fd['clasificacion']}`")
            md_lines.append(f"  - Detalle: `{fd['mensaje']}`")
            md_lines.append(f"  - Trazas: `{fd['http']}`")

    md_path = staging / f"TC-M05-G39{sufijo}_resultado.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Generado: {md_path.name}")

    txt_lines = [
        "================================================================================",
        f"INFORME DE EJECUCION: TC-M05-G39{' (REINTENTO ' + str(args.reintento) + ')' if args.reintento > 0 else ''}",
        'RF-80 v2.0 (RFC-025) "Auditoria y Trazabilidad de Registros de Suministros"',
        "================================================================================",
        f"Fecha/Hora: {ahora_str} (America/Bogota)",
        f"Total tests: {total} | Aprobados: {ok} | Fallidos: {falla}",
        f"Veredicto Final: {veredicto}",
        f"Duracion: {args.duracion_s:.2f} s",
        "",
        "1. TABLA DETALLADA DE CHECKPOINTS",
        "--------------------------------------------------------------------------------",
    ]
    for idx, cp in enumerate(checkpoints, 1):
        txt_lines.append(f"[{idx:02d}] {cp['paso']}")
        txt_lines.append(f"     Esperado: {cp['esperado']}")
        txt_lines.append(f"     Obtenido: {cp['obtenido']}")
        txt_lines.append(f"     Estado:   {cp['estado']}")
        txt_lines.append("")

    txt_lines.append("2. DETALLE DE FALLOS")
    txt_lines.append("--------------------------------------------------------------------------------")
    if not fallos_detalle:
        txt_lines.append("Sin fallos registrados.")
    else:
        for fd in fallos_detalle:
            txt_lines.append(f"- {fd['paso']} [{fd['clasificacion']}] ({fd['fuente']})")
            txt_lines.append(f"  Mensaje: {fd['mensaje']}")
            txt_lines.append(f"  HTTP:    {fd['http']}")

    txt_path = staging / f"INFORME_FASE234_TC-M05-G39{sufijo}.txt"
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()
