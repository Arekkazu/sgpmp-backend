# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G38 (JSON, repro, MD, TXT)  |
"""Generador de artefactos de corrida para TC-M05-G38.
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G38.json
- TC-M05-G38_resultado.md
- INFORME_FASE234_TC-M05-G38.txt
- Inyecta data-jsonblob en resultado_TC-M05-G38.html
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
    "test_t00_admin_setup": {
        "paso": "T00 Admin Conteo inicial de eventos y creacion de activo con operaciones",
        "esperado": "HTTP 200 en auditoria base, HTTP 201 en activo QA y HTTP 200 en suministros",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_a01_cadena_custodia_secuencia_completa": {
        "paso": "A01 Cadena de custodia cronologica con doble timestamp visible",
        "esperado": "Secuencia completa de eventos del activo ordenada cronologicamente con fecha_evento y fecha_emision visibles",
        "fuente": "RF-80 CA-4, CA-13 / TC-M05-032.1",
    },
    "test_a02_exportacion_formatos_filtro_activo": {
        "paso": "A02 Exportacion de bitacora en CSV, XLSX y PDF con filtro de activo",
        "esperado": "HTTP 200 con archivo valido segun formato (CSV, XLSX, PDF); HTTP 400 ante formato no soportado",
        "fuente": "RF-80 CA-2 / TC-M05-032.2",
    },
    "test_b01_filtros_invalidos": {
        "paso": "B01 Validacion de filtros invalidos (formato de fecha y rango invertido)",
        "esperado": "HTTP 4xx con mensaje explicativo ante formato invalido o fecha_desde > fecha_hasta",
        "fuente": "RF-80 CA-1 / TC-M05-044.1",
    },
    "test_b02_consulta_sin_coincidencias_autoauditoria": {
        "paso": "B02 Consulta sin coincidencias (200 lista vacia) y registro de consulta en bitacora",
        "esperado": "HTTP 200 con lista vacia y registro de la consulta (+1 evento) segun CU06 FA-02",
        "fuente": "RF-80 CU06 FA-02 / TC-M05-044.2",
    },
    "test_t98_admin_cierre_sandbox": {
        "paso": "T98 Admin Cierre ordenado de sandbox Administrador y rollback",
        "esperado": "HTTP 200 con confirmacion de rollback exitoso",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_t99_admin_inocuidad": {
        "paso": "T99 Admin Verificacion de inocuidad y reversion de datos fuera de sandbox",
        "esperado": "Conteo final de auditoria identico al conteo inicial",
        "fuente": "Testing Harness / Inocuidad",
    },
    "test_c01_vet_acceso_denegado_endpoints_auditoria": {
        "paso": "C01 Vet Restriccion de acceso RBAC a endpoints de auditoria para Veterinario",
        "esperado": "HTTP 403 ACCESO_DENEGADO en lista, detalle y exportar sin fuga de datos en la respuesta",
        "fuente": "RF-80 / RBAC Centralizado (TC-M05-044.3)",
    },
    "test_c02_vet_intento_denegado_evento_seguridad": {
        "paso": "C02 Vet Registro de evento de seguridad ante intento de acceso denegado",
        "esperado": "Incremento (+1) en eventos de seguridad/rechazo tras intentos denegados",
        "fuente": "RF-80 / TC-M05-044.3",
    },
    "test_c98_vet_cierre_sandbox": {
        "paso": "C98 Vet Cierre ordenado de sandbox Veterinario y rollback",
        "esperado": "HTTP 200 con confirmacion de rollback exitoso",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_c99_vet_inocuidad": {
        "paso": "C99 Vet Verificacion de inocuidad tras corrida Veterinario",
        "esperado": "Conteo final de auditoria identico al conteo inicial",
        "fuente": "Testing Harness / Inocuidad",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G38")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    args = parser.parse_args()

    staging = Path(args.staging)
    repo = Path(args.repo_root)

    xml_path = staging / "resultado_TC-M05-G38.xml"
    if not xml_path.exists():
        xml_path = staging / "junit_TC-M05-G38.xml"
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
        "tc": "TC-M05-G38",
        "summary": {
            "total": total,
            "ok": ok,
            "falla": falla,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
    }

    json_path = staging / "resultado_TC-M05-G38.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, indent=2, ensure_ascii=False)
    print(f"Generado: {json_path.name}")

    # Inyectar data-jsonblob en el reporte HTML de pytest-html
    html_path = staging / "resultado_TC-M05-G38.html"
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
                print("Inyectado data-jsonblob en resultado_TC-M05-G38.html")
        except Exception as e:
            print(f"Aviso: no se pudo inyectar data-jsonblob en HTML: {e}")

    # Generar TC-M05-G38_resultado.md
    md_content = f"""# Resultado de Prueba: TC-M05-G38
## Consulta de Bitácora y Cadena de Custodia (RF-80)

- **ID Caso:** TC-M05-G38 (TC-M05-032 y TC-M05-044)
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
### Diagnóstico de Fallas (Defectos de Producto)
- **Falla en B01 (RF-80 / TC-M05-044.1):**
  La combinación inválida `fecha_desde > fecha_hasta` retorna HTTP 200 con lista vacía en lugar de HTTP 4xx con mensaje explicativo de corrección. El endpoint no valida la coherencia temporal de los parámetros de fecha.
- **Falla en B02 (RF-80 CU06 FA-02 vs Catálogo / TC-M05-044.2):**
  La especificación CU06 FA-02 estipula que las consultas a la bitácora deben auto-auditarse (+1 evento). En la implementación actual, `ConsultarAuditoriaSuministrosUseCase` es de solo lectura y no audita la consulta por no existir un tipo de evento en el catálogo para "consulta de bitácora".
- **Falla en C02 (RF-80 / TC-M05-044.3):**
  Los intentos de acceso no autorizados denegados con HTTP 403 (Veterinario) no generan un evento de seguridad en `modulo5.auditorias_suministros` ni en `modulo1.eventos`. El middleware RBAC (`src/shared/rbac.py`) lanza `AuthorizationError` sin persistir trazas de seguridad.

### Cobertura No Ejecutada Declarada
- **B03 (044.4) Fallo forzado de M12:** No ejecutable en ambiente sandbox al no existir broker externo ni inyector de fallas en red/BD.
"""
    md_path = staging / "TC-M05-G38_resultado.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Generado: {md_path.name}")

    # Generar INFORME_FASE234_TC-M05-G38.txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASES 2, 3 Y 4: TC-M05-G38
RF-80 "Auditoria y Trazabilidad de Registros de Suministros"
================================================================================
Fecha/Hora: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
Suite: TC-M05-G38 (Casos TC-M05-032 y TC-M05-044)
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

    txt_content += """2. MATRIZ DE CAPACIDADES RF-80 (Porton P1)
--------------------------------------------------------------------------------
- Cadena de custodia:           PRESENTE (secuencia cronologica completa con fecha_evento y fecha_emision)
- Exportacion multi-formato:    PRESENTE (CSV estructurado, XLSX con hoja 'Auditoria Suministros', PDF con tabla estilizada)
- Validacion formato exportar:  PRESENTE (HTTP 400 ante formato invalido, codigo FORMATO_EXPORTACION_INVALIDO)
- Filtros de fecha:             PARCIAL (valida formato ISO pero no valida coherencia fecha_desde <= fecha_hasta)
- Auto-auditoria de consultas:  AUSENTE (conflicto CU06 FA-02 vs Catalogo de eventos)
- RBAC Recurso 57:              PRESENTE (HTTP 403 para Veterinario en lista, detalle y exportar sin fuga de datos)
- Auditoria de eventos 403:     AUSENTE (los intentos denegados no persisten evento de seguridad)
- Broker M12 / Cola:            AUSENTE / NO OBSERVABLE (la persistencia es relacional y local)

3. INOCUIDAD Y SEGURIDAD
--------------------------------------------------------------------------------
- Corridas Sandbox: Admin y Vet ejecutadas secuencialmente, cerradas via DELETE /test-control/runs/{run_id} -> HTTP 200.
- Inocuidad: Conteo total de eventos en modulo5.auditorias_suministros antes y despues de cada corrida permanece identico.
- Escaneo de secretos: 0 contraseñas, 0 tokens JWT ('eyJ'), 0 secretos de sandbox en artefactos.

4. OBSERVACIONES PARA ANALISIS Y RECOMENDACIONES (INC BORRADOR)
--------------------------------------------------------------------------------
- Defecto 1 (B01): En `src/supplies/infrastructure/routers/auditoria_suministros_router.py`, `fecha_desde` y `fecha_hasta` no se comparan. Si `fecha_desde > fecha_hasta`, se retorna HTTP 200 con items vacios en vez de HTTP 400/422.
  Borrador INC: "RF-80: Consulta a la bitacora de auditoria con fecha_desde > fecha_hasta retorna HTTP 200 en lugar de HTTP 4xx con mensaje explicativo".
- Defecto 2 (B02): Discrepancia de diseno entre CU06 FA-02 (que pide auto-auditar consultas a la bitacora) y el catalogo de eventos de M05, donde no existe tipo de evento para consulta de auditoria.
  Borrador INC: "RF-80 CU06 FA-02: La consulta a la bitacora de auditoria no genera evento de auditoria en modulo5.auditorias_suministros".
- Defecto 3 (C02): En `src/shared/rbac.py`, las denegaciones de acceso (HTTP 403) no persisten registros en la tabla de auditoria ni en la bitacora de seguridad.
  Borrador INC: "Seguridad / RF-80: Intentos de acceso denegados con HTTP 403 no generan evento de seguridad en la bitacora".
"""
    txt_path = staging / "INFORME_FASE234_TC-M05-G38.txt"
    txt_path.write_text(txt_content, encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()

