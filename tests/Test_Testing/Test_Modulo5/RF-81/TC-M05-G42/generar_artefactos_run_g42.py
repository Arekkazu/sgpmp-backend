# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G42 (JSON, repro, MD, TXT)  |
# | 12/11/2026 | Juan Sebastian Gutierrez | Reintento 1: --reintento N, valores reales, observaciones A02a/A02b/OBS-0 |
"""Generador de artefactos de corrida para TC-M05-G42.
Lee JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G42[_reintentoN].json
- repro
- TC-M05-G42_resultado.md
- Inyecta data-jsonblob en resultado_TC-M05-G42[_reintentoN].html
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ZONA_USUARIO = timezone(timedelta(hours=-5))

MOTIVO_RETIRO_A02 = (
    "Retirado: RF-81 Restriccion 7 y E5 no definen estas validaciones "
    "(vienen de CU04 FA-02, que no esta en la especificacion). Pendiente de decision de Analisis."
)

TEST_METADATA = {
    "test_00_setup_linea_base_y_activos": {
        "paso": "T00 Linea base (run aparte) y setup de activos",
        "esperado": "Run T00 consulta GET /suministros/auditoria (HTTP 200) y cierra con DELETE 200 'Rollback exitoso'; activos A y B con fase abierta y 3 suministros en A (HTTP 201)",
        "fuente": "Protocolo Sandbox / Setup de linea base",
    },
    "test_a01_combinaciones_invalidas_filtros": {
        "paso": "A01 Combinaciones invalidas de filtros (100 / 035)",
        "esperado": "HTTP 422 para fecha_fin < fecha_inicio, costo_max < costo_min y ciclo ajeno (real e inexistente) con mensajes descriptivos distintos y sin items ni resumen",
        "fuente": "RF-81 Restr. 7 / E5 / CA-10 / TC-M05-100 (035)",
    },
    "test_b01a_paginacion_activo_con_mas_de_205_registros": {
        "paso": "B01a Paginacion y recorrido completo param=200 (101 / 036)",
        "esperado": "HTTP 200, 200 registros en p1, total_paginas=3, total_registros_filtrados=500, pagina_actual=1, recorrido completo 500 sin duplicados, orden fecha_aplicacion DESC y suma de costos igual a monto_total_filtrado",
        "fuente": "RF-81 Entradas (registros_por_pagina) y RNF-04",
    },
    "test_b01b_tope_maximo_registros_por_pagina": {
        "paso": "B01b Tope maximo param=201 en pagina 1 (101 / 036)",
        "esperado": "HTTP 200; len(registros)=200; total_registros_filtrados=500; total_paginas=3; pagina_actual=1",
        "fuente": "RF-81 Entradas ('registros_por_pagina | max: 200 | El sistema aplica el limite maximo si se excede'); RNF-04",
    },
    "test_b01c_paginacion_completa_con_exceso_201": {
        "paso": "B01c Paginacion completa paginas 1, 2 y 3 con param=201 (101 / 036)",
        "esperado": "HTTP 200 en paginas 1, 2 y 3; conteos exactos [200, 200, 100]; 500 ids distintos sin duplicados; orden fecha_aplicacion DESC intra e inter pagina",
        "fuente": "RF-81 Entradas (el limite se aplica como tamano de pagina) y Fase 3 (orden por fecha_aplicacion DESC, paginacion maxima de 200)",
    },
    "test_b01d_tope_maximo_extremo_1000": {
        "paso": "B01d Tope maximo extremo param=1000 en pagina 1 (101 / 036)",
        "esperado": "HTTP 200; len(registros)=200; total_paginas=3",
        "fuente": "RF-81 Entradas ('si se excede')",
    },
    "test_98_cierre_sandbox": {
        "paso": "T98 Cierre estricto de corrida sandbox principal",
        "esperado": "DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso'",
        "fuente": "Protocolo Sandbox",
    },
    "test_99_inocuidad_final": {
        "paso": "T99 Inocuidad final en run de sandbox aparte",
        "esperado": "GET /suministros/auditoria igual a T00 (total y ultimo id); GET de activos A, B e historial de A responden HTTP 404; DELETE cierra con HTTP 200 'Rollback exitoso'",
        "fuente": "Protocolo Sandbox / Verificacion de Inocuidad",
    },
}


def calcular_sha256(p: Path) -> str:
    if not p.exists():
        return "NO_EXISTE"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _cargar_trazas(trazas_path: Path) -> list[dict[str, Any]]:
    if not trazas_path.exists():
        return []
    filas: list[dict[str, Any]] = []
    for line in trazas_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            filas.append(json.loads(line))
        except Exception:
            pass
    return filas


def _por_paso(trazas: list[dict[str, Any]], paso: str) -> dict[str, Any] | None:
    for t in trazas:
        if t.get("paso") == paso:
            return t
    return None


def _todos_por_test(trazas: list[dict[str, Any]], test_name: str) -> list[dict[str, Any]]:
    return [t for t in trazas if t.get("test") == test_name]


def _extraer_metricas_historial(traza: dict[str, Any] | None) -> dict[str, Any]:
    if not traza:
        return {}
    body = traza.get("response_body")
    if not isinstance(body, dict):
        return {
            "http": traza.get("status_code"),
            "error_code": traza.get("error_code"),
            "x_request_id": traza.get("x_request_id", ""),
        }
    items = body.get("items")
    resumen = body.get("resumen") if isinstance(body.get("resumen"), dict) else {}
    fields = body.get("fields") if isinstance(body.get("fields"), list) else []
    return {
        "http": traza.get("status_code"),
        "error_code": traza.get("error_code"),
        "fields": fields,
        "len_registros": len(items) if isinstance(items, list) else None,
        "ids": [it.get("id_registro_suministro") for it in items] if isinstance(items, list) else [],
        "total_registros_filtrados": resumen.get("total_registros_filtrados"),
        "total_paginas": resumen.get("total_paginas"),
        "pagina_actual": resumen.get("pagina_actual"),
        "x_request_id": traza.get("x_request_id", ""),
    }


def _formatear_obtenido(
    test_key: str,
    estado_chk: str,
    xml_detalle: str,
    trazas: list[dict[str, Any]],
) -> str:
    trazas_test = _todos_por_test(trazas, test_key)
    req_ids = [t.get("x_request_id") for t in trazas_test if t.get("x_request_id")]

    if test_key == "test_00_setup_linea_base_y_activos":
        t_aud = _por_paso(trazas, "T00_auditoria_inicial")
        t_del = None
        for t in trazas:
            if t.get("paso") == "teardown" and "tc-m05-g42-t00-" in str(t.get("ruta", "")):
                t_del = t
                break
        t_a = _por_paso(trazas, "T00_crear_activo_a")
        t_b = _por_paso(trazas, "T00_crear_activo_b")
        t_h = _por_paso(trazas, "T00_historial_a")
        m_h = _extraer_metricas_historial(t_h)
        aud_body = (t_aud or {}).get("response_body") or {}
        partes = [
            f"T00 auditoria HTTP={(t_aud or {}).get('status_code')} total={aud_body.get('total') if isinstance(aud_body, dict) else None}",
            f"DELETE T00 HTTP={(t_del or {}).get('status_code')}",
            f"activo_a HTTP={(t_a or {}).get('status_code')}",
            f"activo_b HTTP={(t_b or {}).get('status_code')}",
            f"historial_a HTTP={m_h.get('http')} len={m_h.get('len_registros')}",
            f"X-Request-Id=[{', '.join(req_ids)}]",
        ]
        resumen = "; ".join(partes)
    elif test_key == "test_a01_combinaciones_invalidas_filtros":
        t1 = _por_paso(trazas, "A01_fecha_fin_menor_inicio")
        t2 = _por_paso(trazas, "A01_costo_max_menor_min")
        t3 = _por_paso(trazas, "A01_ciclo_real_ajeno")
        t4 = _por_paso(trazas, "A01_ciclo_inexistente")
        partes = [
            f"fecha_fin<inicio: HTTP={(t1 or {}).get('status_code')} ({(t1 or {}).get('error_code')}) xreq={(t1 or {}).get('x_request_id', '')}",
            f"costo_max<min: HTTP={(t2 or {}).get('status_code')} ({(t2 or {}).get('error_code')}) xreq={(t2 or {}).get('x_request_id', '')}",
            f"ciclo_ajeno: HTTP={(t3 or {}).get('status_code')} ({(t3 or {}).get('error_code')}) xreq={(t3 or {}).get('x_request_id', '')}",
            f"ciclo_inexistente: HTTP={(t4 or {}).get('status_code')} ({(t4 or {}).get('error_code')}) xreq={(t4 or {}).get('x_request_id', '')}",
        ]
        resumen = "; ".join(partes)
    elif test_key == "test_b01a_paginacion_activo_con_mas_de_205_registros":
        p1 = _extraer_metricas_historial(_por_paso(trazas, "B01a_tamano_200_p1"))
        p2 = _extraer_metricas_historial(_por_paso(trazas, "B01a_pagina_2"))
        p3 = _extraer_metricas_historial(_por_paso(trazas, "B01a_pagina_3"))
        conteos = [m.get("len_registros") for m in (p1, p2, p3) if m]
        ids_all = p1.get("ids", []) + p2.get("ids", []) + p3.get("ids", [])
        distintos = len(set(ids_all))
        duplicados = len(ids_all) - distintos
        resumen = (
            f"HTTP={p1.get('http')}; len(registros)={p1.get('len_registros')}; "
            f"total_paginas={p1.get('total_paginas')}; total_registros_filtrados={p1.get('total_registros_filtrados')}; "
            f"pagina_actual={p1.get('pagina_actual')}; conteos_paginas={conteos}; "
            f"ids_distintos={distintos}; duplicados={duplicados}; "
            f"X-Request-Id=[{p1.get('x_request_id', '')}, {p2.get('x_request_id', '')}, {p3.get('x_request_id', '')}]"
        )
    elif test_key == "test_b01b_tope_maximo_registros_por_pagina":
        m = _extraer_metricas_historial(_por_paso(trazas, "B01b_tamano_201_p1"))
        resumen = (
            f"HTTP={m.get('http')}; len(registros)={m.get('len_registros')}; "
            f"total_registros_filtrados={m.get('total_registros_filtrados')}; "
            f"total_paginas={m.get('total_paginas')}; pagina_actual={m.get('pagina_actual')}; "
            f"X-Request-Id={m.get('x_request_id', '')}"
        )
    elif test_key == "test_b01c_paginacion_completa_con_exceso_201":
        m1 = _extraer_metricas_historial(_por_paso(trazas, "B01c_tamano_201_p1"))
        m2 = _extraer_metricas_historial(_por_paso(trazas, "B01c_tamano_201_p2"))
        m3 = _extraer_metricas_historial(_por_paso(trazas, "B01c_tamano_201_p3"))
        https = [m.get("http") for m in (m1, m2, m3)]
        conteos = [m.get("len_registros") for m in (m1, m2, m3)]
        ids_all = m1.get("ids", []) + m2.get("ids", []) + m3.get("ids", [])
        distintos = len(set(ids_all))
        duplicados = len(ids_all) - distintos
        resumen = (
            f"HTTP={https}; conteos={conteos}; ids_distintos={distintos}; duplicados={duplicados}; "
            f"X-Request-Id=[{m1.get('x_request_id', '')}, {m2.get('x_request_id', '')}, {m3.get('x_request_id', '')}]"
        )
    elif test_key == "test_b01d_tope_maximo_extremo_1000":
        m = _extraer_metricas_historial(_por_paso(trazas, "B01d_tamano_1000_p1"))
        resumen = (
            f"HTTP={m.get('http')}; len(registros)={m.get('len_registros')}; "
            f"total_paginas={m.get('total_paginas')}; total_registros_filtrados={m.get('total_registros_filtrados')}; "
            f"pagina_actual={m.get('pagina_actual')}; X-Request-Id={m.get('x_request_id', '')}"
        )
    elif test_key == "test_98_cierre_sandbox":
        t_del = _por_paso(trazas, "teardown")
        for t in trazas_test:
            if t.get("paso") == "teardown":
                t_del = t
        body = (t_del or {}).get("response_body")
        resumen = f"HTTP={(t_del or {}).get('status_code')}; body={body}; X-Request-Id={(t_del or {}).get('x_request_id', '')}"
    elif test_key == "test_99_inocuidad_final":
        t_aud = _por_paso(trazas, "T99_auditoria_final")
        t_a = _por_paso(trazas, "T99_get_activo_a")
        t_b = _por_paso(trazas, "T99_get_activo_b")
        t_h = _por_paso(trazas, "T99_historial_activo_a")
        t_del = None
        for t in trazas_test:
            if t.get("paso") == "teardown":
                t_del = t
        aud_body = (t_aud or {}).get("response_body") or {}
        resumen = (
            f"T99 auditoria HTTP={(t_aud or {}).get('status_code')} total={aud_body.get('total') if isinstance(aud_body, dict) else None}; "
            f"GET activo_a HTTP={(t_a or {}).get('status_code')}; GET activo_b HTTP={(t_b or {}).get('status_code')}; "
            f"GET historial_a HTTP={(t_h or {}).get('status_code')}; DELETE T99 HTTP={(t_del or {}).get('status_code')}; "
            f"X-Request-Id=[{', '.join(req_ids)}]"
        )
    else:
        resumen = xml_detalle

    if estado_chk != "OK":
        return f"PENDIENTE_DIAGNOSTICO | {resumen} | Detalle: {xml_detalle}"
    return resumen


def _construir_observaciones(trazas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observaciones = []

    t_a02a = _por_paso(trazas, "OBS_A02a_fecha_fin_futura")
    if t_a02a:
        m = _extraer_metricas_historial(t_a02a)
        observaciones.append({
            "id": "A02a",
            "estado": "RETIRADO",
            "motivo": MOTIVO_RETIRO_A02,
            "http": m.get("http"),
            "error_code": m.get("error_code"),
            "registros": m.get("len_registros"),
            "x_request_id": m.get("x_request_id", ""),
        })

    t_a02b = _por_paso(trazas, "OBS_A02b_fecha_inicio_anterior_ciclo")
    if t_a02b:
        m = _extraer_metricas_historial(t_a02b)
        observaciones.append({
            "id": "A02b",
            "estado": "RETIRADO",
            "motivo": MOTIVO_RETIRO_A02,
            "http": m.get("http"),
            "error_code": m.get("error_code"),
            "registros": m.get("len_registros"),
            "x_request_id": m.get("x_request_id", ""),
        })

    t_obs0 = _por_paso(trazas, "B01a_obs_tamano_cero")
    if t_obs0:
        m = _extraer_metricas_historial(t_obs0)
        campos = [f.get("field") for f in m.get("fields", []) if isinstance(f, dict)]
        observaciones.append({
            "id": "OBS-0",
            "estado": "OBSERVACION",
            "descripcion": "registros_por_pagina=0, pagina=1 (RF-81 no define un error_code especifico)",
            "http": m.get("http"),
            "error_code": m.get("error_code"),
            "campo": campos[0] if campos else None,
            "x_request_id": m.get("x_request_id", ""),
        })

    t_p0 = _por_paso(trazas, "B01a_obs_pagina_cero")
    if t_p0:
        m = _extraer_metricas_historial(t_p0)
        campos = [f.get("field") for f in m.get("fields", []) if isinstance(f, dict)]
        observaciones.append({
            "id": "OBS-PAG0",
            "estado": "OBSERVACION",
            "descripcion": "pagina=0, registros_por_pagina=50",
            "http": m.get("http"),
            "error_code": m.get("error_code"),
            "campo": campos[0] if campos else None,
            "x_request_id": m.get("x_request_id", ""),
        })

    return observaciones


def procesar_corrida(staging: Path, reintento: int, sha_hashes: dict[str, str]):
    sufijo = f"_reintento{reintento}" if reintento > 0 else ""
    junit_path = staging / f"resultado_TC-M05-G42{sufijo}.xml"
    trazas_path = staging / "trazas_http.jsonl"
    repro_path = staging / "repro"
    json_path = staging / f"resultado_TC-M05-G42{sufijo}.json"
    html_path = staging / f"resultado_TC-M05-G42{sufijo}.html"
    narrativo_path = staging / "TC-M05-G42_resultado.md"

    # Repro
    repro_cmd = (
        f"powershell -ExecutionPolicy Bypass -File .\\ejecutar_tc_m05_g42.ps1 -Reintento {reintento}"
        if reintento > 0
        else "powershell -ExecutionPolicy Bypass -File .\\ejecutar_tc_m05_g42.ps1"
    )
    repro_path.write_text(repro_cmd + "\n", encoding="utf-8")

    # Parsear JUnit XML
    tree = ET.parse(junit_path)
    root = tree.getroot()

    casos_xml = {}
    for tc in root.iter("testcase"):
        nombre = tc.attrib.get("name", "")
        nombre_base = nombre.split("[")[0]
        fallo = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")
        if fallo is not None:
            estado = "FALLA"
            msg = fallo.attrib.get("message") or (fallo.text or "").strip().splitlines()[0]
        elif error is not None:
            estado = "FALLA"
            msg = error.attrib.get("message") or (error.text or "").strip().splitlines()[0]
        elif skipped is not None:
            estado = "OMITIDO"
            msg = skipped.attrib.get("message", "Test omitido")
        else:
            estado = "OK"
            msg = "Completado sin excepciones."
        casos_xml[nombre_base] = {"estado": estado, "detalle": msg}

    trazas = _cargar_trazas(trazas_path)
    base_url_env = os.environ.get("TEST_BASE_URL", "")

    checkpoints = []
    total_ok = 0
    total_falla = 0

    for test_key, meta in TEST_METADATA.items():
        xml_info = casos_xml.get(test_key, {"estado": "FALLA", "detalle": "No ejecutado o no encontrado en XML"})
        estado_chk = "OK" if xml_info["estado"] == "OK" else "FALLA"
        if estado_chk == "OK":
            total_ok += 1
        else:
            total_falla += 1

        obtenido = _formatear_obtenido(test_key, estado_chk, xml_info["detalle"], trazas)
        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": obtenido,
            "estado": estado_chk,
        })

    observaciones = _construir_observaciones(trazas)
    veredicto_global = "Aprobado" if total_falla == 0 and total_ok > 0 else "Rechazado"

    res_json_data = {
        "tc": "TC-M05-G42",
        "summary": {
            "total": len(checkpoints),
            "ok": total_ok,
            "falla": total_falla,
            "veredicto": veredicto_global,
        },
        "checkpoints": checkpoints,
        "observaciones": observaciones,
    }
    json_path.write_text(json.dumps(res_json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Inyectar data-jsonblob en el reporte HTML
    if html_path.exists():
        html_txt = html_path.read_text(encoding="utf-8")
        blob_script = (
            f'<script id="data-jsonblob" type="application/json">'
            f'{json.dumps(res_json_data, ensure_ascii=False)}</script>'
        )
        if 'id="data-jsonblob"' not in html_txt:
            if "</body>" in html_txt:
                html_txt = html_txt.replace("</body>", f"{blob_script}</body>")
            else:
                html_txt += blob_script
            html_path.write_text(html_txt, encoding="utf-8")

    # Generar TC-M05-G42_resultado.md narrativo en staging
    md_lines = [
        f"# Reporte de Prueba: TC-M05-G42 (RF-81) - Reintento {reintento}",
        "",
        f"- **Ambiente:** `{base_url_env}`",
        f"- **Veredicto Global:** **{veredicto_global.upper()}** ({total_ok}/{len(checkpoints)} OK, {total_falla} Fallas)",
        f"- **Fecha:** {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)",
        "",
        "## Checkpoints",
        "| # | Paso | Esperado | Obtenido | Estado |",
        "|---|------|----------|----------|--------|",
    ]
    for idx, chk in enumerate(checkpoints, 1):
        md_lines.append(f"| {idx} | {chk['paso']} | {chk['esperado']} | {chk['obtenido']} | **{chk['estado']}** |")
    md_lines.append("")
    md_lines.append("## Observaciones")
    for obs in observaciones:
        md_lines.append(f"- **{obs.get('id')}** ({obs.get('estado')}): {json.dumps(obs, ensure_ascii=False)}")
    narrativo_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"Artefactos generados exitosamente en {staging} (reintento={reintento})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", required=True)
    parser.add_argument("--reintento", type=int, default=0)
    parser.add_argument("--sha-g42-script", default="N/A")
    parser.add_argument("--sha-g42-runner", default="N/A")
    parser.add_argument("--sha-g38-script", default="N/A")
    parser.add_argument("--sha-g37-script", default="N/A")
    parser.add_argument("--sha-g25-script", default="N/A")
    parser.add_argument("--sha-g24-script", default="N/A")
    parser.add_argument("--sha-g21-script", default="N/A")
    parser.add_argument("--sha-g19-script", default="N/A")
    parser.add_argument("--sha-g17-script", default="N/A")
    parser.add_argument("--sha-g16-script", default="N/A")
    parser.add_argument("--sha-g15-script", default="N/A")
    parser.add_argument("--sha-g14-script", default="N/A")
    args = parser.parse_args()

    staging = Path(args.staging)
    sha_hashes = {
        "g42_script": args.sha_g42_script,
        "g42_runner": args.sha_g42_runner,
    }
    procesar_corrida(staging, args.reintento, sha_hashes)


if __name__ == "__main__":
    main()
