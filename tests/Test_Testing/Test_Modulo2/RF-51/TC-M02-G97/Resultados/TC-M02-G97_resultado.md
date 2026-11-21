# RESULTADO — TC-M02-G97 (versión reformulada)

> Esta ejecución reemplaza la anterior de G97. IDs, tokens, permisos, método HTTP y contrato
> se volvieron a verificar desde cero. El cambio principal está en **TC-M02-314**, que ahora
> se prueba de forma ejecutable con un usuario autenticado **sin permiso de lectura** sobre el
> recurso de RF-51, en lugar de exigir un permiso sanitario granular inexistente.

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| **VEREDICTO** | **RECHAZADO** (con TC-M02-314 y TC-M02-312 aprobados) |
| TC-M02-312 | ✅ **APROBADO** |
| TC-M02-313-A | ❌ **RECHAZADO** |
| TC-M02-313-B | ❌ **RECHAZADO** |
| TC-M02-314 | ✅ **APROBADO** |
| SOLICITUDES OFICIALES | **4/4** |
| Método matriz | POST |
| Método OpenAPI | **GET** |
| Discrepancia matriz ↔ OpenAPI | **SÍ** (documentada, OBS-G97-01) |
| SQL writes QA | **0** |
| Cambios funcionales QA | **0** |
| Equipo responsable | **Desarrollo Backend** (DEF-G97-01) |

**Justificación.** Tres de los cuatro sub-casos oficiales se ejecutaron con precondiciones válidas y aisladas. **TC-M02-312** y **TC-M02-314** se comportan como exige la ficha: `404 ACTIVO_NO_ENCONTRADO` para el activo inexistente, y `403 ACCESO_DENEGADO` para el usuario autenticado sin READ, sin exponer indicador ni variables. **TC-M02-313** falla en sus dos variantes: RF-51 no valida el ciclo de vida del activo, acepta rangos anteriores al nacimiento o posteriores a la baja con `200`, y en 313-A publica además un indicador como válido. Al haber un defecto demostrado con precondiciones válidas, el veredicto global es **RECHAZADO** (§28).

---

## 1. Identificación

- **Caso:** TC-M02-G97 (reformulado)
- **RF:** RF-51 — Generación de Indicadores Zootécnicos · **CU:** CU12
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae`
- **Fecha/hora:** 2026-09-11, 03:24Z (gate) — 03:26Z (ejecución)
- **Ambiente:** TEST HTTPS `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Método/endpoint ejecutado:** **`GET /activos-biologicos/{id_activo}/indicadores`** (§2.1)
- **Herramientas:** Postman + Newman · Pytest

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repo | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` |
| HEAD | ✅ `41369ea` · working tree limpio (sin versionados modificados) |
| OpenAPI 200 | ✅ |
| BD read-only | ✅ `current_setting('transaction_read_only') = on`, `current_user = member_qa` |
| Método RF-51 | ✅ **GET** (POST no existe) |
| AUTH_OK | ✅ `m2m.nuevo@ejemplo.com` (usuario 35, Productor, **con** READ) |
| AUTH_NO_READ | ✅ `contador@pecuaria.co` (usuario 5, Contador, **sin** READ, cuenta Activa) |

### 2.1 Resolución POST vs GET (§4) — Escenario B

La matriz conserva `POST /activos-biologicos/{id_activo}/indicadores`. **El contrato vivo declara únicamente `get`**, y ninguna otra ruta expone un POST de indicadores. Se ejecutó G97 sobre **GET** (la operación RF-51 inequívoca) y se registró la **DISCREPANCIA MATRIZ ↔ OPENAPI** (V31). Evidencia ejecutable de diagnóstico: `POST /indicadores` → **`405 Method Not Allowed`** con `Allow: GET`. La matriz no se modificó (§4, error 15 de §36). Queda como **OBS-G97-01**.

Respuestas declaradas por el contrato: `200, 400, 401, 403, 404, 422`. Los tres códigos que exigen los sub-casos (`404`, `400`, `403`) están declarados.

---

## 3. SETUP — SOLO LECTURA

**Escrituras SETUP: 0.** Inventario obtenido con `SELECT` (`readonly=True`) y GET. Nada se reutilizó de la ejecución anterior sin volver a demostrarlo (§3.A).

### Inventario (§6)

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿99999 existe? | **NO** — `count(*) = 0`; `max(id) = 336` |
| D2 | Método RF-51 en OpenAPI | **GET** (POST → 405) |
| D3 | Usuario autorizado 312/313 | `m2m.nuevo@ejemplo.com` (id 35, rol 2, con READ) |
| D4 | Activo con nacimiento/ingreso | **279** `QAJE-CREC-OK` |
| D5 | Activo con baja preexistente | **286** `QAJE-IND-BAJA` (estado 6) |
| D6 | Fecha exacta de baja | **2026-08-31** |
| D7 | Indicador para 313 | `tipo_indicador=CRECIMIENTO` → `ganancia_peso` |
| D8 | Roles autenticables sin READ (29,2) | Contador (5), Supervisor (6), Gestor de Granja (7), Revisor Fiscal (8), Externo AgroFusion (9) |
| D9 | Usuario que autentica sin READ | **`contador@pecuaria.co`** (id 5, cuenta Activa, `Test1234!`) |
| D10 | Activo para 314 | **279** (existente, accesible con READ) |
| D11 | ¿Autorización granular por grupo de datos? | **NO** — el endpoint exige un único permiso `(29, 2)` |
| D12 | ¿Se modificó algo para preparar datos? | **NO** |

### 3.1 TC-M02-312

`SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;` → **0**. Confirmado también por API: `GET /activos-biologicos/99999` → **404** (A1 descartado).

### 3.2 TC-M02-313-A — activo 279

```sql
-- 279 | fecha_inicio_ciclo 2026-06-01 | nacimiento 2026-01-15 | estado 1 (ACTIVO)
```
- **Inicio solicitado:** 2025-12-01 (anterior al nacimiento **y** al ingreso) — única causa
- **Fin solicitado:** 2026-09-10 (dentro del ciclo, no futuro, no invierte el rango)
- Se eligió 279 porque **tiene 4 mediciones reales**: así el rango inválido llega al cálculo y puede observarse si el sistema publica un indicador.

### 3.3 TC-M02-313-B — activo 286

```sql
-- 286 | ingreso 2026-06-01 | baja 2026-08-31 (id_estado_nuevo=6)
--   motivo: "Baja sembrada para TC-M02-313 (rango de fechas fuera del ciclo de vida)."
```
- **Inicio solicitado:** 2026-07-01 (dentro del ciclo) · **Fin solicitado:** 2026-09-05 (posterior a la baja **y en el pasado**, hoy es 2026-09-11 → A9 descartado)
- La baja es **preexistente**; QA no dio de baja ningún activo. Es el único activo de TEST con baja registrada.

### 3.4 TC-M02-314 — usuario sin READ

- **Usuario:** `contador@pecuaria.co` · **id:** 5 · **rol:** 5 (Contador)
- **Autenticación válida:** SÍ (HTTP 200 en `POST /sesiones/`, credencial legítima `Test1234!`) · **Cuenta:** Activa (estado 2)
- **Recurso protegido:** 29 `activos_biologicos`, acción 2 (Leer) — resuelto del código del router (`_RECURSO = 29`, `require_permission(_RECURSO, 2)`), no asumido
- **READ:** **NO**

```sql
SELECT 1 FROM modulo1.permisos
 WHERE id_rol = 5 AND id_recurso = 29 AND id_accion = 2 AND es_activo IS TRUE;   -- 0 filas
```

Confirmado por API en el SETUP: `GET /activos-biologicos/279` con el token del Contador → **403 ACCESO_DENEGADO** (V24). El usuario carece de acceso general a activos biológicos, de modo que el 403 no es específico de indicadores sino de la falta de READ. No hay tabla `usuarios_roles`: el rol es único por usuario, sin herencia (A12 descartado).

- **Activo para 314:** 279 (existe, accesible con READ — control positivo confirma 200)
- **¿Autorización granular por grupo de datos?** NO; la variante granular opcional (§20) no aplica y **no bloquea** el TC-314 principal.

---

## 4. TC-M02-312 — activo inexistente ✅ APROBADO

- **Request:** `GET /activos-biologicos/99999/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-06-01&fecha_fin=2026-08-31` (AUTH_OK)
- **Esperado:** 404 · **Obtenido:** **404** ✅ · **Indicador expuesto:** NO

```json
{"error_code":"ACTIVO_NO_ENCONTRADO",
 "message":"El activo biológico con ID 99999 no existe en los registros del sistema.",
 "fields":[],"timestamp":"2026-09-11T03:25:55.004781+00:00"}
```

V1–V6 cumplidas: inexistencia confirmada, consumidor autorizado, HTTP 404, motivo = activo inexistente (con el ID en el mensaje), sin indicador ni stack trace. **Resultado: APROBADO.** (6/6 assertions.)

---

## 5. TC-M02-313-A — inicio antes del nacimiento ❌ RECHAZADO

- **Vida del activo:** nacimiento 2026-01-15, ingreso 2026-06-01, sin baja (ACTIVO)
- **Rango solicitado:** **2025-12-01** → 2026-09-10
- **Esperado:** 400 · **Obtenido:** **200** ❌ · **Indicador expuesto:** **SÍ** ❌

```json
{"id_activo_biologico":279,"tipo_activo":"INDIVIDUAL",
 "indicadores":[{"tipo":"ganancia_peso","valor":"0.0000","unidad":"kg/dia",
   "periodo_inicio":"2026-09-09","periodo_fin":"2026-09-10",
   "variables_usadas":{"peso_inicial_kg":250.0,"peso_final_kg":250.0,"dias":1,"total_mediciones":4},
   "disponible":true}],"advertencias":[]}
```

V7–V10 (precondición) cumplidas; **V11 (HTTP 400) y V12 (motivo) fallan**: el sistema devuelve `200` sin mención alguna del ciclo de vida y **publica `ganancia_peso = 0.0000` con `disponible: true`** para un periodo que empieza seis semanas antes del nacimiento del animal. **Resultado: RECHAZADO.** (3/6 assertions.)

---

## 6. TC-M02-313-B — fin posterior a la baja ❌ RECHAZADO

- **Vida del activo:** ingreso 2026-06-01, **baja 2026-08-31**
- **Rango solicitado:** 2026-07-01 → **2026-09-05**
- **Esperado:** 400 · **Obtenido:** **200** ❌

```json
{"id_activo_biologico":286,"tipo_activo":"INDIVIDUAL",
 "indicadores":[{"tipo":"ganancia_peso","valor":null,"disponible":false}],
 "advertencias":["DATOS_INSUFICIENTES: ganancia_peso requiere al menos 2 mediciones de peso."]}
```

V14–V18 (precondición) cumplidas; **V19 (HTTP 400) y V20 (motivo) fallan**. El `200` demuestra que la regla temporal no se evalúa, **aunque el indicador venga `disponible: false`** (§18: eso no aprueba el sub-caso). El activo 286 no tiene mediciones, así que su respuesta atribuye el resultado a datos insuficientes; esa circunstancia no debilita la conclusión —la validación de ciclo es de entrada y debe preceder al cálculo—, y el diagnóstico de §9 lo confirma sobre un activo que sí tiene datos. **Resultado: RECHAZADO.** (5/7 assertions.)

---

## 7. TC-M02-314 — usuario autenticado sin READ ✅ APROBADO

- **Usuario autenticado:** `contador@pecuaria.co` (id 5, Contador), cuenta Activa, credencial legítima
- **READ:** NO (recurso 29, acción 2 ausente) · **Activo:** 279 (existe)
- **Request:** `GET /activos-biologicos/279/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-06-01&fecha_fin=2026-09-10` (AUTH_NO_READ)
- **Esperado:** 403 · **Obtenido:** **403** ✅

```json
{"error_code":"ACCESO_DENEGADO",
 "message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.",
 "fields":[],"timestamp":"2026-09-11T03:25:56.329406+00:00"}
```

| Verificación | Resultado |
|---|---|
| V22/V23 — usuario autenticado, credencial válida | ✅ HTTP 200 en login; cuenta Activa |
| V24 — READ ausente demostrado | ✅ por SQL y por API (`GET /activos-biologicos/279` → 403) |
| V25 — activo existe (no 99999) | ✅ |
| V26 — indicador/parámetros válidos | ✅ CRECIMIENTO, rango válido |
| V27 — HTTP 403 | ✅ |
| V28 — causa = autorización (no autenticación ni cuenta inactiva) | ✅ `ACCESO_DENEGADO`, no 401, no `CUENTA_NO_ACTIVA` |
| V29 — no expone indicador ni variables | ✅ cuerpo `ErrorResponse` sin `indicadores` ni `variables_usadas` |

**El 403 es genuinamente de autorización.** No se revocó ningún permiso, no se cambió ningún rol, no se usó token inválido ni cuenta bloqueada (§3.C, §36). La falta de READ es real y preexistente. El control positivo (AUTH_OK sobre el mismo activo → 200) descarta que el 403 provenga de un activo o endpoint inaccesibles para todos. **Resultado: APROBADO.** (7/7 assertions Newman + 7/7 Pytest.)

---

## 8. Verificación de no mutación (§23)

| Contador | ANTES | DESPUÉS | Δ |
|---|---|---|---|
| `modulo2.activos_biologicos` | 259 | 259 | **0** |
| `modulo2.eventos_activos` | 106 | 106 | **0** |
| `modulo2.eventos_sanitarios` | 29 | 29 | **0** |
| `modulo2.historicos_estados_activos` | 75 | 75 | **0** |
| `modulo1.permisos` | 369 | 369 | **0** |
| `modulo1.recursos` | 57 | 57 | **0** |

- **SQL writes QA: 0** (sesión `readonly=True`). No se cambiaron permisos ni roles, no se fabricó ninguna baja, no se creó ningún usuario, no se usó token inválido.
- 279 sigue ACTIVO (ciclo 2026-06-01); 286 sigue en BAJA (2026-08-31); 99999 sigue sin existir.
- **Escrituras automáticas de auditoría del producto (no de QA):** los `GET` exitosos que llegan al cálculo registran `INDICADOR_CALCULADO` en `bitacora_auditoria_m02` con `commit` propio del caso de uso. Es comportamiento del endpoint, no una escritura provocada por QA; los rechazos `404` (TC-312), `400`/`200` sin cálculo y `403` (TC-314) no generan ese registro cuando no se alcanza el cálculo.

---

## 9. Diagnóstico

**¿Fue necesario? SÍ** — desviación en ambas variantes de TC-M02-313.

### 9.1 Prueba de que la regla de ciclo de vida no existe

El activo 279 con un rango **íntegramente dentro** del ciclo (2026-06-01 → 2026-09-10) devuelve una respuesta **indistinguible** de la de TC-313-A (rango inválido): mismo `valor` (`0.0000`), mismo `periodo` (2026-09-09/10), mismas `variables_usadas`. El `periodo_inicio` reportado lo fijan las mediciones, **no** el rango solicitado (2025-12-01). El parámetro de fechas solo filtra qué eventos entran en el cálculo; nunca se contrasta contra el ciclo de vida.

### 9.2 Hipótesis descartadas (§25)

| # | Hipótesis | Descarte |
|---|---|---|
| A1 | 99999 existe | `count=0` + 404 en API |
| A2 | Método equivocado | Contrato: solo GET; POST → 405 |
| A3 | Token autorizado inválido | Control positivo 200 |
| A4 | Indicador inválido | CRECIMIENTO en el contrato |
| A5 | En 313-A el fin también fuera del ciclo | 2026-09-10 posterior al ingreso, activo ACTIVO sin baja |
| A6 | En 313-A el inicio no era anterior | 2025-12-01 < 2026-01-15 y < 2026-06-01 (assertions) |
| A7 | 313-B sin baja | histórico: estado 6 el 2026-08-31 |
| A8 | En 313-B el fin no posterior a baja | 2026-09-05 > 2026-08-31 |
| A9 | 313-B usa fecha futura | 2026-09-05 < 2026-09-11 (hoy) |
| A10 | Usuario 314 no autenticado | login 200; cuenta Activa verificada |
| A11 | Usuario 314 sí tiene READ | 0 filas en permisos (29,2) para rol 5 |
| A12 | Usuario 314 heredó READ | no existe `usuarios_roles`; rol único por usuario |
| A13 | Activo 314 no existe | 279 existe; control positivo 200 |
| A14 | El 403 vino de otro control | `error_code = ACCESO_DENEGADO` (RBAC de rol), no 401 ni `CUENTA_NO_ACTIVA` |
| A15/A16 | Fechas/variables distintas en el request | cada test verifica la URL final |
| A17 | Assertion demasiado literal | motivos con regex semántica amplia |

**Corrección de la prueba.** Una assertion del Pytest falló por un `%` literal en un `ILIKE` que psycopg2 interpretó como marcador de parámetro; se parametrizó correctamente. **ERROR DE APLICACIÓN DE LA PRUEBA (categoría A)**, sin efecto en las conclusiones.

### 9.3 Causa raíz (clasificación E — DEFECTO DEL SISTEMA)

Confirmada por lectura de código (sin modificarlo): el caso de uso solo lanza `NotFoundError` (por eso TC-312 funciona y TC-313 no); el DTO valida el enum y `fecha_inicio <= fecha_fin` pero **no consulta el activo**, de modo que no puede comparar el rango con su ciclo de vida; el repositorio usa las fechas solo como filtro `WHERE ea.fecha BETWEEN` sobre los eventos y nunca lee `fecha_inicio_ciclo`, `fecha_nacimeinto` ni el histórico de estados. **RF-51 valida la existencia del activo pero no su ventana temporal de vida.**

---

## 10. Hallazgos reportables

### DEF-G97-01 — El rango fuera del ciclo de vida se acepta y llega a publicar un indicador

| Campo | Valor |
|---|---|
| Sub-caso / variantes | TC-M02-313-A y TC-M02-313-B |
| Consumidor | `m2m.nuevo@ejemplo.com` (usuario 35), autorizado |
| Activos | 279 `QAJE-CREC-OK` (A) y 286 `QAJE-IND-BAJA` (B) |
| Indicador | `tipo_indicador=CRECIMIENTO` (`ganancia_peso`) |
| Rangos | A: **2025-12-01** → 2026-09-10 (nacimiento 2026-01-15) · B: 2026-07-01 → **2026-09-05** (baja 2026-08-31) |
| Esperado | `400` "El rango solicitado está fuera del ciclo de vida registrado para el activo (Vida: [nacimiento] a [baja/actualidad])" |
| Obtenido | `200` en ambas variantes; en A con `ganancia_peso = "0.0000"`, `disponible: true` |
| Evidencia API | `Resultados/reporte_tc_m02_g97_newman.html` — V11/V12 (313-A), V19/V20 (313-B), "no se expone indicador" (313-A) |
| Evidencia BD | 279: nacimiento 2026-01-15, ingreso 2026-06-01 · 286: baja 2026-08-31 (`historicos_estados_activos`) |
| ¿Indicador/datos expuestos? | **SÍ** (313-A) — indicador sobre un periodo anterior al nacimiento |
| ¿Persistencia parcial? | NO |
| Categoría | VALIDACIÓN TEMPORAL / CÁLCULO |
| **Type** | **bug** |
| **Severity / Priority** | **Severo / Important** |
| Tiempo máximo | 1 día hábil |
| **Fecha límite** | **2026-09-14** |
| **Equipo responsable** | **Desarrollo Backend** |
| Causa raíz | El DTO no consulta el activo y el repositorio usa las fechas solo como filtro de eventos; el ciclo de vida nunca se contrasta con el rango |
| Impacto | RF-51 acepta ventanas en las que el activo no existía o ya había causado baja y publica el resultado como válido. Consumidores analíticos pueden promediar/proyectar sobre periodos biológicamente imposibles sin alerta. Afecta a toda la familia de indicadores |
| Reproducibilidad | 100 % — 2/2 variantes |

### OBS-G97-01 — Discrepancia matriz (POST) ↔ OpenAPI (GET)

| Campo | Valor |
|---|---|
| Descripción | La matriz indica `POST /activos-biologicos/{id_activo}/indicadores`; el contrato solo declara `GET` y el POST devuelve `405`. No hay separación consulta/generación: el GET calcula on-demand |
| **Type / Severity** | mejora de contrato / **Medio** |
| Tiempo máximo | 2 días hábiles · **Fecha límite: 2026-09-15** |
| **Equipo responsable** | Desarrollo Backend / responsable funcional |
| Acción | Alinear la matriz con el contrato, o exponer el POST si RF-51 lo requiere |

---

## 11. VEREDICTO FINAL

# ❌ RECHAZADO

Sub-caso por sub-caso: **TC-M02-312 APROBADO**, **TC-M02-313-A RECHAZADO**, **TC-M02-313-B RECHAZADO**, **TC-M02-314 APROBADO**. Conforme a §28, un defecto demostrado con precondiciones válidas fija el veredicto global en RECHAZADO. Las 4 solicitudes oficiales se ejecutaron; ningún sub-caso quedó bloqueado en esta versión.

---

## 12. Declaración de cumplimiento

- ✅ No se modificó código del producto.
- ✅ No hubo `commit`, `push`, `merge`, `deploy` ni cambio de rama.
- ✅ BD solo lectura: `transaction_read_only = on`; solo `SELECT`.
- ✅ No se cambiaron permisos ni roles (`modulo1.permisos` 369 → 369).
- ✅ No se fabricó ninguna baja (286 ya estaba en BAJA; QA no la creó).
- ✅ No se creó ningún usuario.
- ✅ **No se usó token inválido para TC-M02-314**: el 403 proviene de una falta de READ real y preexistente del rol Contador.
- ✅ Método GET/POST resuelto mediante OpenAPI antes de ejecutar; la matriz no se modificó.
- ✅ Resultados **no heredados** de la ejecución anterior: IDs, tokens, permisos y contrato se volvieron a verificar.
- ✅ Cada variante aisló una única condición; A9 y A5/A17 descartados con fechas pasadas y no invertidas.
- ✅ No se inventaron resultados; ningún hallazgo queda con severidad, plazo, fecha límite o responsable pendientes.

---

## 13. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-51/TC-M02-G97/
├── construir_coleccion.cjs           generador determinista de la colección
├── test_tc_m02_g97.json              colección Postman (14 peticiones, 47 assertions)
├── test_tc_m02_g97.py                Pytest — TC-M02-314 (usuario sin READ)
└── Resultados/
    ├── reporte_tc_m02_g97_newman.html
    ├── reporte_tc_m02_g97_newman.json
    ├── reporte_tc_m02_g97_pytest.xml
    └── TC-M02-G97_resultado.md       este informe
```

| Herramienta | Resultado |
|---|---|
| Newman | 14 peticiones · 47 assertions · **42 correctas / 5 fallidas** · 4.4 s |
| Pytest | 7 tests · **7 passed / 0 failed** · 5.1 s |

Las 5 fallas de Newman corresponden íntegramente a DEF-G97-01 (TC-313-A y TC-313-B). Todas las assertions de SETUP, TC-M02-312, **TC-M02-314** y diagnóstico pasaron.

Por sub-caso: TC-312 **6/6** · TC-313-A 3/6 · TC-313-B 5/7 · TC-314 **7/7**.
