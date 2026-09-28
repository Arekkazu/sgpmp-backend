# TC-M02-G92 — Evaluación V3 (TC-M02-154 / TC-M02-159 · RF-50 / RF-51 · CU12)

Tercera evaluación del consumo de datos analíticos e indicadores zootécnicos de M02 por una identidad
técnica M04 autorizada. Coexiste con los artefactos V1 (`test_tc_m02_g92.json`, `Resultados/`) y con
`EvaluacionV2/Resultados`, todos inmutables.

## Adaptación respecto de V1/V2

V1 y V2 cerraron en BLOQUEADO porque la identidad técnica M04 no estaba provisionada en TEST: la
colección V1 era un gate de solo lectura sobre OpenAPI y los dos subcasos nunca se ejecutaron. Se
conservan de V1 los endpoints y los parámetros de consulta; la adaptación:

- autentica la identidad técnica exacta suministrada, sin normalizarla ni sustituirla;
- descubre por nombre el rol y sus permisos efectivos, incluidos los scopes por tipo de dato;
- revalida el fixture, su finca y sus mediciones de peso, y **recalcula el indicador de forma
  independiente** con aritmética decimal exacta, sin literales fijos;
- mide por separado el acceso a la consulta canónica de datos consolidados, a una sección para la que
  el rol sí tiene scope y al endpoint de indicadores, de modo que un rechazo por scope no se confunda
  con uno por alcance;
- satisface la única precondición preparable —alcance sobre la finca del fixture— por el endpoint
  oficial, preservando las asignaciones activas preexistentes;
- ejecuta los dos subcasos con oráculo y clasifica cada uno por separado.

## Un solo runner, un solo RUN_ID

```bash
# Preflight: git, health, OpenAPI, identidad, RBAC, alcance, fixture y expected. NO crea RUN_ID.
G92_FASE=preflight M04_TEST_EMAIL=… M04_TEST_PASSWORD=… QA_ADMIN_EMAIL=… QA_ADMIN_PASSWORD=… \
  G92_PREFLIGHT_OUT=<ruta temporal> NODE_PATH="$(npm root -g)" node run-newman.cjs

# Preparación de datos: asigna al consumidor la finca del fixture por el endpoint oficial.
G92_FASE=preparar M04_TEST_EMAIL=… M04_TEST_PASSWORD=… QA_ADMIN_EMAIL=… QA_ADMIN_PASSWORD=… \
  G92_PREPARAR_OUT=<ruta temporal> node run-newman.cjs

# Ejecución oficial: crea la única carpeta y ejecuta los dos subcasos.
G92_FASE=oficial G92_V3_RUN_ID=G92-REEVAL-V3-YYYYMMDD-HHMMSS \
  M04_TEST_EMAIL=… M04_TEST_PASSWORD=… QA_ADMIN_EMAIL=… QA_ADMIN_PASSWORD=… NODE_PATH="$(npm root -g)" node run-newman.cjs

# Cierre: consolida seguridad y estado de Git en la misma evidencia.
G92_FASE=cierre G92_V3_RUN_ID=… node run-newman.cjs
```

Las contraseñas se pasan solo como variables de proceso; nunca en la colección, el runner, el Markdown,
el HTML, el JSON, los reportes ni Git. El runner exige las precondiciones comunes para ejecutar
cualquier subcaso, y si a un subcaso le falta su precondición lo clasifica BLOQUEADO y ejecuta el otro,
sin ocultar ninguno. Un 403 por scope granular se clasifica como precondición ausente, no como defecto.

`QA_ADMIN_EMAIL` / `QA_ADMIN_PASSWORD` se usan para el descubrimiento de solo lectura y para la
preparación del alcance; nunca como consumidor del caso. La preparación comprueba antes el permiso de
actualización sobre Usuarios del ejecutor.

La colección se genera en `test_tc_m02_g92_v3.json` a partir de los parámetros descubiertos.
Reejecutable cambiando solo datos de runtime: `BASE_URL`, identidad, `G92_ID_ACTIVO`, las fechas
derivadas y `RUN_ID`.

## Resultado

`G92-REEVAL-V3-20260927-200452`:

| Caso | Resultado |
|---|---|
| **TC-M02-G92** | **BLOQUEADO** |
| TC-M02-154 | BLOQUEADO — 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO`: el rol no tiene scope sobre `metricas`, que la consulta completa exige |
| TC-M02-159 | **APROBADO** — 200 en 142 ms, `ganancia_peso` disponible, 0.9677 kg/día |

Newman: 26 assertions, 4 fallidas (todas del subcaso bloqueado). #241: bloqueo de identidad resuelto y
verificado; queda pendiente conceder al rol el scope sobre `datos_analiticos_metricas`. Ver
`RESULTADOS/G92-REEVAL-V3-20260927-200452/TC-M02-G92_reevaluacion_V3.md`.
