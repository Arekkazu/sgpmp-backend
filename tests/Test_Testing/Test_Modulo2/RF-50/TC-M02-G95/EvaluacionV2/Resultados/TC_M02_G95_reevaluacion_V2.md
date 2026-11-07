# REEVALUACIÓN V2 — TC-M02-G95

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF / CU | RF-50 — Disponibilidad de datos para módulos analíticos / CU12 |
| Subcasos | TC-M02-309 (activo inexistente) · TC-M02-310 (inconsistencia jerárquica) · TC-M02-311 (métrica PESO válida) |
| Rama / HEAD | `qa/juan-esteban-re-evaluacion-m02` / `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`. Tras `git fetch origin`, `HEAD...origin/test` = `0 0` |
| Ambiente | TEST compartido |
| Ejecutable | Variante V2 `EvaluacionV2/test_tc_m02_g95_v2.json`. Solo cambia `fechaPesoBd`, de 2026-09-10 a 2026-09-19 (§2) |
| Newman | 1 ejecución · 3 peticiones · **17 aserciones · 17 correctas · 0 fallidas** (V1: 14/17) |
| TC-M02-309 | ✅ 404 `ACTIVO_NO_ENCONTRADO`, sin dataset. **SIN REGRESIÓN** |
| TC-M02-310 | ✅ **409 `INCONSISTENCIA_JERARQUICA`, sin dataset. CORREGIDO** (V1: 200 con el dataset expuesto) |
| TC-M02-311 | ✅ 200, API = BD (250.0 kg · kg · 2026-09-19), sin NaN, Infinity ni mezcla de activos. **SIN REGRESIÓN** |
| Persistencia de dominio | **NO**: Δ = 0 (hashes de filas de 279/289 idénticos antes y después) |
| Auditoría RF-50 | +1 `DATOS_ANALITICOS_CONSULTADOS` (TC-311). TC-309 y TC-310 no generan registro |
| Hallazgo documental (ruta) | **OBSERVACIÓN PERSISTE EN DOCUMENTACIÓN QA**: la matriz agrupada sigue indicando `/datos-analiticos`. Colateral, no afecta al veredicto |
| Observación contractual nueva | El OpenAPI vivo **no declara 409** en `/datos-consolidados`, aunque TEST lo devuelve. Colateral, no afecta al veredicto |
| Regresiones | Ninguna |
| **Veredicto** | ✅ **APROBADO — CORREGIDO / SIN REGRESIÓN** (V1: RECHAZADO) |

---

## 1. Gate

### 1.1 Rama

| Verificación | Resultado |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| `git rev-parse HEAD` | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git fetch origin` · `HEAD...origin/test` | `origin/test` = `a6220fc8` · `0 0` ✅ |
| `git status --short` | Sin cambios en archivos versionados. Solo aparecen carpetas `EvaluacionV2/` sin seguimiento |

### 1.2 Integridad V1

| Archivo | `git hash-object --no-filters` | Esperado |
|---|---|---|
| `test_tc_m02_g95.json` | `946b30d35ab365c77b73b73c00906abb51e79469` | ✅ |
| `Resultados/TC-M02-G95_resultado.md` | `228e4f080063c0befc4a1333c3d4679670539362` | ✅ |

V1 se leyó completa y no se modificó (fecha de modificación: 2026-09-12). Tiene dos hallazgos formales: el **defecto de TC-M02-310** (directo) y la **desalineación entre la matriz y Swagger** en la ruta (colateral documental).

### 1.3 Contrato actual

`GET /openapi.json` → 200 (2026-09-19 10:35 UTC):

| Comprobación | Resultado |
|---|---|
| `/activos-biologicos/{id_activo}/datos-consolidados` | ✅ existe. Summary: *"Exponer datos consolidados del activo biológico para módulos analíticos (CU12 - RF-50)"* |
| `/datos-analiticos` | ✅ **no existe** en el contrato |
| Respuestas declaradas | `200, 400, 401, 403, 404, 422, 429` |
| 404 / 429 | ✅ declarados |
| **409** | ❌ **no declarado** (ver §9) |

En el código de HEAD, `ConsultarDatosConsolidadosUseCase` lanza `ConflictError(code='INCONSISTENCIA_JERARQUICA')` cuando la asociación vigente apunta a una infraestructura inactiva. En cambio, el decorador de la ruta solo declara `responses={400, 401, 403, 404, 429}`, lo que es coherente con la omisión observada en el contrato vivo.

### 1.4 Rate limit / ventana limpia

El endpoint tiene un límite de 100 solicitudes cada 60 s por usuario. En esta sesión de QA no se había llamado a `datos-consolidados` antes de la ejecución oficial: la ventana de más de 60 s sin tráfico propio estaba garantizada. No se reseteó ni se modificó el limitador. No apareció ningún 429.

### 1.5 Principal autorizado

Por comparabilidad con V1 se usó el **usuario 35** (`m2m.nuevo@ejemplo.com`, rol 2, cuenta en estado 2), con un JWT nuevo obtenido por `POST /sesiones/` (HTTP 200, `sub` = 35). **Este principal no se presenta como M04.** G95 evalúa existencia, integridad jerárquica y normalización de métricas, no la autorización entre módulos; V1 fijó la misma cobertura. El token solo se mantuvo en memoria y se inyectó con `--env-var`; no se guardó en la colección ni en Git (§13).

### 1.6 Fixture TC-309

`SELECT … FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999` → **0 filas** ✅.

### 1.7 Fixture TC-310

BD con `SET default_transaction_read_only = on` (`member_qa` / `sgpmp_test` / `on`). Consulta del 2026-09-19 a las 10:35:22 UTC; son las mismas consultas de V1.

| Condición | Estado actual | Cumple |
|---|---|---|
| Activo 289 | `QAJE-DAT-INFRAINACT`, estado 1 (ACTIVO), `id_infraestructura = 49` | ✅ |
| Infraestructura 49 | `Corral QA JE Baja Logica`, finca 57, **`es_activo = false`** | ✅ |
| Historial vigente | 236: activo 289 → infraestructura 49, inicio 2026-06-01, **`fecha_fin = NULL`** | ✅ |
| Gestión / fase | 68: ciclo 10, **`es_activa = true`**, `fecha_finalizacion = NULL` | ✅ |
| Cierres válidos (`vw_rf52_auditoria_cierres_ciclo_productivo`) | **0 filas** | ✅ |
| Activos con infraestructura inactiva o inexistente | solo el 289 | — |

El escenario histórico se conserva íntegro. **No fue necesario sustituir `id310`.**

### 1.8 Fixture TC-311

| Condición | Estado actual |
|---|---|
| Activo 279 | `QAJE-CREC-OK`, infraestructura 48 **activa** |
| Fuente BD (`vw_rf47_ficha_integral_activo`) | `peso_actual = 250.00` · `unidad_peso = kg` · **`fecha_ultimo_peso = 2026-09-19`** · `cantidad_actual = NULL` · `biomasa_total = NULL` |
| Eventos PESO | 352 (2026-09-19 05:25:06Z), 234, 232, 228 y 227, todos de 250.00 kg |
| PESO ≤ 0 | 0 |

**Cambio respecto de V1:** la fecha del último peso pasó de 2026-09-10 a **2026-09-19**. La causa es el evento 352, que el primer intento de reevaluación V2 de TC-M02-G47 registró legítimamente sobre el activo 279. El activo sigue siendo válido y el peso no cambia. Conforme a §23 del paquete, esto no bloquea el caso: basta una variante V2 que actualice `fechaPesoBd`. No se insertó ningún peso.

---

## 2. Ejecutable V2

`EvaluacionV2/test_tc_m02_g95_v2.json` (`--no-filters` `6fd65dcb752b5a246f8ef278b338ab9a3b8c7422`) es una copia byte a byte de V1 con **un único cambio de datos**:

```diff
@@ -42,7 +42,7 @@
     "key": "fechaPesoBd",
-      "value": "2026-09-10",
+      "value": "2026-09-19",
```

**Motivo:** la fuente BD actual del activo 279 tiene `fecha_ultimo_peso = 2026-09-19` (§1.8). **Sin cambios:** `id310` (289), `id311` (279), `pesoBd` (250.00), `unidadBd` (kg), `identificadorBd`, `cantidadBd`, `biomasaBd`, los HTTP esperados (404/409/200), el endpoint (`datos-consolidados`), las reglas y todas las aserciones. La variable `token` sigue vacía en la colección y se inyectó en tiempo de ejecución.

**Ejecución única**, 2026-09-19, de 10:36:55 a 10:36:56 UTC:

```bash
newman run "$G/EvaluacionV2/test_tc_m02_g95_v2.json" -r cli,json,htmlextra \
  --env-var token="$QA_TOKEN" --timeout-request 30000 \
  --reporter-json-export  "$G/EvaluacionV2/Resultados/reporte_tc_m02_g95_v2.json" \
  --reporter-htmlextra-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g95_v2.html" \
  --reporter-htmlextra-skipHeaders "Authorization"
```

**Redacción del token.** El HTML se generó sin la cabecera `Authorization` y no contiene el token. El reportero JSON de Newman sí serializa cabeceras y variables de entorno. Tras la ejecución, las 4 apariciones del JWT en el JSON se sustituyeron por `<TOKEN_REDACTADO>`, y se verificó que no queda ningún JWT en los reportes. Las únicas cadenas `eyJ` que quedan son el patrón de la regex anti-secretos de los scripts de prueba.

---

## 3. TC-M02-309

| | V1 | V2 |
|---|---|---|
| Request | `GET /activos-biologicos/99999/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20` | ídem |
| HTTP | 404 | **404** (488 ms) |
| `error_code` | `ACTIVO_NO_ENCONTRADO` | **`ACTIVO_NO_ENCONTRADO`** |
| Mensaje | *El activo biológico con ID 99999 no existe en los registros del sistema.* | idéntico |
| Dataset / datos de otro activo / traza interna | no | **no** |
| Aserciones | 4/4 | **4/4** |
| Resultado | APROBADO | **APROBADO — SIN REGRESIÓN** |

---

## 4. TC-M02-310

### Precondición

Fixture 289 intacto (§1.7): asociación vigente (historial 236) hacia la infraestructura 49, **inactiva**; fase 68 activa y sin cierres.

### Respuesta

`GET /activos-biologicos/289/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20` → **HTTP 409** (134 ms):

```json
{"error_code":"INCONSISTENCIA_JERARQUICA",
 "message":"El activo mantiene una asociación vigente con la infraestructura \"Corral QA JE Baja Logica\", la cual está inactiva. Regulariza la jerarquía del activo antes de consultar datos consolidados.",
 "fields":[]}
```

El mensaje identifica semánticamente los tres elementos requeridos: la **asociación vigente**, la **infraestructura inactiva** (con su nombre) y la necesidad de **regularizar antes de consultar**.

### No exposición

El cuerpo contiene solo `error_code`, `message`, `fields` y `timestamp`. **No** aparecen `metricas_actuales`, `historial_eventos`, `historial_fases`, `historico_estados`, `identificador`, `infraestructura_asociada`, `fase_productiva_activa` ni `dataset`, y tampoco el peso 180 que V1 expuso, datos de otro activo, trazas (`Traceback`, `SQLAlchemy`, `psycopg`) ni secretos. Las aserciones "Sin dataset ni datos de otro activo" y "Respuesta sin detalles internos ni secretos" pasaron. Aserciones: **4/4**.

### Evolución del defecto

| | V1 | V2 |
|---|---|---|
| HTTP | **200** | **409** |
| Dataset | expuesto (identificador, infraestructura, fase, historial, `peso_actual = 180.0`) | **no expuesto** |
| Causa comunicada | ninguna | `INCONSISTENCIA_JERARQUICA` |
| Aserciones | 1/4 | **4/4** |

**Defecto TC-M02-310: CORREGIDO** (fix INC-M02-97-G95 / #244, PR #272). **TC-M02-310: APROBADO — CORREGIDO.**

---

## 5. TC-M02-311

### Fuente BD

`vw_rf47_ficha_integral_activo`, activo 279: `QAJE-CREC-OK` · peso 250.00 · kg · 2026-09-19 · cantidad NULL · biomasa NULL. Último evento PESO: 352.

### Respuesta API

`GET /activos-biologicos/279/datos-consolidados?tipo_dato=metricas&pagina=1&page_size=20` → **HTTP 200** (139 ms):

```json
{"id_activo_biologico":279,"identificador":"QAJE-CREC-OK","tipo_activo":"INDIVIDUAL",
 "estado_actual":"ACTIVO","infraestructura_asociada":"Corral QA JE Origen",
 "metricas_actuales":{"peso_actual":250.0,"unidad_peso":"kg","fecha_ultimo_peso":"2026-09-19",
                      "cantidad_actual":null,"biomasa_total":null,"indicadores_historicos":[]}, ...}
```

### Comparación

| Dato | BD | API | ¿Coincide? |
|---|---|---|---|
| Activo | 279 | 279 | ✅ |
| Identificador | QAJE-CREC-OK | QAJE-CREC-OK | ✅ |
| Peso | 250.00 | 250.0 (número finito, > 0) | ✅ |
| Unidad | kg | kg | ✅ |
| Fecha último peso | 2026-09-19 | 2026-09-19 | ✅ |
| Cantidad | NULL | null | ✅ |
| Biomasa | NULL | null | ✅ |

### Integridad

No aparecen NaN, Infinity ni valores numéricos no finitos. No hay pesos negativos, unidades incompatibles ni `id_activo_biologico` distintos de 279 en toda la respuesta, según la aserción de recorrido recursivo. Aserciones: **9/9**. **TC-M02-311: APROBADO — SIN REGRESIÓN.**

---

## 6. Persistencia de dominio

Snapshot solo de lectura, antes (10:35:22Z) y después (10:37:27Z). Se calculó el SHA-256 de las filas completas:

| Conjunto | Filas | Hash PRE | Hash POST | Δ |
|---|---:|---|---|---|
| `activos_biologicos` (279, 289) | 2 | `7410799278b05443` | `7410799278b05443` | **0** |
| `eventos_activos` (279, 289) | 5 | `2ad1ba13b16e4f34` | `2ad1ba13b16e4f34` | **0** |
| `eventos_crecimeinto` (279, 289) | 5 | `82936122ef1da94d` | `82936122ef1da94d` | **0** |
| `historial_infraestructura_activo` (279, 289) | 2 | `55f8ed0d76781e63` | `55f8ed0d76781e63` | **0** |
| `gestiones_fases` (279, 289) | 2 | `8654fb41243efb74` | `8654fb41243efb74` | **0** |
| `infraestructuras` (48, 49) | 2 | `ba30c91d22740652` | `ba30c91d22740652` | **0** |
| `detalles_activos_individuales` (279, 289) | 2 | `61551fdc26bee35e` | `61551fdc26bee35e` | **0** |

Totales globales, sin cambios: `eventos_activos` 171 (máximo 359) · historial 371 · fases 110 · activos 367. Las consultas específicas de 310 (activo, infraestructura, historial, fase y cierres) y de 311 (fuente, eventos, negativos e infraestructura) son idénticas antes y después. La infraestructura 49 sigue inactiva y el historial 236 sigue abierto, es decir, **no hubo autocorrección** ni efecto colateral del 409.

**Δ dominio = 0.**

---

## 7. Auditoría RF-50

Bitácora `modulo2.bitacora_auditoria_m02` con `rf_origen='RF50'`: **17 → 18 (+1)**.

| id_bitacora | tipo_evento | resultado | activo | usuario | timestamp |
|---:|---|---|---:|---:|---|
| 2980 | `DATOS_ANALITICOS_CONSULTADOS` | EXITOSO | 279 | 35 | 2026-09-19 10:36:55.83Z |

TC-M02-311 (200) generó un registro. TC-M02-309 (404) y TC-M02-310 (409) cortan el flujo antes del registro y no generaron auditoría. Es metadata técnica esperada, **no una mutación de dominio**. El login del usuario 35 también actualiza `ultimo_acceso` en la cuenta, que es una escritura técnica de sesión.

---

## 8. Hallazgo documental de ruta

- **V1:** la matriz indicaba `GET /activos-biologicos/{id_activo}/datos-analiticos`, pero el contrato desplegado exponía `/datos-consolidados`. Discrepancia registrada como tarea documental (Menor).
- **Definición:** Desarrollo confirmó en INC-M02-97-G95 / #244 / PR #272 (`anotaciones/modulo_2/inc_m02_97_g95_inconsistencia_jerarquica_datos_consolidados.md`) que la ruta oficial de RF-50 es `/datos-consolidados` y que `/datos-analiticos` no existe. El OpenAPI vivo lo confirma (§1.3).
- **V2:** según el paquete de instrucciones, la **matriz agrupada en uso todavía muestra `/datos-analiticos`**. Esa matriz no forma parte del repositorio (no se encontró localmente) y QA no la ha actualizado en esta reevaluación.
- **Evolución: OBSERVACIÓN PERSISTE EN DOCUMENTACIÓN QA.** Pasará a "OBSERVACIÓN RESUELTA POR DEFINICIÓN CONTRACTUAL" cuando la matriz indique `GET /activos-biologicos/{id_activo}/datos-consolidados`. Es colateral y **no afecta al veredicto funcional**.

---

## 9. Observaciones contractuales nuevas

| Hallazgo nuevo | Relación | Estado |
|---|---|---|
| El OpenAPI vivo de `GET /activos-biologicos/{id_activo}/datos-consolidados` **no declara 409**, aunque TEST responde `409 INCONSISTENCIA_JERARQUICA` (TC-M02-310) | COLATERAL contractual | **Confirmado** en el contrato vivo: se declaran `200, 400, 401, 403, 404, 422, 429`. El decorador `responses={…}` de la ruta en HEAD omite 409 |

No cambia el veredicto funcional de TC-M02-310. No se creó ningún ticket. Un cliente generado a partir del contrato no contemplaría esta respuesta.

---

## 10. Comparación V1 ↔ V2

| Subcaso | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-309 | 404 — APROBADO | 404 `ACTIVO_NO_ENCONTRADO`, sin dataset — APROBADO | **SIN REGRESIÓN** |
| TC-M02-310 | 200 con dataset expuesto — RECHAZADO | 409 `INCONSISTENCIA_JERARQUICA`, sin dataset — APROBADO | **CORREGIDO** |
| TC-M02-311 | 200 + API = BD (250 kg, 2026-09-10) — APROBADO | 200 + API = BD (250 kg, 2026-09-19) — APROBADO | **SIN REGRESIÓN** |

| Hallazgo V1 | Relación | V1 | V2 | Evolución | Afecta al veredicto |
|---|---|---|---|---|---|
| Defecto TC-M02-310 | DIRECTO | Abierto | 409 sin exposición | **CORREGIDO** | SÍ |
| Matriz `/datos-analiticos` frente a contrato `/datos-consolidados` | COLATERAL documental | Abierto | Ruta confirmada por Desarrollo; la matriz sigue sin actualizar | **OBSERVACIÓN PERSISTE EN DOCUMENTACIÓN QA** | NO |

| Hallazgo nuevo | Relación | Estado |
|---|---|---|
| OpenAPI omite 409 de inconsistencia jerárquica | COLATERAL contractual | Confirmado en el contrato vivo |

| Ejecución | V1 | V2 |
|---|---|---|
| Newman | 3 peticiones · 17 aserciones · 14 correctas / 3 fallidas (todas en 310) | 3 peticiones · 17 aserciones · **17 / 0** |

---

## 11. Regresiones

No se identificaron regresiones. TC-309 y TC-311 mantienen su comportamiento, y TC-310 pasó de incumplir a cumplir.

---

## 12. Veredicto final

# ✅ APROBADO — CORREGIDO / SIN REGRESIÓN

- TC-M02-309 → 404 `ACTIVO_NO_ENCONTRADO`, sin dataset (**SIN REGRESIÓN**)
- TC-M02-310 → 409 `INCONSISTENCIA_JERARQUICA`, sin dataset (**CORREGIDO**)
- TC-M02-311 → 200, API = BD, métricas válidas (**SIN REGRESIÓN**)
- Δ dominio = 0.
- Colaterales sin impacto en el veredicto:
  - la matriz sigue con `/datos-analiticos` (**OBSERVACIÓN PERSISTE EN DOCUMENTACIÓN QA**);
  - el OpenAPI no declara 409 (nueva observación contractual).

Evolución del caso: **RECHAZADO (V1) → APROBADO (V2)**.

---

## 13. Integridad

- ✅ **V1 intacta:** `test_tc_m02_g95.json` y `TC-M02-G95_resultado.md` tienen el hash esperado y no se modificaron los reportes V1.
- ✅ **Variante V2 mínima:** solo cambia `fechaPesoBd`, justificado por la fuente BD actual.
- ✅ **Newman se ejecutó una sola vez.** Solo se enviaron los 3 GET oficiales, más un `POST /sesiones/` de autenticación y un `GET /openapi.json` para el gate.
- ✅ **Token protegido:** en memoria, inyectado con `--env-var`, omitido en el HTML y redactado en el JSON. No se guardó en la colección, en Git ni en este informe.
- ✅ **BD TEST solo en lectura** (`transaction_read_only = on`): únicamente `SELECT`.
- ✅ No se fabricó la inconsistencia, no se tocó la infraestructura 49, no se reabrieron historiales, no se modificaron fases ni se insertaron pesos.
- ✅ No se usó `/datos-analiticos`, no se reseteó el rate limiter y no se esperó un HTTP 500 en TC-311.
- ✅ DEV no se usó. No se modificó código productivo, no se hizo commit, push, merge, rebase ni deploy, y no se crearon tickets.
- ✅ Artefactos V2:
  - `EvaluacionV2/test_tc_m02_g95_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g95_v2.json`, con el token redactado;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g95_v2.html`;
  - este informe.
