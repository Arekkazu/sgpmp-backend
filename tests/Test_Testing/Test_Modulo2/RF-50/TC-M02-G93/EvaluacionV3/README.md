# TC-M02-G93 — Evaluación V3 (RF-50 · CU12)

Tercera evaluación de las reglas negativas de datos consolidados:

- **TC-M02-155** — rechazar acceso de módulo sin scope autorizado para el `tipo_dato` (403).
- **TC-M02-156-A** — rechazar `fecha_inicio > fecha_fin` (400).
- **TC-M02-156-B** — rechazar rango futuro (400).
- **TC-M02-157** — rechazar consulta NIC-41 con métricas de PESO insuficientes (422).
- Verificación complementaria de la advertencia de peso fuera del rango.

Coexiste con los artefactos V1 (`construir_coleccion.cjs`, `test_tc_m02_g93.json`, `Resultados/`) y con
`EvaluacionV2/Resultados`, todos inmutables.

## Adaptación respecto de V1/V2

V1 se ejecutó con un consumidor humano porque en el ambiente no existían la identidad técnica M06 ni el
scope granular por `tipo_dato`; TC-155 y TC-157 quedaron BLOQUEADOS. V2 no se ejecutó.

Se conservan de V1 el endpoint, el fixture de referencia, el patrón del constructor de colección y la
regla de no exposición de datos consolidados en los rechazos. La adaptación:

- descubre la identidad técnica, su rol, sus permisos y los recursos de scope, sin identificadores
  fijos;
- revalida el fixture y **deriva los rangos de los datos reales**: el rango NIC-41 como una ventana
  pasada dentro del ciclo con cero métricas de PESO, y el de la verificación complementaria como una
  ventana con PESO dentro y el más reciente fuera;
- calcula el rango futuro contra la fecha observada del ambiente;
- satisface la única precondición que faltaba —alcance de la identidad sobre la finca del activo— por
  el endpoint oficial, preservando las asignaciones activas preexistentes;
- ejecuta un control positivo previo y los cuatro escenarios con la identidad técnica como consumidor.

El control positivo es indispensable: sin él, el 403 de TC-M02-155 no sería atribuible al scope
granular y podría confundirse con un rechazo de autenticación, de permiso general o de alcance.

## Un solo runner, un solo RUN_ID

```bash
# Preflight: contrato, identidad, provisión, fixture, rangos y alcance. NO crea RUN_ID.
G93_FASE=preflight M06_EMAIL=… M06_PASSWORD=… QA_ADMIN_EMAIL=… QA_ADMIN_PASSWORD=… \
  G93_PREFLIGHT_OUT=<ruta temporal> NODE_PATH="$(npm root -g)" node run-newman.cjs

# Preparación de datos: asigna al consumidor la finca del activo por el endpoint oficial.
G93_FASE=preparar M06_EMAIL=… M06_PASSWORD=… QA_ADMIN_EMAIL=… QA_ADMIN_PASSWORD=… \
  G93_PREPARAR_OUT=<ruta temporal> node run-newman.cjs

# Ejecución oficial (solo si el gate se cumple): crea la única carpeta y ejecuta los casos.
G93_FASE=oficial G93_V3_RUN_ID=G93-REEVAL-V3-YYYYMMDD-HHMMSS \
  M06_EMAIL=… M06_PASSWORD=… QA_ADMIN_EMAIL=… QA_ADMIN_PASSWORD=… NODE_PATH="$(npm root -g)" node run-newman.cjs

# Cierre: consolida seguridad y estado de Git en la misma evidencia.
G93_FASE=cierre G93_V3_RUN_ID=… node run-newman.cjs
```

Las contraseñas se pasan solo como variables de proceso; nunca en la colección, el runner, el Markdown,
el HTML, el JSON, los reportes ni Git. El runner no sobrescribe un RUN_ID existente y aborta sin
ejecutar los casos si falta cualquiera de las diecisiete condiciones del gate, incluido el control
positivo en 200.

La fase de preparación exige que el ejecutor tenga permiso de actualización sobre Usuarios, lo
comprueba antes de escribir, envía el conjunto completo de fincas —la unión de las activas
preexistentes con la del activo— y nunca usa la propia identidad técnica para asignarse su alcance.

La colección se genera en `test_tc_m02_g93_v3.json` a partir de los parámetros descubiertos, siguiendo
el patrón constructor de V1. Reejecutable cambiando solo datos de runtime: `BASE_URL`, `M06_EMAIL`,
`M06_PASSWORD`, `G93_ID_ACTIVO`, los rangos derivados y `RUN_ID`.

## Resultado

`G93-REEVAL-V3-20260927-191233`:

| Caso | Resultado |
|---|---|
| **TC-M02-G93** | **APROBADO** |
| TC-M02-155 | APROBADO — 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO` |
| TC-M02-156-A | APROBADO — 400 `PARAMETROS_INVALIDOS`, rango invertido |
| TC-M02-156-B | APROBADO — 400 `PARAMETROS_INVALIDOS`, rango futuro |
| TC-M02-157 | APROBADO — 422 `METRICAS_PESO_INSUFICIENTES` |

Newman: 33 assertions, 0 fallidas. Incidencias #242, #390, #391, #392 y #393: **CORREGIDAS Y
VERIFICADAS EN V3**. Ver
`RESULTADOS/G93-REEVAL-V3-20260927-191233/TC-M02-G93_reevaluacion_V3.md`.
