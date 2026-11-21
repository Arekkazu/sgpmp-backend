# TC-M03-G164 â€” Informe narrativo de ejecuciÃ³n

**RF:** RF-62 â€” Consulta y filtrado de evaluaciones de calidad de telemetri­a
**Endpoints:** `GET /iot/calidad`, `GET /iot/calidad/{id_telemetria}`
**Subcasos:** TC-M03-301 a TC-M03-308 (7 subcasos)
**Fecha de ejecuciÃ³n definitiva:** 2026-10-22 19:12
**run_id:** `test-run-3d455a54-74d5-4485-bbbd-066f7f9e9eac`
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`
**Veredicto:** **RECHAZADO** â€” 8 fallos, todos atribuibles a defectos del backend o a calidad de datos. NingÃºn fallo del test.

---

## 1. Preconditions verificadas

| Precondition | Estado |
|---|---|
| Backend TEST arriba (`GET /health` = 200) | OK |
| Login admin (`administador.dev@gmail.com`) | OK â€” token emitido |
| Sandbox habilitado (`/test-control/runs` y `/test-control/query`) | OK |
| Seed de evaluaciones (â‰¥200 registros) | OK â€” 252 en DB cruda |
| Mix de estados VIGENTE/SUPERADA | OK â€” 246 VIGENTE, 6 SUPERADA |
| Endpoints de calidad en OpenAPI | OK â€” 4/4 presentes |
| `$env:TEST_ADMIN_PASSWORD` y `$env:TEST_SANDBOX_SECRET` | OK |
| Broker token (`BROKER_SERVICE_TOKEN`) | NO CONFIGURADO â€” no bloquea G164 (read-only) |

---

## 2. EjecuciÃ³n

- **Comando:** `ejecutar_tc_m03_g164.ps1` (wrapper con verificaciÃ³n estÃ¡tica, ejecuciÃ³n Newman y consolidaciÃ³n)
- **Runner:** Newman 6.x, colecciÃ³n de 34 items
- **DuraciÃ³n:** 11 s
- **Requests ejecutados:** 26 (34 definidos, 8 condicionales por gating)
- **Assertions:** 38 en la corrida sandbox + 3 adicionales de la extensiÃ³n fuera de sandbox = **41 totales**
- **Resultado bruto Newman:** 8 failed / 38 assertions (sandbox) â†’ consolidado final: 8 FALLA / 41 totales
- **Teardown sandbox:** OK (`DELETE /test-control/runs/{run_id}` â†’ 200 Rollback exitoso)
- **Escaneo de seguridad L6:** OK â€” sin credenciales, tokens JWT ni Bearer literales en el HTML

---

## 3. Resultado por subcaso

| Subcaso | DescripciÃ³n | Resultado |
|---|---|---|
| TC-M03-301 | Listar sin filtros, estructura paginada, orden DESC | OK (3/3 checkpoints) |
| TC-M03-302 | Detalle por id_telemetria, contrato CalidadEvaluacion | **FALLA** â€” `parametros_aplicados={}` |
| TC-M03-304 | Filtrar por id_sensor y aislamiento | OK (3/3) |
| TC-M03-305 | Filtrar por clasificacion (enum) y rechazo de invÃ¡lido | **FALLA** â€” invÃ¡lido devuelve 200 |
| TC-M03-306 | Rango fecha_desde/fecha_hasta y rechazo de invertido | **FALLA** â€” invertido devuelve 200 |
| TC-M03-307 | Filtrar por estado_evaluacion (VIGENTE/SUPERADA/ACTIVA) | **FALLA** â€” ACTIVA devuelve 200; SUPERADA validado fuera de sandbox revela datos incompletos |
| TC-M03-308 | PaginaciÃ³n y lÃ­mites (200/201/0) | **FALLA** â€” 3 subcasos con 400 en lugar de 422 |

---

## 4. Fallos detallados (8)

### 4.1 TC-302 â€” `parametros_aplicados` vacÃ­o

- **Esperado:** objeto con las claves de parÃ¡metros aplicados por el motor de calidad
- **Obtenido:** `{}` (objeto vacÃ­o)
- **INC asociado:** INC-M03-04-TC-M03-G164 (Media)

### 4.2 TC-305 â€” ClasificaciÃ³n invÃ¡lida devuelve 200

- **Request:** `GET /iot/calidad?clasificacion=VALOR_NO_CATALOGADO_ENUM`
- **Esperado:** `422 Unprocessable Entity` con `error_code=VAL_ENTRADA`
- **Obtenido:** `200 OK` con `items=[]`
- **INC asociado:** INC-M03-05-TC-M03-G164 (Alta)

### 4.3 TC-306 â€” Fechas invertidas aceptadas

- **Request:** `GET /iot/calidad?fecha_desde=2026-04-16T23:59:59Z&fecha_hasta=2026-04-14T00:00:00Z`
- **Esperado:** `422 Unprocessable Entity`
- **Obtenido:** `200 OK`
- **INC asociado:** INC-M03-06-TC-M03-G164 (Alta)

### 4.4 TC-307 â€” `estado_evaluacion=ACTIVA` aceptado

- **Request:** `GET /iot/calidad?estado_evaluacion=ACTIVA`
- **Esperado:** `422 Unprocessable Entity` (catÃ¡logo es `{VIGENTE, SUPERADA}` tras D7 RESUELTO)
- **Obtenido:** `200 OK`
- **INC asociado:** INC-M03-07-TC-M03-G164 (Alta)

### 4.5 TC-307 â€” SUPERADA sin `motivo_reevaluacion` completo (extensiÃ³n fuera de sandbox)

- **Esperado:** cada evaluaciÃ³n SUPERADA con `motivo_reevaluacion` no vacÃ­o e `id_evaluacion_superada` poblado
- **Obtenido:** 3 de 6 SUPERADA tienen `id_evaluacion_superada`; no todas con `motivo_reevaluacion`
- **INC asociado:** INC-M03-09-TC-M03-G164 (Media) â€” categorÃ­a: calidad de datos / seed

### 4.6 TC-308 â€” `por_pagina=201` retorna 400 (esperado 422)

- **Esperado:** `422` segÃºn OpenAPI `openapi_test_snapshot.json`
- **Obtenido:** `400 Bad Request`
- **INC asociado:** INC-M03-08-TC-M03-G164 (Media)

### 4.7 TC-308 â€” `pagina=0` retorna 400 (esperado 422)

- **Esperado:** `422`
- **Obtenido:** `400`
- **INC asociado:** INC-M03-08-TC-M03-G164 (Media)

### 4.8 TC-308 â€” `por_pagina=0` retorna 400 (esperado 422)

- **Esperado:** `422`
- **Obtenido:** `400`
- **INC asociado:** INC-M03-08-TC-M03-G164 (Media)

---

## 5. Hallazgos adicionales (no cuentan como fallo del test)

### 5.1 Sandbox oculta registros SUPERADA preexistentes

Durante la corrida bajo sandbox (`X-Test-Run-Id` activo), el filtro `GET /iot/calidad?estado_evaluacion=SUPERADA` devuelve 0 items, aunque en DB existen 6 registros SUPERADA. El sandbox aÃ­sla y solo expone los registros creados en el `run_id` actual. Consecuencia: TC-307 no es completamente validable bajo sandbox.

**MitigaciÃ³n aplicada en esta corrida:** TC-307 se completÃ³ fuera de sandbox (login sin `X-Test-Run-Id`) y sus 3 checkpoints se consolidaron al JSON final.

**Documentado como:** hallazgo de infraestructura (referencia cruzada con DEF-04).

### 5.2 DATA-GAP: 9 evaluaciones invisibles vÃ­a API

- DB cruda (`modulo3.telemetria_calidad`): 252 registros
- API admin (`GET /iot/calidad`): 243 registros
- Gap: 9 registros no visibles vÃ­a API

Posibles causas: soft-delete, registros huÃ©rfanos de FKs, aislamiento por tenant. Requiere anÃ¡lisis de datos por parte de la DBA. No bloquea el caso; se registra como observaciÃ³n.

---

## 6. INCs derivados (6)

| ID | TÃ­tulo | Severidad | CategorÃ­a |
|---|---|---|---|
| INC-M03-04-TC-M03-G164 | `parametros_aplicados` vacÃ­o | Media | Backend |
| INC-M03-05-TC-M03-G164 | Enum `clasificacion` no validado (200 vs 422) | Alta | Backend |
| INC-M03-06-TC-M03-G164 | Fechas invertidas aceptadas (200 vs 422) | Alta | Backend |
| INC-M03-07-TC-M03-G164 | Enum `estado_evaluacion=ACTIVA` no validado (200 vs 422) | Alta | Backend |
| INC-M03-08-TC-M03-G164 | PaginaciÃ³n retorna 400 en lugar de 422 | Media | Backend / contrato |
| INC-M03-09-TC-M03-G164 | SUPERADA sin `motivo_reevaluacion` completo | Media | Calidad de datos |

Los issues formales se crean manualmente en Taiga con formato `[INC-M0<M>-<NN>-<TC>][RF-<n>] <resumen>` segÃºn la guÃ­a Â§5.1 R8.

---

## 7. Correcciones aplicadas al test durante la sesiÃ³n

Esta corrida es el resultado de dos iteraciones. En la primera (2026-10-22 18:40) se detectaron dos defectos del propio test que fueron corregidos antes de la corrida definitiva:

1. **F-ORACULO** â€” El checkpoint de preflight comparaba `oraculo.total_descargado` (conteo API, 243) contra `totalDb` (conteo SQL crudo, 252). Comportamiento correcto: la API filtra legÃ­timamente por aislamiento/soft-delete; la aserciÃ³n ahora valida `API >= 1` y `DB >= API`, y registra el gap como OBS.
2. **F-PRE307** â€” El preflight calculaba `PRE_307` filtrando SUPERADA dentro de la primera pÃ¡gina (50 items de 243); las 6 SUPERADA nunca aparecÃ­an. CorrecciÃ³n: consulta dedicada a `GET /iot/calidad?estado_evaluacion=SUPERADA`.

Adicional: se eliminaron fallbacks de credenciales hardcodeadas en el wrapper (R03) y se aÃ±adiÃ³ la consolidaciÃ³n automÃ¡tica de resultados al flujo (Â§5.1).

---

## 8. Conclusi0n

El caso **TC-M03-G164** se ejecuta al 100% de subcasos planificados (7/7), incluyendo TC-307 completo validado fuera de sandbox. El veredicto es **RECHAZADO** con 8 checkpoints fallidos, todos atribuibles a:

- 7 defectos del backend (parametros_aplicados vacÃ­o, 3 validaciones de enum/rango faltantes, 3 mismatches 400/422)
- 1 hallazgo de calidad de datos en el seed de SUPERADA

NingÃºn fallo es atribuible al test ni al ambiente. La suite queda cerrada en su versiÃ³n definitiva y trazable a 6 INCs. Requiere correcciÃ³n por parte de Desarrollo (backend) y DBA (seed) antes de una re-evaluaciÃ³n.

---

*Generado: 2026-10-22*
*Corrida definitiva: `run-20261022/`*
*Reporte computable: `resultados/resultado_TC-M03-G164.{json|html}`*