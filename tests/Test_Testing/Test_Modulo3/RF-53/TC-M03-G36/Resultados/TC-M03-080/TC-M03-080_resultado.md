# TC-M03-080

Solo este caso. Convención: Markdown en `Resultados/` (no hay `.docx` en Módulo 3).

## Identificador y nombre

- **ID:** TC-M03-080  
- **Función:** `test_tc_m03_080_medicion_valida_sin_conectividad`  
- **Archivo:** `test_tc_m03_g36.py` líneas 327–335  
- **Nombre:** medición válida **sin conectividad**; clasificación local y buffer del nodo

## RF y caso de uso

RF-55.1 (clasificación en Edge) y buffer **RF-54** (AIOT). CU-02.

## Objetivo y precondiciones

Clasificar en el nodo con red cortada y persistir en buffer **del dispositivo**, no `almacenado_buffer` del backend.

Precondiciones no cumplidas: buffer local del nodo, mock de conectividad Edge, clasificador RF-55.1.

## Datos de prueba

Ninguno. Sin credenciales.

## Herramienta y comando

G36 no se reejecutó (evitar sobrescribir json/txt/html canónicos). Log previo del grupo.

Línea de este caso: `test_tc_m03_080_medicion_valida_sin_conectividad SKIPPED`

## Fecha, duración y código de salida

Mismo archivo de origen: `3 passed, 2 skipped in 4.18s`. JSON del grupo: `2026-09-28T04:21:13Z`. Exit code no consta en el txt.

## Resultado esperado

Clasificación local y dato en cola del nodo, independiente de HTTP Dev.

## Resultado obtenido

SKIPPED. El script anota que `almacenado_buffer` en el backend no demuestra buffer Edge sin red.

## Estado

**BLOQUEADO** (SKIPPED en runner).

## Evidencias

- `evidencias/TC-M03-G36-pytest.txt` (copia; el original no se modificó)  
- `evidencias/NOTA_ORIGEN_LOG.md`

## Incidencias y siguiente acción

Dependencia firmware RF-54/RF-55. Confirmar con AIOT. Criterio: medición clasificada con red cortada y evidencia de cola local.
