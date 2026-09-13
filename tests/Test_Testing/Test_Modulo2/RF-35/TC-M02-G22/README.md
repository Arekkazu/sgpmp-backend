# TC-M02-G22 — Reglas de flujo para cambio de estado y eventos pendientes en la gestión individual

**CU-02 · RF-35 — Gestión Individual de Activos Biológicos.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-037) Rechazar cambio de estado directo desde RF-35 · (TC-M02-038) Bloquear operación si hay eventos pendientes |
| Tipo | Validación / Pruebas funcionales |
| Herramienta | API — Postman |
| Precondiciones | 1. Activo individual existente. 2. Activo con eventos sanitarios/biológicos pendientes sin cerrar |
| Datos de entrada | 1. Cambio de `estado_activo` directo → 400 (debe usarse RF-44). 2. Eventos pendientes sin cerrar → 409, bloquea la operación |
| Pasos | 1. Intentar modificar `estado_activo` directamente desde la ficha de gestión individual. 2. Intentar solicitar cambio de estado o actualización crítica |
| Resultado esperado | 1. `400 BAD REQUEST` — "El cambio de estado debe realizarse mediante el módulo de gestión de estados (RF-44)". 2. `409 CONFLICT` — "El activo presenta eventos pendientes que deben ser gestionados antes de continuar" |
| Responsable | Juan Manuel |
| Prioridad | Alta |
| Endpoints | `GET /activos-biologicos/{id_activo}` · `PATCH /activos-biologicos/{id_activo}` |

## ⚠️ Resultado: FAIL en ambos sub-casos — gaps ya confirmados en código, ahora verificados en vivo

**Estado general: FAIL — TC-M02-037 y TC-M02-038 no se comportan como exige el RF.** Esto no es una falla de esta
prueba ni de datos mal preparados: es la primera vez que este proyecto verifica en vivo, contra el TEST desplegado,
dos gaps que ya estaban documentados por lectura de código en `anotaciones/modulo_2/estado.md` (RF-35: *"No valida
eventos pendientes... pese a que el RF lo exige explícitamente"*). Ver `RESULTADOS/TC-M02-G22_resultado.md` para el
detalle completo, y `NOTA_BLOQUEO.md` para un defecto independiente de RF-41 que bloqueó la vía directa de armar la
precondición de TC-M02-038.

La colección Postman (`TC-M02-G22.postman_collection.json`) codifica en sus assertions el comportamiento que **exige
el RF** (no lo que el sistema realmente hace), a propósito: así el reporte de Newman muestra `FAIL` de forma honesta
mientras el gap exista, y pasará a `PASS` automáticamente el día que se corrija — es una prueba de regresión real,
no una que se ajustó para que "diera verde".

### GIVEN / WHEN / THEN (tal como lo exige el RF)

| Caso | GIVEN | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|---|
| TC-M02-037 (a) | Activo individual existente | `PATCH` solo con `estado_activo` | 400, mensaje sobre RF-44 | **400 obtenido, pero con mensaje genérico** ("Al menos un campo debe estar presente"), no el mensaje específico del RF |
| TC-M02-037 (b) | Mismo activo | `PATCH` con `estado_activo` + un campo editable válido | 400 | **200 — FAIL.** El campo se ignora en silencio y la actualización del campo válido se acepta sin ningún aviso |
| TC-M02-038 | Activo con un proceso sanitario abierto sin cerrar (`EN_TRATAMIENTO`) | `PATCH` con un campo editable válido | 409, mensaje sobre eventos pendientes | **200 — FAIL.** La actualización se acepta igual, sin ninguna validación de "eventos/estado pendiente" |

### Por qué TC-M02-038 se adaptó (ver NOTA_BLOQUEO.md)

La precondición literal ("Activo con eventos sanitarios/biológicos pendientes sin cerrar") no se pudo construir vía
`POST /activos-biologicos/{id}/eventos/sanitario` (RF-41): ese endpoint devuelve **500** de forma reproducible para
`DIAGNOSTICO` y `CONTROL_PREVENTIVO` en este entorno TEST — un defecto independiente y bloqueante, documentado en
`NOTA_BLOQUEO.md`. Como workaround **funcionalmente equivalente** para lo que RF-35 necesita verificar (¿bloquea el
endpoint una operación mientras el activo tiene algo abierto sin resolver?), se usó `PATCH /{id}/estado` (RF-44,
endpoint no afectado por el bloqueo) para dejar el activo en `EN_TRATAMIENTO` antes de intentar el `PATCH` de
RF-35. El resultado (200, sin bloqueo) es válido de todas formas: si ni siquiera un estado `EN_TRATAMIENTO`
persistente bloquea la operación, es aún menos probable que exista alguna otra validación de "eventos pendientes"
en el código — confirmado además por búsqueda exhaustiva (`grep -ri "pendiente"` sobre todo `src/biological_assets`
no encontró ninguna coincidencia relevante).

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` (verificado `GET /health` → 200 antes de ejecutar).
- Cuenta usada: `admin.test@sgpmp.com.co` (Administrador, `id_rol=1`).
- Newman 6.2.2 + `newman-reporter-htmlextra` 1.23.1.
- Sin acceso a la base de datos PostgreSQL de TEST desde este entorno — toda la verificación es vía API.
- Fecha de ejecución: 2026-09-09.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G22
newman run TC-M02-G22.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G22.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G22.html \
  --suppress-exit-code
```

`--suppress-exit-code` es intencional: mientras el gap exista, Newman termina con código de salida distinto de 0
(4 assertions fallidas) — se documenta así para no romper un pipeline de CI que solo quiera el reporte, pero el
`FAIL` real queda igualmente registrado en los tres reportes (CLI, JSON, HTML).
