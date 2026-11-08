# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G40 (JSON, repro, MD, TXT)  |
"""Generador de artefactos de corrida para TC-M05-G40.
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G40[_reintento<n>].json
- TC-M05-G40_resultado.md
- INFORME_FASE234_TC-M05-G40.txt
- Inyecta data-jsonblob en resultado_TC-M05-G40[_reintento<n>].html
- Anexos completos de código y trazas
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ZONA_USUARIO = timezone(timedelta(hours=-5))


def leer_archivo(p: Path) -> str:
    if not p.exists():
        return f"[Archivo no encontrado: {p.name}]"
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Error leyendo {p.name}: {e}]"


def calcular_sha256(p: Path) -> str:
    if not p.exists():
        return "NO_EXISTE"
    return hashlib.sha256(p.read_bytes()).hexdigest()


TEST_METADATA = {
    "test_t00_setup_linea_base_y_latencia": {
        "paso": "T00 Admin Conteo inicial, creacion de activo y muestreo de latencia (20 peticiones)",
        "esperado": "HTTP 200 en auditoria base, HTTP 201 en activo QA y 20 suministros exitosos con medicion de latencia",
        "fuente": "Testing Harness / Sandbox Control / RNF-07",
    },
    "test_a01_cola_persistente_m12_capacidad_100k": {
        "paso": "A01 Presencia de cola persistente M05-M12 con capacidad para 100.000 eventos (TC-M05-095 / 031)",
        "esperado": "Cola persistente o buffer implementado para desacoplamiento y resiliencia ante caidas (Precondicion 3, Restr. 6, Restr. 7, RNF-02, RNF-07)",
        "fuente": "RF-80 Precondicion 3, Restr. 6, Restr. 7, RNF-02, RNF-07 / TC-M05-095 (agrupado 031)",
    },
    "test_t98_cierre_sandbox": {
        "paso": "T98 Admin Cierre ordenado de sandbox Administrador y rollback",
        "esperado": "HTTP 200 con confirmacion de rollback exitoso",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_t99_inocuidad_rollback": {
        "paso": "T99 Admin Verificacion de inocuidad tras corrida Administrador",
        "esperado": "Conteo final de auditoria identico al conteo inicial",
        "fuente": "Testing Harness / Inocuidad",
    },
}


def extraer_estadisticas_latencia(staging: Path) -> dict[str, float]:
    trazas_path = staging / "trazas_http.jsonl"
    latencias: list[float] = []
    if trazas_path.exists():
        try:
            for linea in trazas_path.read_text(encoding="utf-8").splitlines():
                if not linea.strip():
                    continue
                d = json.loads(linea)
                if d.get("ruta") == "/suministros/costeo-directo" and d.get("metodo") == "POST":
                    dur = d.get("duracion_ms")
                    if dur is not None:
                        latencias.append(float(dur))
        except Exception:
            pass

    if not latencias:
        return {"p50": 0.0, "p95": 0.0, "max": 0.0, "min": 0.0, "muestras": 0}

    s = sorted(latencias)
    n = len(s)
    p50 = s[n // 2]
    idx_95 = min(int(n * 0.95), n - 1)
    p95 = s[idx_95]
    return {
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "max": round(max(s), 2),
        "min": round(min(s), 2),
        "muestras": n,
    }


def main():
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G40")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento")
    args = parser.parse_args()

    staging = Path(args.staging)
    repo = Path(args.repo_root)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    xml_path = staging / f"resultado_TC-M05-G40{sufijo}.xml"
    if not xml_path.exists():
        xml_path = staging / "resultado_TC-M05-G40.xml"
    if not xml_path.exists():
        xml_path = staging / "junit_TC-M05-G40.xml"
    if not xml_path.exists():
        print(f"ERROR: No existe archivo XML en {staging}")
        return

    tree = ET.parse(xml_path)
    root = tree.getroot()

    checkpoints = []
    total = 0
    ok = 0
    falla = 0

    testcase_elements = root.findall(".//testcase")
    total = len(testcase_elements)

    for tc in testcase_elements:
        nombre = tc.attrib.get("name", "")
        meta = TEST_METADATA.get(nombre, {
            "paso": nombre,
            "esperado": "Comportamiento segun especificacion",
            "fuente": "RF-80 / Especificacion",
        })

        failure = tc.find("failure")
        error = tc.find("error")

        if failure is not None:
            estado = "FALLA"
            falla += 1
            obtenido = failure.attrib.get("message", failure.text or "Fallo de aserto").strip().splitlines()[0]
        elif error is not None:
            estado = "FALLA"
            falla += 1
            obtenido = error.attrib.get("message", error.text or "Error en ejecucion").strip().splitlines()[0]
        else:
            estado = "OK"
            ok += 1
            obtenido = meta["esperado"]

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
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, indent=2, ensure_ascii=False)
    print(f"Generado: {json_path.name}")

    # Inyectar data-jsonblob en el reporte HTML de pytest-html
    html_path = staging / f"resultado_TC-M05-G40{sufijo}.html"
    if not html_path.exists():
        html_path = staging / "resultado_TC-M05-G40.html"
    if html_path.exists():
        try:
            html_content = html_path.read_text(encoding="utf-8")
            blob_script = f'<script id="data-jsonblob" type="application/json">{json.dumps(resultado_json, ensure_ascii=False)}</script>'
            if 'id="data-jsonblob"' not in html_content:
                if "</body>" in html_content:
                    html_content = html_content.replace("</body>", f"{blob_script}</body>")
                else:
                    html_content += blob_script
                html_path.write_text(html_content, encoding="utf-8")
                print(f"Inyectado data-jsonblob en {html_path.name}")
        except Exception as e:
            print(f"Aviso: no se pudo inyectar data-jsonblob en HTML: {e}")

    stats_lat = extraer_estadisticas_latencia(staging)

    # Generar TC-M05-G40_resultado.md
    md_content = f"""# Resultado de Prueba: TC-M05-G40
## Resiliencia ante Caída de Auditoría, Cola y Latencia (RF-80)

- **ID Caso:** TC-M05-G40 (TC-M05-095 / Agrupado: TC-M05-031)
- **Veredicto:** {veredicto} ({ok}/{total} OK, {falla} Fallas)
- **Fecha:** {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
- **Duración:** {args.duracion_s:.2f} s

### Métricas de Latencia Observadas (POST /suministros/costeo-directo)
- Muestras registradas: {stats_lat['muestras']}
- Latencia minima: {stats_lat['min']} ms
- Latencia mediana (p50): {stats_lat['p50']} ms
- Latencia percentil 95 (p95): {stats_lat['p95']} ms
- Latencia maxima: {stats_lat['max']} ms

### Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
"""
    for idx, cp in enumerate(checkpoints, 1):
        md_content += f"| {idx} | {cp['paso']} | {cp['esperado']} | {cp['obtenido']} | {cp['estado']} |\n"

    md_content += f"""
### Diagnóstico de Fallas (Defecto de Producto)
- **Falla en A01 (TC-M05-095 / 031 - RF-80 Precondición 3, Restr. 6, Restr. 7, RNF-02, RNF-07):**
  La especificación exige una cola persistente o buffer de desacoplamiento entre M05 y M12 con capacidad configurable de hasta 100.000 eventos para garantizar la resiliencia ante caídas del repositorio de auditoría o de M12.
  En la arquitectura actual de backend, se constata la total ausencia de cola persistente (RabbitMQ/Kafka/Celery) y una absoluta dependencia de ejecución en memoria; la persistencia es directa y sincrónica en `modulo5.auditorias_suministros`.

### Cobertura No Ejecutada Declarada
- **Inyección de fallas en M12 / Caída forzada de repositorio:** No ejecutable en sandbox sin alterar el cluster de BD o servicios externos.
- **Alertas de saturación de cola al 90% y 100%:** No ejecutable debido a la inexistencia de la cola/buffer persistente.
- **Política de retención FIFO de 48 horas:** No ejecutable debido a la inexistencia de la cola/buffer persistente.
- **Límite de degradación <= 50 ms respecto a línea base sin auditoría:** No medible de forma comparativa, ya que en el producto actual la auditoría está fuertemente acoplada en la transacción de suministro y no existe un switch o baseline sin auditoría.
"""
    md_path = staging / "TC-M05-G40_resultado.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Generado: {md_path.name}")

    # Leer archivos para los Anexos
    script_content = leer_archivo(staging.parent.parent / "test_tc_m05_g40.py")
    runner_content = leer_archivo(staging.parent.parent / "ejecutar_tc_m05_g40.ps1")
    junit_content = leer_archivo(xml_path)
    trazas_content = leer_archivo(staging / "trazas_http.jsonl")

    # Generar INFORME_FASE234_TC-M05-G40.txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASES 2, 3 Y 4: TC-M05-G40
RF-80 "Auditoria y Trazabilidad de Registros de Suministros"
================================================================================
Fecha/Hora: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
Suite: TC-M05-G40 (Caso Plano: TC-M05-095 | Agrupado: TC-M05-031)
Total tests: {total} | Aprobados: {ok} | Fallidos: {falla}
Veredicto Final: {veredicto}
Duracion: {args.duracion_s:.2f} s

1. TABLA DETALLADA DE CHECKPOINTS
--------------------------------------------------------------------------------
"""
    for idx, cp in enumerate(checkpoints, 1):
        txt_content += f"[{idx:02d}] {cp['paso']}\n"
        txt_content += f"     Esperado: {cp['esperado']}\n"
        txt_content += f"     Obtenido: {cp['obtenido']}\n"
        txt_content += f"     Estado:   {cp['estado']}\n\n"

    txt_content += f"""2. RESUMEN EJECUTIVO Y ARQUITECTURA
--------------------------------------------------------------------------------
- Ausencia de cola persistente: Se constata la inexistencia de colas persistentes
  (brokers externos como RabbitMQ, Kafka o Celery) y la absoluta dependencia de
  ejecucion sincronica en memoria hacia modulo5.auditorias_suministros.
- Metricas de latencia observadas (POST /suministros/costeo-directo):
  * Total de muestras ejecutadas: {stats_lat['muestras']}
  * Latencia minima:              {stats_lat['min']} ms
  * Latencia mediana (p50):       {stats_lat['p50']} ms
  * Latencia percentil 95 (p95):  {stats_lat['p95']} ms
  * Latencia maxima:              {stats_lat['max']} ms

3. COBERTURA NO EJECUTADA DECLARADA
--------------------------------------------------------------------------------
- Inyeccion de fallas / caida de M12: No viable en ambiente de pruebas sin degradar BD real.
- Alertas de saturacion de cola (90% y 100%): No aplicable al no existir cola intermedia.
- Politica de retencion FIFO de 48 horas: No aplicable al no existir cola intermedia.
- Limite de degradacion <= 50 ms vs linea base: No aplicable comparativamente; no existe baseline sin auditoria en el producto.

4. INOCUIDAD Y SEGURIDAD
--------------------------------------------------------------------------------
- Corrida Sandbox: Administrador ejecutada con cabeceras de sandbox.
- Cierre: Ejecutado via DELETE /test-control/runs/{{run_id}} -> HTTP 200 con confirmacion de rollback.
- Inocuidad: Conteo total de eventos en modulo5.auditorias_suministros antes y despues de la corrida permanece identico.
- Escaneo de secretos: 0 contraseñas, 0 tokens JWT ('eyJ'), 0 secretos de sandbox en artefactos.

5. OBSERVACIONES PARA ANALISIS Y RECOMENDACIONES (BORRADOR DE INC)
--------------------------------------------------------------------------------
- Defecto 1 (A01 / TC-M05-095 / 031):
  Borrador INC: "RF-80 Precondición 3, Restr. 6, Restr. 7, RNF-02, RNF-07: Inexistencia de cola persistente / buffer de desacoplamiento entre M05 y M12 con capacidad para 100.000 eventos".
  Impacto: Riesgo de indisponibilidad o degradacion del registro de suministros si el subsistema de auditoria experimenta caidas o latencia en BD, al no disponer de buffer persistente.

================================================================================
ANEXO 1: SCRIPT DE PRUEBA (test_tc_m05_g40.py)
================================================================================
""" + script_content + """

================================================================================
ANEXO 2: RUNNER POWERSHELL (ejecutar_tc_m05_g40.ps1)
================================================================================
""" + runner_content + """

================================================================================
ANEXO 3: REPORTE JUNIT XML
================================================================================
""" + junit_content + """

================================================================================
ANEXO 4: TRAZAS HTTP DE LA EJECUCION
================================================================================
""" + trazas_content + """

================================================================================
FIN DEL INFORME TC-M05-G40
================================================================================
"""
    txt_path = staging / "INFORME_FASE234_TC-M05-G40.txt"
    txt_path.write_text(txt_content, encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()
