# | Fecha      | Nombre                   | Que se hizo                                                                              |
# |------------|--------------------------|------------------------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G37 (JSON, repro, MD, TXT)                    |
# | 2026-11-11 | Juan Sebastian Gutierrez | Reevaluacion v2.0: --reintento, obtenido real desde JUnit/trazas, sin textos fijos M12   |
"""Generador de artefactos de corrida para TC-M05-G37 (RF-80 v2.0 / RFC-025).

Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G37[_reintentoN].json
- TC-M05-G37[_reintentoN]_resultado.md
- INFORME_FASE234_TC-M05-G37[_reintentoN].txt
- Inyecta data-jsonblob en resultado_TC-M05-G37[_reintentoN].html
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ZONA_USUARIO = timezone(timedelta(hours=-5))

TEST_METADATA: dict[str, dict[str, str]] = {
    "test_t00_linea_base": {
        "paso": "T00 Linea base en corrida sandbox independiente de solo lectura",
        "esperado": "HTTP 200 en auditoria base con total y ultimo_id capturados; cierre DELETE -> 200 Rollback exitoso",
        "fuente": "Regla sandbox / Inocuidad",
    },
    "test_a01a_rf78_exito_y_persistencia": {
        "paso": "A01a RF-78 exito: SERVICIO_VETERINARIO con unidad 'servicio' y 3 eventos <= 2 s",
        "esperado": "HTTP 200 y exactamente SUMINISTRO_REGISTRADO, PRECIO_MANUAL_INGRESADO, ACUMULADO_ACTUALIZADO en <= 2.0 s con campos R8/RNF-08 y sub JWT",
        "fuente": "RF-80 v2.0 CA-1, Entradas, R8, RNF-08; TC-M05-090",
    },
    "test_a01b_rf81_exito_historial": {
        "paso": "A01b RF-81 exito: GET /suministros/historial -> 1 CONSULTA_HISTORIAL_EJECUTADA <= 2 s",
        "esperado": "HTTP 200 y exactamente 1 CONSULTA_HISTORIAL_EJECUTADA con id_usuario, hash SHA-256 y latencia <= 2.0 s",
        "fuente": "RF-80 v2.0 CA-1, R8; TC-M05-090",
    },
    "test_a02a_rf78_rechazo_sin_fase_y_repeticion": {
        "paso": "A02a RF-78 rechazo sin fase abierta (409 CICLO_NO_ACTIVO), sin efectos parciales y repeticion",
        "esperado": "HTTP 409 CICLO_NO_ACTIVO, 1 REGISTRO_FALLIDO (RECHAZADO/FALLIDO, TECNICO/1 año, registro_incompleto=true), acumulado 404, historial 0 y +1 evento al repetir",
        "fuente": "RF-80 v2.0 CA-1, R8, E2; criterio INC-M05-275-G37",
    },
    "test_a02b_rf78_rechazo_con_fase_abierta": {
        "paso": "A02b RF-78 rechazo con fase abierta (cantidad -1 -> 422 COSTO_REGISTRO_INVALIDO)",
        "esperado": "HTTP 422 COSTO_REGISTRO_INVALIDO y 1 REGISTRO_FALLIDO con id_ciclo_productivo e id_gestion_fases no nulos en <= 2.0 s",
        "fuente": "RF-80 v2.0 CA-1, R8; TC-M05-090",
    },
    "test_a02c_rf79_rechazo_ciclo_activo": {
        "paso": "A02c RF-79 rechazo: consolidar con ciclo activo (409 CICLO_ACTIVO)",
        "esperado": "HTTP 409 CICLO_ACTIVO y >= 1 evento nuevo con resultado FALLIDO/RECHAZADO, id_usuario=Admin y latencia <= 2.0 s",
        "fuente": "RF-80 v2.0 CA-1; TC-M05-G37 v2.0 (TC-M05-090)",
    },
    "test_a02d_rf81_rechazo_filtros_invalidos": {
        "paso": "A02d RF-81 rechazo: historial con fecha_fin < fecha_inicio (422 COMBINACION_FILTROS_INVALIDA)",
        "esperado": "HTTP 422 COMBINACION_FILTROS_INVALIDA y >= 1 evento nuevo con resultado FALLIDO/RECHAZADO, id_usuario=Admin y latencia <= 2.0 s",
        "fuente": "RF-80 v2.0 CA-1; TC-M05-G37 v2.0 (TC-M05-090)",
    },
    "test_a01c_rf79_exito_cierre": {
        "paso": "A01c RF-79 exito: cierre de ciclo -> CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO <= 2 s",
        "esperado": "HTTP 200 en cierre y eventos CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO EXITOSO con costo_afectado y hash <= 2.0 s",
        "fuente": "RF-80 v2.0 CA-1, R8; TC-M05-090",
    },
    "test_a03_consistencia_lista_detalle_y_filtros": {
        "paso": "A03 Consistencia lista vs detalle /{id} y filtros para EXITOSO y REGISTRO_FALLIDO",
        "esperado": "Identidad campo por campo lista == detalle /{id} y aparicion en los 6 filtros para SUMINISTRO_REGISTRADO y REGISTRO_FALLIDO",
        "fuente": "RF-80 v2.0 Postc.3, CA-4, RNF-08; TC-M05-090",
    },
    "test_a04_restriccion_8_campos_minimos": {
        "paso": "A04 Restriccion 8: campos minimos por tipo y flag registro_incompleto",
        "esperado": "Todos los eventos del catalogo cumplen campos minimos o registran registro_incompleto=true con detalle_causa nombrando el faltante",
        "fuente": "RF-80 v2.0 Restriccion 8, E2, CA-12",
    },
    "test_b01_clasificacion_y_retencion_catalogo": {
        "paso": "B01 Clasificacion y retencion por catalogo (NIC41 / 5 años vs TECNICO / 1 año)",
        "esperado": "SUMINISTRO_REGISTRADO, ACUMULADO_ACTUALIZADO, CICLO_CONSOLIDADO, REPORTE_COSTOS_GENERADO=NIC41/5 años; PRECIO_MANUAL_INGRESADO, CONSULTA_HISTORIAL_EJECUTADA, REGISTRO_FALLIDO=TECNICO/1 año",
        "fuente": "RF-80 v2.0 Descripcion, Fase 3, CA-3; TC-M05-091",
    },
    "test_b02_tipo_no_catalogado_nic41": {
        "paso": "B02 Tipo no catalogado -> NIC41 / 5 años en TEST y en clasificar_retencion",
        "esperado": ">= 1 evento real no catalogado en TEST clasificado NIC41/5 años y unitario clasificar_retencion=('NIC41', '5 años')",
        "fuente": "RF-80 v2.0 Descripcion, Fase 3; TC-M05-091",
    },
    "test_t98_cierre_sandbox_principal": {
        "paso": "T98 Cierre de la corrida sandbox principal",
        "esperado": "DELETE /test-control/runs/{run_id} -> HTTP 200 Rollback exitoso",
        "fuente": "Regla sandbox / Testing Harness",
    },
    "test_t99_inocuidad_post_rollback": {
        "paso": "T99 Inocuidad en corrida sandbox independiente de solo lectura",
        "esperado": "total y ultimo_id iguales a T00; GET a activos, acumulados/historial de suministro y provision creados -> HTTP 404",
        "fuente": "Regla sandbox / Inocuidad",
    },
}


def _cargar_trazas_por_test(trazas_path: Path) -> dict[str, list[dict[str, Any]]]:
    por_test: dict[str, list[dict[str, Any]]] = {}
    if not trazas_path.exists():
        return por_test
    for linea in trazas_path.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s:
            continue
        try:
            item = json.loads(s)
        except Exception:
            continue
        nombre = item.get("test") or "init"
        por_test.setdefault(nombre, []).append(item)
    return por_test


def _resumen_http_y_eventos(trazas: list[dict[str, Any]], sysout: str) -> str:
    llamadas: list[str] = []
    eventos_vistos: dict[int, dict[str, Any]] = {}

    for t in trazas:
        metodo = t.get("metodo")
        ruta = t.get("ruta")
        sc = t.get("status_code")
        ec = t.get("error_code")
        xid = t.get("x_request_id")
        rb = t.get("response_body")

        es_poll_aud = (
            metodo == "GET"
            and ruta == "/suministros/auditoria"
            and isinstance(rb, dict)
            and "items" in rb
        )
        if not es_poll_aud or len(trazas) <= 3:
            et = f"{metodo} {ruta} -> HTTP {sc}"
            if ec:
                et += f" ({ec})"
            if xid:
                et += f" [X-Request-Id={xid}]"
            llamadas.append(et)

        if isinstance(rb, dict):
            if "id_auditoria_suministro" in rb and "tipo_operacion" in rb:
                ev_id = int(rb["id_auditoria_suministro"])
                eventos_vistos[ev_id] = rb
            elif isinstance(rb.get("items"), list):
                for it in rb["items"]:
                    if isinstance(it, dict) and "id_auditoria_suministro" in it and "tipo_operacion" in it:
                        ev_id = int(it["id_auditoria_suministro"])
                        eventos_vistos[ev_id] = it

    partes: list[str] = []
    if llamadas:
        muestra = llamadas[:5]
        suf = f" (+{len(llamadas) - 5} requests)" if len(llamadas) > 5 else ""
        partes.append("HTTP: " + "; ".join(muestra) + suf)

    if eventos_vistos:
        evs_res = []
        for ev_id in sorted(eventos_vistos.keys())[-4:]:
            ev = eventos_vistos[ev_id]
            evs_res.append(
                f"ev#{ev_id}:{ev.get('tipo_operacion')}/{ev.get('resultado')}/"
                f"{ev.get('clasificacion_registro')}/{ev.get('retencion_aplicable')}/"
                f"inc={ev.get('registro_incompleto')}"
            )
        partes.append("Eventos vistos: " + ", ".join(evs_res))

    for linea in (sysout or "").splitlines():
        if linea.startswith(("T00_BASELINE", "B02_OK", "T99_INOCUIDAD")):
            partes.append(linea.strip()[:260])

    return " | ".join(partes) if partes else "Sin trazas HTTP registradas"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G37 (RF-80 v2.0)")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (0 = corrida inicial)")
    args = parser.parse_args()

    staging = Path(args.staging)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    candidatos_xml = [
        staging / f"resultado_TC-M05-G37{sufijo}.xml",
        staging / f"junit_TC-M05-G37{sufijo}.xml",
        staging / "resultado_TC-M05-G37.xml",
    ]
    xml_path = next((p for p in candidatos_xml if p.exists()), None)
    if xml_path is None:
        print(f"ERROR: No existe archivo XML en {staging}")
        return

    trazas_por_test = _cargar_trazas_por_test(staging / "trazas_http.jsonl")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    checkpoints: list[dict[str, Any]] = []
    fallas_detalle: list[dict[str, str]] = []
    testcase_elements = root.findall(".//testcase")
    total = len(testcase_elements)
    ok = 0
    falla = 0

    for tc in testcase_elements:
        nombre = tc.attrib.get("name", "")
        meta = TEST_METADATA.get(nombre, {
            "paso": nombre,
            "esperado": "Comportamiento segun especificacion RF-80 v2.0",
            "fuente": "RF-80 v2.0",
        })
        sysout_el = tc.find("system-out")
        sysout = (sysout_el.text or "").strip() if sysout_el is not None else ""
        trazas_tc = trazas_por_test.get(nombre, [])
        resumen_trazas = _resumen_http_y_eventos(trazas_tc, sysout)

        failure = tc.find("failure")
        error = tc.find("error")
        if failure is not None or error is not None:
            estado = "FALLA"
            falla += 1
            nodo = failure if failure is not None else error
            msg = (nodo.attrib.get("message") or (nodo.text or "Fallo de aserto")).strip()
            primera_linea = msg.splitlines()[0] if msg else "Fallo de aserto"
            obtenido = f"{primera_linea} | {resumen_trazas}"
            fallas_detalle.append({
                "test": nombre,
                "paso": meta["paso"],
                "fuente": meta["fuente"],
                "clasificacion": "PENDIENTE_DIAGNOSTICO",
                "detalle_junit": msg[:1200],
                "resumen_trazas": resumen_trazas,
            })
        else:
            estado = "OK"
            ok += 1
            obtenido = resumen_trazas

        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": obtenido,
            "estado": estado,
        })

    veredicto = "Aprobado" if falla == 0 and total > 0 else "Rechazado"
    resultado_json = {
        "tc": "TC-M05-G37",
        "summary": {
            "total": total,
            "ok": ok,
            "falla": falla,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
    }

    json_path = staging / f"resultado_TC-M05-G37{sufijo}.json"
    json_path.write_text(json.dumps(resultado_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generado: {json_path.name}")

    html_path = staging / f"resultado_TC-M05-G37{sufijo}.html"
    if html_path.exists():
        try:
            html_content = html_path.read_text(encoding="utf-8")
            blob_script = (
                '<script id="data-jsonblob" type="application/json">'
                f"{json.dumps(resultado_json, ensure_ascii=False)}"
                "</script>"
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
        "# Resultado de Prueba: TC-M05-G37",
        "## Persistencia y Clasificacion de Eventos (RF-80 v2.0 / RFC-025)",
        "",
        "- **ID Caso:** TC-M05-G37 (TC-M05-090 / TC-M05-091)",
        f"- **Veredicto:** {veredicto} ({ok}/{total} OK, {falla} Fallas)",
        f"- **Fecha:** {ahora_str} (America/Bogota)",
        f"- **Duracion:** {args.duracion_s:.2f} s",
        "",
        "### Resumen de Checkpoints",
        "| # | Paso | Esperado | Obtenido | Estado |",
        "|---|------|----------|----------|--------|",
    ]
    for idx, cp in enumerate(checkpoints, 1):
        paso_c = cp["paso"].replace("|", "/")
        esp_c = cp["esperado"].replace("|", "/")
        obt_c = cp["obtenido"].replace("|", "/")
        md_lines.append(f"| {idx} | {paso_c} | {esp_c} | {obt_c} | {cp['estado']} |")

    md_lines.extend(["", "### Diagnostico de Fallas"])
    if fallas_detalle:
        for fd in fallas_detalle:
            md_lines.append(f"- **{fd['paso']}** (`{fd['test']}`): **{fd['clasificacion']}**")
            md_lines.append(f"  - Fuente: {fd['fuente']}")
            md_lines.append(f"  - Trazas: {fd['resumen_trazas']}")
            md_lines.append(f"  - JUnit: `{fd['detalle_junit'].splitlines()[0] if fd['detalle_junit'] else ''}`")
    else:
        md_lines.append("No se presentaron fallas en la corrida.")

    md_path = staging / f"TC-M05-G37{sufijo}_resultado.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Generado: {md_path.name}")

    txt_lines = [
        "=" * 80,
        f"INFORME DE EJECUCION: TC-M05-G37 (Reintento={args.reintento})",
        "RF-80 v2.0 (RFC-025) Auditoria Local M05",
        "=" * 80,
        f"Fecha/Hora: {ahora_str} (America/Bogota)",
        f"Total tests: {total} | Aprobados: {ok} | Fallidos: {falla}",
        f"Veredicto Final: {veredicto}",
        f"Duracion: {args.duracion_s:.2f} s",
        "",
        "1. TABLA DE CHECKPOINTS (OBTENIDO REAL DESDE JUNIT Y TRAZAS)",
        "-" * 80,
    ]
    for idx, cp in enumerate(checkpoints, 1):
        txt_lines.extend([
            f"[{idx:02d}] {cp['paso']}",
            f"     Esperado: {cp['esperado']}",
            f"     Obtenido: {cp['obtenido']}",
            f"     Estado:   {cp['estado']}",
            "",
        ])

    txt_lines.extend(["2. FALLOS REGISTRADOS", "-" * 80])
    if fallas_detalle:
        for fd in fallas_detalle:
            txt_lines.extend([
                f"- Test: {fd['test']} | Estado diagnostico: {fd['clasificacion']}",
                f"  Fuente: {fd['fuente']}",
                f"  Trazas: {fd['resumen_trazas']}",
                f"  Mensaje: {fd['detalle_junit']}",
                "",
            ])
    else:
        txt_lines.append("Sin fallos en la corrida.")

    txt_path = staging / f"INFORME_FASE234_TC-M05-G37{sufijo}.txt"
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()
