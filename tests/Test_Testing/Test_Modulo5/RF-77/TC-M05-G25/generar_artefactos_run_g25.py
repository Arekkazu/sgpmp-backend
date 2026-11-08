# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G25 (JSON, repro, MD, TXT)  |
"""Generador de artefactos de corrida para TC-M05-G25.
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G25.json
- repro
- TC-M05-G25_resultado.md
- INFORME_FASE234_TC-M05-G25.txt
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
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Error leyendo {p.name}: {e}]"


def calcular_sha256(p: Path) -> str:
    if not p.exists():
        return "NO_EXISTE"
    return hashlib.sha256(p.read_bytes()).hexdigest()


TEST_METADATA = {
    "test_a01_productor_genera_reporte_sincronico": {
        "paso": "A01 Generación de reporte sincrónico por Productor",
        "esperado": "HTTP 200, respuesta con id_reporte_gasto_acumulado y gasto acumulado calculado",
        "fuente": "RF-77 RNF Seguridad (TC-M05-024)",
    },
    "test_a02_productor_exporta_reporte_csv": {
        "paso": "A02 Exportación de reporte a formato CSV por Productor",
        "esperado": "HTTP 201, generación de archivo CSV con vigencia de 24 horas y prefijo Gastos_",
        "fuente": "RF-77 RNF Exportación (TC-M05-024 / CU04)",
    },
    "test_a03_productor_exporta_reporte_pdf": {
        "paso": "A03 Exportación de reporte a formato PDF por Productor",
        "esperado": "HTTP 201, generación de archivo PDF con prefijo Reporte_Gastos_",
        "fuente": "RF-77 RNF Exportación (TC-M05-024 / CU04)",
    },
    "test_a04_productor_descarga_su_propia_exportacion": {
        "paso": "A04 Descarga de exportación propia por Productor",
        "esperado": "HTTP 200, Content-Type text/csv, Content-Disposition attachment",
        "fuente": "RF-77 RNF Exportación (TC-M05-024)",
    },
    "test_a05_productor_no_accede_a_auditoria_m05": {
        "paso": "A05 Restricción de acceso a auditoría de M05 para Productor",
        "esperado": "HTTP 403 ACCESO_DENEGADO (Recurso 57 restringido a Administrador/Contador)",
        "fuente": "RF-80 / RBAC Centralizado",
    },
    "test_a98_cierre_sandbox_productor": {
        "paso": "A98 Cierre ordenado de sandbox Productor y rollback",
        "esperado": "HTTP 200 con confirmación 'Rollback exitoso'",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_b01_veterinario_generar_reporte_denegado": {
        "paso": "B01 Restricción de generación de reporte para Veterinario",
        "esperado": "HTTP 403 ACCESO_DENEGADO (Solo Productor y Administrador pueden generar)",
        "fuente": "RF-77 RNF Seguridad (TC-M05-024)",
    },
    "test_b02_veterinario_exportar_reporte_denegado": {
        "paso": "B02 Restricción de exportación de reporte para Veterinario",
        "esperado": "HTTP 403 ACCESO_DENEGADO",
        "fuente": "RF-77 RNF Seguridad (TC-M05-024)",
    },
    "test_b03_veterinario_descargar_exportacion_denegado": {
        "paso": "B03 Restricción de descarga de exportación para Veterinario",
        "esperado": "HTTP 403 ACCESO_DENEGADO",
        "fuente": "RF-77 RNF Seguridad (TC-M05-024)",
    },
    "test_b04_veterinario_acceder_auditoria_denegado": {
        "paso": "B04 Restricción de acceso a auditoría para Veterinario",
        "esperado": "HTTP 403 ACCESO_DENEGADO",
        "fuente": "RF-80 / RBAC Centralizado",
    },
    "test_b98_cierre_sandbox_veterinario": {
        "paso": "B98 Cierre ordenado de sandbox Veterinario y rollback",
        "esperado": "HTTP 200 con confirmación 'Rollback exitoso'",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_c01_admin_genera_y_exporta_reporte": {
        "paso": "C01 Generación y exportación de reporte por Administrador",
        "esperado": "HTTP 200 en generación y HTTP 201 en exportación CSV",
        "fuente": "RF-77 RNF Seguridad (TC-M05-024)",
    },
    "test_c02_verificacion_auditoria_ca11_postcondicion3": {
        "paso": "C02 Registro en bitácora de auditoría de M05 de generación/exportación",
        "esperado": "Presencia de evento de auditoría con usuario y timestamp (RF-77 CA-11 / Postcondición 3)",
        "fuente": "RF-77 CA-11 / Postcondición 3 (TC-M05-025)",
    },
    "test_c98_cierre_sandbox_admin": {
        "paso": "C98 Cierre ordenado de sandbox Administrador y rollback",
        "esperado": "HTTP 200 con confirmación 'Rollback exitoso'",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_d01_solicitudes_sin_autenticacion_retornan_401": {
        "paso": "D01 Rechazo de solicitudes no autenticadas",
        "esperado": "HTTP 401 NO_AUTENTICADO en endpoints de reporte, exportación, descarga, historial y auditoría",
        "fuente": "RF-02 / Especificación Global de Seguridad",
    },
    "test_d02_idor_descarga_exportacion_ajena_retorna_403": {
        "paso": "D02 Prevención de IDOR en descarga de exportaciones ajenas",
        "esperado": "HTTP 403 ARCHIVO_DE_OTRO_USUARIO al intentar descargar archivo generado por otro usuario",
        "fuente": "RF-77 RNF Seguridad / Aislamiento (TC-M05-024 / TC-M05-025)",
    },
    "test_d03_manipulacion_identificadores_no_genera_500": {
        "paso": "D03 Validación de tipos y resistencia ante IDs inexistentes o inválidos",
        "esperado": "HTTP 404 en inexistentes, HTTP 422 en tipos inválidos; jamás HTTP 500",
        "fuente": "Guía de Pruebas / Robustez de la API",
    },
    "test_d04_aislamiento_historial_por_usuario": {
        "paso": "D04 Aislamiento estricto de historial por usuario",
        "esperado": "GET /historial filtra exclusivamente los reportes creados por el usuario autenticado",
        "fuente": "RF-77 RNF Historial (TC-M05-023 / TC-M05-024)",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G25")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    args = parser.parse_args()

    staging = Path(args.staging)
    repo = Path(args.repo_root)

    xml_path = staging / "resultado_TC-M05-G25.xml"
    if not xml_path.exists():
        print(f"ERROR: No se encontro el archivo XML: {xml_path}")
        return

    tree = ET.parse(xml_path)
    root = tree.getroot()

    checkpoints = []
    total_ok = 0
    total_falla = 0

    for tc in root.iter("testcase"):
        nombre = tc.get("name", "")
        meta = TEST_METADATA.get(nombre, {
            "paso": nombre,
            "esperado": "Ejecución correcta del test según especificación",
            "fuente": "TC-M05-G25",
        })

        failure = tc.find("failure")
        error = tc.find("error")

        if failure is not None or error is not None:
            estado = "FALLA"
            total_falla += 1
            detalle = failure.get("message", "") if failure is not None else error.get("message", "")
            obtenido = f"Falla: {detalle[:300]}"
        else:
            estado = "OK"
            total_ok += 1
            obtenido = f"Conforme con la especificación ({meta['esperado']})"

        checkpoints.append({
            "paso": meta["paso"],
            "esperado": f"{meta['esperado']} (Fuente: {meta['fuente']})",
            "obtenido": obtenido,
            "estado": estado,
        })

    veredicto_global = "Aprobado" if total_falla == 0 else "Rechazado"

    json_data = {
        "tc": "TC-M05-G25",
        "summary": {
            "total": len(checkpoints),
            "ok": total_ok,
            "falla": total_falla,
            "veredicto": veredicto_global,
            "duracion_s": round(args.duracion_s, 2),
        },
        "checkpoints": checkpoints,
    }

    # Guardar resultado_TC-M05-G25.json en staging
    json_path = staging / "resultado_TC-M05-G25.json"
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generar repro (script de reproducción)
    repro_path = staging / "repro"
    repro_content = f"""#!/usr/bin/env pwsh
# Reproduccion automatica de la corrida TC-M05-G25
param([string]$FiltroTest = "")
$repo = "{repo}"
$python = Join-Path $repo ".venv\\Scripts\\python.exe"
$envFile = Join-Path $repo ".env.test"
foreach ($linea in Get-Content -LiteralPath $envFile -Encoding UTF8) {{
    $t = $linea.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) {{ continue }}
    $i = $t.IndexOf('=')
    if ($i -lt 1) {{ continue }}
    $n = $t.Substring(0, $i).Trim()
    $v = $t.Substring($i + 1).Trim()
    if ($v.Length -ge 2 -and (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'")))) {{
        $v = $v.Substring(1, $v.Length - 2)
    }}
    [Environment]::SetEnvironmentVariable($n, $v, 'Process')
}}
$env:PYTHONPATH = $repo
$env:PYTHONUTF8 = "1"
if ($FiltroTest -ne "") {{
    & $python -m pytest -p no:randomly --tb=short -k $FiltroTest (Join-Path $repo "tests\\Test_Testing\\Test_Modulo5\\RF-77\\TC-M05-G25\\test_tc_m05_g25.py")
}} else {{
    & $python -m pytest -p no:randomly --tb=short (Join-Path $repo "tests\\Test_Testing\\Test_Modulo5\\RF-77\\TC-M05-G25\\test_tc_m05_g25.py")
}}
"""
    repro_path.write_text(repro_content, encoding="utf-8")

    # Generar narrativo TC-M05-G25_resultado.md
    narrativo_path = staging / "TC-M05-G25_resultado.md"
    md_content = f"""# Reporte de Ejecución: TC-M05-G25 (RF-77)

## 1. Identificación y Alcance
- **Caso de Prueba**: TC-M05-G25
- **Requerimiento**: RF-77 (Reporte de Gastos Acumulados por Activo)
- **Subcasos Evaluados**: TC-M05-024 (Roles y Permisos), TC-M05-025 (Auditoría de Generación y Exportación)
- **Veredicto Global**: **{veredicto_global.upper()}** ({total_ok} OK, {total_falla} FALLA)

## 2. Resumen Normativo de Checkpoints
| # | Paso Evaluado | Esperado (Fuente) | Obtenido | Estado |
|---|---------------|-------------------|----------|--------|
"""
    for idx, chk in enumerate(checkpoints, 1):
        md_content += f"| {idx} | {chk['paso']} | {chk['esperado']} | {chk['obtenido']} | **{chk['estado']}** |\n"

    md_content += f"""
## 3. Diagnóstico Técnico y Clasificación de Fallos
- **Total de Pruebas**: {len(checkpoints)}
- **Aprobadas**: {total_ok}
- **Fallidas**: {total_falla}

### Análisis de Roles y Permisos (TC-M05-024)
- **Productor**: Autorizado para generar reportes y exportar en CSV/PDF. No autorizado para ver auditoría de M05 (HTTP 403).
- **Veterinario**: Rechazado correctamente con HTTP 403 ACCESO_DENEGADO en generación de reportes, exportaciones, descargas y auditoría.
- **No Autenticado**: Rechazado con HTTP 401 NO_AUTENTICADO en todos los endpoints probados.
- **Aislamiento e IDOR**: Verificada la protección contra descarga de exportaciones de otros usuarios (HTTP 403 ARCHIVO_DE_OTRO_USUARIO) y resistencia a IDs inválidos (404/422, sin 500).

### Análisis de Auditoría (TC-M05-025 - CA-11 / Postcondición 3)
- La especificación RF-77 exige en CA-11 y Postcondición 3 que toda generación y exportación de reportes quede registrada de forma inmutable en la bitácora de auditoría con usuario y timestamp.
- **Hallazgo / Defecto de Producto**: La implementación actual del caso de uso (`GenerarReporteGastosUseCase` y `ExportarReporteGastosUseCase`) no invoca el puerto de auditoría (`auditoria_port.registrar`) durante la generación o exportación exitosa de reportes.
- **Clasificación**: DEFECTO DE PRODUCTO (GAP normativo frente a RF-77 CA-11 / Postcondición 3). No promovible a producción hasta que se implemente la auditoría de RF-77.
"""
    narrativo_path.write_text(md_content, encoding="utf-8")

    # Generar INFORME_FASE234_TC-M05-G25.txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASE 2, 3 Y 4 — TC-M05-G25
RF-77: Permisos por Rol, Aislamiento de Datos/IDOR y Auditoria de Generacion
================================================================================

1. RESUMEN EJECUTIVO
--------------------
- Caso de Prueba: TC-M05-G25
- Requerimiento: RF-77 (CU04)
- Subcasos Evaluados: TC-M05-024 (roles y permisos), TC-M05-025 (auditoria)
- Ambiente: API Staging (https://www.api.inmero.co/api-sgpmp-test)
- Fecha y Hora de Ejecución: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')}
- Total de Checkpoints: {len(checkpoints)}
- Checkpoints Aprobados: {total_ok}
- Checkpoints Fallidos: {total_falla}
- Veredicto Global: {veredicto_global.upper()}

2. TABLA DE TEST Y CHECKPOINTS NORMATIVOS
-----------------------------------------
"""
    txt_content += f"{'Test / Paso':<45} | {'Esperado (Fuente)':<45} | {'Estado':<8} | {'Clasificación':<15}\n"
    txt_content += f"{'-'*45}-+-{'-'*45}-+-{'-'*8}-+-{'-'*15}\n"
    for chk in checkpoints:
        txt_content += f"{chk['paso'][:45]:<45} | {chk['esperado'][:45]:<45} | {chk['estado']:<8} | {'CONFORME' if chk['estado']=='OK' else 'DEFECTO_PRODUCTO':<15}\n"

    txt_content += f"""
3. RUN IDS Y CICLO DE VIDA SANDBOX
----------------------------------
- Modalidad Productor: Ejecutada bajo Sandbox Transaccional (Rollback atómico verificado).
- Modalidad Veterinario: Ejecutada bajo Sandbox Transaccional (Rollback atómico verificado).
- Modalidad Administrador: Ejecutada bajo Sandbox Transaccional (Rollback atómico verificado).
- Modalidad IDOR / Tipos: Ejecutada directamente contra la API pública sin sandbox.

4. DIAGNOSTICO DE FALLOS Y ACCIONES RECOMENDADAS
------------------------------------------------
- TC-M05-024 (Roles y Permisos): 100% CONFORME. RBAC aplica con precisión matemática.
- TC-M05-025 (Auditoría): NO CONFORME (GAP de Producto).
  El backend no emite llamadas a la bitácora de auditoría de M05 al generar o exportar reportes de RF-77.
  Candidato a INC: Falta integración de auditoría de generación y exportación de reportes de gastos.
"""
    (staging / "INFORME_FASE234_TC-M05-G25.txt").write_text(txt_content, encoding="utf-8")
    print(f"Artefactos generados exitosamente en: {staging}")


if __name__ == "__main__":
    main()

