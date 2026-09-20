# REEVALUACIÓN V2 — TC-M02-G47

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF | RF-40 — Registro de eventos de crecimiento |
| Caso | TC-M02-G47 |
| Subcaso | TC-M02-089 — Stored XSS en `descripcion` (ASVS V5.3 / OWASP API8) |
| Ambiente | TEST (backend HTTPS, frontend y PostgreSQL de TEST) |
| Rama | `qa/juan-esteban-re-evaluacion-m02` (nombre exacto devuelto por Git) |
| HEAD V2 | `7e1174d145b2785b331f8c63f49dc6f1b0989621` — *Reevaluaciones M09, RF-17 y RF-24* |
| Pytest V1 base | `test_tc_m02_g47.py` |
| Pytest V2 | `EvaluacionV2/test_tc_m02_g47_v2.py` |
| Cypress V1 base | `verificar_render_tc_m02_g47.cy.js` |
| Cypress V2 | `EvaluacionV2/verificar_render_tc_m02_g47_v2.cy.js` |
| Único cambio funcional permitido | Fixtures (IDs de activo e identificadores) |
| Fixtures V2 | 450 / 451 / 452 |
| Pytest | **21/21 aprobados**, 0 fallidos |
| Cypress | **3/3 aprobados**, 0 fallidos |
| BD | ✅ Exactamente 1 evento XSS por fixture (355 / 356 / 357), descripción idéntica, +3 global, sin otras escrituras |
| Veredicto TC-M02-089 | ✅ **APROBADO** |
| Hallazgos V1 reevaluados | 3 de 3. **OBS-G47-03 (`/sesiones/refresh` → 500): OBSERVACIÓN PERSISTE**. Credencial del Veterinario: OBSERVACIÓN RESUELTA. Paginación del listado: OBSERVACIÓN RESUELTA |
| Regresiones | Ninguna |

**Hay dos resultados independientes:**

- **A. Caso principal TC-M02-089: APROBADO.** El sistema almacena el payload como dato y lo presenta escapado, sin ejecución y sin navegación a `evil.test`, para los tres actores.
- **B. Hallazgo OBS-G47-03: PERSISTE.** Ahora se reproduce de forma determinista, por API y por interfaz, con los tres actores. `POST /sesiones/refresh` con una cookie válida devuelve **HTTP 500 `AUDITORIA_OBLIGATORIA_FALLIDA`**. La evidencia de BD (read-only) apunta a que el catálogo de TEST no tiene el tipo de evento 23 (§14.3).

---

## 1. Objetivo

La reevaluación tiene dos partes:

1. **Reejecutar TC-M02-089** con la misma automatización funcional de V1: mismo payload, actores, credenciales, endpoint, criterios y aserciones. La única sustitución son los fixtures, por equivalentes limpios de TEST.
2. **Reevaluar de forma dirigida cada hallazgo de V1**, reproduciendo expresamente su escenario sin deducir su estado a partir de la prueba principal.

---

## 2. Trazabilidad V1

Informe V1: `TC-M02-G47/Resultados/TC-M02-G47_resultado.md`. Se leyó completo y su hash coincide con el blob de `HEAD` (`0b453d1c…`).

| Elemento | V1 |
|---|---|
| Veredicto TC-M02-089 | **APROBADO** |
| Pytest ejecutado | `test_tc_m02_g47.py` (S1–S5, S8 y aislamiento, ×3 actores) |
| Resultado Pytest | 21/21 aprobados (`Resultados/reporte_tc_m02_g47.xml`) |
| Cypress ejecutado | `verificar_render_tc_m02_g47.cy.js` (S6/S7, ×3 actores) |
| Resultado Cypress | 3/3 aprobados |
| Activos usados | 279 `QAJE-CREC-OK` / 311 `QAJE-CREC-OK-VET` / 312 `QAJE-CREC-OK-ING` |
| Eventos creados V1 | 234 / 235 / 236 (2026-09-10 08:33:36Z) |
| Evidencia BD | `descripcion` idéntica al payload, Δ +1 por activo, +3 global |
| Evidencia renderizado | Pestaña Historial: `textContent` = payload, `innerHTML` con `&lt;script&gt;`, 0 nodos hijo, 0 peticiones a `evil.test` |
| HEAD V1 | `41369ea4ab3948eacb1ab9b2d0549310e285eeae` (rama `qa/juan-esteban-m02`) |
| Bloqueos | Ninguno |

### 2.1 Inventario de hallazgos V1

Se buscaron en V1 y en sus ejecutables las etiquetas `DEF-`, `BUG`, `OBS-`, `BLOQUEO`, "incidencia" y "hallazgo". V1 no contiene `DEF-`, `BUG` ni `BLOQUEO`. Las etiquetas `OBS-` de V1 **no son consistentes**, y se conservan exactamente como aparecen:

| # | Etiqueta real en V1 | Dónde | Tipo | Escenario V1 | Resultado V1 |
|---|---|---|---|---|---|
| H1 | **OBS-G47-01** | §3.2 | Credencial / datos de prueba | Login del Veterinario con `juan.carlos@email.com` / `Test1234!` | HTTP 401 `CREDENCIALES_INVALIDAS`; el correo no existía en `modulo1.usuarios`. Se usó el usuario id 3 (`juan.carlos.qa133@sgpmp-test.com`) |
| H2 | **OBS-G47-01** (§10) y **OBS-G47-02** (comentario del spec Cypress V1) | §10 y `verificar_render_tc_m02_g47.cy.js:93` | Funcional / frontend, severidad Media | Listado de activos del Productor: 22 registros en 2 páginas | `RegistryView` mostraba solo la página 1, sin control de paginación. Estado: Abierto |
| H3 | **OBS-G47-03** | §8.3 | Backend / sesión, causa no confirmada | Cypress: login por la interfaz y después `cy.visit()` (recarga) | `POST /sesiones/refresh` → **HTTP 500**. Por API solo se probaron las variantes sin cookie y con cookie inválida (401), y el 500 no se reprodujo fuera de Cypress |
| — | (sin etiqueta) §8.1 | Diagnóstico | Error de aplicación de la prueba | Fecha fija futura en el payload | `422 FECHA_FUTURA`, comportamiento correcto del producto. No es hallazgo de producto |
| — | (sin etiqueta) §8.2 | Diagnóstico | Atribuido en V1 a la prueba | `cy.visit()` tras el login llevaba a `/login` | V1 lo atribuyó al token en memoria. Se reanaliza en §14.4 |

---

## 3. Motivo de nuevos fixtures

Los eventos biológicos de TEST son **inmutables**: no se pueden eliminar por API, están prohibidos los borrados por SQL y hay triggers de inmutabilidad que no deben desactivarse. Los activos de V1 conservan eventos históricos con el payload:

| Activo V1 | Eventos con el payload |
|---|---|
| 279 | 234 (V1, 2026-09-10) y 352 (reevaluación V2 anterior, 2026-09-19 05:25Z) |
| 311 | 235 y 353 |
| 312 | 236 y 354 |

Con esos residuos, la aserción de aislamiento `COUNT(payload) == 1` falla por diseño en cualquier reejecución sobre 279/311/312. Por eso QA creó tres fixtures equivalentes y limpios (450/451/452), sobre los que la aserción original vuelve a ser válida **sin relajarla**.

Los artefactos del intento V2 anterior fueron retirados por QA: al comenzar, `EvaluacionV2/` no existía. Sus eventos 352–354 siguen en TEST y **no se tocaron**.

---

## 4. Fixtures V2

Datos del gate read-only (`gate_pre_v2.json`, 2026-09-19 06:18:14Z):

| Actor | V1 | V2 | Identificador | Estado | Tipo | Fase activa | Eventos PRE | PRE XSS |
|---|---:|---:|---|---|---|---:|---:|---:|
| Productor (usuario 35) | 279 | **450** | `QAJE-G47-V2-PROD` | ACTIVO | INDIVIDUAL | 1 | 0 | **0** |
| Veterinario (usuario 3) | 311 | **451** | `QAJE-G47-V2-VET` | ACTIVO | INDIVIDUAL | 1 | 0 | **0** |
| Ingeniero de campo (usuario 4) | 312 | **452** | `QAJE-G47-V2-ING` | ACTIVO | INDIVIDUAL | 1 | 0 | **0** |

Los fixtures los creó QA previamente. El agente no los creó, modificó ni borró.

---

## 5. Equivalencia del Pytest

`EvaluacionV2/test_tc_m02_g47_v2.py` es una copia del ejecutable V1. Diff completo (`Resultados/diff_pytest_v1_v2.txt`, `git diff --no-index`, 3 líneas añadidas y 3 eliminadas):

```diff
 ACTORES: list[Actor] = [
-    Actor('productor', 'Productor', 'm2m.nuevo@ejemplo.com', 'Test1234!', 35, 279),
-    Actor('veterinario', 'Veterinario', 'juan.carlos.qa133@sgpmp-test.com', 'Test1234!', 3, 311),
-    Actor('ingeniero', 'Ingeniero de campo', 'ingeniero@pecuaria.co', 'Pruebas12#', 4, 312),
+    Actor('productor', 'Productor', 'm2m.nuevo@ejemplo.com', 'Test1234!', 35, 450),
+    Actor('veterinario', 'Veterinario', 'juan.carlos.qa133@sgpmp-test.com', 'Test1234!', 3, 451),
+    Actor('ingeniero', 'Ingeniero de campo', 'ingeniero@pecuaria.co', 'Pruebas12#', 4, 452),
 ]
```

No cambió nada más. Se mantienen `PAYLOAD_XSS`, `FECHA_EVENTO`, `TIPO_MEDICION`, `VALOR_MEDICION`, `UNIDAD_MEDIDA`, `BASE_URL`, `DSN`, las credenciales, los nombres de test, las aserciones, el HTTP esperado 201, las consultas de persistencia, el criterio `COUNT == 1`, la lógica PRE/POST y la de evidencia.

| Archivo | Hash |
|---|---|
| V1 `test_tc_m02_g47.py` | `9fa2d566aeb7329617697765c05a33a14649d6fe` (= blob de `HEAD`) |
| V2 `test_tc_m02_g47_v2.py` | `a177a398e2e1b8e429b46b3a0bca0584bb5883ac` |

Al estar en `EvaluacionV2/`, la fixture `volcar_evidencia` del código escribe su evidencia en `EvaluacionV2/Resultados/evidencia_g47.json`, sin tocar V1.

**Formulación correcta:** V1 y V2 **no** usan los mismos IDs de activo. V2 usa la misma automatización funcional y las mismas aserciones de V1, sustituyendo solo los identificadores de fixtures por equivalentes limpios de TEST. No es el mismo archivo byte a byte.

---

## 6. Gate

| # | Verificación | Resultado |
|---|---|---|
| 1 | Rama / HEAD | ✅ `qa/juan-esteban-re-evaluacion-m02` / `7e1174d1`. Sin cambios en archivos versionados |
| 2 | BD read-only | ✅ `SET default_transaction_read_only = on`. `member_qa` / `sgpmp_test` / `transaction_read_only = on` |
| 3 | OpenAPI TEST | ✅ 200. `POST /activos-biologicos/{id_activo}/eventos/crecimiento` declarado |
| 4 | DTO | ✅ Obligatorios `tipo_medicion`, `valor_medicion`, `unidad_medida`. `descripcion` = `anyOf [string, null]`, sin `maxLength` |
| 5 | Fixtures 450/451/452 | ✅ ACTIVO, INDIVIDUAL, 1 fase activa, 0 eventos, **0 XSS** (§4) |
| 6 | Safety stop | ✅ Ningún fixture con `eventos_xss > 0`. Se confirmó con el gate ya generado antes de lanzar Pytest |
| 7 | Login y acceso | ✅ Productor: login 200, `sub` 35, `GET /activos-biologicos/450` → 200 `QAJE-G47-V2-PROD`. Veterinario: login 200, `sub` 3, `GET …/451` → 200 `QAJE-G47-V2-VET`. Ingeniero: login 200, `sub` 4, `GET …/452` → 200 `QAJE-G47-V2-ING` |
| 8 | Línea base global | `eventos_activos` = 166 filas, `max(id_eventos)` = 354. `eventos_crecimeinto` = 61. Eventos con el payload = 6 (234–236 y 352–354, todos en 279/311/312) |

---

## 7. Resultado Pytest

Ejecución única, desde la raíz de `sgpmp-backend`, 2026-09-19 06:24:52 → 06:25:29 UTC:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest "$G/EvaluacionV2/test_tc_m02_g47_v2.py" -v -p no:cacheprovider \
  --junitxml="$G/EvaluacionV2/Resultados/reporte_tc_m02_g47_v2.xml" 2>&1 | tee "$G/EvaluacionV2/Resultados/reporte_tc_m02_g47_v2.txt"
```

- **total:** 21
- **passed:** 21
- **failed:** 0 (errors 0, skipped 0), 34,68 s

| Actor | S1 | S2 | S3 | S4 | S5 | S8 | Aislamiento |
|---|---|---|---|---|---|---|---|
| Productor | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Veterinario | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ingeniero de campo | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

En V2 el aislamiento `COUNT(payload) == 1` pasa **sin modificarlo**, porque los fixtures empezaron con 0 eventos XSS.

---

## 8. Eventos creados V2

Datos de `evidencia_g47.json` (V2) y de `bd_post_pytest_v2.json`:

| Actor | Activo | Evento | Usuario | HTTP | Conteo antes → después | Payload | Resultado |
|---|---:|---:|---:|---:|---|---|---|
| Productor | 450 | **355** | 35 | 201 | 0 → 1 | idéntico | ✅ |
| Veterinario | 451 | **356** | 3 | 201 | 0 → 1 | idéntico | ✅ |
| Ingeniero de campo | 452 | **357** | 4 | 201 | 0 → 1 | idéntico | ✅ |

Cuerpo enviado, idéntico para los 3 actores:

```json
{"tipo_medicion": "PESO", "valor_medicion": 250, "unidad_medida": "kg", "fecha": "2026-09-19T06:22:54Z", "descripcion": "<script>document.location=\"http://evil.test\"</script>"}
```

La fecha la calcula el propio ejecutable al cargarse (*ahora − 2 min*), igual que en V1.

---

## 9. Evidencia BD

Todas las consultas se hicieron con la sesión en `transaction_read_only = on`. Solo `SELECT`.

```sql
SELECT ea.id_eventos, ea.id_activo_biologico, ea.id_usuario, ea.fecha, ea.descripcion,
       ec.tipo_medicion, ec.valor_medicion, ec.unidad_medida,
       length(ea.descripcion), md5(ea.descripcion), ea.descripcion = :payload
FROM modulo2.eventos_activos ea
JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico IN (450,451,452)
  AND ea.descripcion = '<script>document.location="http://evil.test"</script>'
ORDER BY ea.id_activo_biologico;
```

| id_eventos | activo | usuario | fecha | tipo | valor | unidad | descripcion | long. | md5 | = payload |
|---:|---:|---:|---|---|---:|---|---|---:|---|---|
| 355 | 450 | 35 | 2026-09-19 06:22:54+00 | PESO | 250.00 | kg | `<script>document.location="http://evil.test"</script>` | 53 | `af18f434…ccfffd1` | true |
| 356 | 451 | 3 | 2026-09-19 06:22:54+00 | PESO | 250.00 | kg | `<script>document.location="http://evil.test"</script>` | 53 | `af18f434…ccfffd1` | true |
| 357 | 452 | 4 | 2026-09-19 06:22:54+00 | PESO | 250.00 | kg | `<script>document.location="http://evil.test"</script>` | 53 | `af18f434…ccfffd1` | true |

El md5 de referencia del payload es `af18f4345a585504f34b0af13ccfffd1` (53 caracteres). **Se almacenó sin alteraciones**: sin escapado, truncado ni sanitización destructiva.

Conteo de eventos XSS por fixture (consulta de §16 del paquete), tomado después de Pytest (06:25:49Z) y en la verificación final después de Cypress (06:27:23Z), con el mismo resultado:

| id_activo_biologico | cantidad |
|---:|---:|
| 450 | 1 |
| 451 | 1 |
| 452 | 1 |

| Métrica global | Gate | Final | Δ |
|---|---:|---:|---:|
| `eventos_activos` — filas | 166 | 169 | **+3** |
| `eventos_activos` — `max(id_eventos)` | 354 | 357 | **+3** |
| `eventos_crecimeinto` — filas | 61 | 64 | **+3** |
| Eventos con el payload | 6 | 9 | **+3** |
| Eventos con `id_eventos > 354` | — | 355, 356, 357 | solo los oficiales |

Los fixtures 450/451/452 siguen ACTIVO, INDIVIDUAL y con 1 fase activa. Los eventos históricos 234, 235, 236, 352, 353 y 354 siguen intactos.

---

## 10. Equivalencia Cypress

`EvaluacionV2/verificar_render_tc_m02_g47_v2.cy.js` es una copia del spec V1. Diff completo (`Resultados/diff_cypress_v1_v2.txt`, 6 líneas añadidas y 6 eliminadas):

```diff
-    idActivo: 279,
-    identificador: 'QAJE-CREC-OK',
+    idActivo: 450,
+    identificador: 'QAJE-G47-V2-PROD',
 ...
-    idActivo: 311,
-    identificador: 'QAJE-CREC-OK-VET',
+    idActivo: 451,
+    identificador: 'QAJE-G47-V2-VET',
 ...
-    idActivo: 312,
-    identificador: 'QAJE-CREC-OK-ING',
+    idActivo: 452,
+    identificador: 'QAJE-G47-V2-ING',
```

**Campo `idEvento` (234/235/236): se dejó intacto.** Se comprobó en el código que solo aparece en su declaración (líneas 37, 45 y 53 del spec V1) y que ninguna aserción, selector ni navegación lo usa. Es un campo legado inactivo del spec y no participa en la ejecución.

Hashes: V1 `38f049c5ce81b5cb96a869b514a0f2780143bc57` (= blob de `HEAD`); V2 `c5185110fc9acf77d0044b16927e31838c9322d0`. No se añadió ningún complemento de renderizado: el spec V2 equivalente cubre S6/S7 por completo, porque en cada fixture la única celda con el payload es la del evento V2.

---

## 11. Resultado Cypress

Ejecución única, 2026-09-19 06:26:01 → 06:27:06 UTC. Cypress 14.5.4, Electron 130 headless, Node 22.15.1.

- **total:** 3
- **passed:** 3
- **failed:** 0 (14 s)

Evidencia: `reporte_cypress_g47_v2.txt`, `mochawesome_cypress_g47_v2/mochawesome.html` y `screenshots/verificar_render_tc_m02_g47_v2.cy.js/render_seguro_historial_productor.png`. Mochawesome escribe por configuración en `mochawesome-report/` en la raíz, y el reporte se movió a `EvaluacionV2/Resultados/`. No quedó ningún residuo fuera de V2.

---

## 12. Evidencia de renderizado seguro

Vista: `/activos-biologicos/{id}` → pestaña **Historial** del frontend TEST (`https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`). Login por la interfaz y navegación dentro de la SPA.

| Actor | Activo | Evento | Texto visible literal | `innerHTML` escapado | `<script>` en la celda / nodos hijo | Scripts contaminados en el documento | Hostname / pathname | Peticiones a evil.test | Excepciones | Vista operativa | Resultado |
|---|---:|---:|---|---|---|---|---|---:|---|---|---|
| Productor | 450 | 355 | ✅ | ✅ `&lt;script&gt;` | ✅ ninguno / 0 | ✅ 0 | ✅ TEST / `/activos-biologicos/450` | **0** | ✅ 0 | ✅ | **APROBADO** |
| Veterinario | 451 | 356 | ✅ | ✅ `&lt;script&gt;` | ✅ ninguno / 0 | ✅ 0 | ✅ TEST / `/activos-biologicos/451` | **0** | ✅ 0 | ✅ | **APROBADO** |
| Ingeniero de campo | 452 | 357 | ✅ | ✅ `&lt;script&gt;` | ✅ ninguno / 0 | ✅ 0 | ✅ TEST / `/activos-biologicos/452` | **0** | ✅ 0 | ✅ | **APROBADO** |

La captura del Productor muestra `QAJE-G47-V2-PROD` (ID #450) → Historial con 2 registros: `FASE_PRODUCTIVA` (2026-06-01) y `CRECIMIENTO` (2026-09-19). En la columna Descripción de esta última aparece `<script>document.location="http://evil.test"</script>` como texto legible. Al haber una sola fila con el payload, la celda comprobada es sin ambigüedad la del evento 355.

---

## 13. Reejecución de TC-M02-089

**TC-M02-089 = APROBADO.** Con los tres actores:

- el POST registra el evento (`201`);
- el payload queda almacenado como dato, idéntico byte a byte;
- la API lo devuelve como cadena JSON;
- la vista lo presenta como texto codificado;
- no se crea ni ejecuta ningún `<script>`;
- no hay navegación ni peticiones a `evil.test`;
- la vista sigue operativa.

Pytest 21/21, Cypress 3/3 y la BD lo confirman.

---

## 14. Reevaluación dirigida de hallazgos V1

Esta parte se ejecutó después de Pytest y Cypress, para que las operaciones de sesión no afectaran a la prueba principal. Ninguna de estas ejecuciones escribió datos de dominio. Artefactos: `EvaluacionV2/hallazgos_g47_v2.cy.js`, `EvaluacionV2/hallazgos_paginacion_g47_v2.cy.js` y `EvaluacionV2/hallazgos_api_g47_v2.py`. Evidencia: `hallazgos_ui_v2.json`, `hallazgos_paginacion_v2.json` y `hallazgos_api_v2.json` (tokens y cookies redactados), más sus reportes y capturas.

### 14.1 H1 — OBS-G47-01 (V1 §3.2): credencial documentada del Veterinario

- **Escenario V1:** `POST /sesiones/` con `juan.carlos@email.com` / `Test1234!`.
- **Resultado V1:** HTTP 401 `CREDENCIALES_INVALIDAS`; el correo no existía en `modulo1.usuarios`.
- **Ejecución dirigida V2** (`hallazgos_api_g47_v2.py`, 2026-09-19 06:28:50Z): el mismo `POST /sesiones/` con las mismas credenciales, más un `SELECT` read-only sobre `modulo1.usuarios`.
- **Evidencia:**
  - Login → **HTTP 200**, `tipo: Bearer`, `expira_en: 28799`, mensaje *«Sesión iniciada exitosamente. Se ha cerrado automáticamente la sesión activa en otros dispositivos…»*.
  - BD: `juan.carlos@email.com` existe ahora como **usuario id 97, rol 3 (Veterinario)**. El usuario id 3 (`juan.carlos.qa133@sgpmp-test.com`, rol 3) sigue existiendo y es el que usa la automatización.
- **Evolución: OBSERVACIÓN RESUELTA** respecto del síntoma de V1: la credencial documentada ya autentica.
- **Nota:** esa credencial corresponde a **otro usuario** (id 97), no al usuario 3 que usan V1 y V2, y no se verificó si el usuario 97 tiene acceso a los fixtures. La recomendación de V1 de alinear el paquete de instrucciones con el actor realmente usado sigue vigente. Efecto colateral: por la política de sesión única, este login cerró cualquier otra sesión activa del usuario 97.

### 14.2 H2 — OBS-G47-01 (V1 §10) / OBS-G47-02 (spec V1): listado de activos sin paginación

- **Escenario V1:** el Productor abre «Activos biológicos». El backend devolvía 22 registros en 2 páginas, pero `RegistryView` mostraba solo la primera, sin control de paginación.
- **Resultado V1:** Abierto, severidad Media, Desarrollo Frontend.
- **Ejecución dirigida V2:**
  1. `hallazgos_api_g47_v2.py`: `GET /activos-biologicos` con cada actor.
  2. `hallazgos_g47_v2.cy.js`: inspección del listado por la interfaz con cada actor.
  3. `hallazgos_paginacion_g47_v2.cy.js`: el Productor pulsa «Siguiente» y después «Anterior».
- **Evidencia:**

| Actor | API: registros / páginas | UI: contador | UI: filas | UI: «Página X de Y» | Botones Anterior / Siguiente | Fixture visible |
|---|---|---:|---:|---|---|---|
| Productor | 23 / **2** | 23 | 20 | ✅ | ✅ / ✅ | ✅ `QAJE-G47-V2-PROD` |
| Veterinario | 9 / 1 | 9 | 9 | — (1 página) | — | ✅ `QAJE-G47-V2-VET` |
| Ingeniero de campo | 9 / 1 | 9 | 9 | — (1 página) | — | ✅ `QAJE-G47-V2-ING` |

Comportamiento con el Productor (`hallazgos_paginacion_v2.json`):

- inicial: `Página 1 de 2 · 23 registro(s)`, 20 filas;
- tras «Siguiente»: `Página 2 de 2 · 23 registro(s)`, **3 filas** (20 + 3 = 23), con filas distintas de las de la página 1;
- «Anterior» vuelve a la página 1;
- peticiones `GET /activos-biologicos?pagina=1` → 200, `?pagina=2` → 200 y `?pagina=1` → 200.

Captura: `screenshots/hallazgos_paginacion_g47_v2.cy.js/listado_productor_pagina_2.png`.

- **Evolución: OBSERVACIÓN RESUELTA.** El control de paginación existe y funciona en el frontend desplegado en TEST.
- **Nota:** la copia local del repositorio del frontend (`SGPMP-FRONT-END-PWA`, commit `45cdb05`) todavía no usa `Paginacion` en `RegistryView.tsx`. La compilación desplegada en TEST difiere de esa copia local, y la clasificación se basa en el comportamiento observado en TEST.
- **Incidencia de la propia automatización, no del producto:** los dos primeros intentos de `hallazgos_paginacion_g47_v2.cy.js` fallaron porque el texto «Página X de Y» quedaba fuera del área visible, debajo de una tabla de 20 filas dentro de un contenedor con `position: fixed`. En el primer intento falló la línea 29 y en el segundo la 48; en el segundo ya se había llegado a la página 2. Se añadió `scrollIntoView()` sin cambiar ninguna comprobación, y el tercer intento pasó 1/1. Los tres intentos son de solo lectura y su evidencia se conserva (`reporte_cypress_paginacion_v2_intento1.txt`, `…_intento2.txt`, `mochawesome_paginacion_v2_intento1/`, `…_intento2/` y capturas `(failed)`).

### 14.3 H3 — OBS-G47-03 (V1 §8.3): `POST /sesiones/refresh` → HTTP 500

- **Escenario V1:** con los tres actores, login por la interfaz y a continuación `cy.visit()` a la ruta del activo. Esa recarga descarta el access token en memoria y la SPA llama a `POST /sesiones/refresh` con la cookie HttpOnly `refresh_token`.
- **Resultado V1:** HTTP 500 en la traza de Cypress. Por API, sin cookie → 401 `REFRESH_TOKEN_REQUERIDO` y con cookie inválida → 401 `REFRESH_TOKEN_INVALIDO`. **No se probó por API una cookie válida.** Causa no confirmada.
- **Contrato actual (OpenAPI TEST):** `POST /sesiones/refresh` canjea la cookie `refresh_token` por un access token nuevo. La descripción dice expresamente que *«reemplaza justamente la necesidad de credenciales cuando el access token en memoria se perdió (recarga de página) o expiró»*. Respuestas declaradas: **200, 401, 410, 422**. El 500 no está declarado.
- **Ejecución dirigida V2:**
  1. **Escenario V1 exacto** (`hallazgos_g47_v2.cy.js`, 06:27:24 → 06:28:30Z): login por la interfaz con cada actor y después `cy.visit()` a `/activos-biologicos/{450|451|452}`. Se intercepta `POST **/sesiones/refresh`.
  2. **Por API** (`hallazgos_api_g47_v2.py`, 06:28:50 → 06:29:05Z): con cada actor, login (emite `Set-Cookie: refresh_token=…; HttpOnly; Max-Age=604799; Path=/; SameSite=lax; Secure`) y después `POST /sesiones/refresh` en cuatro variantes: sin cookie, con cookie inválida, con la cookie válida recién emitida y reutilizando esa misma cookie.
- **Evidencia:**

| Variante | Productor | Veterinario | Ingeniero de campo |
|---|---|---|---|
| UI: recarga tras login (escenario V1), cookie enviada | **500** → redirige a `/login` | **500** → `/login` | **500** → `/login` |
| API: sin cookie | 401 `REFRESH_TOKEN_REQUERIDO` | 401 | 401 |
| API: cookie inválida | 401 `REFRESH_TOKEN_INVALIDO` | 401 | 401 |
| API: **cookie válida** del login | **500** | **500** | **500** |
| API: misma cookie reutilizada | **500** | **500** | **500** |

Cuerpo de todos los 500:

```json
{"error_code":"AUDITORIA_OBLIGATORIA_FALLIDA",
 "message":"Fallo crítico de seguridad: No se pudo generar el registro de auditoría obligatorio. La operación REFRESH_TOKEN_ROTADO ha sido cancelada para garantizar la trazabilidad del sistema.",
 "fields":[]}
```

Ningún 500 emitió una cookie nueva (`refresh_emite_cookie_nueva = false`): la rotación se revierte completa. Capturas `screenshots/hallazgos_g47_v2.cy.js/tras_recarga_{450,451,452}.png`: pantalla «Iniciar sesión» tras la recarga.

- **Causa probable (evidencia read-only, sin traza del servidor):**
  - `src/identity_access/application/use_cases/sesiones/refresh_token_use_case.py` (≈ línea 157) registra un evento de auditoría con `tipo_evento = 23` (`REFRESH_TOKEN_ROTADO`) antes del `commit`.
  - `src/identity_access/infrastructure/repositories/evento_repository.py` (≈ línea 355) traduce cualquier fallo de ese registro en `AUDITORIA_OBLIGATORIA_FALLIDA`, y el caso de uso hace `rollback`.
  - En la BD de TEST, `modulo1.tipos_eventos` contiene los ids 1–22, 25 y 26 (24 filas, máximo 26), pero **no el 23**. `modulo1.eventos` tiene la restricción `fk_tipo_evento FOREIGN KEY (tipo_evento) REFERENCES modulo1.tipos_eventos(id_tipo_evento)`. `SELECT count(*) FROM modulo1.eventos WHERE tipo_evento = 23` → **0**: nunca se ha registrado una rotación.
  - Conclusión: el INSERT de auditoría viola la FK, la operación se cancela y el endpoint devuelve 500 en **todo** refresh legítimo. Esta causa es consistente con toda la evidencia, pero no está confirmada con el log del backend.
- **Impacto:** fuera del alcance de RF-40 / TC-M02-089. Cualquier usuario pierde la sesión al recargar la página, y también cuando expira el access token (el refresh es el mecanismo de renovación), y tiene que volver a autenticarse.
- **Evolución: OBSERVACIÓN PERSISTE.** V2 la reproduce deliberadamente con el mismo escenario de V1 y además por API, de forma determinista (6/6 refresh legítimos → 500).
- **Datos para un posible registro (no se creó incidencia):** RF de sesiones del Módulo 1 (identidad y acceso). Categoría backend/BD (catálogo de tipos de evento incompleto en TEST). Equipo sugerido: Backend / BD. Severidad sugerida, a confirmar por QA: **Alta**, porque impide el refresh de sesión para todos los usuarios.

### 14.4 Diagnósticos V1 sin etiqueta (§8.1 y §8.2)

- **§8.1 — `422 FECHA_FUTURA` por una fecha fija en el ejecutable.** V1 lo clasificó como error de aplicación de la prueba; el producto se comportó correctamente al rechazar la fecha futura. **No es hallazgo de producto**, así que no requiere reproducción. En V2 el ejecutable calcula la fecha como *ahora − 2 min*, S1 afirma que no es futura (aprobado ×3) y los POST devolvieron 201.
- **§8.2 — pérdida de sesión al recargar en Cypress.** V1 lo atribuyó a la prueba, porque el token vive solo en memoria. **La evidencia V2 corrige esa atribución:** según el contrato, tras una recarga la SPA recupera la sesión con `/sesiones/refresh`. La pérdida de sesión observada en V1 se explica por OBS-G47-03 (refresh → 500), no solo por el diseño del token en memoria. Evolución: **no es un hallazgo independiente**; queda absorbido por OBS-G47-03, que **PERSISTE**. La navegación dentro de la SPA que usan los specs sigue siendo válida y no afecta a TC-M02-089.

---

## 15. Comparación V1 ↔ V2

### 15.1 Caso principal

| Dimensión | V1 | V2 | Evolución |
|---|---|---|---|
| Pytest API/persistencia | 21/21 sobre 279/311/312 | 21/21 sobre 450/451/452 | **SIN REGRESIÓN** |
| Productor | 201, evento 234, idéntico, aislado | 201, evento 355, idéntico, aislado | **SIN REGRESIÓN** |
| Veterinario | 201, evento 235, idéntico, aislado | 201, evento 356, idéntico, aislado | **SIN REGRESIÓN** |
| Ingeniero | 201, evento 236, idéntico, aislado | 201, evento 357, idéntico, aislado | **SIN REGRESIÓN** |
| BD | +1 por activo, +3 global | 1 XSS por fixture, +3 global, md5 idéntico | **SIN REGRESIÓN** |
| Cypress renderizado | 3/3 | 3/3 | **SIN REGRESIÓN** |
| No ejecución XSS | 0 `<script>` derivados, 0 excepciones | 0 `<script>` derivados, 0 excepciones | **SIN REGRESIÓN** |
| No navegación evil.test | 0 peticiones, sin navegación | 0 peticiones, sin navegación | **SIN REGRESIÓN** |
| TC-M02-089 | APROBADO | APROBADO | **SIN REGRESIÓN** |

### 15.2 Hallazgos

| Hallazgo | V1 | Verificación V2 | Resultado V2 | Evolución |
|---|---|---|---|---|
| OBS-G47-01 (§3.2) — credencial del Veterinario | Login `juan.carlos@email.com` → 401; el correo no existía | Mismo login y `SELECT` de usuarios | Login 200; el correo existe como usuario id 97 (rol 3), distinto del id 3 que usa la prueba | **OBSERVACIÓN RESUELTA** (síntoma). Nota de alineación del paquete (§14.1) |
| OBS-G47-01 (§10) / OBS-G47-02 — paginación del listado | Solo página 1, sin control | API + UI con 3 actores; clic en Siguiente/Anterior con el Productor | «Página 1 de 2», Siguiente → página 2 con 3 filas, Anterior → página 1; peticiones 200 | **OBSERVACIÓN RESUELTA** |
| OBS-G47-03 — `/sesiones/refresh` → 500 | 500 en Cypress tras la recarga; por API solo se probaron las variantes 401 | Escenario V1 (recarga) ×3 + API con cookie válida, inválida, ausente y reutilizada | 500 `AUDITORIA_OBLIGATORIA_FALLIDA` en 6/6 refresh legítimos; 401 correcto en las variantes inválidas | **OBSERVACIÓN PERSISTE** |
| §8.1 — `FECHA_FUTURA` | Error de la prueba; producto correcto | No requiere reproducción | No es hallazgo de producto | No aplica |
| §8.2 — pérdida de sesión al recargar | Atribuida al token en memoria | Mismo escenario que OBS-G47-03 | Causada por el 500 del refresh | Absorbido por OBS-G47-03 (**PERSISTE**) |

---

## 16. Regresiones

No se identificaron regresiones en TC-M02-089 ni en ningún hallazgo V1: ninguno pasó de resuelto a fallido.

OBS-G47-03 no es una regresión: ya existía en V1. Lo nuevo en V2 es que se reprodujo de forma determinista y se aisló su causa probable.

---

## 17. Observaciones

1. **OBS-G47-03 persiste y afecta a toda la aplicación.** Aunque es ajeno a RF-40, no se oculta: ver §14.3 con la causa probable (falta el tipo de evento 23 en `modulo1.tipos_eventos` de TEST).
2. **Etiquetas duplicadas en V1.** `OBS-G47-01` se usa para dos observaciones distintas (§3.2 y §10), y el spec V1 llama `OBS-G47-02` a la segunda. No existe una `OBS-G47-02` formal en el informe V1. Aquí se conservaron las etiquetas reales; conviene normalizarlas si se registran.
3. **Credencial del Veterinario.** El correo documentado ahora pertenece al usuario 97, no al usuario 3 que ejecuta la prueba. Hay que confirmar cuál es el actor Veterinario de referencia de RF-40.
4. **El frontend desplegado difiere de la copia local** (paginación, §14.2). La verificación se hizo contra TEST.
5. **Efectos de sesión.** Los logins de los scripts de hallazgos, incluido el del usuario 97, cerraron por política de sesión única otras sesiones activas de esos usuarios. No afecta a datos de dominio.
6. **Datos residuales en TEST.** Los eventos 355/356/357 son la evidencia inmutable de V2 y no se eliminarán. Una nueva reejecución sobre 450/451/452 volvería a romper `COUNT == 1`; requeriría nuevos fixtures limpios preparados por QA.

---

## 18. Veredicto final

**A. TC-M02-089 — ✅ APROBADO**

- Pytest cumple todas las aserciones: 21/21.
- Cada actor creó exactamente 1 evento (355 / 356 / 357).
- La BD confirma una persistencia exacta: payload idéntico, PESO / 250.00 / kg, usuario y activo correctos, +3 global.
- Cypress demuestra el renderizado como texto: 3/3.
- 0 `<script>` ejecutables.
- 0 navegaciones o peticiones a `evil.test`.

**B. Hallazgos V1**

| Hallazgo | Estado V2 |
|---|---|
| OBS-G47-01 (§3.2) — credencial del Veterinario | **OBSERVACIÓN RESUELTA** (con nota de alineación) |
| OBS-G47-01 (§10) / OBS-G47-02 — paginación del listado | **OBSERVACIÓN RESUELTA** |
| OBS-G47-03 — `/sesiones/refresh` → 500 | ⚠️ **OBSERVACIÓN PERSISTE** |

---

## 19. Declaración de integridad

- ✅ **V1 intacta.** `test_tc_m02_g47.py` (`9fa2d566…`), `verificar_render_tc_m02_g47.cy.js` (`38f049c5…`), `Resultados/TC-M02-G47_resultado.md` (`0b453d1c…`), `reporte_tc_m02_g47.xml` (`a4eda106…`) y `evidencia_g47.json` (`69fc374f…`) coinciden con el blob de `HEAD` al final de la ejecución. Fechas de modificación sin cambios (2026-09-12).
- ✅ **No se borraron eventos históricos** (234–236 y 352–354 intactos) ni los de esta V2 (355–357).
- ✅ **No se desactivaron triggers.**
- ✅ **Los fixtures V2 (450/451/452) los creó QA previamente.** El agente no los creó, modificó ni borró.
- ✅ **El agente no escribió directamente en la BD.** Todas las sesiones estuvieron en `transaction_read_only = on`, y el ejecutable abre su conexión con `readonly=True`. Solo `SELECT`.
- ✅ **Las únicas escrituras de dominio V2 fueron los 3 POST oficiales de TC-M02-089** (eventos 355, 356 y 357), confirmado por Δ global +3 y por los ids nuevos (> 354). Pytest se ejecutó **una sola vez**.
- ✅ **Pytest V2 difiere de V1 solo en los IDs** 279→450, 311→451 y 312→452 (`diff_pytest_v1_v2.txt`).
- ✅ **Cypress V2 difiere solo en los IDs e identificadores de fixture** (`diff_cypress_v1_v2.txt`). `idEvento` legado intacto.
- ✅ **No se modificaron aserciones ni se relajaron criterios.**
- ✅ Los scripts de hallazgos solo hicieron login, GET, `POST /sesiones/refresh` y `SELECT`, sin escrituras de dominio. El spec de paginación solo se corrigió en su desplazamiento (`scrollIntoView`), no en sus comprobaciones, y sus intentos fallidos se conservan como evidencia.
- ✅ **DEV no se usó.**
- ✅ **No se modificó código productivo** del backend ni del frontend; `src/` solo se leyó.
- ✅ **No se hizo commit, push, merge, rebase ni deploy**, y no se cambió de rama. `package.json` y `package-lock.json` siguen sin cambios.
- ✅ No se creó ningún ticket en Taiga ni Issue en GitHub, y no se modificó el Registro de Errores.
- ✅ No se navegó deliberadamente a `evil.test` ni se desactivaron protecciones; el dominio se interceptó.

### Artefactos V2

```text
TC-M02-G47/EvaluacionV2/
├── test_tc_m02_g47_v2.py                    Pytest V2 (copia de V1, solo fixtures)
├── verificar_render_tc_m02_g47_v2.cy.js     Cypress V2 (copia de V1, solo fixtures)
├── hallazgos_api_g47_v2.py                  reevaluación de hallazgos (API + BD read-only)
├── hallazgos_g47_v2.cy.js                   reevaluación de hallazgos (listado + recarga/refresh)
├── hallazgos_paginacion_g47_v2.cy.js        reevaluación de la paginación (comportamiento)
└── Resultados/
    ├── gate_pre_v2.json                     gate y safety stop
    ├── diff_pytest_v1_v2.txt / diff_cypress_v1_v2.txt
    ├── reporte_tc_m02_g47_v2.xml / .txt     Pytest V2 (21/21)
    ├── evidencia_g47.json                   evidencia volcada por el ejecutable V2
    ├── bd_post_pytest_v2.json / bd_post_final_v2.json
    ├── reporte_cypress_g47_v2.txt + mochawesome_cypress_g47_v2/   Cypress V2 (3/3)
    ├── hallazgos_ui_v2.json + reporte_cypress_hallazgos_v2.txt + mochawesome_hallazgos_v2/
    ├── hallazgos_api_v2.json
    ├── hallazgos_paginacion_v2.json + reporte_cypress_paginacion_v2*.txt + mochawesome_paginacion_v2*/
    ├── screenshots/
    └── TC_M02_G47_reevaluacion_V2.md        este informe
```
