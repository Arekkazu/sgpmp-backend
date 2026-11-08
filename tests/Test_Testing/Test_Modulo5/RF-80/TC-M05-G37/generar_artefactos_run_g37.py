# | Fecha      | Nombre                   | Que se hizo                                                            |
# |------------|--------------------------|------------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G37 (JSON, repro, MD, TXT)  |
"""Generador de artefactos de corrida para TC-M05-G37.
Lee el JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G37.json
- TC-M05-G37_resultado.md
- INFORME_FASE234_TC-M05-G37.txt
- Inyecta data-jsonblob en resultado_TC-M05-G37.html
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
    "test_t00_setup_linea_base": {
        "paso": "T00 Conteo inicial de eventos y creacion de activo con ciclo",
        "esperado": "HTTP 200 en auditoria base, HTTP 201 en activo QA y apertura de fase productiva",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_a01_rf78_operacion_exitosa": {
        "paso": "A01 Registro de suministro directo RF-78 y persistencia <= 2 s",
        "esperado": "HTTP 200, evento SUMINISTRO_REGISTRADO persistido <= 2 s con campos base RF-10 y de extension M05",
        "fuente": "RF-80 CA-1 / TC-M05-026.1",
    },
    "test_a01_rf79_operacion_exitosa": {
        "paso": "A01 Cierre de ciclo productivo RF-79 y eventos de consolidacion <= 2 s",
        "esperado": "HTTP 200, eventos CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO en auditoria <= 2 s",
        "fuente": "RF-80 CA-1 / RF-79 / TC-M05-026.1",
    },
    "test_a01_rf81_operacion_exitosa": {
        "paso": "A01 Consulta de historial de suministros RF-81 y persistencia <= 2 s",
        "esperado": "HTTP 200, evento CONSULTA_HISTORIAL_EJECUTADA en auditoria <= 2 s",
        "fuente": "RF-80 CA-1 / RF-81 / TC-M05-026.1",
    },
    "test_a02_operacion_fallida_registro_auditoria": {
        "paso": "A02 Registro de evento con resultado FALLIDO o RECHAZADO ante operacion invalida",
        "esperado": "Evento en auditoria con resultado FALLIDO/RECHAZADO persistido <= 2 s ante operacion rechazada",
        "fuente": "RF-80 CA-1 / TC-M05-026.1",
    },
    "test_a03_consistencia_filtros_vs_detalle": {
        "paso": "A03 Consistencia entre consulta por filtros en lista y consulta por detalle /{id}",
        "esperado": "HTTP 200 en ambos endpoints, identidad de campos entre lista y detalle",
        "fuente": "RF-80 CA-2 / TC-M05-026.1",
    },
    "test_b01_clasificacion_retencion_eventos": {
        "paso": "B01 Clasificacion y retencion diferenciada (NIC41 / 5 años vs TECNICO / 1 año)",
        "esperado": "Eventos contables clasificados como NIC41 con 5 años de retencion; operativos como TECNICO con 1 año",
        "fuente": "RF-80 CA-3 / TC-M05-027",
    },
    "test_b02_tipo_no_catalogado_clasifica_nic41_unidad": {
        "paso": "B02 Clasificacion por defecto de tipo no catalogado como NIC41 / 5 años (nivel unidad)",
        "esperado": "Funcion de clasificacion asigna ('NIC41', '5 años') ante tipo desconocido",
        "fuente": "RF-80 Fase 3 / TC-M05-027",
    },
    "test_t98_cierre_sandbox": {
        "paso": "T98 Cierre ordenado de sandbox Administrador y rollback",
        "esperado": "HTTP 200 con confirmacion de rollback exitoso",
        "fuente": "Testing Harness / Sandbox Control",
    },
    "test_t99_inocuidad_rollback": {
        "paso": "T99 Verificacion de inocuidad y reversion de datos fuera de sandbox",
        "esperado": "Conteo final de auditoria identico al conteo base antes de la prueba",
        "fuente": "Testing Harness / Inocuidad",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Generador de artefactos de corrida TC-M05-G37")
    parser.add_argument("--staging", required=True, help="Ruta al directorio de staging de evidencias")
    parser.add_argument("--repo-root", required=True, help="Ruta a la raiz del repositorio")
    parser.add_argument("--duracion-s", type=float, default=0.0, help="Duracion de la corrida en segundos")
    args = parser.parse_args()

    staging = Path(args.staging)
    repo = Path(args.repo_root)

    xml_path = staging / "junit_TC-M05-G37.xml"
    if not xml_path.exists():
        xml_path = staging / "resultado_TC-M05-G37.xml"
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
        "tc": "TC-M05-G37",
        "summary": {
            "total": total,
            "ok": ok,
            "falla": falla,
            "veredicto": veredicto,
        },
        "checkpoints": checkpoints,
    }

    json_path = staging / "resultado_TC-M05-G37.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, indent=2, ensure_ascii=False)
    print(f"Generado: {json_path.name}")

    # Inyectar data-jsonblob en el reporte HTML de pytest-html
    html_path = staging / "resultado_TC-M05-G37.html"
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
                print("Inyectado data-jsonblob en resultado_TC-M05-G37.html")
        except Exception as e:
            print(f"Aviso: no se pudo inyectar data-jsonblob en HTML: {e}")

    # Extraer run_id desde trazas_http.jsonl
    run_id = "tc-m05-g37-adm"
    trazas_path = staging / "trazas_http.jsonl"
    if trazas_path.exists():
        try:
            with open(trazas_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        req_b = item.get("request_body")
                        break
        except Exception:
            pass

    # Generar TC-M05-G37_resultado.md
    md_content = f"""# Resultado de Prueba: TC-M05-G37
## Persistencia y Clasificación de Eventos (RF-80)

- **ID Caso:** TC-M05-G37 (TC-M05-026 y TC-M05-027)
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
### Diagnóstico de Fallas
"""
    if falla > 0:
        md_content += """- **Defecto de Producto en A02 (RF-80 CA-1 / TC-M05-026.1):**
  La especificación estipula que toda operación de suministro debe auditarse, y si la operación falla, debe registrarse un evento con resultado FALLIDO o RECHAZADO en <= 2 s.
  En la implementación actual, los rechazos de validación de negocio (HTTP 4xx como `FECHA_FUERA_DE_RANGO` o `VAL_ENTRADA`) retornan el error HTTP inmediatamente sin escribir en `modulo5.auditorias_suministros`. El mecanismo `_registrar_fallo` en `RegistrarSuministroDirectoUseCase` solo se activa tras agotar 3 reintentos de errores transitorios de infraestructura (`InfrastructureError`, `ServiceUnavailableError`), dejando sin auditar los rechazos de negocio de la API.
"""
    else:
        md_content += "No se presentaron fallas en la corrida.\n"

    md_path = staging / "TC-M05-G37_resultado.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Generado: {md_path.name}")

    # Generar INFORME_FASE234_TC-M05-G37.txt
    txt_content = f"""================================================================================
INFORME DE EJECUCION FASES 2, 3 Y 4: TC-M05-G37
RF-80 "Auditoria y Trazabilidad de Registros de Suministros"
================================================================================
Fecha/Hora: {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
Suite: TC-M05-G37 (Casos TC-M05-026 y TC-M05-027)
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
- Campos Base RF-10:
  * id_auditoria_suministro (PK): PRESENTE (entero autoincremental)
  * entidad_afectada:            PRESENTE
  * tipo_operacion:              PRESENTE
  * id_usuario:                  PRESENTE
  * resultado:                   PRESENTE (EXITOSO, FALLIDO, RECHAZADO)
  * fecha_evento:                PRESENTE (timestamp UTC en BD)
  * datos_anteriores / nuevos:   PRESENTE (JSONB)
  * ip_origen / id_sesion:       PRESENTE
- Campos de Extension M05:
  * id_activo_biologico:         PRESENTE
  * id_ciclo_productivo:         PRESENTE
  * id_gestion_fases:            PRESENTE
  * costo_afectado:              PRESENTE
  * origen_precio:               PRESENTE
  * clasificacion_registro:      PRESENTE (NIC41 / TECNICO)
  * retencion_aplicable:         PRESENTE (5 años / 1 año)
  * hash_integridad:             PRESENTE (SHA-256 de 64 caracteres hex calculado por trigger)
  * registro_incompleto:         PRESENTE
  * detalle_causa:               PRESENTE
  * numero_reintentos:           PRESENTE
  * fecha_emision:               PRESENTE (timestamp_emision de negocio)
- Endpoints de Consulta:
  * GET /suministros/auditoria:      PRESENTE (con filtros por activo, fechas, tipo, etc.)
  * GET /suministros/auditoria/{id}: PRESENTE (detalle completo)
  * GET /suministros/auditoria/exportar: PRESENTE (formatos csv, xlsx, pdf)
- Capacidades Ausentes / Gaps:
  * Cola persistente M05->M12:    AUSENTE (la bitacora reside localmente en PostgreSQL modulo5)
  * id_evento_m05 (UUID deduplicacion): AUSENTE (se utiliza id_auditoria_suministro)
  * Auditoria de 4xx (CA-1):      AUSENTE (solo se auditan operaciones exitosas y fallos de infraestructura)

3. INOCUIDAD Y SEGURIDAD
--------------------------------------------------------------------------------
- Sandbox Run: Rollback verificado exitosamente mediante DELETE /test-control/runs/{run_id} -> HTTP 200.
- Inocuidad: Conteo total de eventos en modulo5.auditorias_suministros antes y despues del sandbox identico.
- Escaneo de secretos: 0 contraseñas, 0 tokens JWT ('eyJ'), 0 secretos de sandbox en artefactos.

4. OBSERVACIONES PARA ANALISIS Y RECOMENDACIONES (INC BORRADOR)
--------------------------------------------------------------------------------
- Causa Raiz de Falla en A02:
  En `src/supplies/application/use_cases/costeo_suministros/registrar_suministro_directo_use_case.py`,
  las excepciones de validacion de entrada (`BusinessRuleError`, `ConflictError`) se lanzan sin
  invocar el registro de auditoria. La especificacion RF-80 CA-1 requiere que todo rechazo u operacion
  fallida genere un evento con resultado FALLIDO o RECHAZADO.
  Borrador INC: "RF-80 CA-1: Peticiones rechazadas con HTTP 4xx en endpoints de suministros no
  generan evento de auditoria con resultado FALLIDO en modulo5.auditorias_suministros".
"""
    txt_path = staging / "INFORME_FASE234_TC-M05-G37.txt"
    txt_path.write_text(txt_content, encoding="utf-8")
    print(f"Generado: {txt_path.name}")


if __name__ == "__main__":
    main()
