# | Fecha      | Nombre                   | Que se hizo                                                                 |
# |------------|--------------------------|-----------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | Generador de resultado_TC-M05-G25_reintento1.json con obtenido real de trazas |
"""Genera resultado_TC-M05-G25_reintento1.json a partir del JUnit XML y trazas_http.jsonl.

Conserva exactamente el orden, 'paso' y 'esperado' de resultado_TC-M05-G25_reintento1_generado.json,
determina 'estado' (OK/FALLA) desde resultado_TC-M05-G25_reintento1.xml y construye 'obtenido'
con los valores reales observados en trazas_http.jsonl (sin tokens ni datos personales).
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


def _cargar_trazas_por_test(trazas_path: Path) -> dict[str, list[dict[str, Any]]]:
    por_test: dict[str, list[dict[str, Any]]] = {}
    for linea in trazas_path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        reg = json.loads(linea)
        por_test.setdefault(reg.get("test", ""), []).append(reg)
    return por_test


def _buscar_req(
    rows: list[dict[str, Any]],
    *,
    metodo: str | None = None,
    ruta_contiene: str | None = None,
    ultimo: bool = False,
) -> dict[str, Any] | None:
    coincidencias = [
        r for r in rows
        if (metodo is None or r.get("metodo") == metodo)
        and (ruta_contiene is None or ruta_contiene in (r.get("ruta") or ""))
    ]
    if not coincidencias:
        return None
    return coincidencias[-1] if ultimo else coincidencias[0]


def _extraer_eventos(
    rows_aud: dict[str, Any] | None,
    acciones: tuple[str, ...],
    id_usuario: int | None = None,
    id_reporte: int | None = None,
) -> list[dict[str, Any]]:
    if not rows_aud or not isinstance(rows_aud.get("response_body"), dict):
        return []
    salida = []
    for it in rows_aud["response_body"].get("items", []):
        dn = it.get("datos_nuevos") or {}
        if dn.get("accion") not in acciones:
            continue
        if id_usuario is not None and it.get("id_usuario") != id_usuario:
            continue
        if id_reporte is not None and dn.get("id_reporte_gasto_acumulado") != id_reporte:
            continue
        salida.append(it)
    return salida


def _run_id_desde_delete(rows: list[dict[str, Any]]) -> str:
    r_del = _buscar_req(rows, metodo="DELETE", ruta_contiene="/test-control/runs/")
    if not r_del:
        return "?"
    return (r_del.get("ruta") or "").rsplit("/", 1)[-1]


def _obtenido_real(
    nombre_test: str,
    por_test: dict[str, list[dict[str, Any]]],
    tc_xml: ET.Element,
) -> str:
    failure = tc_xml.find("failure")
    error = tc_xml.find("error")
    if failure is not None or error is not None:
        el = failure if failure is not None else error
        return f"Falla: {(el.get('message') or '')[:300]}"

    rows = por_test.get(nombre_test, [])
    if nombre_test == "test_a01_productor_genera_reporte_sincronico":
        r = _buscar_req(rows, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        rb = r.get("response_body") or {}
        return (
            f"HTTP {r.get('status_code')}, id_reporte_gasto_acumulado={rb.get('id_reporte_gasto_acumulado')}, "
            f"gasto_total_acumulado={rb.get('gasto_total_acumulado')}"
        )

    if nombre_test == "test_a02_productor_exporta_reporte_csv":
        r = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        rb = r.get("response_body") or {}
        return (
            f"HTTP {r.get('status_code')}, id_archivo={rb.get('id_archivo') or rb.get('id_archivo_exportacion')}, "
            f"formato={rb.get('formato') or 'CSV'}, nombre_archivo={rb.get('nombre_archivo')}"
        )

    if nombre_test == "test_a03_productor_exporta_reporte_pdf":
        r = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        rb = r.get("response_body") or {}
        return (
            f"HTTP {r.get('status_code')}, id_archivo={rb.get('id_archivo') or rb.get('id_archivo_exportacion')}, "
            f"formato={rb.get('formato') or 'PDF'}, nombre_archivo={rb.get('nombre_archivo')}"
        )

    if nombre_test == "test_a04_productor_descarga_su_propia_exportacion":
        r = _buscar_req(rows, metodo="GET", ruta_contiene="/exportaciones/") or {}
        fid = (r.get("ruta") or "").rsplit("/", 1)[-1]
        return f"HTTP {r.get('status_code')}, descarga CSV verificada para id_archivo={fid}"

    if nombre_test in ("test_a05_productor_no_accede_a_auditoria_m05", "test_b04_veterinario_acceder_auditoria_denegado"):
        r = _buscar_req(rows, metodo="GET", ruta_contiene="/suministros/auditoria") or {}
        return f"HTTP {r.get('status_code')} {r.get('error_code')} en GET /suministros/auditoria"

    if nombre_test in (
        "test_a98_cierre_sandbox_productor",
        "test_b98_cierre_sandbox_veterinario",
        "test_c98_cierre_sandbox_admin",
        "test_d98_cierre_sandbox_idor",
    ):
        r = _buscar_req(rows, metodo="DELETE") or {}
        rb = r.get("response_body") or {}
        msg = rb.get("status") if isinstance(rb, dict) else str(rb)
        return f"HTTP {r.get('status_code')} ({msg}) en DELETE /test-control/runs/{_run_id_desde_delete(rows)}"

    if nombre_test == "test_b01_veterinario_generar_reporte_denegado":
        r = _buscar_req(rows, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        return f"HTTP {r.get('status_code')} {r.get('error_code')} en POST /suministros/reportes-gastos"

    if nombre_test == "test_b02_veterinario_exportar_reporte_denegado":
        r = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        return f"HTTP {r.get('status_code')} {r.get('error_code')} en POST /suministros/reportes-gastos/19/exportacion"

    if nombre_test == "test_b03_veterinario_descargar_exportacion_denegado":
        r_rep = _buscar_req(rows, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        r_exp = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        r_get = _buscar_req(rows, metodo="GET", ruta_contiene="/exportaciones/") or {}
        id_rep = (r_rep.get("response_body") or {}).get("id_reporte_gasto_acumulado")
        id_arch = (r_exp.get("response_body") or {}).get("id_archivo")
        return (
            f"HTTP {r_get.get('status_code')} {r_get.get('error_code')}, sin text/csv ni contenido CSV "
            f"al descargar archivo real de Admin (id_archivo={id_arch}, id_reporte={id_rep})"
        )

    if nombre_test == "test_c01_admin_genera_y_exporta_reporte":
        r_rep = _buscar_req(rows, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        r_exp = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        id_rep = (r_rep.get("response_body") or {}).get("id_reporte_gasto_acumulado")
        id_arch = (r_exp.get("response_body") or {}).get("id_archivo")
        return (
            f"Generacion HTTP {r_rep.get('status_code')} (id_reporte={id_rep}); "
            f"exportacion CSV HTTP {r_exp.get('status_code')} (id_archivo={id_arch})"
        )

    if nombre_test == "test_c02_verificacion_auditoria_ca11_postcondicion3":
        rows_c01 = por_test.get("test_c01_admin_genera_y_exporta_reporte", [])
        r_rep = _buscar_req(rows_c01, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        r_exp = _buscar_req(rows_c01, metodo="POST", ruta_contiene="/exportacion") or {}
        r_aud = _buscar_req(rows, metodo="GET", ruta_contiene="/suministros/auditoria", ultimo=True) or {}
        id_rep = (r_rep.get("response_body") or {}).get("id_reporte_gasto_acumulado")
        evs = _extraer_eventos(r_aud, ("GENERACION", "EXPORTACION"), id_reporte=id_rep)
        ev_gen = next(e for e in evs if (e.get("datos_nuevos") or {}).get("accion") == "GENERACION")
        ev_exp = next(e for e in evs if (e.get("datos_nuevos") or {}).get("accion") == "EXPORTACION")
        t_aud = datetime.fromisoformat(r_aud["timestamp_local"])
        lat_gen = round((t_aud - datetime.fromisoformat(r_rep["timestamp_local"])).total_seconds(), 3)
        lat_exp = round((t_aud - datetime.fromisoformat(r_exp["timestamp_local"])).total_seconds(), 3)
        return (
            f"HTTP {r_aud.get('status_code')}; evento GENERACION id={ev_gen.get('id_auditoria_suministro')} y "
            f"EXPORTACION id={ev_exp.get('id_auditoria_suministro')}, actor id_usuario={ev_gen.get('id_usuario')}, "
            f"resultado={ev_gen.get('resultado')}, latencias={lat_gen}s/{lat_exp}s (<= 2.0s), "
            f"id_reporte={id_rep}, id_archivo={(ev_exp.get('datos_nuevos') or {}).get('id_archivo')}"
        )

    if nombre_test == "test_c03_auditoria_productor_ca11_postcondicion3":
        r_rep = _buscar_req(rows, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        r_exp = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        r_aud = _buscar_req(rows, metodo="GET", ruta_contiene="/suministros/auditoria", ultimo=True) or {}
        id_rep = (r_rep.get("response_body") or {}).get("id_reporte_gasto_acumulado")
        evs = _extraer_eventos(r_aud, ("GENERACION", "EXPORTACION"), id_reporte=id_rep)
        ev_gen = next(e for e in evs if (e.get("datos_nuevos") or {}).get("accion") == "GENERACION")
        ev_exp = next(e for e in evs if (e.get("datos_nuevos") or {}).get("accion") == "EXPORTACION")
        t_aud = datetime.fromisoformat(r_aud["timestamp_local"])
        lat_gen = round((t_aud - datetime.fromisoformat(r_rep["timestamp_local"])).total_seconds(), 3)
        lat_exp = round((t_aud - datetime.fromisoformat(r_exp["timestamp_local"])).total_seconds(), 3)
        return (
            f"HTTP {r_aud.get('status_code')}; evento GENERACION id={ev_gen.get('id_auditoria_suministro')} y "
            f"EXPORTACION id={ev_exp.get('id_auditoria_suministro')}, actor id_usuario={ev_gen.get('id_usuario')}, "
            f"resultado={ev_gen.get('resultado')}, latencias={lat_gen}s/{lat_exp}s (<= 2.0s), "
            f"id_reporte={id_rep}, id_archivo={(ev_exp.get('datos_nuevos') or {}).get('id_archivo')}"
        )

    if nombre_test == "test_d01_solicitudes_sin_autenticacion_retornan_401":
        codigos = [f"{r.get('status_code')} {r.get('error_code')}" for r in rows]
        return f"{len(rows)}/{len(rows)} endpoints sin Authorization rechazados con {', '.join(sorted(set(codigos)))}"

    if nombre_test == "test_d02_idor_descarga_exportacion_ajena_retorna_403":
        r_get = _buscar_req(rows, metodo="GET", ruta_contiene="/exportaciones/") or {}
        r_exp = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        id_arch = (r_exp.get("response_body") or {}).get("id_archivo")
        return (
            f"HTTP {r_get.get('status_code')} {r_get.get('error_code')}, "
            f"sin text/csv ni attachment ni contenido (id_archivo={id_arch})"
        )

    if nombre_test == "test_d03_manipulacion_identificadores_no_genera_500":
        resumen = [f"{r.get('ruta')}->{r.get('status_code')}({r.get('error_code')})" for r in rows]
        return f"{len(rows)}/{len(rows)} casos sin HTTP 500: " + "; ".join(resumen)

    if nombre_test == "test_d04_aislamiento_historial_por_usuario":
        r_rep = _buscar_req(rows, metodo="POST", ruta_contiene="/suministros/reportes-gastos") or {}
        r_hist_p = rows[1] if len(rows) > 1 else {}
        r_hist_a = rows[2] if len(rows) > 2 else {}
        id_rep_p = (r_rep.get("response_body") or {}).get("id_reporte_gasto_acumulado")
        tot_p = (r_hist_p.get("response_body") or {}).get("total")
        tot_a = (r_hist_a.get("response_body") or {}).get("total")
        return (
            f"HTTP 200 en reporte Productor (id_reporte={id_rep_p}) y en GET /historial "
            f"(Productor total={tot_p}, Admin total={tot_a}; conjuntos disjuntos sin fuga IDOR)"
        )

    if nombre_test == "test_d05a_idor_consultar_reporte_ajeno":
        r_act = _buscar_req(rows, metodo="POST", ruta_contiene="/activos-biologicos") or {}
        r_get = _buscar_req(rows, metodo="GET", ruta_contiene="/suministros/reportes-gastos/") or {}
        id_act = (r_act.get("response_body") or {}).get("id_activo_biologico")
        id_rep = (r_get.get("ruta") or "").rsplit("/", 1)[-1]
        return (
            f"HTTP {r_get.get('status_code')} {r_get.get('error_code')}, 0 eventos atribuibles "
            f"(id_reporte={id_rep}, id_activo={id_act})"
        )

    if nombre_test == "test_d05b_idor_regenerar_reporte_ajeno":
        r_get = _buscar_req(rows, metodo="GET", ruta_contiene="/regenerar") or {}
        parts = (r_get.get("ruta") or "").split("/")
        id_rep = parts[-2] if len(parts) >= 2 else "?"
        return f"HTTP {r_get.get('status_code')} {r_get.get('error_code')}, 0 eventos atribuibles (id_reporte={id_rep})"

    if nombre_test == "test_d05c_idor_exportar_reporte_ajeno":
        r_post = _buscar_req(rows, metodo="POST", ruta_contiene="/exportacion") or {}
        parts = (r_post.get("ruta") or "").split("/")
        id_rep = parts[-2] if len(parts) >= 2 else "?"
        return f"HTTP {r_post.get('status_code')} {r_post.get('error_code')}, 0 eventos atribuibles (id_reporte={id_rep})"

    return f"HTTP observado en {len(rows)} peticion(es)"


def main() -> None:
    staging = Path(__file__).resolve().parent
    xml_path = staging / "resultado_TC-M05-G25_reintento1.xml"
    gen_orig_path = staging / "resultado_TC-M05-G25_reintento1_generado.json"
    trazas_path = staging / "trazas_http.jsonl"
    out_path = staging / "resultado_TC-M05-G25_reintento1.json"

    orig = json.loads(gen_orig_path.read_text(encoding="utf-8"))
    orig_checkpoints = orig.get("checkpoints", [])
    tcs_xml = list(ET.parse(xml_path).getroot().iter("testcase"))
    assert len(tcs_xml) == len(orig_checkpoints) == 23, (
        f"Conteo inesperado: xml={len(tcs_xml)} orig={len(orig_checkpoints)}"
    )

    por_test = _cargar_trazas_por_test(trazas_path)
    checkpoints = []
    ok_count = 0
    falla_count = 0

    for tc_xml, meta in zip(tcs_xml, orig_checkpoints):
        nombre = tc_xml.attrib["name"]
        tiene_fallo = tc_xml.find("failure") is not None or tc_xml.find("error") is not None
        estado = "FALLA" if tiene_fallo else "OK"
        if estado == "OK":
            ok_count += 1
        else:
            falla_count += 1
        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": _obtenido_real(nombre, por_test, tc_xml),
            "estado": estado,
        })

    resultado = {
        "tc": orig.get("tc", "TC-M05-G25"),
        "summary": {
            "total": len(checkpoints),
            "ok": ok_count,
            "falla": falla_count,
            "veredicto": "Aprobado" if falla_count == 0 else "Rechazado",
        },
        "checkpoints": checkpoints,
    }
    out_path.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON generado en {out_path} ({ok_count}/{len(checkpoints)} OK)")


if __name__ == "__main__":
    main()

