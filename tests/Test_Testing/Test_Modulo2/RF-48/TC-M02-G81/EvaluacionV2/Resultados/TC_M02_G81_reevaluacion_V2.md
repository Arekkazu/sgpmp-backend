# REEVALUACIÓN V2 — TC-M02-G81

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF / CU | RF-48 — Transferencia interna de activos biológicos / CU10C |
| Subcasos | TC-M02-138, **TC-M02-139 (reformulado)**, TC-M02-140, TC-M02-141 |
| Rama | `qa/juan-esteban-re-evaluacion-m02` |
| HEAD V2 | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`. Tras `git fetch origin`, `HEAD...origin/test` = `0 0` |
| Ambientes | **TEST compartido** para TC-138, TC-139 y TC-140 · **LOCAL AISLADO** solo para TC-141 |
| Base funcional | INC-M02-87-G81 / Issue #238: RF-48 **siempre transfiere el activo completo** |
| Ejecutables | Colección V2 controlada `EvaluacionV2/test_tc_m02_g81_v2.json` (derivada de V1) · Pytest V1 `test_tc_m02_g81_rollback.py` **sin cambios** |
| Newman (TEST) | 1 ejecución · 24 peticiones · **103 aserciones · 0 fallos** |
| Pytest (LOCAL) | 1 ejecución · **6 tests · 6 aprobados** |
| DEF-G81-01 (TC-140) | **CORREGIDO** |
| BLOQ-G81-02 (TC-139) | **BLOQUEO RESUELTO POR DEFINICIÓN FUNCIONAL** y TC-139 reformulado **APROBADO** |
| Regresiones | Ninguna |
| **Veredicto global** | ✅ **APROBADO — CORREGIDO / SIN REGRESIÓN** (V1: RECHAZADO) |

> **Esta V2 sustituye a la V2 anterior de G81**, que concluía BLOQUEADO al tratar la ausencia de un campo de cantidad como un gap del contrato. Esa conclusión se descartó tras la definición funcional INC-M02-87-G81. Los artefactos de la V2 anterior fueron retirados por QA antes de esta ejecución, y esta reevaluación se ejecutó desde cero.

---

## 1. Gate

### 1.1 Rama

| Verificación | Resultado |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| `git rev-parse HEAD` | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git fetch origin` + `git rev-list --left-right --count HEAD...origin/test` | `origin/test` = `a6220fc8` · `0 0` ✅ |
| `git status --short` | Sin cambios en archivos versionados. Solo aparecen carpetas `EvaluacionV2/` sin seguimiento |

### 1.2 Integridad V1

| Archivo | `git hash-object --no-filters` | Blob en `HEAD` (normalizado autocrlf) |
|---|---|---|
| `test_tc_m02_g81.json` | `4dff93f18bff9fa7ef4a0797bcba875f2258fa2e` ✅ | `3b1b2192…` = archivo |
| `test_tc_m02_g81_rollback.py` | `9b44bac2fefd9f00bdb0bd5197aa5f58264848c6` ✅ | `55eab197…` = archivo |
| `construir_coleccion.cjs` | `612def44a758e71937805c104f37e37754dc116b` ✅ | `6c2797c6…` = archivo |

`Resultados/` de V1 está intacta: los cuatro archivos coinciden con `HEAD` y conservan su fecha de modificación (2026-09-12). **`construir_coleccion.cjs` no se ejecutó.**

### 1.3 Fixtures TC-138/140

BD con `SET default_transaction_read_only = on`: `member_qa` / `sgpmp_test` / `transaction_read_only = on`. Consulta del 2026-09-19 a las 09:00 UTC.

| Uso | Activo | Estado | Infra / asociación vigente | Válido |
|---|---:|---|---|---|
| TC-138 Productor | 284 `QAJE-TRF-NOACT` | **INACTIVO (2)** | 48 / [48] | ✅ |
| TC-138 Administrador | 288 `QAJE-CREC-CERRADO` | **CERRADO (5)** | 48 / [48] | ✅ |
| TC-140 Productor | 292 `QAJE-TRF-OK` | ACTIVO (1) | 48 / [48] | ✅ |
| TC-140 Administrador | 295 `QAJE-DAT-COMPL` | ACTIVO (1) | 48 / [48] | ✅ |

La infraestructura destino es la **51** (`Corral QA JE Destino OK`): activa, de la finca 57, especie 40, tipo Corral, capacidad 200 y ocupación 1. En la ejecución, la colección confirmó con `GET /292/transferencias/disponibles` que figura como destino disponible (A5). Los fixtures aíslan las mismas condiciones que en V1.

**Seguridad de TC-140.** E-10 (`FECHA_TRANSFERENCIA_FUTURA`, `BusinessRuleError` → 422) se evalúa en el caso de uso antes de cualquier escritura, así que el envío con fecha futura no puede persistir datos.

### 1.4 Fixture poblacional TC-139

| Condición | Estado real (09:00 UTC) | Cumple |
|---|---|---|
| Activo 281 | existe, `POBLACIONAL`, especie 40 | ✅ |
| Estado | ACTIVO (1) | ✅ |
| `cantidad_actual` / `cantidad_inicial` | 100 / 100 | ✅ |
| Infraestructura / asociación vigente | 48 / **una sola**, [48] | ✅ |
| Historial / movimientos previos | 1 / 0 | ✅ |
| Transferencia en curso | Ninguna. E-01 es un bloqueo de fila `FOR UPDATE NOWAIT`, sin estado persistente, así que dos POST secuenciales no colisionan | ✅ |
| Origen 48 | `Corral QA JE Origen`: activa, finca 57, especie NULL, capacidad 1000, ocupación 221 | ✅ |
| Destino 51 | activa, finca 57, especie 40 (C1 ✅), Corral (C2 ✅) | ✅ |
| C3 ida | 1 + **100** = 101 ≤ 200 | ✅ |
| C3 regreso | (221 − 100) + **100** = 221 ≤ 1000 | ✅ |
| `GET /281/transferencias/disponibles` | `[51]`: el propio sistema lo considera transferible | ✅ |

Línea base global: `movimientos` 26 filas (máximo 30) · `historial_infraestructura_activo` 365 (máximo 403) · `activos_biologicos` 363 (máximo 452) · `detalles_activos_biologicos_poblacionales` 99 filas, Σ `cantidad_actual` = 30707 · bitácora RF48, 25 registros. Por API, el listado del Productor da `total_registros` = 23.

### 1.5 Contrato actual y definición INC-M02-87-G81

`GET /openapi.json`, verificado por el SETUP de la colección (8/8):

| Elemento | Valor | Interpretación V2 |
|---|---|---|
| `RegistrarTransferenciaDTO` | `infraestructura_origen_id`, `infraestructura_destino_id`, `fecha_transferencia`, `motivo_transferencia` | **COHERENTE CON RF-48**: la transferencia es completa por diseño |
| `cantidad` / `parcial` / `unidades` / `subconjunto` | No existe ninguno | Coherente; no es bloqueo, gap ni defecto |
| Respuestas declaradas | `201, 401, 403, 404, 409, 422, 500` | 409 (TC-138), 422 (TC-140) y 500 (TC-141) declarados |

No existe ningún mecanismo de parcialidad que contradiga la definición funcional, así que no fue necesario detenerse (§15 del paquete).

### 1.6 Preflight LOCAL

| Campo | Valor |
|---|---|
| Servicio | Clúster PostgreSQL **18.3** desechable, creado desde cero con `initdb` en el directorio temporal de la sesión y arrancado con `pg_ctl` en `127.0.0.1:5465`, sin tocar ningún servicio del equipo |
| Base | `sgpmp_g81_v2_local_test`, nueva, sin reutilizar ninguna base previa |
| `DATABASE_URL` / `TC_G81_DSN` | `postgresql://postgres:***@127.0.0.1:5465/sgpmp_g81_v2_local_test`, exportadas explícitamente. No existe `.env` y `load_dotenv()` no sobrescribe variables ya definidas |
| Esquema | `alembic upgrade head` → `1147428cd8fb (head)`, 383 tablas `modulo*` |
| Compatibilidad del Pytest V1 | Bloque transaccional sin cambios: a) UPDATE historial → b) INSERT historial → c) UPDATE activo → (c2, solo POBLACIONAL) → d) `transferencia_repo.guardar` → `commit`, con `rollback` y auditoría `TRANSFERENCIA_FALLIDA` en `except`. El catálogo C2 local solo tiene reglas para `Estanque`, así que el Corral del fixture es válido. **Se reutilizó sin cambios** |
| NO uso de `158.69.200.27:5448/sgpmp_test` | **Confirmado** por el preflight codificado y los dos `test_preflight_*` |

Al terminar, el clúster se detuvo y eliminó, y el puerto 5465 quedó libre.

---

## 2. Ejecución TEST

**Colección V2 controlada** `EvaluacionV2/test_tc_m02_g81_v2.json` (`--no-filters` `da3b9aa6…`). Se generó a partir de la V1 con un script determinista y la V1 no se tocó. `git diff --no-index` da 328 líneas añadidas y 7 eliminadas:

| Cambio | Detalle |
|---|---|
| `info.name` / `info.description` | Describen la V2 reformulada |
| Gate de OpenAPI (SETUP) | Solo cambian el nombre de la petición y la **redacción** de dos tests: "CONTRATO TC-M02-139: … sin cantidad (coherente con RF-48: transferencia completa por diseño, INC-M02-87-G81)" y "… no existe mecanismo de parcialidad (coherente con RF-48 …)". **Misma lógica**: 4 campos exactos y ninguno de cantidad |
| Nueva carpeta `02-TC-M02-139-REFORMULADO` | 8 peticiones: PRE ×2, POST Productor, INTERMEDIA ×2, POST Administrador, FINAL ×2 |
| Renumeración | `02-TC-M02-140` → `03-TC-M02-140` · `03-VERIFICACION-NO-PERSISTENCIA` → `04-…` |
| Sin cambios | Cálculo de `fecha_hoy` / `fecha_futura` (hoy + 5), logins, A5, estados ANTES, TC-138, TC-140 y verificaciones DESPUÉS de 284/288/292/295 |

**Protección de la secuencia.** Cada petición de TC-139 evalúa sus condiciones de integridad. Si alguna falla, ejecuta `postman.setNextRequest(null)` y la colección se detiene, de modo que el POST del Administrador no se habría enviado si la verificación intermedia hubiera fallado. En la ejecución real no se activó.

**Ejecución única**, 2026-09-19, de 09:02:18 a 09:02:24 UTC:

```bash
newman run "$G/EvaluacionV2/test_tc_m02_g81_v2.json" -r cli,json,htmlextra \
  --reporter-json-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g81_v2.json" \
  --reporter-htmlextra-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g81_v2.html"
```

Resultado: **24 peticiones · 103 aserciones · 0 fallos** (V1: 16 peticiones · 64 aserciones · 4 fallos).

---

## 3. TC-M02-138 — activo no ACTIVO (E-03)

| Actor | Activo | V1 | V2 | Mensaje V2 | Aserciones | Evolución |
|---|---|---|---|---|---:|---|
| Productor | 284 (INACTIVO), 48 → 51 | 409 `ACTIVO_NO_ACTIVO` | **409 `ACTIVO_NO_ACTIVO`** | *El activo QAJE-TRF-NOACT se encuentra en estado INACTIVO. Solo se pueden transferir activos en estado ACTIVO.* | 7/7 | **SIN REGRESIÓN** |
| Administrador | 288 (CERRADO), 48 → 51 | 409 `ACTIVO_NO_ACTIVO` | **409 `ACTIVO_NO_ACTIVO`** | *El activo QAJE-CREC-CERRADO se encuentra en estado CERRADO. Solo se pueden transferir activos en estado ACTIVO.* | 7/7 | **SIN REGRESIÓN** |

Sin `id_movimiento` y Δ dominio = 0 (§6).

---

## 4. TC-M02-139 REFORMULADO

### 4.1 Definición funcional

INC-M02-87-G81 / Issue #238: *RF-48 siempre transfiere el activo biológico completo*. Un activo INDIVIDUAL se transfiere entero; uno POBLACIONAL se transfiere con la totalidad de su `cantidad_actual`. **No existe división parcial de un lote entre infraestructuras.**

El subcaso vigente es **positivo**: la transferencia de un lote debe realizarse sobre la totalidad del lote, sin división. No se envió `cantidad` ni ningún otro campo inventado. Cada POST llevó exactamente los 4 campos del contrato, comprobado por aserción.

### 4.2 PRE

| Verificación (API) | Valor |
|---|---|
| `GET /activos-biologicos/281` | 200 · id 281 · POBLACIONAL · ACTIVO · **infra 48** · **cantidad_actual 100** (6/6) |
| `GET /activos-biologicos` (Productor) | `total_registros` = **23** (2/2) |

### 4.3 Productor 48 → 51

`POST /activos-biologicos/281/transferencias` con `token_productor` (usuario 35). Aserciones: **7/7**.

```json
{"id_movimiento":31,"id_activo_biologico":281,
 "infraestructura_origen":"Corral QA JE Origen","infraestructura_destino":"Corral QA JE Destino OK",
 "fecha_transferencia":"2026-09-19T00:00:00Z",
 "motivo_transferencia":"QA G81 V2 TC-M02-139 Productor - transferencia completa de lote",
 "mensaje":"Transferencia registrada exitosamente. El activo fue transferido a Corral QA JE Destino OK en fecha 2026-09-19."}
```

**HTTP 201** · `id_activo_biologico` 281 · `id_movimiento` 31 · origen y destino correctos · el mensaje confirma la transferencia.

### 4.4 Verificación intermedia

| Verificación | Resultado |
|---|---|
| `GET /activos-biologicos/281` (API) | 200 · **mismo id 281** · POBLACIONAL · ACTIVO · **infra 51** · **cantidad_actual 100** (6/6) |
| `GET /activos-biologicos` (API) | `total_registros` = **23** = PRE: no apareció ningún activo nuevo (2/2) |
| Historial (BD, reconstruido tras la ejecución) | El historial 229 (48) se cerró a las 09:02:22.027Z y en ese mismo instante se abrió el **404 (51)**. Entre ambos POST, la única asociación vigente fue la 51 |
| Movimiento (BD) | **+1** (id 31, usuario 35, 48 → 51) |

Transferencia íntegra: la guarda permitió continuar con el Administrador.

### 4.5 Administrador 51 → 48

`POST /activos-biologicos/281/transferencias` con `token_admin` (usuario 1). Aserciones: **8/8**, incluida la que comprueba que es un movimiento distinto del 31.

```json
{"id_movimiento":32,"id_activo_biologico":281,
 "infraestructura_origen":"Corral QA JE Destino OK","infraestructura_destino":"Corral QA JE Origen",
 "fecha_transferencia":"2026-09-19T00:00:00Z",
 "motivo_transferencia":"QA G81 V2 TC-M02-139 Administrador - transferencia completa de lote",
 "mensaje":"Transferencia registrada exitosamente. El activo fue transferido a Corral QA JE Origen en fecha 2026-09-19."}
```

### 4.6 POST final

| Verificación | PRE | POST final | Δ |
|---|---|---|---|
| API `GET /281` | infra 48 · cantidad 100 | **infra 48 · cantidad 100** (6/6) | — |
| API `total_registros` (Productor) | 23 | **23** (2/2) | 0 |
| BD: movimientos de 281 | 0 | **2** (31 y 32) | **+2** |
| BD: historial de 281 | 1 | **3** (229, 404, 405) | **+2** |
| BD: asociaciones vigentes de 281 | [48] | **[48]**, una sola (405) | — |
| BD: `modulo2.movimientos` | 26 / máximo 30 | 28 / máximo 32 | +2 (solo 31 y 32, ambos del 281) |
| BD: `historial_infraestructura_activo` | 365 / máximo 403 | 367 / máximo 405 | +2 (solo 404 y 405, ambos del 281) |
| BD: `activos_biologicos` | 363 / máximo 452 | 363 / máximo 452 | **0** (ningún id > 452) |
| BD: `detalles_activos_biologicos_poblacionales` | 99 filas | 99 filas | **0** |
| BD: Σ `cantidad_actual` poblacional | 30707 | 30707 | **0** |
| BD: 281 `cantidad_actual` / `cantidad_inicial` | 100 / 100 | **100 / 100** | 0 |
| Ocupación 48 / 51 | 221 / 1 | 221 / 1 | 0 |

Historial completo del 281:

| id_historial | infra | fecha_inicio | fecha_fin | usuario |
|---:|---:|---|---|---:|
| 229 | 48 | 2026-06-01 08:00:00Z | 2026-09-19 09:02:22.027Z | 1 |
| **404** | 51 | 2026-09-19 09:02:22.027Z | 2026-09-19 09:02:22.704Z | 35 |
| **405** | 48 | 2026-09-19 09:02:22.704Z | *NULL (vigente)* | 1 |

Movimientos del 281: **31** (usuario 35, `salida`, 48 → 51) y **32** (usuario 1, `salida`, 51 → 48). La tabla `movimientos` no tiene columna de cantidad. Cada movimiento referencia el **activo completo** 281, cuyo único detalle poblacional conservó `cantidad_actual = 100` antes, entre y después de ambos movimientos.

La igualdad de ubicación PRE/POST (48 → 48) se debe al **ciclo controlado de dos actores**, no a la ausencia de transferencia. Los 2 movimientos y las 2 filas históricas son la **persistencia esperada** de TC-139 y no contaminación accidental.

**Efecto colateral esperado del producto.** La `densidad` del lote pasó de NULL a **0.1**. En cada transferencia se recalcula contra la superficie del destino: DEF-RF48-02 / INC-M02-40-G28, paso c2 del caso de uso. El valor final corresponde a 100 / 1000 m² de la infraestructura 48. No afecta a ningún criterio de TC-139 y no representa una división.

### 4.7 Integridad del lote — criterios de §33

| # | Criterio | Resultado |
|---:|---|---|
| 1 | Productor 201 en 48 → 51 | ✅ (movimiento 31) |
| 2 | Administrador 201 en 51 → 48 | ✅ (movimiento 32) |
| 3 | `cantidad_actual` = 100 en todo momento | ✅ PRE, INTERMEDIA y FINAL por API; BD final 100 |
| 4 | Sigue existiendo el mismo activo 281 | ✅ |
| 5 | No se creó un segundo activo poblacional | ✅ activos Δ 0, ningún id > 452, `total_registros` 23 constante |
| 6 | No se creó un segundo detalle poblacional fraccionario | ✅ detalles Δ 0, Σ cantidades Δ 0 |
| 7 | Una sola asociación vigente tras cada transferencia | ✅ tras el POST 1: [51] (404); tras el POST 2: [48] (405) |
| 8 | El movimiento del Productor registra el lote completo | ✅ 31 referencia el activo 281 entero, sin cantidad parcial |
| 9 | El movimiento del Administrador registra el lote completo | ✅ 32, ídem |
| 10 | Movimientos = PRE + 2 | ✅ (0 → 2 en el 281; 26 → 28 global) |
| 11 | Historial = PRE + 2 | ✅ (1 → 3 en el 281; 365 → 367 global) |
| 12 | Sin evidencia de división 40/60, 1/99 u otra | ✅ |

**TC-M02-139: APROBADO.**

---

## 5. TC-M02-140 — fecha futura (E-10)

Fecha enviada: `fecha_futura` = hoy + 5 días, calculada por la colección.

| Actor | Activo | V1 | V2 | Respuesta V2 | Aserciones | Evolución |
|---|---|---|---|---|---:|---|
| Productor | 292, 48 → 51 | 400 `VAL_ENTRADA` | **422 `FECHA_TRANSFERENCIA_FUTURA`** | *La fecha de transferencia no puede ser posterior a la fecha actual.* · `field = fecha_transferencia` | 7/7 | **CORREGIDO** |
| Administrador | 295, 48 → 51 | 400 `VAL_ENTRADA` | **422 `FECHA_TRANSFERENCIA_FUTURA`** | idéntico | 7/7 | **CORREGIDO** |

422 es el código de la ficha para E-10 y está declarado en el contrato. Sin persistencia (§6).

---

## 6. Persistencia TEST

| Subcaso | Esperado | Observado |
|---|---|---|
| TC-138 (284, 288) | Δ dominio = 0 | ✅ estados 2/5 sin cambio · infra 48 · asociación [48] · historial 1 · movimientos 0 |
| TC-139 (281) | movimientos +2 · historial +2 · cantidad, activos y detalles sin cambio · ubicación final 48 | ✅ exactamente eso (§4.6) |
| TC-140 (292, 295) | Δ dominio = 0 | ✅ 292: infra 48, historial 3, movimientos 2 (los mismos del PRE) · 295: infra 48, historial 1, movimientos 0 |
| Global | movimientos +2 e historial +2, solo del 281 | ✅ nuevos movimientos {31, 32} y nuevos historiales {404, 405}, todos del activo 281 |

**Auditoría RF-52**, que no es persistencia indebida. La bitácora RF48 pasó de 25 a 31 registros, **+6**, uno por POST:

- `TRANSFERENCIA_RECHAZADA` para 284/35 y 288/1 (`ACTIVO_NO_ACTIVO`);
- `TRANSFERENCIA_REGISTRADA / EXITOSO` para 281/35 y 281/1;
- `TRANSFERENCIA_RECHAZADA` para 292/35 y 295/1 (`FECHA_TRANSFERENCIA_FUTURA`).

**Estado final del lote 281:** infraestructura 48 · asociación vigente única [48] · `cantidad_actual` 100 · ACTIVO.

---

## 7. TC-M02-141 / rollback LOCAL

**Ambiente: LOCAL AISLADO** (`127.0.0.1:5465/sgpmp_g81_v2_local_test`). En TEST no se ejecutó ningún fault injection.

Pytest V1 **sin cambios**, en una única ejecución del 2026-09-19 de 09:03:42 a 09:03:46 UTC: **6 tests · 6 aprobados · 0 fallidos · 2,95 s**.

- Dos preflight de ambiente: ✅
- Control positivo de Productor y Administrador: **201**, el activo pasa al destino y los movimientos suben +1 ✅
- Fault injection en `SqlAlchemyTransferenciaRepository.guardar` (paso d), **después** de a/b/c y **antes** del `commit`.

Estado leído por una conexión psycopg2 independiente (XML `system-out`):

| Elemento | Productor (activo 3, 5 → 6) | Administrador (activo 4, 7 → 8) |
|---|---|---|
| Dentro de la transacción, antes del commit | `infra=6 vigentes=[6]` | `infra=8 vigentes=[8]` |
| HTTP | **500**, sin filtrar el detalle técnico | **500** |
| Infraestructura del activo | 5 → **5** | 7 → **7** |
| Asociación vigente | [5] → **[5]** | [7] → **[7]** |
| Historial | 1 → **1** | 1 → **1** |
| Movimientos | 0 → **0** | 0 → **0** |
| Ocupación origen / destino | 1/0 → **1/0** | 1/0 → **1/0** |
| Estado | 1 → **1** | 1 → **1** |
| `TRANSFERENCIA_FALLIDA` | 0 → **1** | 0 → **1** |

Rollback completo, sin persistencia parcial y con el fallo auditado. **TC-M02-141: SIN REGRESIÓN.**

---

## 8. Reevaluación de hallazgos y bloqueos V1

### DEF-G81-01 — directo (TC-M02-140)

- **V1:** `HTTP 400 VAL_ENTRADA`, un código no declarado en el contrato, con ambos actores. Severidad Media, estado Abierto.
- **V2:** `HTTP 422 FECHA_TRANSFERENCIA_FUTURA`, con `field = fecha_transferencia`, en ambos actores y sin persistencia.
- **Evolución: CORREGIDO.** Afecta al veredicto.

### BLOQ-G81-02 — directo (TC-M02-139)

- **V1:** BLOQUEADO. No existía una definición funcional inequívoca sobre la parcialidad del lote y el DTO no tenía campo de cantidad. No se emitió ningún POST.
- **Definición:** INC-M02-87-G81 / Issue #238 confirma que RF-48 transfiere siempre el activo completo. La ausencia de `cantidad` es coherente con el diseño.
- **V2 funcional:** TC-139 reformulado se ejecutó con ambos actores (movimientos 31 y 32) y cumple los 12 criterios de §33: lote completo, `cantidad_actual` 100 constante, sin lote hijo y una sola asociación vigente en cada momento.
- **Evolución: BLOQUEO RESUELTO POR DEFINICIÓN FUNCIONAL**, con **TC-M02-139 APROBADO**. Afecta al veredicto. Es un elemento directo del subcaso, no colateral.

---

## 9. Comparación V1 ↔ V2

| Subcaso | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-138 Productor | 409 `ACTIVO_NO_ACTIVO` | 409 `ACTIVO_NO_ACTIVO` | **SIN REGRESIÓN** |
| TC-M02-138 Administrador | 409 `ACTIVO_NO_ACTIVO` | 409 `ACTIVO_NO_ACTIVO` | **SIN REGRESIÓN** |
| TC-M02-139 Productor | BLOQUEADO / no ejecutado | 281, 48 → 51 · **201** · movimiento 31 · cantidad 100 · asociación única [51] | **BLOQUEO RESUELTO + APROBADO** |
| TC-M02-139 Administrador | BLOQUEADO / no ejecutado | 281, 51 → 48 · **201** · movimiento 32 · cantidad 100 · asociación única [48] | **BLOQUEO RESUELTO + APROBADO** |
| TC-M02-140 Productor | 400 `VAL_ENTRADA` | 422 `FECHA_TRANSFERENCIA_FUTURA` | **CORREGIDO** |
| TC-M02-140 Administrador | 400 `VAL_ENTRADA` | 422 `FECHA_TRANSFERENCIA_FUTURA` | **CORREGIDO** |
| TC-M02-141 Productor | 500 + rollback completo (LOCAL) | 500 + rollback completo (LOCAL) | **SIN REGRESIÓN** |
| TC-M02-141 Administrador | 500 + rollback completo (LOCAL) | 500 + rollback completo (LOCAL) | **SIN REGRESIÓN** |

| Hallazgo / bloqueo V1 | Relación | V1 | V2 | Evolución | Impacto |
|---|---|---|---|---|---|
| DEF-G81-01 | Directo — TC-140 | Abierto (400 `VAL_ENTRADA`) | 422 `FECHA_TRANSFERENCIA_FUTURA` | **CORREGIDO** | Sí |
| BLOQ-G81-02 | Directo — TC-139 | Bloqueado | Definición funcional + prueba reformulada aprobada | **BLOQUEO RESUELTO** (TC-139 APROBADO) | Sí |

| Ejecución | V1 | V2 |
|---|---|---|
| Newman TEST | 16 peticiones · 64 aserciones · 60 / 4 fallidas | 24 peticiones · 103 aserciones · **103 / 0** |
| Pytest LOCAL | 6/6 | **6/6** |

---

## 10. Regresiones

No se identificaron regresiones. TC-138 y TC-141 mantienen su comportamiento de V1, TC-140 pasó de incumplir a cumplir y TC-139 dejó de estar bloqueado y se verificó positivamente.

---

## 11. Veredicto final

# ✅ APROBADO — CORREGIDO / SIN REGRESIÓN

- TC-M02-138 → 409 ×2, sin persistencia (**SIN REGRESIÓN**)
- TC-M02-139 reformulado → 201 ×2, transferencia completa del lote 281 sin división (**APROBADO**; BLOQ-G81-02 **RESUELTO**)
- TC-M02-140 → 422 ×2, sin persistencia (**CORREGIDO**; DEF-G81-01 **CORREGIDO**)
- TC-M02-141 → 500 + rollback completo, LOCAL (**SIN REGRESIÓN**)

Evolución del caso: **RECHAZADO (V1) → APROBADO (V2)**.

---

## 12. Integridad de artefactos

- ✅ **V1 intacta.** `test_tc_m02_g81.json`, `test_tc_m02_g81_rollback.py`, `construir_coleccion.cjs` y los cuatro archivos de `Resultados/` coinciden con `HEAD` (hashes en §1.2) y conservan su fecha de modificación.
- ✅ **`construir_coleccion.cjs` no se ejecutó.** La colección V2 se generó con un script externo, desde la V1 en modo lectura (§2).
- ✅ **Newman se ejecutó una sola vez.** Las únicas escrituras de dominio en TEST fueron las **2 transferencias positivas esperadas de TC-139** (movimientos 31 y 32; historiales 404 y 405). Los otros 4 POST fueron rechazados sin persistencia de dominio. No se enviaron POST adicionales, parámetros inventados ni `cantidad = 40`.
- ✅ **No se restauraron ni borraron** los movimientos ni historiales de TC-139: son evidencia de V2.
- ✅ **BD TEST solo en lectura** (`transaction_read_only = on`): únicamente `SELECT`. No se hizo ningún INSERT, UPDATE ni DELETE directo, no se cambiaron 284/288 de estado y no se movieron 292/295.
- ✅ Llamadas adicionales de solo lectura: login, `GET /openapi.json`, `GET /activos-biologicos/281`, `GET /activos-biologicos` y `GET /281/transferencias/disponibles`, todas en el gate.
- ✅ **Pytest se ejecutó una sola vez**, exclusivamente en LOCAL AISLADO. `alembic upgrade head` solo corrió sobre la base local, que se eliminó al terminar. No quedó `__pycache__` ni `.pytest_cache` en la carpeta V1.
- ✅ **DEV no se usó.** No se modificó código productivo, no se hizo commit, push, merge, rebase ni deploy, y no se crearon tickets.
- ✅ Artefactos V2:
  - `EvaluacionV2/test_tc_m02_g81_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g81_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g81_v2.html`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g81_rollback_v2.xml`;
  - este informe.
