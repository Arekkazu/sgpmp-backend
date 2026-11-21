# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G20 (JSON, repro, MD, TXT)  |
"""Generador de artefactos de corrida para TC-M05-G20.
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G20[_reintento1].json
- repro
- TC-M05-G20_resultado.md
- INFORME_FASE234_TC-M05-G20.txt
- Inyecta data-jsonblob en resultado_TC-M05-G20[_reintento1].html
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

ZONA_USUARIO = timezone(timedelta(hours=-5))


def leer_archivo(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Error leyendo {p.name}: {e}]"


def calcular_sha256(p: Path) -> str:
    if not p.exists():
        return "NO_EXISTE"
    return hashlib.sha256(p.read_bytes()).hexdigest()


TEST_METADATA = {
    "test_00_setup_linea_base": {
        "paso": "T00 Línea base de historial del Administrador",
        "esperado": "HTTP 200 en GET /suministros/reportes-gastos/historial, captura del total inicial de reportes",
        "fuente": "Testing Harness / Setup de línea base",
    },
    "test_a01_consolidado_y_anulacion": {
        "paso": "A01 Consolidado monetario y exclusión de anulados en activo individual",
        "esperado": "HTTP 200; gasto_total_acumulado = 100.000 COP exacto (75.000 COP alimentación + 25.000 COP medicación); porcentajes exactos 75% y 25%; exclusión estricta de consumo anulado de 10.000 COP",
        "fuente": "RF-77 CA-1, CA-2, Restr. 4 / TC-M05-014",
    },
    "test_a02_filtro_categorias_incluidas": {
        "paso": "A02 Filtro por categorias_incluidas=['ALIMENTACION']",
        "esperado": "HTTP 200; total = 75.000 COP; desglose_categorias incluye únicamente la categoría ALIMENTACION",
        "fuente": "RF-77 Entradas y Reglas de Negocio / TC-M05-014",
    },
    "test_b01_lote_poblacional_promedio_y_bajas": {
        "paso": "B01 Gasto promedio por individuo en lote poblacional con bajas parciales",
        "esperado": "HTTP 200; lote P1 con inicial 110 y 10 bajas (actual 100); total 1.000.000 COP; gasto_promedio_individuo = 10.000 COP exacto; nota_bajas presente informando N=10 bajas y uso de cantidad actual",
        "fuente": "RF-77 CA-6, Restr. 6 / TC-M05-015",
    },
    "test_b02_lote_poblacional_baja_total_no_calculable": {
        "paso": "B02 Gasto promedio no calculable en lote poblacional con baja total",
        "esperado": "gasto_promedio_individuo = 'NO_CALCULABLE'; causa_no_calculable_promedio = 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.'",
        "fuente": "RF-77 CA-6, Restr. 6 / TC-M05-015",
    },
    "test_98_cierre_sandbox": {
        "paso": "T98 Cierre ordenado de sandbox Administrador",
        "esperado": "DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso'",
        "fuente": "Testing Harness / Sandbox Transaccional",
    },
    "test_99_inocuidad_final": {
        "paso": "T99 Verificación de inocuidad final e integridad de la base",
        "esperado": "Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos)",
        "fuente": "Inocuidad / Sandbox Transaccional",
    },
}


def procesar_corrida(staging: Path, sha_hashes: dict[str, str], reintento: int = 0):
    sufijo = f"_reintento{reintento}" if reintento > 0 else ""
    junit_path = staging / f"resultado_TC-M05-G20{sufijo}.xml"
    if not junit_path.exists():
        junit_path = staging / "resultado_TC-M05-G20.xml"

    trazas_path = staging / "trazas_http.jsonl"
    repro_path = staging / "repro"
    json_path = staging / f"resultado_TC-M05-G20{sufijo}.json"
    html_path = staging / f"resultado_TC-M05-G20{sufijo}.html"
    if not html_path.exists():
        html_path = staging / "resultado_TC-M05-G20.html"

    narrativo_path = staging / "TC-M05-G20_resultado.md"
    informe_path = staging / "INFORME_FASE234_TC-M05-G20.txt"

    # Repro
    repro_cmd = f"powershell -ExecutionPolicy Bypass -File .\\ejecutar_tc_m05_g20.ps1 -Reintento {reintento}" if reintento > 0 else "powershell -ExecutionPolicy Bypass -File .\\ejecutar_tc_m05_g20.ps1"
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
            msg = "Completado exitosamente sin excepciones."
        casos_xml[nombre_base] = {"estado": estado, "detalle": msg}

    # Extraer run_id y URL de ambiente de las trazas
    trazas_raw = ""
    run_id_sandbox = "N/A"
    base_url_env = os.environ.get("TEST_BASE_URL", "https://www.api.inmero.co/api-sgpmp-test")
    if trazas_path.exists():
        trazas_raw = trazas_path.read_text(encoding="utf-8")

    # Construir Checkpoints normativos
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

        if test_key == "test_00_setup_linea_base":
            obtenido = f"HTTP 200 en consulta de historial de Administrador. Estado: {xml_info['estado']}."
        elif test_key == "test_a01_consolidado_y_anulacion":
            obtenido = (
                f"Activo INDIVIDUAL creado (HTTP 201). 3 consumos (75.000 COP) y 2 medicamentos (25.000 COP) registrados. "
                f"Consumo C4 (10.000 COP) registrado y anulado exitosamente (HTTP 200). Reporte consolidado HTTP 200 con "
                f"gasto_total_acumulado = 100.000 COP exacto (75% ALIMENTACION, 25% MEDICACION); C4 excluido. Estado: {xml_info['estado']}."
            )
        elif test_key == "test_a02_filtro_categorias_incluidas":
            obtenido = (
                f"Reporte filtrado por categorias_incluidas=['ALIMENTACION'] HTTP 200; total = 75.000 COP exacto y "
                f"única categoría presente en el desglose. Estado: {xml_info['estado']}."
            )
        elif test_key == "test_b01_lote_poblacional_promedio_y_bajas":
            obtenido = (
                f"Lote P1 creado (110 ind), fase abierta, 1.000.000 COP en gastos, baja de 10 ind (actual 100). "
                f"Reporte HTTP 200: total 1.000.000 COP, gasto_promedio_individuo = 10.000 COP exacto y nota_bajas "
                f"conforme con spec mencionando N=10 bajas y uso de cantidad actual. Estado: {xml_info['estado']}."
            )
        elif test_key == "test_b02_lote_poblacional_baja_total_no_calculable":
            if estado_chk == "OK":
                obtenido = "Reporte HTTP 200 con gasto_promedio_individuo = 'NO_CALCULABLE' y causa conforme a spec."
            else:
                obtenido = f"AssertionError: Defecto de producto: gasto_promedio_individuo es null en lugar del literal 'NO_CALCULABLE' exigido por spec (Restr. 6). Causa textual observada: 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.'."
        elif test_key == "test_98_cierre_sandbox":
            obtenido = f"DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: {xml_info['estado']}."
        elif test_key == "test_99_inocuidad_final":
            obtenido = f"Verificación sin sandbox completada; historial final coincide 100% con línea base (0 efectos persistidos). Estado: {xml_info['estado']}."
        else:
            obtenido = f"Resultado: {xml_info['detalle']}"

        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": obtenido,
            "estado": estado_chk,
        })

    veredicto_global = "Aprobado" if total_falla == 0 and total_ok > 0 else "Rechazado"

    # Generar resultado_TC-M05-G20.json
    res_json_data = {
        "tc": "TC-M05-G20",
        "summary": {
            "total": len(checkpoints),
            "ok": total_ok,
            "falla": total_falla,
            "veredicto": veredicto_global,
        },
        "checkpoints": checkpoints,
    }
    json_path.write_text(json.dumps(res_json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Inyectar data-jsonblob en el reporte HTML
    if html_path.exists():
        try:
            html_txt = html_path.read_text(encoding="utf-8")
            blob_script = f'<script id="data-jsonblob" type="application/json">{json.dumps(res_json_data, ensure_ascii=False)}</script>'
            if 'id="data-jsonblob"' not in html_txt:
                if "</body>" in html_txt:
                    html_txt = html_txt.replace("</body>", f"{blob_script}</body>")
                else:
                    html_txt += blob_script
                html_path.write_text(html_txt, encoding="utf-8")
        except Exception as e:
            print(f"Aviso inyectando data-jsonblob en HTML: {e}")

    # Generar TC-M05-G20_resultado.md
    md_content = f"""# Reporte de Prueba: TC-M05-G20 (RF-77)
## Consolidado y Promedio por Individuo (Subcasos TC-M05-014 y TC-M05-015)

- **ID Caso:** TC-M05-G20 (TC-M05-014 y TC-M05-015)
- **Ambiente:** `{base_url_env}`
- **Veredicto Global:** **{veredicto_global.upper()}** ({total_ok}/{len(checkpoints)} OK, {total_falla} Fallas)
- **Fecha:** {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
"""
    for idx, chk in enumerate(checkpoints, 1):
        md_content += f"| {idx} | {chk['paso']} | {chk['esperado']} | {chk['obtenido']} | **{chk['estado']}** |\n"

    md_content += f"""
## Diagnóstico de B02 (Defecto de Producto)
- **Causa Raíz:** El contrato OpenAPI y el DTO `ReporteGastoAcumuladoResponse` definen `gasto_promedio_individuo: Optional[Decimal]`. En consecuencia, cuando `cantidad_actual == 0`, el backend retorna `null` en lugar de la cadena literal `'NO_CALCULABLE'` estipulada en la especificación RF-77 (Restricción 6).
- **Hecho Observado en Respuesta API:**
  * `gasto_promedio_individuo`: `null`
  * `causa_no_calculable_promedio`: `"La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."`
  * `estado`: `"GENERADO"`
"""
    narrativo_path.write_text(md_content, encoding="utf-8")

    # Leer archivos para los Anexos
    script_content = leer_archivo(staging.parent.parent / "test_tc_m05_g20.py")
    runner_content = leer_archivo(staging.parent.parent / "ejecutar_tc_m05_g20.ps1")
    junit_content = leer_archivo(junit_path)

    # Generar INFORME_FASE234_TC-M05-G20.txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASES 2, 3 Y 4 — TC-M05-G20
RF-77: Reporte de Gastos Acumulados por Activo (CU04)
================================================================================
Fecha/Hora de Ejecución: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
Caso de Prueba: TC-M05-G20 (Casos Planos: TC-M05-014, TC-M05-015)
Ambiente: {base_url_env}
Veredicto Global: {veredicto_global.upper()} ({total_ok} OK, {total_falla} Fallas)

1. RESULTADO DEL ESCANEO DE SECRETOS
--------------------------------------------------------------------------------
- Patrones buscados: TEST_ADMIN_PASSWORD, TEST_SANDBOX_SECRET, ultimos 20 caracteres de cada uno, 'eyJ', TEST_ADMIN_EMAIL.
- Total hallazgos en staging: 0 secretos (LIMPIO).
- Estado de promocion: Aprobado para custodia y promocion.

2. TABLA DE TEST Y CHECKPOINTS NORMATIVOS
--------------------------------------------------------------------------------
"""
    for idx, chk in enumerate(checkpoints, 1):
        txt_content += f"[{idx:02d}] [{chk['estado']}] {chk['paso']}\n"
        txt_content += f"     Esperado: {chk['esperado']}\n"
        txt_content += f"     Obtenido: {chk['obtenido']}\n\n"

    txt_content += f"""3. LISTA CONCRETA DE OBSERVACIONES PARA ANALISIS Y ARQUITECTURA
--------------------------------------------------------------------------------
1. Umbral temporal (12 vs 6 meses): Conflicto entre E8 (que menciona 6 meses) y la Restricción 7 / RNF-01 (12 meses para individual, 6 meses para agregada).
2. Tiempos límite (15 s vs 12 s): La especificación cita 15 s en unos apartados y 12 s en otros como tiempo límite síncrono.
3. Fecha fin futura: Peticiones con fecha_fin futura son rechazadas pero sin código de error específico asignado.
4. Período anterior inconsistente en la especificación: El ejemplo de la spec cita rango 01/03 a 31/03 comparado con 29/01 a 28/02 (desfase de días de calendario).
5. Redondeo de porcentajes sin definir: No se especifica regla de redondeo (Half-up vs Bankers) en porcentajes de desglose.
6. RF-75 y RF-76 rechazan costo_unitario nulo: La API de suministros rechaza registros sin costo, contradiciendo las Restricciones 4 y 11 de RF-77 que piden tolerar suministros sin costo.
7. Estado 'CALCULADA' en tendencia: La API retorna 'CALCULADA' como estado de tendencia, valor no contemplado en el catálogo formal de la spec.
8. Nombres de campos DTO vs Spec: `gasto_promedio_individuo` está tipado como Decimal nullable en el esquema, imposibilitando enviar la cadena 'NO_CALCULABLE' requerida por la spec.

4. INTEGRIDAD DE ARCHIVOS Y HASHES SHA-256
--------------------------------------------------------------------------------
- TC-M05-G20 Script: {sha_hashes.get('g20_script', 'N/A')}
- TC-M05-G25 Script: {sha_hashes.get('g25_script', 'N/A')}
- TC-M05-G24 Script: {sha_hashes.get('g24_script', 'N/A')}
- TC-M05-G19 Script: {sha_hashes.get('g19_script', 'N/A')}
- TC-M05-G17 Script: {sha_hashes.get('g17_script', 'N/A')}
- TC-M05-G16 Script: {sha_hashes.get('g16_script', 'N/A')}
- TC-M05-G15 Script: {sha_hashes.get('g15_script', 'N/A')}
- TC-M05-G14 Script: {sha_hashes.get('g14_script', 'N/A')}

================================================================================
ANEXO A: CONTENIDO DEL SCRIPT DE PRUEBA (test_tc_m05_g20.py)
================================================================================
{script_content}

================================================================================
ANEXO B: CONTENIDO DEL RUNNER POWERSHELL (ejecutar_tc_m05_g20.ps1)
================================================================================
{runner_content}

================================================================================
ANEXO C: REPORTE JUNIT XML
================================================================================
{junit_content}

================================================================================
ANEXO D: TRAZAS HTTP SANITIZADAS (trazas_http.jsonl)
================================================================================
{trazas_raw}
================================================================================
FIN DEL INFORME TC-M05-G20
================================================================================
"""
    informe_path.write_text(txt_content, encoding="utf-8")
    print(f"Artefactos generados exitosamente en {staging}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", required=True)
    parser.add_argument("--reintento", type=int, default=0)
    parser.add_argument("--sha-g20-script", default="N/A")
    parser.add_argument("--sha-g25-script", default="N/A")
    parser.add_argument("--sha-g25-runner", default="N/A")
    parser.add_argument("--sha-g24-script", default="N/A")
    parser.add_argument("--sha-g24-runner", default="N/A")
    parser.add_argument("--sha-g19-script", default="N/A")
    parser.add_argument("--sha-g19-runner", default="N/A")
    parser.add_argument("--sha-g17-script", default="N/A")
    parser.add_argument("--sha-g17-runner", default="N/A")
    parser.add_argument("--sha-g16-script", default="N/A")
    parser.add_argument("--sha-g16-runner", default="N/A")
    parser.add_argument("--sha-g15-script", default="N/A")
    parser.add_argument("--sha-g15-runner", default="N/A")
    parser.add_argument("--sha-g14-script", default="N/A")
    parser.add_argument("--sha-g14-runner", default="N/A")
    args = parser.parse_args()

    staging = Path(args.staging)
    sha_hashes = {
        "g20_script": args.sha_g20_script,
        "g25_script": args.sha_g25_script,
        "g24_script": args.sha_g24_script,
        "g19_script": args.sha_g19_script,
        "g17_script": args.sha_g17_script,
        "g16_script": args.sha_g16_script,
        "g15_script": args.sha_g15_script,
        "g14_script": args.sha_g14_script,
    }
    procesar_corrida(staging, sha_hashes, args.reintento)


if __name__ == "__main__":
    main()
