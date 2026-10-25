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

## ✅ Resultado vigente (2026-09-26): PASS — 10/10 assertions, 0 fallidas

Los 2 gaps de RF-35 del 2026-09-19 están corregidos en TEST (fix `b77f8124`, PR #446
`fix/inc-m02-g22-rf35-patch-activo`, INC-M02-G22). La colección se re-ejecutó **sin cambios**: sus assertions ya
codificaban lo que exige el RF, así que pasaron a verde solas, como se esperaba de la prueba de regresión.

| Caso | WHEN | Resultado real (2026-09-26) |
|---|---|---|
| TC-M02-037 (a) | `PATCH` solo con `estado_activo` | **400** `VAL_ENTRADA`, campo `estado_activo`: "El estado del activo no se puede modificar en esta operación. Use el cambio de estado del activo (RF-44)." — PASS |
| TC-M02-037 (b) | `PATCH` con `estado_activo` + `raza` | **400**, mismo mensaje; ya no se ignora en silencio — PASS |
| TC-M02-038 | `PATCH` de `raza` con el activo `EN_TRATAMIENTO` (evento sanitario `CONTROL_PREVENTIVO` abierto vía RF-41 → 201) | **409** `EVENTO_PENDIENTE_SIN_CERRAR`: "No se puede editar el activo mientras tenga un evento sanitario pendiente sin cerrar (estado actual: EN_TRATAMIENTO)..." — PASS |

La verificación final (`GET`) confirma que el activo sigue `EN_TRATAMIENTO` con la `raza` original: ninguno de los
`PATCH` rechazados alteró datos. Activo propio creado por la corrida (`id_activo_biologico=615`); `GET /health` → 200
antes de ejecutar. Evidencia: `RESULTADOS/TC-M02-G22_resultado.html` (Newman htmlextra, 2026-09-26).

---

## Histórico — FAIL en ambos sub-casos (2026-09-19)

**Estado (2026-09-19): FAIL — 6/10 assertions, 4 fallidas.** Confirmado en vivo contra TEST: RF-35 sigue sin
validar `estado_activo` ni "eventos/estado pendiente" tal como exige el RF. El bloqueo de RF-41 que impedía antes
construir la precondición (`NOTA_BLOQUEO.md`) ya está resuelto — el evento sanitario ahora se registra en `201` y
deja el activo en `EN_TRATAMIENTO` automáticamente, así que la precondición literal de TC-M02-038 ya se construye
por la vía directa, sin workaround. Los 2 gaps de RF-35 de abajo persisten sin cambios desde la primera verificación
del 2026-09-09. Ver `RESULTADOS/TC-M02-G22_resultado.html` para el reporte completo.

La colección Postman (`TC-M02-G22.postman_collection.json`) codifica en sus assertions el comportamiento que **exige
el RF** (no lo que el sistema realmente hace), a propósito: así el reporte de Newman muestra `FAIL` de forma honesta
mientras el gap exista, y pasará a `PASS` automáticamente el día que se corrija — es una prueba de regresión real,
no una que se ajustó para que "diera verde".

### GIVEN / WHEN / THEN (tal como lo exige el RF)

| Caso | GIVEN | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|---|
| TC-M02-037 (a) | Activo individual existente | `PATCH` solo con `estado_activo` | 400, mensaje sobre RF-44 | **400 obtenido, pero con mensaje genérico** ("Al menos un campo debe estar presente"), no el mensaje específico del RF |
| TC-M02-037 (b) | Mismo activo | `PATCH` con `estado_activo` + un campo editable válido | 400 | **200 — FAIL.** El campo se ignora en silencio y la actualización del campo válido se acepta sin ningún aviso |
| TC-M02-038 | Activo con un proceso sanitario abierto sin cerrar (`EN_TRATAMIENTO`, via RF-41 directo) | `PATCH` con un campo editable válido | 409, mensaje sobre eventos pendientes | **200 — FAIL.** La actualización se acepta igual, sin ninguna validación de "eventos/estado pendiente" |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` (verificado `GET /health` → 200 antes de ejecutar).
- Cuenta usada: `admin.test@sgpmp.com.co` (Administrador, `id_rol=1`).
- Newman 6.2.2 + `newman-reporter-htmlextra` 1.23.1.
- Sin acceso a la base de datos PostgreSQL de TEST desde este entorno — toda la verificación es vía API.
- Fecha de ejecución: 2026-09-19.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G22
newman run TC-M02-G22.postman_collection.json -r cli,htmlextra \
  --reporter-htmlextra-export RESULTADOS/TC-M02-G22_resultado.html \
  --suppress-exit-code
```

`--suppress-exit-code` es intencional: mientras el gap exista, Newman termina con código de salida distinto de 0
(4 assertions fallidas) — se documenta así para no romper un pipeline de CI que solo quiera el reporte, pero el
`FAIL` real queda igualmente registrado en el reporte HTML.
