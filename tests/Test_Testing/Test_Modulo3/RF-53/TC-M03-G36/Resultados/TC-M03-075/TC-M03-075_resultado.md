# TC-M03-075

Este archivo cubre **solo** TC-M03-075. No hay `.docx` en Módulo 3; la convención del grupo es Markdown bajo `Resultados/`.

## Identificador y nombre

- **ID:** TC-M03-075  
- **Función:** `test_tc_m03_075_medicion_valida_con_conectividad`  
- **Archivo:** `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G36/test_tc_m03_g36.py` (líneas 317–324)  
- **Nombre (script):** medición válida con conectividad; clasificación local `NORMAL` (RF-55.1)

## RF y caso de uso

- **Script:** RF-55 / RF-55.1, CU-02.  
- **Matriz QA referida en el diagnóstico:** RF-53 (visión / `POST /iot/telemetria/vision`).  
No se reasignó el requisito ni se editó el script.

## Objetivo y precondiciones

Objetivo del script: procesar una medición válida dentro de umbral local en el **nodo** y clasificar `NORMAL`, con conectividad.

Precondiciones exigidas y no disponibles: mecanismo RF-55.1 en el repo, umbral local en el nodo, medición válida en el nodo, simulador Edge. No se inventaron IDs ni umbrales.

## Datos de prueba

Ninguno. El script prohíbe fabricar medición, umbral o clasificación. Sin credenciales.

## Herramienta y comando

No se reejecutó G36 el 2026-10-25: el fixture de sesión reescribe `Resultados/TC-M03-G36.json`, `.txt` y `-evidencia.html`.

Evidencia de skip: log pytest **previo** del grupo (incluye también otros tests del mismo archivo).

- Herramienta: pytest 9.0.3, Python 3.13.7, Windows 11  
- Línea de este caso en el log: `test_tc_m03_075_medicion_valida_con_conectividad SKIPPED`

## Fecha, duración y código de salida

El log recuperado no trae timestamp ISO. Resumen del archivo: `3 passed, 2 skipped in 4.18s`. Fecha en `TC-M03-G36.json` (no sobrescrito): `2026-09-28T04:21:13.141359+00:00`. Exit code no consta en ese txt.

## Resultado esperado

Clasificación `NORMAL` en el nodo, con evidencia de procesamiento local.

## Resultado obtenido

SKIPPED. `pytest.skip` con bloqueo: no hay procesamiento Edge RF-55.1 en `src/`. `RecibirEventoEdgeUseCase` exige `clasificacion_rf55` ya calculada (RF-56).

## Estado

**BLOQUEADO.** El runner marcó **SKIPPED**. No es PASSED.

## Evidencias (relativas a esta carpeta)

- `evidencias/TC-M03-G36-pytest.txt` (copia del log original del grupo; no se reescribió el original)  
- Original intacto: `../TC-M03-G36-pytest.txt`

## Incidencias y siguiente acción

Discrepancia RF-53 (visión) vs RF-55.1 (Edge). Confirmar con QA dueña de matriz. Desbloqueo: firmware o simulador que clasifique vs umbral local. Equipo AIOT; sin fecha comprometida aquí. Visión RF-53 en `tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py` no es este ID.
