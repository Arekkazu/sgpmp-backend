# TC-M09-G32 — Evaluación V3 (TC-M09-69, RF-17 → Monitoreo)

Tercera evaluación de **TC-M09-69 — Verificar que una modificación de umbral actualice la
configuración utilizada por Monitoreo**. Coexiste con V1 (`RF-17/TC-M09-G32/RESULTADOS`, BLOCKED) y
con `EvaluacionV2/`, ambas de solo lectura e inmutables.

## Adaptación respecto de V2

`EvaluacionV2/run-newman.cjs` es de solo lectura: no existía forma de correlacionar `RF17_BEFORE` con
`MONITORING_BEFORE`, porque el historial no identificaba el umbral aplicado, y por eso no se ejecutó
la modificación. Tras PR #382 el historial expone `id_especie`, `id_umbral_ambiental`,
`valor_min_umbral`, `valor_max_umbral` y `version_umbral`, de modo que la correlación es demostrable
y el flujo puede completarse.

La adaptación consiste en:

- discovery de una lectura histórica **ya vinculada** (activo → especie → variable → umbral RF-17),
  sin generar telemetría nueva;
- verificación del fixture y del contrato desplegado antes de cualquier escritura;
- captura de `RF17_BEFORE` y `MONITORING_BEFORE`;
- un **único** `PATCH` sobre el umbral descubierto, con reconciliación inmediata por `GET` y sin
  reintentos;
- captura de `RF17_AFTER` y `MONITORING_AFTER` sobre la **misma** lectura, más la auditoría del
  umbral como prueba independiente de la transición.

Se conserva de V2 la selección por API, el sanitizado de secretos, los actores y el oráculo de
Monitoreo. El caso mantiene su semántica: una modificación válida del rango debe ser la que Monitoreo
utilice después.

El `RF17_AFTER` se deriva del `BEFORE` real: nunca se usan valores literales fijos. El rango general
se normaliza a la cobertura de los tres niveles contiguos y su límite superior se expande en `DELTA`
unidades dentro del rango físico de la variable; el payload se valida contra las reglas de RF-17
antes de enviarse.

## Ejecución

```bash
# Preflight y discovery: health, contrato, credenciales TEST/DEV, fixture. NO crea RUN_ID.
G32_FASE=preflight TEST_ADMIN_PASSWORD=… DEV_ADMIN_PASSWORD=… \
  G32_PREFLIGHT_OUT=<ruta temporal> NODE_PATH="$(npm root -g)" node run-newman.cjs

# Ejecución oficial: crea la única carpeta de resultados y aplica el único PATCH.
G32_FASE=oficial G32_V3_RUN_ID=G32-REEVAL-V3-YYYYMMDD-HHMMSS \
  TEST_ADMIN_PASSWORD=… DEV_ADMIN_PASSWORD=… NODE_PATH="$(npm root -g)" node run-newman.cjs

# Cierre: consolida seguridad y estado de Git dentro de la misma evidencia.
G32_FASE=cierre G32_V3_RUN_ID=… node run-newman.cjs
```

Las contraseñas se pasan solo como variables de proceso: nunca en scripts, colecciones, JSON,
Markdown, HTML, logs ni evidencias. El script no sobrescribe un RUN_ID existente, y aborta sin
escribir si el contrato no expone los campos de #382, si el fixture está incompleto, si
`MONITORING_BEFORE` no representa el mismo `RF17_BEFORE` o si la modificación propuesta no es válida.

Reejecutable cambiando únicamente datos de runtime: `BASE_URL`, actor, credenciales, `RUN_ID` y,
opcionalmente, `G32_ID_UMBRAL` para fijar la configuración a modificar.

## Resultado

`G32-REEVAL-V3-20260927-063540`: **TC-M09-69 APROBADO**; INC-M09-107-G32 (#298) **corregido y
verificado en V3**. Ver `RESULTADOS/G32-REEVAL-V3-20260927-063540/TC-M09-G32_reevaluacion_V3.md`.
