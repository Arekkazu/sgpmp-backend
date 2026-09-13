# TC-M02-G34 — Resultado de ejecución

**Estado general: BLOQUEADO — 0/4 sub-casos pudieron verificarse. 3/8 assertions PASS, 5/8 FAIL** vía Postman/Newman
contra el backend TEST desplegado. Causas raíz documentadas en `NOTA_BLOQUEO.md`.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G34 (TC-M02-040, 041, 043, 044) |
| RF / CU | RF-37 / CU-02 |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Activos de prueba | 204 (especie 2, para 040/041/043) · 205 (especie 2, para 044) |
| Fecha de ejecución | 2026-09-10, ~00:44 UTC |

## TC-M02-040 — Fecha inválida

```json
// POST /activos-biologicos/204/fases {"id_ciclo_productiva":2,"motivo_cambio":"...","fecha_inicio":"2027-01-01T00:00:00Z"}
// HTTP 500 {"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno..."}
```
Bloqueado por INC-M02-37-01. Adicionalmente, confirmado por lectura de código que `CambiarFaseDTO` no tiene
ningún `field_validator` sobre `fecha_inicio` — no hay validación de fecha futura ni de fecha anterior al inicio de
la fase actual en ningún punto del código. Este es un gap independiente que persistirá tras corregir el crash.

## TC-M02-041 — Salto sin confirmación

```json
// POST /activos-biologicos/204/fases {"id_ciclo_productiva":2,"motivo_cambio":"...","fase_destino_id":9999}
// HTTP 500 (mismo error genérico — fase_destino_id fue descartado por el DTO antes de llegar aqui)
```
Bloqueado por INC-M02-37-01. El campo `fase_destino_id` no existe en `CambiarFaseDTO` (mismo gap ya reportado como
INC-M02-37-02 en TC-M02-G33) — no hay forma de expresar un "salto" fuera de secuencia con la API actual.

## TC-M02-043 — Solapamiento de fases

```json
// POST /activos-biologicos/204/fases {"id_ciclo_productiva":2,"motivo_cambio":"QA-G34 primera fase para solapamiento"}
// HTTP 500 — no se pudo crear ni la primera fase
```
Bloqueado en su precondición: para forzar un solapamiento se necesitan al menos 2 fases; no se pudo crear ni
siquiera la primera. No es posible determinar si existe una validación de solapamiento a nivel de base de datos
(mencionada en notas de desarrollo previas) porque el `INSERT` nunca llega a ejecutarse.

## TC-M02-044 — Activo CERRADO/BAJA

**Precondición bloqueada por un defecto nuevo e independiente** (no INC-M02-37-01):

```json
// Setup: activo 205, especie 2, SIN fase previa (para evitar el codigo afectado por INC-M02-37-01)
// POST /activos-biologicos/205/eventos/baja {"tipo_baja":"muerte","fecha_baja":"...","motivo_baja":"..."}
// HTTP 500 {"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos"}
```

Mensaje de error **distinto** al de INC-M02-37-01 ("Error inesperado en base de datos" vs "Ocurrió un error
interno") — indica un problema real de base de datos, no un `TypeError` de Python. Evidencia comparativa: el mismo
tipo de operación (cambio de estado del activo) **sí funciona** cuando el código pasa `modulo_origen='MANUAL'`
(confirmado en `TC-M02-G22`, `PATCH /{id}/estado` → 200), pero **falla** cuando pasa `modulo_origen='RF-45'` (esta
prueba, `POST /eventos/baja`). Hipótesis con evidencia fuerte (no confirmada por falta de acceso a BD): el CHECK
`chk_historico_modulo_origen_valido` no fue actualizado para aceptar todos los literales de RF que el código ya usa
tras el refactor de centralización de cambio de estado (RF-38/44/45). Detalle completo en `NOTA_BLOQUEO.md`,
sección 2.

Como la precondición no se pudo completar, la petición de prueba real de TC-M02-044 (`POST /fases` sobre el activo
en BAJA) se ejecutó igual sobre el activo aún en estado ACTIVO — y falló con el mismo 500 de INC-M02-37-01, sin
poder aislar si existiría además una validación de estado correcta.

## Resumen de assertions (Newman)

| # | Assertion | Resultado |
|---|---|---|
| 1–2 | Login / Setup activo A | PASS |
| 3 | **TC-M02-040: fecha futura → 400** | **FAIL — 500** |
| 4 | **TC-M02-041: salto sin confirmar → 409** | **FAIL — 500** |
| 5 | **TC-M02-043 precondición: primera fase → 201** | **FAIL — 500** |
| 6 | Setup activo B | PASS |
| 7 | **TC-M02-044 precondición: baja → 201** | **FAIL — 500 (defecto nuevo)** |
| 8 | **TC-M02-044: rechazo sobre activo BAJA → 409** | **FAIL — 500** |

## Evidencia

- [Colección Postman](../TC-M02-G34.postman_collection.json)
- [Nota de bloqueo](../NOTA_BLOQUEO.md)
- [Reporte Newman HTML](newman-TC-M02-G34.html) · [JSON](newman-TC-M02-G34.json)

## Conclusión

TC-M02-G34 no pudo verificar ninguno de sus 4 sub-casos. Tres de ellos (040, 041, 043) están bloqueados por
INC-M02-37-01 ya reportado, con dos gaps adicionales confirmados por código (sin validación de fecha; sin mecanismo
de confirmación no estándar, este último ya reportado como INC-M02-37-02). El cuarto (044) reveló un **defecto
adicional e independiente** en RF-45 (posible CHECK de BD desactualizado tras el refactor de `modulo_origen`), que
bloquea su precondición incluso evitando por completo el código de RF-37. Se recomienda resolver INC-M02-37-01
primero (ya tiene fix de una línea identificado), luego investigar y confirmar el CHECK de `modulo_origen` con
acceso a la base de datos de TEST, y solo entonces reintentar este caso completo.
