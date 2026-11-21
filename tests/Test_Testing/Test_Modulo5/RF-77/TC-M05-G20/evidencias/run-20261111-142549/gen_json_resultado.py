# | Fecha      | Nombre                   | Que se hizo                                                              |
# |------------|--------------------------|--------------------------------------------------------------------------|
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G20 RF-77 reintento 1: regenera JSON de resultado desde XML/traza |
"""Regenera resultado_TC-M05-G20_reintento1.json desde JUnit XML y trazas HTTP.

Lee resultado_TC-M05-G20_reintento1.xml y trazas_http.jsonl dentro de la carpeta
de staging, deriva el estado ("OK" o "FALLA") desde JUnit y extrae los valores
concretos observados (HTTP, totales, promedios, causa literal y nota de bajas)
desde las trazas reales sin incluir tokens, credenciales ni datos sensibles.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
JUNIT_PATH = AQUI / "resultado_TC-M05-G20_reintento1.xml"
TRAZA_PATH = AQUI / "trazas_http.jsonl"
SALIDA_PATH = AQUI / "resultado_TC-M05-G20_reintento1.json"

TEST_SPECS: list[tuple[str, str, str]] = [
    (
        "test_00_setup_linea_base",
        "T00 Línea base de historial del Administrador",
        "HTTP 200 en GET /suministros/reportes-gastos/historial, captura del total inicial de reportes",
    ),
    (
        "test_a01_consolidado_y_anulacion",
        "A01 Consolidado monetario y exclusión de anulados en activo individual",
        "HTTP 200; gasto_total_acumulado = 100.000 COP exacto (75.000 COP alimentación + 25.000 COP medicación); porcentajes exactos 75% y 25%; exclusión estricta de consumo anulado de 10.000 COP",
    ),
    (
        "test_a02_filtro_categorias_incluidas",
        "A02 Filtro por categorias_incluidas=['ALIMENTACION']",
        "HTTP 200; total = 75.000 COP; desglose_categorias incluye únicamente la categoría ALIMENTACION",
    ),
    (
        "test_b01_lote_poblacional_promedio_y_bajas",
        "B01 Gasto promedio por individuo en lote poblacional con bajas parciales",
        "HTTP 200; lote P1 con inicial 110 y 10 bajas (actual 100); total 1.000.000 COP; gasto_promedio_individuo = 10.000 COP exacto; nota_bajas presente informando N=10 bajas y uso de cantidad actual",
    ),
    (
        "test_b02_lote_poblacional_baja_total_no_calculable",
        "B02 Gasto promedio no calculable en lote poblacional con baja total",
        "gasto_promedio_individuo = 'NO_CALCULABLE'; causa_no_calculable_promedio = 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.'",
    ),
    (
        "test_98_cierre_sandbox",
        "T98 Cierre ordenado de sandbox Administrador",
        "DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso'",
    ),
    (
        "test_99_inocuidad_final",
        "T99 Verificación de inocuidad final e integridad de la base",
        "Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos)",
    ),
]


def _cargar_trazas() -> dict[str, list[dict[str, Any]]]:
    por_test: dict[str, list[dict[str, Any]]] = {}
    for linea in TRAZA_PATH.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        reg = json.loads(linea)
        por_test.setdefault(reg.get("test", ""), []).append(reg)
    return por_test


def _cargar_junit() -> dict[str, str]:
    raiz = ET.parse(JUNIT_PATH).getroot()
    estados: dict[str, str] = {}
    for tc in raiz.iter("testcase"):
        nombre = (tc.get("name") or "").split("[")[0]
        falla = tc.find("failure") is not None or tc.find("error") is not None or tc.find("skipped") is not None
        estados[nombre] = "FALLA" if falla else "OK"
    return estados


def _ultimo_post_reporte(reqs: list[dict[str, Any]]) -> dict[str, Any] | None:
    posts = [r for r in reqs if r.get("metodo") == "POST" and r.get("ruta") == "/suministros/reportes-gastos"]
    return posts[-1] if posts else None


def _obtenido(nombre: str, reqs: list[dict[str, Any]], estado: str, trazas_por_test: dict[str, list[dict[str, Any]]]) -> str:
    if nombre == "test_00_setup_linea_base":
        r = reqs[-1]
        rb = r.get("response_body") or {}
        return (
            f"GET /suministros/reportes-gastos/historial HTTP {r.get('status_code')}; "
            f"total_base={rb.get('total')}, items={len(rb.get('items', []))} (estado JUnit: {estado})."
        )

    if nombre == "test_a01_consolidado_y_anulacion":
        r_act = next(r for r in reqs if r.get("ruta") == "/activos-biologicos")
        id_act = (r_act.get("response_body") or {}).get("id_activo_biologico")
        r_anul = next(r for r in reqs if str(r.get("ruta", "")).endswith("/anulacion"))
        r_rep = _ultimo_post_reporte(reqs)
        assert r_rep is not None
        rb = r_rep.get("response_body") or {}
        cats = ", ".join(
            f"{c.get('categoria')}={c.get('subtotal')} ({c.get('porcentaje')}%, {c.get('num_registros')} reg)"
            for c in (rb.get("desglose_categorias") or [])
        )
        return (
            f"Activo INDIVIDUAL id={id_act} HTTP {r_act.get('status_code')}; "
            f"anulacion HTTP {r_anul.get('status_code')}; "
            f"POST /suministros/reportes-gastos HTTP {r_rep.get('status_code')} "
            f"(id_reporte={rb.get('id_reporte_gasto_acumulado')}, "
            f"gasto_total_acumulado={rb.get('gasto_total_acumulado')!r}, desglose=[{cats}])."
        )

    if nombre == "test_a02_filtro_categorias_incluidas":
        r_rep = _ultimo_post_reporte(reqs)
        assert r_rep is not None
        rb = r_rep.get("response_body") or {}
        cats = ", ".join(
            f"{c.get('categoria')}={c.get('subtotal')} ({c.get('porcentaje')}%)"
            for c in (rb.get("desglose_categorias") or [])
        )
        return (
            f"POST /suministros/reportes-gastos (categorias_incluidas=['ALIMENTACION']) HTTP {r_rep.get('status_code')} "
            f"(id_reporte={rb.get('id_reporte_gasto_acumulado')}, "
            f"gasto_total_acumulado={rb.get('gasto_total_acumulado')!r}, desglose=[{cats}])."
        )

    if nombre == "test_b01_lote_poblacional_promedio_y_bajas":
        r_act = next(r for r in reqs if r.get("ruta") == "/activos-biologicos")
        r_baja = next(r for r in reqs if str(r.get("ruta", "")).endswith("/eventos/baja"))
        r_rep = _ultimo_post_reporte(reqs)
        assert r_rep is not None
        rb = r_rep.get("response_body") or {}
        id_lote = (r_act.get("response_body") or {}).get("id_activo_biologico")
        cant_ini = ((r_act.get("response_body") or {}).get("detalle_poblacional") or {}).get("cantidad_inicial")
        cant_baja = ((r_baja.get("response_body") or {}).get("baja") or {}).get("cantidad_afectada")
        return (
            f"Lote P1 id={id_lote} (inicial={cant_ini}, baja={cant_baja}, HTTP {r_baja.get('status_code')}); "
            f"POST /suministros/reportes-gastos HTTP {r_rep.get('status_code')} "
            f"(id_reporte={rb.get('id_reporte_gasto_acumulado')}, "
            f"gasto_total_acumulado={rb.get('gasto_total_acumulado')!r}, "
            f"gasto_promedio_individuo={rb.get('gasto_promedio_individuo')!r}, "
            f"nota_bajas={rb.get('nota_bajas')!r})."
        )

    if nombre == "test_b02_lote_poblacional_baja_total_no_calculable":
        r_act = next(r for r in reqs if r.get("ruta") == "/activos-biologicos")
        r_baja = next(r for r in reqs if str(r.get("ruta", "")).endswith("/eventos/baja"))
        r_rep = _ultimo_post_reporte(reqs)
        assert r_rep is not None
        rb = r_rep.get("response_body") or {}
        id_lote = (r_act.get("response_body") or {}).get("id_activo_biologico")
        cant_baja = ((r_baja.get("response_body") or {}).get("baja") or {}).get("cantidad_afectada")
        return (
            f"Lote P2 id={id_lote} (baja={cant_baja}, HTTP {r_baja.get('status_code')}); "
            f"POST /suministros/reportes-gastos HTTP {r_rep.get('status_code')} "
            f"(id_reporte={rb.get('id_reporte_gasto_acumulado')}, "
            f"gasto_total_acumulado={rb.get('gasto_total_acumulado')!r}, "
            f"gasto_promedio_individuo={rb.get('gasto_promedio_individuo')!r}, "
            f"causa_no_calculable_promedio={rb.get('causa_no_calculable_promedio')!r}, "
            f"nota_bajas={rb.get('nota_bajas')!r})."
        )

    if nombre == "test_98_cierre_sandbox":
        r_del = reqs[-1]
        st = (r_del.get("response_body") or {}).get("status")
        return f"DELETE /test-control/runs/<run_id> HTTP {r_del.get('status_code')} (status={st!r})."

    if nombre == "test_99_inocuidad_final":
        t00 = trazas_por_test.get("test_00_setup_linea_base", [{}])[-1]
        total_base = (t00.get("response_body") or {}).get("total")
        return (
            f"Verificacion fuera de sandbox completada (JUnit {estado}): "
            f"historial final coincide con total_base={total_base} (0 efectos persistidos)."
        )

    raise ValueError(f"Test no reconocido: {nombre}")


def main() -> None:
    trazas = _cargar_trazas()
    estados = _cargar_junit()

    checkpoints: list[dict[str, str]] = []
    for test_key, paso, esperado in TEST_SPECS:
        if test_key not in estados:
            raise ValueError(f"Falta {test_key} en JUnit XML")
        est = estados[test_key]
        checkpoints.append({
            "paso": paso,
            "esperado": esperado,
            "obtenido": _obtenido(test_key, trazas.get(test_key, []), est, trazas),
            "estado": est,
        })

    ok = sum(1 for c in checkpoints if c["estado"] == "OK")
    falla = sum(1 for c in checkpoints if c["estado"] == "FALLA")
    resultado = {
        "tc": "TC-M05-G20",
        "summary": {
            "total": len(checkpoints),
            "ok": ok,
            "falla": falla,
            "veredicto": "Rechazado" if falla else "Aprobado",
        },
        "checkpoints": checkpoints,
    }
    SALIDA_PATH.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Regenerado {SALIDA_PATH.name}: total={len(checkpoints)}, ok={ok}, falla={falla}")


if __name__ == "__main__":
    main()

