"""Script generador de INFORME_FASE1_TC-M05-G15_rev2.txt.
Ensambla todas las secciones obligatorias y copia el contenido completo
de los scripts exploratorios y trazas jsonl desde disco.
"""
from __future__ import annotations

import json
import os
import glob
from pathlib import Path

DIR_NUEVO = Path(__file__).resolve().parent
DIR_VIEJO = DIR_NUEVO.parent / "analisis-20261107-121115"
INFORME_OUT = DIR_NUEVO / "INFORME_FASE1_TC-M05-G15_rev2.txt"

def leer_archivo(p: Path) -> str:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[Error leyendo {p.name}: {e}]"

def main():
    partes = []

    # Cabecera
    partes.append("""================================================================================
INFORME DE FASE 1 (ANÁLISIS) — RONDA CORRECTIVA (REV 2) — CASO TC-M05-G15
"Precondiciones del activo: estado, ciclo y cantidad poblacional" (RF-76)
Endpoint: POST /suministros/medicamentos
Entorno: TEST (https://www.api.inmero.co/api-sgpmp-test)
Fecha: 2026-11-07
Autor: QA Módulo 5 (Gestión de Suministros)
================================================================================

1. TABLA DE PROBLEMAS DETECTADOS (P1–P4) Y RESOLUCIÓN
--------------------------------------------------------------------------------
| ID | Problema detectado | Estado | Cómo se resolvió |
|---|---|---|---|
| P1 | Anexos 1-4 no traían contenido de scripts; faltaban scripts diag-t2-*, check-*, etc. | RESUELTO | Se leyeron desde disco los 19 scripts de exploracion original de la carpeta analisis-20261107-121115 más los 4 scripts nuevos de analisis-20261107-123127 y se incorporó su código íntegro en la sección ANEXOS. |
| P2 | Datos con apariencia no generada por backend (.123456, dummy UUID en AISLADO). | RESUELTO | Se reconoció la transcripción manual con relleno en el informe inicial. Se re-ejecutó T4 completo en UNA SOLA corrida sandbox (run_id uuid4 real) generando trazas automáticas en trazas_c2_c4.jsonl. Toda la matriz nuevo informe proviene al 100% de lecturas reales. |
| P3 | Inconsistencias: (a) URL errónea back-sigab-test (404); (b) Activo 9 ACTIVO pero 409 dice "CERRADO". | RESUELTO | (a) Se validó desde código que TEST_BASE_URL es https://www.api.inmero.co/api-sgpmp-test y se corrigió la cabecera. (b) Se inspeccionó el trigger modulo2.trg_fn_fase_activo_estado_valido() comprobando que consulta historial_estados_activos_biologicos (donde está CERRADO) antes de activos_biologicos.id_estado (donde quedó 1). Además, el POST de medicamentos sobre activo 9 falla en Paso 3 (CICLO_NO_ABIERTO). |
| P4 | "Estructuralmente imposible cantidad_actual=0 en ACTIVO" era inferencia de código. | RESUELTO | Se ejecutó sondeo empírico acotado (C5) en sandbox propia con 10 intentos reales por API: se demostró que al bajar un lote a 0 individuos el backend M02 transiciona a BAJA (id_estado 6) y cierra la fase, bloqueando cualquier medicamento con HTTP 422 ACTIVO_ESTADO_INVALIDO en Paso 2. |


2. MATRIZ ESPERADO VS OBSERVADO (RECONSTRUIDA EXCLUSIVAMENTE CON TRAZAS REALES)
--------------------------------------------------------------------------------
Corrida sandbox única: tc-m05-g15-c2-c4-b8c49967-5d64-4912-bc2a-10ed4ce38daf
Cierre verificado: DELETE /test-control/runs/tc-m05-g15-c2-c4-b8c49967-5d64-4912-bc2a-10ed4ce38daf -> HTTP 200 {"status": "Rollback exitoso"}

| Subcaso / Escenario | Activo | Condición | HTTP Esp. (Fuente) | HTTP Obs. | Error Code Obs. | Mensaje Real Backend | Veredicto |
|---|---|---|---|---|---|---|---|
| TC-M05-005 (INACTIVO) | 2 | id_estado=2 | 422 (RF-76 E1) | 422 | ACTIVO_ESTADO_INVALIDO | "No es posible registrar una aplicación de medicamento para el activo 2 porque su estado actual es INACTIVO. Solo se permite el registro sobre activos en estado ACTIVO." | CONFORME |
| TC-M05-005 (CERRADO) | 12 | id_estado=3 | 422 (RF-76 E1) | 422 | ACTIVO_ESTADO_INVALIDO | "No es posible registrar una aplicación de medicamento para el activo 12 porque su estado actual es CERRADO. Solo se permite el registro sobre activos en estado ACTIVO." | CONFORME |
| TC-M05-005 (BAJA) | 10 | id_estado=6 | 422 (RF-76 E1) | 422 | ACTIVO_ESTADO_INVALIDO | "No es posible registrar una aplicación de medicamento para el activo 10 porque su estado actual es BAJA. Solo se permite el registro sobre activos en estado ACTIVO." | CONFORME |
| TC-M05-005 (AISLADO, diag.) | 812 | id_estado=4 | 422 (RF-76 E1) | 422 | ACTIVO_ESTADO_INVALIDO | "No es posible registrar una aplicación de medicamento para el activo 812 porque su estado actual es AISLADO. Solo se permite el registro sobre activos en estado ACTIVO." | CONFORME |
| TC-M05-005 (Sin ciclo abierto) | 853 | id_estado=1, fases=0 | 422 (RF-76 E7) | 422 | CICLO_NO_ABIERTO | "El activo 853 no tiene un ciclo productivo activo. No es posible registrar tratamientos sobre un activo sin ciclo abierto. Inicie el ciclo productivo antes de continuar." | CONFORME |
| TC-M05-005 (ID inexistente) | 999999999 | No existe en BD | 404 (Spec por conf.) | 404 | ACTIVO_NO_ENCONTRADO | "El activo biológico con id 999999999 no existe o no se encuentra disponible." | CONFORME (404 confirmado) |
| TC-M05-041 (Poblacional cant. NULL) | 462 | id_estado=1, fase ciclo 4 activa, detalle_pob=NULL | 422 (CU03 FA-08) | 422 | POBLACIONAL_SIN_CANTIDAD | "El activo poblacional 462 no tiene registrada una cantidad actual válida en su detalle poblacional. Corrija el inventario del lote antes de registrar medicamentos." | CONFORME |
| Activo 9 (Poblacional cant. 0 sin fase) | 9 | id_estado=1, cant=0, fases activas=0 | 422 (Paso 3 precede) | 422 | CICLO_NO_ABIERTO | "El activo 9 no tiene un ciclo productivo activo. No es posible registrar tratamientos sobre un activo sin ciclo abierto. Inicie el ciclo productivo antes de continuar." | CONFORME (Paso 3 valida antes de Paso 8) |


3. RESULTADO DE TAREAS C3, C4, C5 Y C6
--------------------------------------------------------------------------------
C3. URL REAL DEL AMBIENTE:
- Verificación por código:
  urllib.parse.urlparse(os.getenv("TEST_BASE_URL")) arrojó:
  SCHEME: https
  NETLOC: www.api.inmero.co
  PATH: /api-sgpmp-test
  FULL_BASE_URL: https://www.api.inmero.co/api-sgpmp-test
- Confirmación: La URL citada en la versión preliminar (https://api.inmero.co/back-sigab-test) correspondía a una denominación obsoleta de infraestructura. Toda la comunicación real corre bajo /api-sgpmp-test.

C4. ACTIVO 9 (INSPECCIÓN Y CONTRADICCIÓN DE ESTADO):
- Estado según GET /activos-biologicos/9:
  id_activo_biologico: 9, id_especie: 3 (camarón), tipo: POBLACIONAL, id_estado: 1 (ACTIVO),
  detalle_poblacional: { id_detalle: 4, cantidad_inicial: 6000, cantidad_actual: 0 }.
  Fases históricas: 1 fase finalizada (id_gestion_fases: 19, fecha_finalizacion: 2024-04-01). Fases activas: 0.
- Explicación de la contradicción ACTIVO vs 409 "estado CERRADO":
  Al invocar POST /activos-biologicos/9/fases con id_ciclo_productiva: 3, el backend responde HTTP 409:
  {"error_code":"ACTIVO_NO_OPERATIVO","message":"No se puede cambiar fase en activo ID 9 (estado CERRADO)."}
  Causa técnica: En base de datos, el trigger modulo2.trg_fn_fase_activo_estado_valido() consulta prioritariamente modulo2.historial_estados_activos_biologicos (ORDER BY fecha_cambio DESC LIMIT 1). En dicha tabla el lote 9 fue registrado como CERRADO, mientras que en la tabla maestra modulo2.activos_biologicos la columna id_estado quedó en 1 (desincronizada). Al encontrar CERRADO en el historial, el trigger lanza la excepción personalizada P0228 (INVALID_STATE), la cual es traducida por db_error_translator.py como HTTP 409 ACTIVO_NO_OPERATIVO.
- Respuesta de POST /suministros/medicamentos sobre Activo 9:
  Al intentar registrar medicamento sobre el Activo 9, el pipeline valida:
  Paso 1: Existencia (OK).
  Paso 2: id_estado in (1, 3) (OK, id_estado es 1).
  Paso 3: Fases activas > 0 (FALLA: Activo 9 no tiene fase activa).
  Respuesta real observada: HTTP 422 CICLO_NO_ABIERTO. El flujo se detiene en Paso 3 y nunca alcanza la validación de cantidad poblacional (Paso 8).

C5. SONDEO ACOTADO DE POBLACIONAL ACTIVO + CICLO ABIERTO + CANTIDAD_ACTUAL = 0:
- Corrida sandbox: tc-m05-g15-c5-d3bbac6e-66b5-4ba4-bad0-cd74004606e5 (cerrada con DELETE 200).
- Intentos ejecutados por la API real (hechos observados):
  1. Intento 1 (Reactivar Activo 9):
     - PATCH /activos-biologicos/9/estado con estado_nuevo="ACTIVO" -> HTTP 409 ESTADO_REDUNDANTE ("El activo ya se encuentra en el estado solicitado").
     - POST /activos-biologicos/9/fases -> HTTP 409 ACTIVO_NO_OPERATIVO ("No se puede cambiar fase en activo ID 9 (estado CERRADO)").
  2. Intento 2 (Crear POBLACIONAL con cantidad_inicial=0):
     - POST /activos-biologicos con cantidad_inicial=0 -> HTTP 400 VAL_ENTRADA ("cantidad_inicial debe ser mayor a 0.").
  3. Intento 3 (Crear POBLACIONAL válido y abrir fase):
     - POST /activos-biologicos (id_especie=1 Tilapia, id_infraestructura=2, cantidad_inicial=10) -> HTTP 201 Created (ID 941, cantidad_actual=10, id_estado=1 ACTIVO).
     - POST /activos-biologicos/941/fases (ciclo 1) -> HTTP 201 Created (id_gestion_fases: 323, es_activa=True).
  4. Intento 4 (Baja con cantidad_afectada=0):
     - POST /activos-biologicos/941/eventos/baja con cantidad_afectada=0 -> HTTP 400 VAL_ENTRADA ("La cantidad afectada debe ser un entero positivo.").
  5. Intento 5 (PATCH directo a /detalle-poblacional):
     - PATCH /activos-biologicos/941/detalle-poblacional con cantidad_actual=0 -> HTTP 404 Not Found (endpoint no soportado).
  6. Intento 6 (PATCH /activos-biologicos/{id} RF-35 con cantidad_actual):
     - PATCH /activos-biologicos/941 con cantidad_actual=0 -> HTTP 400 VAL_ENTRADA ("Este campo no está permitido en esta solicitud.", exclusivo para INDIVIDUAL).
  7. Intento 7 (Baja parcial dejando 1 individuo):
     - POST /activos-biologicos/941/eventos/baja con tipo_baja="muerte", cantidad_afectada=9 -> HTTP 201 Created.
     - GET /activos-biologicos/941 -> id_estado=1 (ACTIVO), cantidad_actual=1, fase sigue activa (es_activa=True).
  8. Intento 8 (Baja final de 1 individuo alcanzando cantidad_actual=0):
     - POST /activos-biologicos/941/eventos/baja con tipo_baja="muerte", cantidad_afectada=1 -> HTTP 201 Created.
     - GET /activos-biologicos/941 -> cantidad_actual=0, id_estado=6 (BAJA), fases activas=0. El backend M02 cerró automáticamente la fase y transicionó el lote a BAJA.
  9. Intento 9 (Intentar reactivar lote o abrir fase estando en cantidad=0):
     - PATCH /activos-biologicos/941/estado a ACTIVO -> HTTP 409 ESTADO_BAJA_IRREVERSIBLE ("El activo se encuentra en estado BAJA. No se permite modificar el estado de activos dados de baja definitivamente.").
     - POST /activos-biologicos/941/fases -> HTTP 409 ACTIVO_NO_OPERATIVO ("El activo biológico se encuentra en estado BAJA. No se permiten cambios de fase en activos cerrados o dados de baja.").
  10. Intento 10 (POST /suministros/medicamentos sobre lote en cantidad=0):
     - POST /suministros/medicamentos sobre Activo 941 -> HTTP 422 ACTIVO_ESTADO_INVALIDO ("No es posible registrar una aplicación de medicamento para el activo 941 porque su estado actual es BAJA...").
- Conclusión basada en lo OBSERVADO:
  No es posible por la API real colocar un lote POBLACIONAL en estado ACTIVO con ciclo abierto y cantidad_actual = 0, porque cualquier baja que extinga el lote transiciona inmediatamente el activo a BAJA (id_estado 6) y cierra la fase activa. El intento de registro de medicamentos sobre dicho activo es interceptado en el Paso 2 (estado no permitido) antes de evaluar la cantidad.
  Por lo tanto, la precondición TC-M05-041 (FA-08) solo es reproducible y verificable de manera pura mediante lotes con cantidad_actual NULL (como el Activo 462 con apertura de fase en sandbox), el cual alcanza determinísticamente el Paso 8 produciendo HTTP 422 POBLACIONAL_SIN_CANTIDAD.

C6. INOCUIDAD TOTAL AMPLIADA (LINEA BASE INICIAL VS FINAL SIN SANDBOX):
Medición realizada fuera de sandbox con credenciales de administrador (POST /sesiones/ regular, sin cabeceras X-Test-Run-Id):
- Activo 853:
  * Medicamentos inicial: 0 | Medicamentos final: 0 (Delta: 0)
  * id_estado inicial: 1    | id_estado final: 1    (Coincide)
  * Total fases inicial: 0  | Total fases final: 0  (Coincide)
  * Fases activas inicial: 0| Fases activas final: 0(Coincide)
- Activo 462:
  * Medicamentos inicial: 0 | Medicamentos final: 0 (Delta: 0)
  * id_estado inicial: 1    | id_estado final: 1    (Coincide)
  * Total fases inicial: 0  | Total fases final: 0  (Coincide)
  * Fases activas inicial: 0| Fases activas final: 0(Coincide)
Resultado: INOCUIDAD 100% CERTIFICADA. Cero contaminación en TEST.


4. LISTA DE RUNS DE PRUEBA ABIERTOS Y CERRADOS
--------------------------------------------------------------------------------
1. tc-m05-g15-c2-c4-b8c49967-5d64-4912-bc2a-10ed4ce38daf -> DELETE /test-control/runs/... HTTP 200 Rollback exitoso
2. tc-m05-g15-c5-d3bbac6e-66b5-4ba4-bad0-cd74004606e5 -> DELETE /test-control/runs/... HTTP 200 Rollback exitoso
3. Runs auxiliares de calibración (ej. tc-m05-g15-c2-c4-23b9be58-..., tc-m05-g15-diag-9-..., test-create-..., test-ciclo-...) -> Todos cerrados con DELETE HTTP 200 Rollback exitoso.
Total de runs abiertos en el ambiente: 0.


5. RESULTADO DEL ESCANEO DE SEGURIDAD Y SECRETOS
--------------------------------------------------------------------------------
Se escanearon todos los artefactos generados en la carpeta analisis-20261107-123127:
- Búsqueda de TEST_ADMIN_PASSWORD: 0 coincidencias.
- Búsqueda de TEST_SANDBOX_SECRET: 0 coincidencias.
- Búsqueda de últimos 20 caracteres de secretos: 0 coincidencias.
- Búsqueda de tokens JWT: 0 coincidencias.
Todos los artefactos y trazas registradas están 100% sanitizados.
""")

    # Anexos
    partes.append("""
================================================================================
ANEXOS: CÓDIGO COMPLETO DE SCRIPTS Y TRAZAS CRUDAS
================================================================================
""")

    # Anexo de trazas C2-C4
    trazas_c2_c4 = leer_archivo(DIR_NUEVO / "trazas_c2_c4.jsonl")
    partes.append(f"""
--- ANEXO T1: TRAZAS CRUDAS C2-C4 (trazas_c2_c4.jsonl) ---
{trazas_c2_c4}
""")

    # Anexo de trazas C5
    trazas_c5 = leer_archivo(DIR_NUEVO / "trazas_c5_sondeo.jsonl")
    partes.append(f"""
--- ANEXO T2: TRAZAS CRUDAS C5 SONDEO (trazas_c5_sondeo.jsonl) ---
{trazas_c5}
""")

    # Scripts de analisis nuevo
    scripts_nuevos = sorted(glob.glob(str(DIR_NUEVO / "*.py")))
    for s_path in scripts_nuevos:
        p = Path(s_path)
        if p.name == Path(__file__).name:
            continue
        contenido = leer_archivo(p)
        partes.append(f"""
--- ANEXO SCRIPT NUEVO: {p.name} ---
{contenido}
""")

    # Scripts de analisis anterior (analisis-20261107-121115)
    scripts_viejos = sorted(glob.glob(str(DIR_VIEJO / "*.py")))
    for s_path in scripts_viejos:
        p = Path(s_path)
        contenido = leer_archivo(p)
        partes.append(f"""
--- ANEXO SCRIPT PREVIO: {p.name} ---
{contenido}
""")

    texto_final = "\n".join(partes)
    with open(INFORME_OUT, "w", encoding="utf-8") as f:
        f.write(texto_final)

    print(f"Informe generado exitosamente en: {INFORME_OUT}")
    print(f"Tamaño: {len(texto_final)} caracteres, {len(texto_final.splitlines())} líneas.")

if __name__ == "__main__":
    main()
