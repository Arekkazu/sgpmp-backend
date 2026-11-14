# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G25 (JSON, repro, MD, TXT)  |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G25 fase 3: sufijo reintento y clasificacion dinamica sin textos fijos |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G25 fase 3 (1b): C03 auditoría Productor, D05 IDOR de reporte, B03 con archivo real, patrón de escáner |
# | 2026-11-11 | Juan Sebastian Gutierrez | TC-M05-G25 fase 3 (1c): D02 403/404 por RLS, setup D05 alineado, ps1 ASCII |
"""Generador de artefactos de corrida para TC-M05-G25.
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G25[_reintentoN].json
- repro
- TC-M05-G25_resultado[_reintentoN].md
- INFORME_FASE234_TC-M05-G25[_reintentoN].txt
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
        "paso": "B03 Restricción de descarga de exportación real para Veterinario",
        "esperado": "HTTP 403 ACCESO_DENEGADO sin contenido CSV al descargar archivo real exportado por Administrador",
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
        "paso": "C02 Registro en bitácora de auditoría de M05 de generación y exportación de Admin",
        "esperado": "Exactamente 1 evento GENERACION y 1 evento EXPORTACION con actor Admin, fecha_evento y registro <= 2 s",
        "fuente": "RF-77 CA-11 / Postcondición 3 (TC-M05-025)",
    },
    "test_c03_auditoria_productor_ca11_postcondicion3": {
        "paso": "C03 Registro en bitácora de auditoría de M05 de generación y exportación de Productor",
        "esperado": "Exactamente 1 evento GENERACION y 1 evento EXPORTACION con actor Productor, fecha_evento y registro <= 2 s",
        "fuente": "RF-77 CA-11 / Postcondición 3 (TC-M05-025)",
    },
    "test_c98_cierre_sandbox_admin": {
        "paso": "C98 Cierre ordenado de sandbox Administrador y rollback",
        "esperado": "HTTP 200 con confirmación 'Rollback exitoso'",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_d01_solicitudes_sin_autenticacion_retornan_401": {
        "paso": "D01 Rechazo de solicitudes no autenticadas",
        "esperado": "HTTP 401 sin Authorization (con cabeceras sandbox) en generación, exportación, descarga, historial y auditoría",
        "fuente": "RF-02 / RF-77 RNF Seguridad",
    },
    "test_d02_idor_descarga_exportacion_ajena_retorna_403": {
        "paso": "D02 Prevención de IDOR en descarga de exportaciones ajenas",
        "esperado": "HTTP 403 (ARCHIVO_DE_OTRO_USUARIO) o 404 (ARCHIVO_NO_ENCONTRADO por RLS de modulo5) sin contenido del archivo al descargar CSV exportado por otro usuario en el mismo sandbox",
        "fuente": "RF-77 RNF Seguridad / TC-M05-024",
    },
    "test_d03_manipulacion_identificadores_no_genera_500": {
        "paso": "D03 Validación de tipos y resistencia ante IDs inexistentes o inválidos",
        "esperado": "HTTP 404 en inexistentes, HTTP 400/422 en tipos inválidos; jamás HTTP 500",
        "fuente": "Guía de Pruebas / Robustez de la API",
    },
    "test_d04_aislamiento_historial_por_usuario": {
        "paso": "D04 Aislamiento estricto de historial por usuario",
        "esperado": "GET /historial devuelve los reportes propios del usuario y excluye por completo los de otro usuario",
        "fuente": "RF-77 RNF Historial (TC-M05-024)",
    },
    "test_d05a_idor_consultar_reporte_ajeno": {
        "paso": "D05a Prevención de IDOR al consultar reporte de otro usuario",
        "esperado": "HTTP 403 o 404 sin datos del reporte ajeno ni eventos indebidos en auditoría",
        "fuente": "RF-77 RNF Seguridad / TC-M05-024",
    },
    "test_d05b_idor_regenerar_reporte_ajeno": {
        "paso": "D05b Prevención de IDOR al regenerar reporte de otro usuario",
        "esperado": "HTTP 403 o 404 sin datos del reporte ajeno ni evento REGENERACION en auditoría",
        "fuente": "RF-77 RNF Seguridad / TC-M05-024",
    },
    "test_d05c_idor_exportar_reporte_ajeno": {
        "paso": "D05c Prevención de IDOR al exportar reporte de otro usuario",
        "esperado": "HTTP 403 o 404 sin creación de archivo ni evento EXPORTACION en auditoría",
        "fuente": "RF-77 RNF Seguridad / TC-M05-024",
    },
    "test_d98_cierre_sandbox_idor": {
        "paso": "D98 Cierre ordenado de sandbox IDOR/Aislamiento y rollback",
        "esperado": "HTTP 200 con confirmación 'Rollback exitoso'",
        "fuente": "Testing Harness / Sandbox Control",
    },
}


def _cargar_trazas(trazas_path: Path) -> list[dict]:
    if not trazas_path.exists():
        return []
    registros = []
    for linea in trazas_path.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            registros.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return registros


def main():
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G25")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    parser.add_argument("--reintento", type=int, default=0, help="Numero de reintento (>0 agrega sufijo _reintentoN)")
    args = parser.parse_args()

    staging = Path(args.staging)
    repo = Path(args.repo_root)
    sufijo = f"_reintento{args.reintento}" if args.reintento > 0 else ""

    xml_path = staging / f"resultado_TC-M05-G25{sufijo}.xml"
    if not xml_path.exists():
        print(f"ERROR: No se encontro el archivo XML: {xml_path}")
        return

    tree = ET.parse(xml_path)
    root = tree.getroot()
    trazas = _cargar_trazas(staging / "trazas_http.jsonl")

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
        },
        "checkpoints": checkpoints,
    }

    # Guardar resultado_TC-M05-G25[_reintentoN].json en staging
    json_path = staging / f"resultado_TC-M05-G25{sufijo}.json"
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

    fallidos = [c for c in checkpoints if c["estado"] == "FALLA"]
    errores_conexion = sum(1 for t in trazas if t.get("error_conexion"))

    # Generar narrativo TC-M05-G25_resultado[_reintentoN].md
    narrativo_path = staging / f"TC-M05-G25_resultado{sufijo}.md"
    md_content = f"""# Reporte de Ejecución: TC-M05-G25 (RF-77)

## 1. Identificación y Alcance
- **Caso de Prueba**: TC-M05-G25
- **Requerimiento**: RF-77 (Reporte de Gastos Acumulados por Activo)
- **Subcasos Evaluados**: TC-M05-024 (Roles y Permisos / Aislamiento IDOR), TC-M05-025 (Auditoría de Generación y Exportación)
- **Trazas HTTP Registradas**: {len(trazas)} (errores de conexión: {errores_conexion})
- **Duración Medida**: {round(args.duracion_s, 2)} s
- **Veredicto Global**: **{veredicto_global.upper()}** ({total_ok} OK, {total_falla} FALLA)

## 2. Resumen Normativo de Checkpoints
| # | Paso Evaluado | Esperado (Fuente) | Obtenido | Estado |
|---|---------------|-------------------|----------|--------|
"""
    for idx, chk in enumerate(checkpoints, 1):
        md_content += f"| {idx} | {chk['paso']} | {chk['esperado']} | {chk['obtenido']} | **{chk['estado']}** |\n"

    md_content += f"""
## 3. Diagnóstico Técnico y Clasificación Derivada de Resultados
- **Total de Pruebas**: {len(checkpoints)}
- **Aprobadas**: {total_ok}
- **Fallidas**: {total_falla}
"""
    if not fallidos:
        md_content += "- **Clasificación Global**: **CONFORME** (todos los checkpoints aprobaron en JUnit/trazas).\n"
    else:
        md_content += "- **Clasificación Global**: **PENDIENTE_DIAGNOSTICO**\n"
        for f in fallidos:
            md_content += f"  - **{f['paso']}** (`PENDIENTE_DIAGNOSTICO`): {f['obtenido']}\n"

    narrativo_path.write_text(md_content, encoding="utf-8")

    # Generar INFORME_FASE234_TC-M05-G25[_reintentoN].txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASE 2, 3 Y 4 — TC-M05-G25
RF-77: Permisos por Rol, Aislamiento de Datos/IDOR y Auditoria de Generacion
================================================================================

1. RESUMEN EJECUTIVO
--------------------
- Caso de Prueba: TC-M05-G25
- Requerimiento: RF-77 (CU04)
- Subcasos Evaluados: TC-M05-024 (roles y permisos / IDOR), TC-M05-025 (auditoria)
- Ambiente: TEST (desde TEST_BASE_URL)
- Fecha y Hora de Ejecución: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')}
- Trazas HTTP registradas: {len(trazas)} (errores_conexion={errores_conexion})
- Total de Checkpoints: {len(checkpoints)}
- Checkpoints Aprobados: {total_ok}
- Checkpoints Fallidos: {total_falla}
- Veredicto Global: {veredicto_global.upper()}

2. TABLA DE TEST Y CHECKPOINTS NORMATIVOS
-----------------------------------------
"""
    txt_content += f"{'Test / Paso':<45} | {'Esperado (Fuente)':<45} | {'Estado':<8} | {'Clasificación':<21}\n"
    txt_content += f"{'-'*45}-+-{'-'*45}-+-{'-'*8}-+-{'-'*21}\n"
    for chk in checkpoints:
        clasif = "CONFORME" if chk["estado"] == "OK" else "PENDIENTE_DIAGNOSTICO"
        txt_content += f"{chk['paso'][:45]:<45} | {chk['esperado'][:45]:<45} | {chk['estado']:<8} | {clasif:<21}\n"

    txt_content += """
3. RUN IDS Y CICLO DE VIDA SANDBOX
----------------------------------
- Modalidad Productor: Ejecutada bajo Sandbox Transaccional (Rollback atómico en A98).
- Modalidad Veterinario: Ejecutada bajo Sandbox Transaccional (Rollback atómico en B98).
- Modalidad Administrador: Ejecutada bajo Sandbox Transaccional (Rollback atómico en C98).
- Modalidad IDOR / Tipos / Aislamiento: Ejecutada bajo Sandbox Transaccional (Rollback atómico en D98).

4. DIAGNOSTICO DERIVADO DE RESULTADOS REALES
--------------------------------------------
"""
    if not fallidos:
        txt_content += f"- Sin fallos registrados ({total_ok}/{len(checkpoints)} OK). Clasificación: CONFORME.\n"
    else:
        txt_content += f"- Se registraron {total_falla} fallo(s) en JUnit. Clasificación: PENDIENTE_DIAGNOSTICO.\n"
        for f in fallidos:
            txt_content += f"  * {f['paso']} [PENDIENTE_DIAGNOSTICO]: {f['obtenido']}\n"

    (staging / f"INFORME_FASE234_TC-M05-G25{sufijo}.txt").write_text(txt_content, encoding="utf-8")
    print(f"Artefactos generados exitosamente en: {staging}")


if __name__ == "__main__":
    main()

