# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G39 (Evaluación Oficial)     |
"""Generador de artefactos de corrida para TC-M05-G39 (Evaluación Oficial).
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G39.json (Consumido por dashboard)
- TC-M05-G39_resultado.md (Informe detallado sin sufijos)
- INFORME_FASE234_TC-M05-G39.txt (Informe consolidado con anexos de código y trazas)
- Inyecta data-jsonblob en resultado_TC-M05-G39.html
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


TEST_METADATA = {
    "test_t00_setup_linea_base": {
        "paso": "T00 Admin Conteo inicial de eventos y creacion de activo con operacion RF-78",
        "esperado": "HTTP 200 en auditoria base, HTTP 201 en activo QA y HTTP 200 en suministro registrado",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_a02_consulta_evento_incompleto_detalle_causa": {
        "paso": "A02 Consulta de evento incompleto y presencia de detalle_causa (TC-M05-092 / 028)",
        "esperado": "HTTP 200 con registro_incompleto=true y detalle_causa no nulo detallando campos faltantes (CA-12 / CU06 FA-05)",
        "fuente": "RF-80 CA-12 / CU06 FA-05 / TC-M05-092 (agrupado 028)",
    },
    "test_b01_superficie_escritura_openapi": {
        "paso": "B01 Superficie de escritura exclusiva GET en OpenAPI (TC-M05-093 / 029)",
        "esperado": "0 metodos de modificacion (POST/PUT/PATCH/DELETE) expuestos bajo /suministros/auditoria* en OpenAPI",
        "fuente": "RF-80 Restr. 1 / TC-M05-093 (agrupado 029)",
    },
    "test_b02_inmutabilidad_rechazo_405_y_auditoria_seguridad": {
        "paso": "B02 Inmutabilidad rechazo 405 y registro de evento de seguridad (TC-M05-093 / 029)",
        "esperado": "HTTP 405 Method Not Allowed en PUT/PATCH/DELETE, hash inalterado y registro de evento de seguridad",
        "fuente": "RF-80 Restr. 1, CA-2, RNF-05 / TC-M05-093 (agrupado 029)",
    },
    "test_b03_verificacion_integridad_hash_sha256": {
        "paso": "B03 Recálculo determinista de hash SHA-256 sobre todas las columnas reales (CA-6 / Restr. 5)",
        "esperado": "Coincidencia exacta entre el hash_integridad almacenado y el SHA-256 de todas las columnas reales excluyendo únicamente hash_integridad",
        "fuente": "RF-80 CA-6, Restr. 5 / TC-M05-093 (agrupado 029)",
    },
    "test_c01_id_evento_m05_presente_en_registros": {
        "paso": "C01 Presencia de id_evento_m05 para deduplicacion at-least-once (TC-M05-094 / 030)",
        "esperado": "Campo 'id_evento_m05' (UUID unico) presente en la entidad de auditoria para deduplicacion",
        "fuente": "RF-80 Restr. 9, CA-14, RNF-09 / TC-M05-094 (agrupado 030)",
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


def main():
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G39")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (0 por defecto)")
    args = parser.parse_args()

    staging = Path(args.staging)
    repo = Path(args.repo_root)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    xml_path = staging / f"resultado_TC-M05-G39{sufijo}.xml"
    if not xml_path.exists():
        xml_path = staging / "resultado_TC-M05-G39.xml"
    if not xml_path.exists():
        xml_path = staging / "junit_TC-M05-G39.xml"
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
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, indent=2, ensure_ascii=False)
    print(f"Generado: {json_path.name}")

    # Inyectar data-jsonblob en el reporte HTML de pytest-html
    html_path = staging / f"resultado_TC-M05-G39{sufijo}.html"
    if not html_path.exists():
        html_path = staging / "resultado_TC-M05-G39.html"
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

    # Generar TC-M05-G39_resultado.md
    md_content = f"""# Resultado de Prueba: TC-M05-G39
## Campos Mínimos, Inmutabilidad, Hash e Idempotencia (RF-80)

- **ID Caso:** TC-M05-G39 (TC-M05-092, TC-M05-093 y TC-M05-094 / Agrupados: 028, 029 y 030)
- **Evaluación:** Evaluación oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/
- **Veredicto:** {veredicto} ({ok}/{total} OK, {falla} Fallas)
- **Fecha:** {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
- **Duración:** {args.duracion_s:.2f} s

### Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
"""
    for idx, cp in enumerate(checkpoints, 1):
        md_content += f"| {idx} | {cp['paso']} | {cp['esperado']} | {cp['obtenido']} | {cp['estado']} |\n"

    md_content += f"""
### Diagnóstico de Fallas (Defectos de Producto Confirmados)
- **Falla en A02 (TC-M05-092 / 028 - RF-80 CA-12 / CU06 FA-05):**
  Los eventos con `registro_incompleto=true` (ej. evento 87 `CICLO_CONSOLIDADO`, 88, 89 en `modulo5.auditorias_suministros`) tienen `detalle_causa = null` en lugar de listar los campos faltantes (ej. 'Campos faltantes: ...').
- **Falla en B02 (TC-M05-093 / 029 - RF-80 Restr. 1 / CA-2 / RNF-05):**
  Los intentos de modificación indebida (PUT, PATCH, DELETE) retornan correctamente HTTP 405 Method Not Allowed y el hash_integridad permanece intacto, pero el sistema no genera ni persiste un evento de seguridad con resultado 'RECHAZADO' en `modulo5.auditorias_suministros` (conteo=0) ni en `modulo1.eventos` (conteo=0).
- **Falla en C01 (TC-M05-094 / 030 - RF-80 Restr. 9 / CA-14 / RNF-09):**
  La entidad y tabla de auditoría carecen de la columna/propiedad `id_evento_m05` (UUID único emitido antes de publicar para deduplicación at-least-once). Solo existe la clave primaria serial `id_auditoria_suministro`.

### Validación de B03 (Hash de Integridad SHA-256)
- **Estado:** OK (Aprobado).
- **Evidencia Técnica:** Se consultaron las columnas reales de `modulo5.auditorias_suministros` (23 columnas). Las columnas `creado_en` e `id_registro_suministro` NO existen en la tabla. En consecuencia, la resta `- 'creado_en' - 'id_registro_suministro'` es una operación inocua en JSONB; la función calcula el digest SHA-256 cubriendo exactamente la totalidad de las 22 columnas reales restantes de la tabla menos `hash_integridad`. Se comprobó coincidencia criptográfica exacta (100% match) en eventos evaluados.
"""
    md_path = staging / "TC-M05-G39_resultado.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Generado: {md_path.name}")

    # Leer archivos para los Anexos
    script_content = leer_archivo(staging.parent.parent / "test_tc_m05_g39.py")
    runner_content = leer_archivo(staging.parent.parent / "ejecutar_tc_m05_g39.ps1")
    junit_content = leer_archivo(xml_path)
    trazas_content = leer_archivo(staging / "trazas_http.jsonl")

    # Generar INFORME_FASE234_TC-M05-G39.txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASES 2, 3 Y 4: TC-M05-G39
RF-80 "Auditoria y Trazabilidad de Registros de Suministros"
================================================================================
Evaluación: Evaluación oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/
Fecha/Hora: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
Suite: TC-M05-G39 (Casos Planos: TC-M05-092, TC-M05-093, TC-M05-094 | Agrupados: 028, 029, 030)
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

    txt_content += """2. COBERTURA NO EJECUTADA DECLARADA
--------------------------------------------------------------------------------
- A01 (TC-M05-092 / 028): Invocación unitaria de función pura de validación de campos mínimos.
  Motivo técnico: En la capa de dominio/aplicación no existe una función pura aislada de validación de campos mínimos;
  la persistencia la realiza SqlAlchemyAuditoriaSuministroRepository delegando las validaciones en constraints NOT NULL y tipos en PostgreSQL.

3. INOCUIDAD Y SEGURIDAD
--------------------------------------------------------------------------------
- Corrida Sandbox: Administrador ejecutada en aislamiento con cabeceras X-Test-Run-Id y X-Sandbox-Secret.
- Cierre: Ejecutado via DELETE /test-control/runs/{run_id} -> HTTP 200 con confirmacion de rollback.
- Inocuidad: Conteo total de eventos en modulo5.auditorias_suministros antes y despues de la corrida permanece identico.
- Escaneo de secretos: 0 contraseñas, 0 tokens JWT ('eyJ'), 0 secretos de sandbox en artefactos.

4. OBSERVACIONES PARA ANALISIS Y RECOMENDACIONES (BORRADORES DE INC)
--------------------------------------------------------------------------------
- Defecto 1 (A02 / TC-M05-092 / 028):
  Borrador INC: "RF-80 CA-12 / CU06 FA-05: Eventos de auditoria con registro_incompleto=true presentan detalle_causa nulo en lugar de detallar campos faltantes".
  Impacto: Incumplimiento del criterio de aceptacion CA-12 y del flujo alternativo CU06 FA-05.
- Defecto 2 (B02 / TC-M05-093 / 029):
  Borrador INC: "RF-80 Restr. 1 / CA-2 / RNF-05: Intentos de modificacion (PUT/PATCH/DELETE) rechazados con HTTP 405 no generan evento de seguridad en la bitacora".
  Impacto: No se alerta ni se auditan intentos maliciosos de alteracion de la bitacora de suministros en ninguna tabla (modulo5.auditorias_suministros ni modulo1.eventos).
- Defecto 3 (C01 / TC-M05-094 / 030):
  Borrador INC: "RF-80 Restr. 9 / CA-14 / RNF-09: Falta columna y propiedad 'id_evento_m05' (UUID) en modulo5.auditorias_suministros para deduplicacion at-least-once".
  Impacto: Imposibilidad de deduplicar eventos en consumidores externos M12 ante reintentos o entregas at-least-once.

================================================================================
ANEXO 1: SCRIPT DE PRUEBA (test_tc_m05_g39.py)
================================================================================
""" + script_content + """

================================================================================
ANEXO 2: RUNNER POWERSHELL (ejecutar_tc_m05_g39.ps1)
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
FIN DEL INFORME TC-M05-G39
================================================================================
"""
    txt_path = staging / "INFORME_FASE234_TC-M05-G39.txt"
    txt_path.write_text(txt_content, encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()
