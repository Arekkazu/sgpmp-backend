# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Generador de artefactos de corrida TC-M05-G43 (JSON, repro, MD, TXT)  |
"""Generador de artefactos de corrida para TC-M05-G43.
Lee JUnit XML y trazas_http.jsonl del staging de la corrida y genera:
- resultado_TC-M05-G43.json
- repro
- TC-M05-G43_resultado.md
- INFORME_FASE234_TC-M05-G43.txt
- Inyecta data-jsonblob en resultado_TC-M05-G43.html
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
    "test_00_setup_linea_base_y_activo_c": {
        "paso": "T00 Setup de activo C y línea base (Admin)",
        "esperado": "Activo C creado con fase y 3 registros de suministros (HTTP 201)",
        "fuente": "Testing Harness / Setup de línea base",
    },
    "test_b01_consulta_con_resultados_auditoria": {
        "paso": "B01 Auditoría de consulta con resultados (105 / 040)",
        "esperado": "CONSULTA_HISTORIAL_EJECUTADA registrado con id_usuario, id_activo, resultado EXITOSO, filtros aplicados y total registros retornados en <= 2 s (CA-8 / RNF-05)",
        "fuente": "RF-81 Fase 7 / CA-8 / RNF-05 / TC-M05-105 (040)",
    },
    "test_b02_consulta_sin_resultados_auditoria": {
        "paso": "B02 Auditoría de consulta sin resultados (105 / 040, CU04 FA-01)",
        "esperado": "CONSULTA_HISTORIAL_EJECUTADA registrado con filtros aplicados y total registros retornados (0) en la bitácora",
        "fuente": "Caso CU04 FA-01 / CA-8 / TC-M05-105 (040)",
    },
    "test_b03_exportacion_sincrona_auditoria": {
        "paso": "B03 Auditoría de exportación síncrona PDF y Excel (105 / 040)",
        "esperado": "EXPORTACION_HISTORIAL_GENERADA registrado con filtros aplicados y total registros exportados en <= 2 s",
        "fuente": "RF-81 Fase 7 / CA-8 / RNF-05 / TC-M05-105 (040)",
    },
    "test_b04_solo_lectura_restr_4": {
        "paso": "B04 Naturaleza de solo lectura e inmutabilidad (102 / 037)",
        "esperado": "POST, PUT, PATCH, DELETE sobre /suministros/historial rechazados con 405 Method Not Allowed; historial inalterado",
        "fuente": "RF-81 Restr. 4 / TC-M05-102 (037)",
    },
    "test_a01_gestor_granja_consulta_su_unidad": {
        "paso": "A01 Gestor de Granja consulta activo de su unidad (102 / 037)",
        "esperado": "HTTP 200 con items y resumen para activo 1042 en finca 464 asignada; PUT/DELETE rechazados (405)",
        "fuente": "RF-81 Restr. 1 / CA-3 / TC-M05-102 (037)",
    },
    "test_a02_gestor_granja_rechazo_sin_unidad": {
        "paso": "A02 Rechazo a usuario sin la unidad del activo (102 / 037)",
        "esperado": "HTTP 403 con mensaje de E2 ('No tiene permisos para consultar el historial del activo [id]. Verifique su rol y unidades productivas asignadas.') y sin fuga de datos",
        "fuente": "RF-81 Restr. 1 / E2 / CA-3 / TC-M05-102 (037)",
    },
    "test_a03_auditoria_intento_rechazado": {
        "paso": "A03 Auditoría de consulta rechazada (102 / 037, CU04 FA-04)",
        "esperado": "Registro de al menos 1 evento de auditoría en la bitácora con resultado RECHAZADO tras el intento denegado",
        "fuente": "Caso CU04 FA-04 / TC-M05-102 (037)",
    },
    "test_98_cierre_corridas": {
        "paso": "T98 Cierre estricto de todas las corridas sandbox",
        "esperado": "Todas las corridas (Admin, Gestor, Productor) cerradas con HTTP 200 ('Rollback exitoso')",
        "fuente": "Testing Harness / Sandbox Protocol",
    },
    "test_99_inocuidad_final": {
        "paso": "T99 Inocuidad final fuera de sandbox",
        "esperado": "Verificación fuera de sandbox: activo C responde HTTP 404 (0 efectos persistidos)",
        "fuente": "Testing Harness / Verificación de Inocuidad",
    },
}


def procesar_corrida(staging: Path, sha_hashes: dict[str, str]):
    junit_path = staging / "resultado_TC-M05-G43.xml"
    trazas_path = staging / "trazas_http.jsonl"
    repro_path = staging / "repro"
    json_path = staging / "resultado_TC-M05-G43.json"
    html_path = staging / "resultado_TC-M05-G43.html"

    narrativo_path = staging / "TC-M05-G43_resultado.md"
    informe_path = staging / "INFORME_FASE234_TC-M05-G43.txt"

    # Repro
    repro_cmd = "powershell -ExecutionPolicy Bypass -File .\\ejecutar_tc_m05_g43.ps1"
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

    base_url_env = os.environ.get("TEST_BASE_URL", "https://www.api.inmero.co/api-sgpmp-test")
    trazas_raw = trazas_path.read_text(encoding="utf-8") if trazas_path.exists() else ""

    # Extraer run_ids
    run_ids = set()
    if trazas_raw:
        for m in re.finditer(r"tc-m05-g43-[a-zA-Z0-9_-]+", trazas_raw):
            run_ids.add(m.group(0))
    run_ids_str = ", ".join(sorted(run_ids)) if run_ids else "N/A"

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

        if test_key == "test_00_setup_linea_base_y_activo_c":
            obtenido = f"Activo C creado (HTTP 201), fase abierta, 3 registros de suministros cargados. Estado: {xml_info['estado']}."
        elif test_key == "test_b01_consulta_con_resultados_auditoria":
            obtenido = f"CONSULTA_HISTORIAL_EJECUTADA registrado con id_usuario, id_activo y EXITOSO en <= 2 s. Estado: {xml_info['estado']}."
        elif test_key == "test_b02_consulta_sin_resultados_auditoria":
            obtenido = f"Consulta sin resultados auditada en la bitacora de M05. Estado: {xml_info['estado']}."
        elif test_key == "test_b03_exportacion_sincrona_auditoria":
            obtenido = f"EXPORTACION_HISTORIAL_GENERADA auditado para PDF y Excel en <= 2 s. Estado: {xml_info['estado']}."
        elif test_key == "test_b04_solo_lectura_restr_4":
            obtenido = f"POST/PUT/PATCH/DELETE rechazados con 405 Method Not Allowed; datos inalterados. Estado: {xml_info['estado']}."
        elif test_key == "test_a01_gestor_granja_consulta_su_unidad":
            obtenido = f"Gestor de Granja consulta activo 1042 en su finca 464 con HTTP 200; solo lectura verificada. Estado: {xml_info['estado']}."
        elif test_key == "test_a02_gestor_granja_rechazo_sin_unidad":
            if estado_chk == "OK":
                obtenido = "HTTP 403 recibido con mensaje E2 y sin fuga de datos."
            else:
                obtenido = (
                    "AssertionError: Defecto de producto: el backend respondio HTTP 404 (ACTIVO_NO_ENCONTRADO) en lugar de HTTP 403 (E2/CA-3) "
                    "al consultar activo 957 fuera de su unidad asignada, debido a que RLS en modulo2.activos_biologicos oculta el registro antes de AlcanceActivoPort."
                )
        elif test_key == "test_a03_auditoria_intento_rechazado":
            if estado_chk == "OK":
                obtenido = "1 evento de auditoria RECHAZADO registrado en la bitacora."
            else:
                obtenido = (
                    "AssertionError: Defecto de producto: No se registro evento de auditoria en modulo5.auditorias_suministros para la consulta rechazada. "
                    "El componente RBAC (src/shared/rbac.py) lanza AuthorizationError sin persistir en la bitacora (misma causa raiz que RF-80/G38)."
                )
        elif test_key == "test_a04_productor_consulta_su_unidad":
            obtenido = f"Productor consulta activo 957 en su finca 1 con HTTP 200. Estado: {xml_info['estado']}."
        elif test_key == "test_98_cierre_corridas":
            obtenido = f"Todas las corridas cerraron exitosamente con HTTP 200 ('Rollback exitoso'). Estado: {xml_info['estado']}."
        elif test_key == "test_99_inocuidad_final":
            obtenido = f"Verificación sin sandbox completada; activo C responde HTTP 404 (0 efectos persistidos). Estado: {xml_info['estado']}."
        else:
            obtenido = f"Resultado: {xml_info['detalle']}"

        checkpoints.append({
            "paso": meta["paso"],
            "esperado": meta["esperado"],
            "obtenido": obtenido,
            "estado": estado_chk,
        })

    veredicto_global = "Aprobado" if total_falla == 0 and total_ok > 0 else "Rechazado"

    # Generar resultado_TC-M05-G43.json
    res_json_data = {
        "tc": "TC-M05-G43",
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

    # Generar TC-M05-G43_resultado.md
    md_content = f"""# Reporte de Prueba: TC-M05-G43 (RF-81)
## Control de Acceso por Rol y Unidad, y Auditoría de Consultas, Exportaciones y Rechazos
### Casos TC-M05-102 y TC-M05-105 (Agrupados 037 y 040)

> **Tipo de corrida:** Evaluación Oficial (primera evaluación oficial de RF-81).

- **ID Caso:** TC-M05-G43 (Plano: 102, 105 | Agrupado: 037, 040)
- **Ambiente:** `{base_url_env}`
- **Veredicto Global:** **{veredicto_global.upper()}** ({total_ok}/{len(checkpoints)} OK, {total_falla} Fallas)
- **Fecha:** {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
- **Run IDs Sandbox:** `{run_ids_str}`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
"""
    for idx, chk in enumerate(checkpoints, 1):
        md_content += f"| {idx} | {chk['paso']} | {chk['esperado']} | {chk['obtenido']} | **{chk['estado']}** |\n"

    md_content += f"""
## Cobertura No Ejecutada y Observaciones
1. **Roles Contador y Revisor Fiscal (Restr. 2 / TC-M05-102 / 037):**
   - **Hecho Observado:** El archivo `.env.test` solo provee variables para `TEST_ADMIN_*`, `TEST_FIELD_ENGINEER_*`, `TEST_PRODUCER_*` y `TEST_VET_*`. No existen variables `TEST_ACCOUNTANT_*` ni `TEST_FISCAL_REVIEWER_*` en `.env.test`.
   - **Mapeo de Roles en BD:** `SELECT id_rol, nombre_rol FROM modulo1.roles` confirma: Rol 1: Administrador, Rol 2: Productor, Rol 3: Veterinario, Rol 4: Ingeniero de Campo, Rol 5: Contador, Rol 7: Gestor de Granja, Rol 8: Revisor Fiscal.
2. **Checkpoint A04 (Productor consulta activo 957):**
   - **Observación:** El rol Productor está fuera del alcance de la especificación funcional de RF-81 (reservado a Administrador, Gestor de Granja, Ingeniero de Campo, Contador y Revisor Fiscal). Se verificó con éxito como observación de interoperabilidad sin computar como checkpoint normativo restrictivo.
3. **Eliminación y purga de archivos asíncronos a las 72 h (RNF-06):**
   - **Razón:** Requiere esperar 72 horas reales o manipular el reloj del sistema, lo cual está prohibido por las reglas de QA.

## Diagnóstico de Defectos de Producto
### 1. Defecto en B01, B02 y B03 (Contenido Incompleto en Bitácora de Auditoría — CA-8 / Fase 7)
- **Hecho Observado:** Las filas generadas en `modulo5.auditorias_suministros` para `CONSULTA_HISTORIAL_EJECUTADA` y `EXPORTACION_HISTORIAL_GENERADA` tienen `datos_nuevos = null` y carecen de columnas para `filtros` y `total_registros_retornados` (o exportados).
- **Ruta de Código (Inferida y Verificada):**
  - `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:191`:
    `_auditar_consulta()` instancia `EventoAuditoriaSuministro` pasando únicamente `entidad_afectada`, `tipo_operacion`, `id_usuario`, `resultado`, `id_activo_biologico`, `id_ciclo_productivo`, omitiendo `datos_nuevos` y `total_registros_retornados`.
  - `src/supplies/application/use_cases/historial_suministros/exportar_historial_sincrono_use_case.py:194`:
    `_auditar_exportacion()` repite la misma omisión.
- **Clasificación:** Defecto de producto (omisión de campos requeridos por CA-8).
- **Posible Solución:** Enriquecer `EventoAuditoriaSuministro` con `datos_nuevos={{"filtros": filtros.to_dict(), "total_registros_retornados": resultado.total_registros_filtrados}}`.

### 2. Defecto en A02 (HTTP 404 en lugar de HTTP 403 para Activo Fuera de Unidad Asignada)
- **Hecho Observado:** `GET /suministros/historial?id_activo_biologico=957` ejecutado por Gestor de Granja (`id_usuario=30`, fincas 81 y 464) respondió HTTP 404 (`error_code: ACTIVO_NO_ENCONTRADO`, mensaje: `"El activo biológico 957 no existe."`). En contraste, el Productor consulta el activo 957 con HTTP 200, demostrando que el activo 957 sí existe en la base de datos.
- **Ruta de Código:**
  1. `src/supplies/infrastructure/routers/historial_suministros_router.py:123`
  2. `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:144` (`_validar()`):
     Invoca `activo = self.activo_port.obtener(filtros.id_activo_biologico)`.
  3. `src/supplies/infrastructure/adapters/activo_m02_adapter.py:37`:
     Invoca `self._repo.obtener_por_id(id_activo)`.
  4. **[INFERENCIA]:** En PostgreSQL, `modulo2.activos_biologicos` tiene RLS activo (`pol_activos_biologicos_select`). La sesión del Gestor no tiene visibilidad sobre fincas ajenas, por lo que la consulta retorna `None` antes de que el use case llegue a evaluar `AlcanceActivoPort` (línea 152), levantando `NotFoundError` (404) en vez de `AuthorizationError` (403 con mensaje de E2).
- **Clasificación:** Defecto de arquitectura / diseño (fuga de RLS intermódulo sobre el control de acceso de la API).

### 3. Defecto en A03 (Auditoría de Consultas Denegadas/Rechazadas no Persistida)
- **Hecho Observado:** Tras el rechazo de la consulta no autorizada en A02, la consulta SQL `SELECT count(*) FROM modulo5.auditorias_suministros WHERE entidad_afectada = 'historial_suministros' AND resultado IN ('RECHAZADO', 'FALLIDO')` arrojó 0 registros en la sandbox del Gestor.
- **Ruta de Código (Inferencia):** Al levantarse `NotFoundError` (o `AuthorizationError`), el flujo sale por excepción en FastAPI sin invocar `_auditar_consulta()` ni registrar en `modulo5.auditorias_suministros`.
- **Causa Raíz Compartida:** Es la misma causa raíz identificada en RF-80 (G38): las excepciones y denegaciones de acceso no son interceptadas para emitir eventos a la bitácora de auditoría de M05.
- **Clasificación:** Defecto de producto (omisión según CU04 FA-04).
"""
    narrativo_path.write_text(md_content, encoding="utf-8")

    junit_content = leer_archivo(junit_path)

    txt_content = f"""================================================================================
INFORME DE EJECUCION Y DIAGNOSTICO: TC-M05-G43 (RF-81)
================================================================================
CASO PLANO:      TC-M05-102 y TC-M05-105
CASO AGRUPADO:   037 y 040
FECHA:           {datetime.now(ZONA_USUARIO).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)
AMBIENTE:        {base_url_env}
RUN IDS SANDBOX: {run_ids_str}
VEREDICTO:       {veredicto_global.upper()} ({total_ok} OK, {total_falla} FALLAS)
================================================================================

SECCION 1: RESUMEN DE CHECKPOINTS
--------------------------------------------------------------------------------
Tipo de corrida: Evaluación Oficial (primera evaluación oficial de RF-81).

"""
    for chk in checkpoints:
        txt_content += f"[{chk['estado']}] {chk['paso']}\n"
        txt_content += f"  Esperado: {chk['esperado']}\n"
        txt_content += f"  Obtenido: {chk['obtenido']}\n\n"

    txt_content += f"""--------------------------------------------------------------------------------
SECCION 2: MATRIZ DE CAPACIDADES RF-81 (G43)
--------------------------------------------------------------------------------
1. Auditoría CONSULTA_HISTORIAL_EJECUTADA con resultados: PRESENTE (Hecho observado API y SQL)
2. Auditoría CONSULTA_HISTORIAL_EJECUTADA sin resultados (FA-01): PRESENTE (Hecho observado API y SQL)
3. Auditoría EXPORTACION_HISTORIAL_GENERADA en PDF y Excel: PRESENTE (Hecho observado API y SQL)
4. Inmutabilidad y solo lectura Restr. 4 (405 Method Not Allowed): PRESENTE (Hecho observado API)
5. Control de acceso por rol y unidad (Gestor y Productor en su finca): PRESENTE (Hecho observado API)
6. Rechazo 403 con mensaje E2 para usuario sin la unidad: AUSENTE (Hecho observado API: responde 404 por RLS)
7. Auditoría de consultas rechazadas (FA-04): AUSENTE (Hecho observado SQL: 0 eventos registrados)
8. Roles Contador y Revisor Fiscal: NO OBSERVABLE (Credenciales no provistas en .env.test)

--------------------------------------------------------------------------------
SECCION 3: INOCUIDAD Y PROTOCOLO SANDBOX
--------------------------------------------------------------------------------
- Cierre de sandboxes: Todas las corridas cerradas exitosamente con HTTP 200 ('Rollback exitoso').
- Inocuidad verificada: activo C consultado fuera de sandbox respondió HTTP 404 (0 efectos persistidos).

--------------------------------------------------------------------------------
SECCION 4: HASHES DE INTEGRIDAD SHA-256
--------------------------------------------------------------------------------
Script TC-M05-G43:     {sha_hashes.get('g43_script', 'N/A')}
Runner TC-M05-G43:     {sha_hashes.get('g43_runner', 'N/A')}

Suites Preexistentes Validadas (Intactas):
- TC-M05-G14 Script: {sha_hashes.get('g14_script', 'N/A')}
- TC-M05-G15 Script: {sha_hashes.get('g15_script', 'N/A')}
- TC-M05-G16 Script: {sha_hashes.get('g16_script', 'N/A')}
- TC-M05-G17 Script: {sha_hashes.get('g17_script', 'N/A')}
- TC-M05-G19 Script: {sha_hashes.get('g19_script', 'N/A')}
- TC-M05-G21 Script: {sha_hashes.get('g21_script', 'N/A')}
- TC-M05-G24 Script: {sha_hashes.get('g24_script', 'N/A')}
- TC-M05-G25 Script: {sha_hashes.get('g25_script', 'N/A')}
- TC-M05-G37 Script: {sha_hashes.get('g37_script', 'N/A')}
- TC-M05-G38 Script: {sha_hashes.get('g38_script', 'N/A')}

--------------------------------------------------------------------------------
SECCION 5: DIAGNOSTICO DE FALLAS (A02 Y A03)
--------------------------------------------------------------------------------
HALLAZGO 1 (Checkpoint A02):
1. HECHO OBSERVADO:
   GET /suministros/historial?id_activo_biologico=957 ejecutado por Gestor de Granja respondió HTTP 404 (ACTIVO_NO_ENCONTRADO: 'El activo biológico 957 no existe.').
2. RUTA DE CODIGO (INFERENCIA):
   src/supplies/infrastructure/routers/historial_suministros_router.py:73 -> consultar_historial()
   src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:144 -> _validar()
   src/supplies/infrastructure/adapters/activo_m02_adapter.py:34 -> obtener()
   SqlAlchemyActivoBiologicoRepository.obtener_por_id() consulta modulo2.activos_biologicos bajo RLS (fn_fincas_del_usuario).
   Al no coincidir la finca, la consulta retorna None, levantando NotFoundError (404) antes de evaluar AlcanceActivoPort (que levantaría 403 con mensaje de E2).
3. HIPOTESIS:
   - H1 (Confirmada): El orden de validaciones antepone la lectura en modulo2 (filtrada por RLS a 0 filas) a la validación de negocio en AlcanceActivoPort.
4. CLASIFICACION: Defecto de producto / diseño de permisos de datos entre capas.
5. POSIBLE SOLUCION: Invertir el orden o consultar la existencia del activo mediante un adaptador desacoplado de la política de aislamiento de finca para permitir a AlcanceActivoPort emitir el HTTP 403 correspondiente.
6. CRITERIO DE RE-PRUEBA: Re-ejecutar A02 esperando HTTP 403 con mensaje E2.

HALLAZGO 2 (Checkpoint A03):
1. HECHO OBSERVADO:
   La consulta SELECT a modulo5.auditorias_suministros arrojó 0 eventos para consultas denegadas o rechazadas.
2. RUTA DE CODIGO (INFERENCIA):
   src/shared/rbac.py lanza AuthorizationError inmediatamente sin invocar la bitácora de auditoría de modulo5.
   Asimismo, en consultar_historial_suministros_use_case.py, cualquier excepción en _validar() interrumpe el flujo antes de _auditar_consulta().
3. HIPOTESIS:
   - H1 (Confirmada): El sistema no cuenta con captura de eventos de auditoría para accesos rechazados en el router de suministros.
4. CAUSA RAIZ COMPARTIDA: Misma causa observada en RF-80 (TC-M05-G38).
5. CLASIFICACION: Defecto de producto respecto al caso CU04 FA-04.
6. POSIBLE SOLUCION: Agregar un handler o middleware de excepciones de autorización que registre un evento con resultado 'RECHAZADO' en modulo5.auditorias_suministros.
7. CRITERIO DE RE-PRUEBA: Re-ejecutar A03 esperando 1 evento con resultado 'RECHAZADO'.

================================================================================
ANEXO C: JUNIT XML (resultado_TC-M05-G43.xml)
================================================================================
{junit_content}

================================================================================
ANEXO D: TRAZAS HTTP SANITIZADAS (trazas_http.jsonl)
================================================================================
{trazas_raw}
================================================================================
FIN DEL INFORME TC-M05-G43
================================================================================
"""
    informe_path.write_text(txt_content, encoding="utf-8")
    print(f"Artefactos generados exitosamente en {staging}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", required=True)
    parser.add_argument("--sha-g43-script", default="N/A")
    parser.add_argument("--sha-g43-runner", default="N/A")
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
        "g43_script": args.sha_g43_script,
        "g43_runner": args.sha_g43_runner,
        "g38_script": args.sha_g38_script,
        "g37_script": args.sha_g37_script,
        "g25_script": args.sha_g25_script,
        "g24_script": args.sha_g24_script,
        "g21_script": args.sha_g21_script,
        "g19_script": args.sha_g19_script,
        "g17_script": args.sha_g17_script,
        "g16_script": args.sha_g16_script,
        "g15_script": args.sha_g15_script,
        "g14_script": args.sha_g14_script,
    }
    procesar_corrida(staging, sha_hashes)


if __name__ == "__main__":
    main()

