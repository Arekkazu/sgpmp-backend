# TC-M09-G30 — REEVALUACIÓN V2

Caso original: **TC-M09-64 — Verificar auditoría de creación y modificación de umbrales**
RF-17 · CU-03 · Auditoría (OWASP A09) · Herramienta: Newman
Responsable QA: Juan Esteban · RUN_ID: `G30-REEVAL-V2-20260913-020215` · Fecha local: 2026-09-13 · Entorno decisorio: **TEST**

---

## DECISIÓN GENERAL

### REEVALUACIÓN APROBADA — TC-M09-64 APROBADO

Con **1 CREATE y 1 UPDATE sobre el mismo recurso** (umbral **44**, Bovino +
Temperatura Corporal), la auditoría de umbrales registró dos eventos
distinguibles y correlacionados de forma inequívoca:

- **CREATE #7:** usuario 104, `fecha_gestion` dentro de la ventana del POST, sin
  valores anteriores y con `valores_nuevos` igual a la configuración creada.
- **UPDATE #8:** usuario 104, `fecha_gestion` dentro de la ventana del PATCH,
  `valores_anteriores` iguales a los del CREATE y `valores_nuevos` iguales a los
  del UPDATE.

Las 30 aserciones Newman pasaron (6 create, 8 auditoría tras create, 5 update y
11 auditoría final).

El bloqueo de V1 (auditoría de umbrales no consultable por API) está resuelto:
**INC-M09-30-G30, corrección verificada por QA**.

| Caso | V1 | V2 | Ambiente decisorio | Motivo | Categoría | Equipo | Acción |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-M09-64 | BLOCKED — auditoría no expuesta/no verificable (0 escrituras) | **APROBADO** | TEST | CREATE (201) y UPDATE (200) del umbral 44 generan los eventos CREATE #7 y UPDATE #8 en `GET /configuracion/umbrales/44/auditoria`, con usuario, fecha/hora, operación y valores correctos | Sin defecto funcional · 2 observaciones | Desarrollo (cierre + observaciones) | **ACTUALIZAR INC-M09-30-G30 COMO CORRECCIÓN VERIFICADA POR QA** · informar observaciones a Desarrollo |

> **Observaciones (no afectan al resultado; se informan a Desarrollo):**
> 1. **D09 global no integra la auditoría de umbrales.** `GET /auditoria/` (D09)
>    no registra ningún evento de las operaciones CREATE/UPDATE de umbrales: en
>    la ventana de la prueba solo contiene LOGIN_EXITOSO, CONSULTA_PERFIL_PROPIO
>    y CONSULTA_AUDITORIA. La trazabilidad de RF-17 vive en su auditoría
>    específica (`modulo9.auditorias_umbrales_ambientales`), expuesta por
>    `GET /configuracion/umbrales/{id}/auditoria`. RF-17 queda cubierto, pero un
>    auditor que consulte solo D09 no verá estos cambios.
> 2. **Formato decimal inconsistente en los snapshots auditados.** Algunos
>    límites se guardan como `"42.0"`, `"41.0"` o `"43.0"` y otros como
>    `"42.00"` (por ejemplo, `critico.limite_superior` es `"42.0"` en el CREATE
>    y `"42.00"` en los `valores_anteriores` del UPDATE). Los valores son
>    numéricamente idénticos a los enviados; es una inconsistencia de
>    representación que dificulta comparar textualmente los snapshots.

---

## RESUMEN V1

Evidencia V1: `RF-17/TC-M09-G30/RESULTADOS/run-20260905/` (solo lectura, intacta).

| Campo | V1 |
| --- | --- |
| Resultado V1 | **BLOCKED — AUDITORÍA NO EXPUESTA/NO VERIFICABLE EN TEST** (`CONTRACT_REQUIREMENT_MISMATCH`) |
| Causa | RF-17 persistía la auditoría en `modulo9.auditorias_umbrales_ambientales`, pero no había API para consultarla por `id_umbral_ambiental`. D09 (`GET /auditoria/`) no expone recurso RF-17 y su catálogo no tiene eventos de umbral |
| HTTP | Solo lecturas: login 200, `/usuarios/me` 200, `/auditoria/` 200, catálogo 200 |
| Actor | Administrador TEST (`id_usuario=1` en aquel momento), con permisos D09 (6/2) y umbrales 20/1-2-3 |
| Ambiente | TEST |
| ID de configuración | Ninguno (0 POST, 0 PATCH) |
| Evento creación encontrado | No verificable (no ejecutado) |
| Evento modificación encontrado | No verificable (no ejecutado) |
| Campos de auditoría (modelo) | `id_auditoria_umbral, id_umbral_ambiental, id_usuario, tipo_operacion, valores_anteriores, valores_nuevos, fecha_gestion` |
| Incidencia | Registrada después por Desarrollo como **INC-M09-30-G30** («Faltaba endpoint `GET /umbrales/{id}/auditoria`»), corregida en el commit `693fd57` (en rc.33) |
| Categoría / equipo V1 | Defecto de contrato y observabilidad API → Desarrollo Backend |

V1 no tuvo errores de prueba: la ausencia de API era real.

**Alcance (TEST_SCOPE_MISMATCH):** la matriz menciona «cambio de temperatura,
humedad y pH», pero TC-M09-64 es un único original cuyo objetivo es auditar la
creación y la modificación. V1 no exigía cubrir las tres variables. La
auditoría RF-17 es genérica por entidad umbral: el mismo caso de uso y la misma
tabla sirven para cualquier variable. Se aplicó la estrategia mínima de 1 CREATE
+ 1 UPDATE sobre una variable de Temperatura. Cubrir las tres variables
requeriría una instrucción formal y un presupuesto de escrituras adicional.

---

## CAUSA DE REEVALUACIÓN

Verificar la corrección de INC-M09-30-G30. El endpoint
`GET /configuracion/umbrales/{id_umbral_ambiental}/auditoria` existe en el
código evaluado (`693fd57` es ancestro de `ff5f6c9`) y en el OpenAPI desplegado
en TEST, así que ahora se puede ejecutar el oráculo completo de TC-64.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Entorno decisorio | **TEST** (G30 no usa MQTT; RF-17 y la auditoría están desplegados en TEST) |
| Backend usado | `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| URL suministrada (HTTP) | `http://…/api-sgpmp-test`: 404 del proxy. Se usó HTTPS, criterio ya autorizado en G77, G22 y G24 |
| Contrato desplegado | POST umbrales `201,401,403,404,409,422` · PATCH `200,401,403,404,412,422` · **auditoría umbral `200,401,403,404,422`** · `AuditoriaUmbralResponse` con los 7 campos del modelo · D09 `GET /auditoria/` `200,206,400,403,422,500` |
| DEV | No utilizado: TEST tiene RF-17 y la auditoría desplegados y el caso pasó |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 (existentes); nada instalado; sin Cypress |
| PostgreSQL | No utilizado; la auditoría se verificó por API |

---

## GIT / SHAs

| Repositorio | Rama | SHA | Uso |
| --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-re-evaluacion-M02` | `ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0` (= `origin/test`; contiene `693fd57`) | Lectura de contrato y única zona escribible (`TC-M09-G30/EvaluacionV2/`) |

---

## ACTOR MODIFICADOR

| Elemento | Valor |
| --- | --- |
| Usuario | `administador.dev@gmail.com`. El paquete cita `admin.dev@gmail.com`, pero el responsable QA confirmó que el correo correcto es `administador.dev@gmail.com` |
| Rol (`GET /usuarios/me`) | **Administrador**, cuenta `Activo`, `id_usuario` **104** |
| Permisos recurso 20 | `[1, 2, 3, 4]` (crear, consultar, modificar y desactivar) |
| Ejecutó | El POST (CREATE) y el PATCH (UPDATE) |
| Fallback Veterinario / DEV | No necesarios |

## ACTOR CONSULTA D09

| Consulta | Permiso requerido (contrato) | Actor |
| --- | --- | --- |
| `GET /configuracion/umbrales/{id}/auditoria` (auditoría RF-17) | Recurso 20, acción 2 | El mismo Administrador (tiene 20/2) |
| `GET /auditoria/` (D09 global, solo observación) | Recurso 6, acción 2 | El mismo Administrador (tiene 6/2) |

Las consultas no alteran la atribución: los eventos registran a quien modificó
(`id_usuario` 104), no a quien consulta. En este caso ambos son el mismo actor.

---

## DISCOVERY

Solo GET, sin escrituras exploratorias.

- **Contrato:**
  - `RegistrarUmbralUseCase` escribe la auditoría `CREATE` con
    `valores_nuevos = snapshot`.
  - `EditarUmbralUseCase` escribe `UPDATE` con `valores_anteriores = snapshot
    previo` y `valores_nuevos = snapshot posterior`, dentro de la misma
    transacción.
  - `ConsultarAuditoriaUmbralUseCase` lista los eventos por
    `id_umbral_ambiental`, ordenados por `fecha_gestion desc`, sin paginación, y
    responde 404 si el umbral no existe.
  - El PATCH exige `fecha_actualizacion` igual a la vigente (concurrencia
    optimista, 412).
  - La auditoría es síncrona: no requiere polling.
- **Mapa especie-variable:** en `estado-tc64.json`: especies activas,
  variables, combinaciones ocupadas y libres.
- **Selección:** especie **39 Bovino** (activa) + variable **13 Temperatura
  Corporal** (°C, rango físico **30–50**), combinación libre y comprobada otra
  vez justo antes del POST. Es coherente (temperatura corporal para una especie
  terrestre) y no se toman datos literales de la matriz ni de V1.
- **AUDIT_BEFORE_CREATE:**
  - Auditoría RF-17 del recurso: no aplica, porque el recurso no existía y el
    endpoint responde 404 para IDs inexistentes. La frontera la marcan la
    creación y `total = 1` tras el CREATE.
  - D09 global del actor en la hora previa: 200, 36 eventos, ninguno de umbral.
- **Checklist previo al CREATE (§143):** 15/15 «Sí».

---

## CONFIGURACIÓN UTILIZADA

| Campo | CREATE / BEFORE | UPDATE / AFTER | Cambió |
| --- | --- | --- | --- |
| ID | 44 | 44 | No (esperado) |
| Especie | 39 Bovino | 39 Bovino | No (esperado) |
| Variable | 13 Temperatura Corporal | 13 Temperatura Corporal | No (esperado) |
| Min | 38.00 | 37.00 | **Sí** |
| Max | 42.00 | 43.00 | **Sí** |
| Niveles | normal 38.00–39.33 · precaución 39.33–40.66 · crítico 40.66–42.00 | normal 37.00–39.00 · precaución 39.00–41.00 · crítico 41.00–43.00 | **Sí** (rediseño continuo, sin huecos ni solapes) |
| `fecha_actualizacion` | `null` | `2026-09-13T07:06:24.186751Z` | Sí (gestionado por el sistema) |

Ambos conjuntos respetan el rango físico, `min < max` y la continuidad exacta de
los niveles.

---

## AUDITORÍA DE CREACIÓN

| Etapa | Resultado |
| --- | --- |
| CREATE | `POST /configuracion/umbrales` → **201**, `id_umbral_ambiental` **44** · ventana `07:05:43.067Z – 07:06:02.030Z` |
| Persistencia | GET por especie: umbral 44 presente una vez con los valores CREATE; umbrales previos conservados |
| Evento | `GET /configuracion/umbrales/44/auditoria` → 200, `total = 1` |
| `id_auditoria_umbral` | 7 |
| Recurso | `id_umbral_ambiental = 44` (y `valores_nuevos.id_umbral_ambiental = 44`) |
| Usuario | 104 = actor del POST |
| Fecha/hora | `2026-09-13T07:06:01.126077Z`, dentro de la ventana del POST (UTC) |
| Operación | `CREATE` |
| Valores | `valores_anteriores = null`; `valores_nuevos` con especie 39, variable 13, 38.00–42.00 y los tres niveles enviados |
| Secretos en el evento | Ninguno (sin password, token, Authorization ni JWT) |
| Checklist §144 | 10/10 «Sí» · Newman `newman-TC-M09-64-audit-create-v2.html`: 8/8 |

## MODIFICACIÓN

| Etapa | Resultado |
| --- | --- |
| Checklist previo §145 | Mismo ID, CREATE persistido, valores distintos y válidos, sin duplicado, evento CREATE identificado, snapshot BEFORE guardado: 7/7 «Sí» |
| CONFIG_BEFORE_UPDATE | Umbral 44: 38.00–42.00, `fecha_actualizacion null` |
| UPDATE | `PATCH /configuracion/umbrales/44` con 37.00–43.00, niveles B y `fecha_actualizacion null` (valor vigente) → **200** · ventana `07:06:22.919Z – 07:06:24.897Z` |
| CONFIG_AFTER_UPDATE | GET: umbral 44 con 37.00–43.00 y niveles B; sigue siendo único para la combinación |
| Newman | `newman-TC-M09-64-update-v2.html`: 5/5 |

## AUDITORÍA DE MODIFICACIÓN

| Etapa | Resultado |
| --- | --- |
| Evento | `GET /configuracion/umbrales/44/auditoria` → 200, `total = 2` (CREATE #7 y UPDATE #8) |
| CREATE conservado | #7 sin cambios (mismo `id_auditoria_umbral`) |
| `id_auditoria_umbral` UPDATE | 8, distinto del CREATE; `fecha_gestion` posterior |
| Recurso | 44 |
| Usuario | 104 = actor del PATCH |
| Fecha/hora | `2026-09-13T07:06:24.181488Z`, dentro de la ventana del PATCH (UTC) |
| Operación | `UPDATE` |
| `valores_anteriores` | 38.00–42.00 y niveles A (= valores CREATE) |
| `valores_nuevos` | 37.00–43.00 y niveles B (= valores UPDATE); especie y variable sin cambio |
| Checklist §146 | 10/10 «Sí» · Newman `newman-TC-M09-64-audit-v2.html`: 11/11 |

---

## CORRELACIÓN

Se usó el nivel de correlación más fuerte (1, **resource ID**), reforzado con
actor, operación, ventana temporal y valores:

| Evento | Resource ID | Usuario | Fecha/hora | Operación | Valores correctos | Correlacionado | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CREATE | 44 | 104 | 2026-09-13T07:06:01.126077Z | CREATE | Sí | Sí | PASS |
| UPDATE | 44 | 104 | 2026-09-13T07:06:24.181488Z | UPDATE | Sí (anteriores = CREATE, nuevos = UPDATE) | Sí | PASS |

La consulta es por ID y sin paginación, así que el conjunto de eventos del
recurso está completo (`total = 2`). No se aceptó «algún evento de
configuración» como evidencia.

---

## COMPARACIÓN V1 VS V2

| Aspecto | V1 | V2 |
| --- | --- | --- |
| Ambiente | TEST | TEST |
| Actor modificador | Administrador (no llegó a modificar) | Administrador `administador.dev@gmail.com` (id 104) |
| Resource ID | Ninguno | 44 |
| CREATE funcional | No ejecutado | Sí — 201, persistido |
| Audit CREATE | No verificable (sin API) | Sí — evento #7 |
| UPDATE funcional | No ejecutado | Sí — 200, persistido |
| Audit UPDATE | No verificable | Sí — evento #8 |
| Usuario correcto | N/A | Sí (104 en ambos) |
| Fecha/hora | N/A | Coherente con cada operación |
| Valores | N/A | Correctos (CREATE nuevos; UPDATE anteriores y nuevos) |
| Escrituras | 0 | 2 (1 POST + 1 PATCH) |
| Resultado | Rechazado (BLOCKED) | **APROBADO** |

## COMPARACIÓN TEST VS DEV

DEV no se utilizó: TEST tiene RF-17 y la auditoría de umbrales desplegados, y el
caso se decidió allí con PASS (§147 no se activó).

---

## ORIGEN DEL FALLO

No hay fallo en V2.

| Hallazgo | Producto | Automatización | Entorno | Bloqueo | Estado |
| --- | --- | --- | --- | --- | --- |
| Auditoría RF-17 no consultable por API (V1) | Sí | No | No | Sí (V1) | **Corregido y verificado** (INC-M09-30-G30) |
| D09 global sin eventos de umbral | Diseño/integración | No | No | No | Observación a Desarrollo |
| Formato decimal inconsistente en snapshots | Menor | No | No | No | Observación a Desarrollo |

---

## CATEGORÍA / EQUIPO / ACCIÓN

| Hallazgo | Categoría | Equipo | Acción |
| --- | --- | --- | --- |
| INC-M09-30-G30 (auditoría RF-17 no consultable) | FLUJO (V1) | Desarrollo | **ACTUALIZAR INCIDENCIA COMO CORRECCIÓN VERIFICADA POR QA** |
| Observación 1: D09 global no refleja CREATE/UPDATE de umbrales | FLUJO — Flujo / Proceso (trazabilidad transversal) | Desarrollo | Informar a Desarrollo para que decida si integra la auditoría RF-17 en D09; no afecta al resultado |
| Observación 2: decimales inconsistentes (`"42.0"` / `"42.00"`) en snapshots | FLUJO — Flujo / Proceso (representación de datos auditados) | Desarrollo | Informar a Desarrollo para normalizar la serialización; no afecta al resultado |

---

## INCIDENCIAS

### INC-M09-30-G30 — actualizar como corrección verificada

- **ID reutilizado:** INC-M09-30-G30 (V1 la dejó como «ID pendiente»;
  Desarrollo la registró y corrigió con el commit `693fd57`). No se crea
  incidencia duplicada.
- **Severidad:** la vigente en el Registro de Errores; no se infiere de
  «Prioridad Alta» ni de «OWASP A09».
- **Texto sugerido:** «Reevaluación V2 de TC-M09-G30 / TC-M09-64 (RUN_ID
  `G30-REEVAL-V2-20260913-020215`, TEST, 2026-09-13). El umbral 44 (Bovino +
  Temperatura Corporal) se creó (201) y se modificó (200) por el Administrador
  id 104. `GET /configuracion/umbrales/44/auditoria` devuelve CREATE #7 y
  UPDATE #8 con usuario, fecha/hora, operación y valores anteriores/nuevos
  correctos. Corrección verificada por QA.»

### Observaciones (sin incidencia de producto bloqueante)

Si Desarrollo decide registrarlas:
`ID pendiente de asignación según Registro de Errores vigente` · severidad
pendiente de validar.

No se creó ningún ticket (Taiga, issue ni PR).

---

## EVIDENCIAS

En `RF-17/TC-M09-G30/EvaluacionV2/RESULTADOS/G30-REEVAL-V2-20260913-020215/`:

| Archivo | Contenido |
| --- | --- |
| `TC-M09-64-auditoria-v2.json` | Consolidado saneado: environment, actor, resource_id, species, variable, create_timestamp/values/audit_event, update_timestamp, before/after values, update_audit_event, observación D09 global, assertions, result |
| `estado-tc64.json` | Plan (preflight, contrato, mapa, selección, checklist) y estado por fase con ventanas temporales, respuestas y guardas de no repetición |
| `newman/newman-TC-M09-64-create-v2.html` | POST + GET de persistencia (6/6) |
| `newman/newman-TC-M09-64-audit-create-v2.html` | Auditoría tras CREATE (8/8) |
| `newman/newman-TC-M09-64-update-v2.html` | PATCH + GET de persistencia (5/5) |
| `newman/newman-TC-M09-64-audit-v2.html` | Auditoría CREATE + UPDATE (11/11) |
| `seguridad-evidencias.json` · `git-final.json` | Escaneo de secretos y estado Git |

Automatización en `EvaluacionV2/`: `helpers.cjs`, `run.cjs` (fases plan →
create → audit-create → update → audit, con guardas que impiden repetir una
escritura persistida), `TC-M09-G30-reevaluacion-v2.postman_collection.json` y
`README.md`.

---

## SEGURIDAD

- La contraseña se usó solo como variable de proceso (`TEST_ADMIN_PASSWORD`);
  token en memoria. Reporter con `omitHeaders`, sin datos de entorno y omitiendo
  la variable `token`; HTML y JSON saneados.
- De D09 global se guardaron solo campos mínimos (id, tipo, fecha, módulo,
  resultado y descripción), sin IP ni user agent.
- Los eventos de auditoría RF-17 no contienen password, token, Authorization ni
  JWT (verificado por aserción).
- Detalle del escaneo en `seguridad-evidencias.json`.
- Sin SQL, sin cleanup y sin modificar eventos de auditoría. El umbral 44 se
  conserva como evidencia.

---

## GIT FINAL

Detalle en `git-final.json`.

- Backend (`qa/juan-esteban-re-evaluacion-M02`, `ff5f6c9`): `git diff --stat`
  vacío. Todos los archivos nuevos están en
  `tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G30/EvaluacionV2/`.
- Cambios preexistentes ajenos a TC-M09-G30 EvaluacionV2 (carpetas sin
  seguimiento de evaluaciones anteriores): `RF-17/TC-M09-G24/EvaluacionV2/`,
  `RF-17/TC-M09-G29/EvaluacionV2/`, `RF-24/TC-M09-G77/EvaluacionV2/` y
  `RF-24/TC-M09-G78/EvaluacionV1/`. No se tocaron.
- V1 de G30 intacta. Sin commit, push, pull, merge, rebase, reset, clean,
  stash, checkout, cambio de rama, tag ni PR. Sin cambios en código,
  infraestructura ni dependencias.

**Resultado final: REEVALUACIÓN APROBADA — TC-M09-64 APROBADO, con dos observaciones informadas a Desarrollo. La ejecución se detiene aquí para revisión humana. No se avanza a otro grupo.**
