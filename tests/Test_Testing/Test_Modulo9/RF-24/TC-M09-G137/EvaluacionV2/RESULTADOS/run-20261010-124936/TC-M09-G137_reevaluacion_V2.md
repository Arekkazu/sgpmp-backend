# TC-M09-G137 — SEGUNDA EVALUACIÓN

RF-24 v2.0 · Módulo 9 · CU05 — Gestionar Dispositivos IoT, **Flujo F (calibración VISION)**
Casos **TC-M09-275**, **TC-M09-276** y **TC-M09-277**
RUN_ID: **run-20261010-124936** · Ambiente decisorio: **TEST** · Herramientas: **API - Postman / Newman**

---

## DECISIÓN GENERAL ACTUAL

| Elemento | Resultado |
|---|---|
| TC-M09-275 — Ingeniero de Campo | **APROBADO** |
| TC-M09-276 — Administrador | **APROBADO** |
| TC-M09-277 — Productor, 403 | **APROBADO** |
| **TC-M09-G137** | **APROBADO** |
| **Corrección del 409 `RECURSO_DUPLICADO`** | **VALIDADA** |
| Incidencia | **CERRAR** |

**Evolución del grupo:** `RECHAZADO → APROBADO`. El resultado RECHAZADO de la ejecución 1 se conserva en el historial de este mismo informe y no fue eliminado.

La segunda calibración VISION manual sobre el mismo par (área, especie), ejecutada por el Administrador, **ya no responde 409 `RECURSO_DUPLICADO`**: devuelve **HTTP 201**, crea una calibración nueva **EXITOSA** y **reemplaza correctamente la línea base vigente**, conservando en el historial la calibración anterior y todas las previas.

---

## HISTORIAL DE EJECUCIONES

Este informe es el único del grupo y cubre las dos ejecuciones de la segunda evaluación.

### EJECUCIÓN 1 — SEGUNDA EVALUACIÓN INICIAL

| | |
|---|---|
| RUN | `run-20261010-105849` |
| Fecha/hora | 2026-10-10 10:58 (−05:00) |
| Rama / HEAD | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` / `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| TC-M09-275 | **APROBADO** |
| TC-M09-276 | **RECHAZADO** |
| TC-M09-277 | **APROBADO** |
| **TC-M09-G137** | **RECHAZADO** |
| Newman | 48 de 48 items · 48 requests · 156 assertions · **15 fallidas** |
| Presupuesto | 3 POST calibración · 1 lote M03 · 0 reintentos · 0 DELETE |

**Lo que aportó esa ejecución.** Confirmó que el contrato VISION ya estaba desplegado y que el
Flujo F es ejecutable de punta a punta: el disparo manual del Ingeniero (TC-275) publicó su
línea base correctamente, y el Productor (TC-277) recibió su 403 con el mensaje literal sin
alterar nada. Y destapó un defecto que la primera evaluación no había podido observar: **el
reemplazo de la línea base vigente no funcionaba**.

**El defecto.** La segunda calibración del mismo par (área 279, especie 41), ejecutada por el
Administrador, respondió **HTTP 409 `RECURSO_DUPLICADO`** contra el índice único
`linea_base_vision_id_infraestructura_id_especie`, en lugar de sustituir la vigente. No se
creó calibración, no se publicó línea base y la vigente siguió siendo la **4**, la de TC-275.

**Causa raíz diagnosticada entonces.** El repositorio de línea base VISION usa
`SELECT ... FOR UPDATE` para localizar y reemplazar la línea vigente del par (área, especie).
La migración original de VISION contemplaba una política RLS de UPDATE sobre
`modulo9.lineas_base_vision`, pero la migración posterior de seguridad F5 reconstruyó las
políticas RLS de Módulo 9 **sin volver a crear la de UPDATE** de esa tabla. Así, la fila
vigente no resultaba actualizable, el repositorio interpretaba que no existía, intentaba un
`INSERT` y colisionaba con la restricción única.

**Incidencia que se abrió:** Desarrollo · `type: bug` · `severity: Important` ·
`priority: High`, sobre TC-M09-276.

**Las 15 assertions que fallaron**, tal como quedaron registradas en el `evidencia.json` de
aquel RUN:

| Item | Assertion | Error |
|---|---|---|
| `TC-M09-276 POST calibrar VISION` | la respuesta pertenece a 2xx | `expected 409 to be within 200..299` |
| `TC-M09-276 POST calibrar VISION` | devuelve id_calibracion_vision | `id_calibracion_vision: expected undefined to be a number` |
| `TC-M09-276 POST calibrar VISION` | modo_calibracion VISION | `expected undefined to deeply equal 'VISION'` |
| `TC-M09-276 POST calibrar VISION` | area_id es el del caso | `expected NaN to deeply equal 279` |
| `TC-M09-276 POST calibrar VISION` | especie_id es la del área | `expected NaN to deeply equal 41` |
| `TC-M09-276 POST calibrar VISION` | origen_disparo MANUAL | `expected undefined to deeply equal 'MANUAL'` |
| `TC-M09-276 POST calibrar VISION` | id_usuario es el Administrador | `expected NaN to deeply equal 104` |
| `TC-M09-276 POST calibrar VISION` | estado EXITOSA | `expected undefined to deeply equal 'EXITOSA'` |
| `TC-M09-276 POST calibrar VISION` | linea_base no nula | `expected +0 to be above +0` |
| `TC-M09-276 POST calibrar VISION` | usó observaciones válidas suficientes | `expected NaN to be at least 30` |
| `TC-M09-276 — es una calibración distinta de la de TC-M09-275` | se registró exactamente una calibración nueva y es la devuelta | `expected [] to deeply equal [ NaN ]` |
| `TC-M09-276 — es una calibración distinta de la de TC-M09-275` | el registro del historial es del Administrador y MANUAL | `Cannot read properties of undefined (reading 'id_usuario')` |
| `TC-M09-276 — línea base vigente` | la línea vigente es la calibración creada | `expected 4 to deeply equal NaN` |
| `TC-M09-276 — la línea vigente ya NO es la de TC-M09-275` | reemplazó la línea base de TC-M09-275 | `expected 4 to not deeply equal 4` |
| `TC-M09-276 — la línea vigente ya NO es la de TC-M09-275` | la línea vigente es la del Administrador | `expected 4 to deeply equal NaN` |

> **Sobre los artefactos de esa ejecución.** Su carpeta `run-20261010-105849` —informe,
> `evidencia.json` y HTML de Newman— se eliminó por decisión de QA el 2026-10-11, para dejar
> un solo RUN y un solo informe en `EvaluacionV2` y evitar la confusión de tener dos
> documentos con el mismo nombre. Lo que contenía está recogido aquí: los veredictos, el
> defecto, su causa raíz y las quince assertions con su mensaje exacto. Lo que no sobrevive
> es la presentación navegable del HTML y el detalle de los 48 requests que sí pasaron.

### CORRECCIÓN DE DESARROLLO

Desarrollo/DBA restauró por migración la política RLS de UPDATE sobre
`modulo9.lineas_base_vision` y verificó los privilegios UPDATE del rol de aplicación, y
solicitó la reevaluación en TEST.

### EJECUCIÓN 2 — REEJECUCIÓN OFICIAL POST-FIX

| | |
|---|---|
| RUN | `run-20261010-124936` (el vigente, y el único que queda en disco) |
| Fecha/hora | 2026-10-10 12:49 (−05:00) |
| TC-M09-275 / 276 / 277 | **APROBADO** / **APROBADO** / **APROBADO** |
| **TC-M09-G137** | **APROBADO** |
| Newman | 43 de 43 items · 43 requests · 137 assertions · **0 fallidas** |

El detalle de esta ejecución es el resto de este informe.

---

## MOTIVO DE LA REEJECUCIÓN

**Desarrollo informó la corrección del defecto de reemplazo de línea base VISION y solicitó reevaluación en TEST.**

Se reejecutaron los **tres** casos, no solo TC-M09-276: TC-276 depende de la línea base que publica TC-275, y TC-277 debe comprobar que el Productor no altera la línea finalmente publicada. Ejecutar únicamente TC-276 habría dejado sin verificar la cadena completa.

---

## BASELINE DEL RECHAZO ANTERIOR

Baseline de esta reejecución: la **ejecución 1** del RUN `run-20261010-105849`, la que dejó
G137 RECHAZADO. Su resultado, el defecto y sus quince assertions fallidas están recogidos en
la sección **HISTORIAL DE EJECUCIONES** de este informe.

Sus artefactos se eliminaron el 2026-10-11, por decisión de QA, para que `EvaluacionV2` tenga
un solo RUN y un solo informe. No se modificó ninguno antes de borrarlo.

| Caso | Resultado entonces | Observación |
|---|---|---|
| TC-M09-275 | APROBADO | HTTP 201, `id_calibracion_vision` 4, línea base publicada y vigente |
| TC-M09-276 | **RECHAZADO** | **HTTP 409 `RECURSO_DUPLICADO`** sobre `linea_base_vision_id_infraestructura_id_especie`; no creó calibración y no reemplazó la línea. El Administrador **sí** veía la línea previa (200, id 4) |
| TC-M09-277 | APROBADO | HTTP 403 con el mensaje literal, sin efecto alguno |
| **G137** | **RECHAZADO** | — |

Antes de eso, la primera evaluación (**run-20261007-100743**) había quedado RECHAZADA porque TEST no publicaba ninguna operación RF-24 VISION. Esa causa ya estaba resuelta.

---

## VERIFICACIÓN DEL FIX RLS

Comprobado por **SELECT de solo lectura** antes de cualquier POST funcional, sobre `modulo9.lineas_base_vision`. **0 DML.**

| Elemento | Valor observado |
|---|---|
| **POLITICA_UPDATE_PRESENTE** | **SÍ** |
| **GRANT_UPDATE_SGPMP_APP** | **NO VISIBLE PARA member_qa** |

Políticas RLS publicadas en la tabla:

| `policyname` | `cmd` |
|---|---|
| `pol_lineas_base_vision_insert` | INSERT |
| `pol_lineas_base_vision_select` | SELECT |
| `pol_lineas_base_vision_servicio` | ALL |
| **`pol_lineas_base_vision_update`** | **UPDATE** ← la que faltaba |

`pol_lineas_base_vision_update` lleva `qual` y `with_check` equivalentes:

```sql
id_infraestructura IN (
  SELECT i.id_infraestructura
  FROM modulo9.fn_infraestructuras_del_usuario(
         (SELECT modulo1.fn_id_usuario_actual())) i(id_infraestructura))
```

| Elemento | Valor |
|---|---|
| RLS en la tabla | **activa** y **forzada** (`relforcerowsecurity`), owner `dba` |
| Índices únicos | `lineas_base_vision_pkey` y **`uq_linea_base_vision_id_infraestructura_id_especie`** |

**El índice único sigue existiendo, como debe.** Lo que cambió no es la restricción, sino que ya no se alcanza: con la política de `UPDATE`, el segundo actor puede bloquear la fila vigente en el `SELECT ... FOR UPDATE` de `publicar()` y la operación **actualiza** en lugar de intentar un `INSERT` duplicado.

El `GRANT UPDATE` para `sgpmp_app` no es observable con la cuenta de QA: `information_schema.role_table_grants` solo muestra los privilegios en los que el usuario actual es otorgante o beneficiario, y `member_qa` no lo es. `pg_policies`, en cambio, es catálogo y sí fue consultable. Esto se deja declarado como **NO VERIFICABLE** y no como ausencia.

**La prueba funcional sigue siendo el oráculo definitivo:** la existencia de la política no sustituye los POST. Esta verificación es diagnóstica y se repitió al cerrar, con el mismo resultado.

---

## FIXTURE REUTILIZADO / ACTUALIZADO

Los IDs de la ejecución anterior son **referencia histórica** y se **revalidaron por API**, no se asumieron.

| Elemento | Valor | Revalidación |
|---|---|---|
| Finca | **163** «Finca QA Vision cacgbababafiej» | Ingeniero **200** · Administrador **200** · activa |
| Área | **279** «QA-G137-AREA-20261010-105849» | Ingeniero **200** · Administrador **200** · activa |
| Especie | **41** «Ave Qa Je» | activa, `tipo_modelo` **MODELO_AVES** |
| Modelo del área | **MODELO_AVES** | **POBLACIONAL** |
| Compuerta de acceso compartido | **PASS: ambos actores acceden a la finca y al área** | si alguno fallaba, la colección se detenía antes de cualquier POST |
| Línea base previa al RUN | **id 4** | visible a **ambos** actores (200/200) |
| Historial previo | total **1**, ids `[4]` | — |

**Reutilizado:** la misma finca, la misma área, la misma especie y la línea base previa del mismo par. No se cambió de área ni de especie, no se borró ninguna línea base y **no se evitó que existiera una línea previa**.

**Actualizado, y solo lo indispensable:**

| Recurso | Motivo |
|---|---|
| Cámara **221**, activa | La cámara 214 del RUN anterior quedó desactivada por su propia restauración y **la API no publica reactivación de dispositivos** (`/dispositivos-iot/{id}/desactivar` es el único endpoint de estado). Registrar una activa es indispensable, no gratuito: el caso de uso exige al menos una cámara activa |
| **40** observaciones VISION, ventana nueva | Las observaciones se asocian al `device_id`, así que la cámara nueva necesita su propio lote. Cargadas por el endpoint oficial M03, **1 solo lote**, sin SQL |

Ingesta M03: **HTTP 201**, enviadas **40**, aceptadas **40**, duplicadas **0**, **aptas para IA 40** (≥ 30 exigidas).
Ventana: **2026-10-10T17:26:11.501Z → 17:48:41.501Z**, 40 observaciones cada 30 s, todas en el pasado y dentro de la ventana.

---

## TC-M09-275

**Actor:** Ingeniero de Campo (id 4) · Ejecutado **una** vez, 0 reintentos.

```json
{"modo_calibracion":"VISION","area_id":279,
 "ventana_observacion":{"inicio":"2026-10-10T17:26:11.501Z","fin":"2026-10-10T17:48:41.501Z"},
 "observaciones":"QA TC-M09-275","fecha_calibracion":"2026-10-10T17:49:48.840Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 2xx | **201** |
| `id_calibracion_vision` | nuevo | **6** |
| `modo_calibracion` | VISION | **VISION** |
| `area_id` / `especie_id` | 279 / 41 | **279 / 41** |
| `origen_disparo` | MANUAL | **MANUAL** |
| `id_usuario` | Ingeniero (4) | **4** |
| `estado` | EXITOSA | **EXITOSA** |
| `linea_base` | no nula | no nula |
| `n_observaciones_validas` | ≥ 30 | **40** · iteraciones **1** |
| Línea base PRE | id 4 (previa del par) | **id 4** |
| **Línea base vigente POST** | id 6 | **6** |
| Historial PRE → POST | +1, conservando lo anterior | **1 → 2**, ids `[6, 4]`, nuevas `[6]` |
| RF-10 | evento exitoso correlacionado | **1** evento correlacionado por campos estructurados |

Nótese que **TC-275 ya fue en sí mismo un reemplazo**: existía la línea 4 del mismo par y pasó a estar vigente la 6, conservándose la 4 en el historial. Es el mismo mecanismo que fallaba, ejercitado por el mismo usuario que había creado la 4.

**Resultado: APROBADO** (oráculo completo en `true`).

---

## TC-M09-276

**Actor:** Administrador (id 104) · Ejecutado **una** vez, 0 reintentos. **Este es el caso que fallaba.**

Confirmado inmediatamente antes del POST, que era la condición en la que el defecto se manifestaba:

| Precondición | Obtenido |
|---|---|
| Ingeniero ve el área | **SÍ** (200) |
| Administrador ve el área | **SÍ** (200) |
| **Administrador ve la línea base de TC-275** | **SÍ — HTTP 200, `id_calibracion_vision` = 6** |
| Línea vigente según el Ingeniero | **6** |

```json
{"modo_calibracion":"VISION","area_id":279,
 "ventana_observacion":{"inicio":"2026-10-10T17:26:11.501Z","fin":"2026-10-10T17:48:41.501Z"},
 "observaciones":"QA TC-M09-276","fecha_calibracion":"2026-10-10T17:49:50.207Z"}
```

Mismo `area_id`, misma especie, misma cámara y misma ventana que TC-275.

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 2xx | **201** |
| **¿409 `RECURSO_DUPLICADO`?** | **NO** | **NO** — sin `error_code` |
| `id_calibracion_vision` | nuevo y distinto del de TC-275 | **7** (≠ 6) |
| `modo_calibracion` | VISION | **VISION** |
| `origen_disparo` | MANUAL | **MANUAL** |
| `id_usuario` | Administrador (104) | **104** |
| `estado` | EXITOSA | **EXITOSA** |
| `linea_base` | no nula | no nula |

**Resultado: APROBADO** (oráculo completo en `true`, incluidos `no_es_409`, `sin_recurso_duplicado`, `administrador_veia_la_linea_previa`, `id_distinto_de_275`, `reemplazo_de_la_vigente`, `la_vigente_ya_no_es_275`, `historial_conserva_275` y `vigente_visible_al_administrador`).

---

## VALIDACIÓN DEL REEMPLAZO

| Elemento | Esperado | Obtenido |
|---|---|---|
| Línea base vigente antes de TC-276 | id de TC-275 | **6** |
| **Línea base vigente después de TC-276** | id de TC-276 | **7** |
| ¿Sigue siendo la de TC-275? | **NO** | **NO** |
| ¿La ve así el Administrador? | sí | **sí** (200, id **7**) |
| Historial conserva la de TC-275 | **SÍ** | **SÍ** — id 6 presente |
| Historial conserva las previas | SÍ | **SÍ** — id 4 presente |
| Historial PRE → POST | 2 → 3 | **2 → 3**, ids `[7, 6, 4]`, nuevas `[7]` |
| Par (área, especie) de la línea vigente | 279 / 41 | **279 / 41** |

TC-275 **no se eliminó**: solo dejó de ser la línea vigente. Exactamente el comportamiento que exige el flujo alterno de RF-24 v2.0 y que el defecto impedía.

### Sin workarounds

El resultado se obtuvo **sin ninguno** de los atajos que invalidarían el caso:

| Comprobación | Valor |
|---|---|
| Misma área que el baseline (279) | **SÍ** |
| Misma especie del área (41) | **SÍ** |
| Creó otra finca | **NO** (0 POST a `/configuracion/fincas`) |
| Creó otra área | **NO** (0 POST a `/configuracion/infraestructuras`) |
| Creó otra especie | **NO** (0 POST a `/configuracion/especies`) |
| Borró algo | **NO** (0 DELETE) |
| Ejecutó SQL DML | **NO** (0) |
| Existía línea previa al RUN | **SÍ** (id 4) |
| **TC-276 fue una SEGUNDA calibración sobre el MISMO par** | **SÍ** |

El runner aborta por diseño si la colección intentara crear finca, área o especie en esta reejecución.

---

## TC-M09-277

**Actor:** Productor (id 35, Activo, rol confirmado por API) · Ejecutado **una** vez.

Línea vigente capturada antes del intento: **7** (la de TC-276), como exige el oráculo de no efecto.

Body VISION **estructuralmente válido** sobre la **misma** área: el rechazo debe venir del control RBAC.

```json
{"modo_calibracion":"VISION","area_id":279,
 "ventana_observacion":{"inicio":"2026-10-10T17:26:11.501Z","fin":"2026-10-10T17:48:41.501Z"},
 "observaciones":"QA TC-M09-277","fecha_calibracion":"2026-10-10T17:49:51.516Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | **403** | **403** |
| ¿401? / ¿422? | no aceptables | **ninguno** |
| `error_code` | — | `ACCESO_DENEGADO` |
| Mensaje | literal de la ficha | **idéntico, carácter por carácter** |
| `id_calibracion_vision` | ausente | **ausente** |
| Línea vigente antes → después | **7 → 7** | **7 → 7** |
| Historial PRE → POST | sin cambios | **3 → 3**, ids `[7, 6, 4]`, nuevas `[]` |
| Calibración atribuible al Productor | ninguna | **ninguna** |

**Mensaje obtenido:**

> Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.

Comparación **literal estricta**: prohibido `contains`, `startsWith`, regex o equivalencia semántica.

**Auditoría RF-10 del rechazo** (evidencia complementaria): `id_evento` **46884**, `tipo_evento` 29, resultado **fallido**, `codigo_http` **403**. Eso no es efecto funcional sobre la línea base.

**Resultado: APROBADO** (oráculo completo en `true`, 16 criterios).

---

## VERIFICACIÓN BD

Consultada como **diagnóstico complementario**, en sesión **READ ONLY**. **Solo SELECT · 0 DML.**

| Consulta | Resultado |
|---|---|
| Privilegios del rol QA sobre las tablas VISION | **ejecutada** |
| `modulo9.calibraciones_vision` del área | **permission denied for table calibraciones_vision** |
| `modulo9.lineas_base_vision` del par | **permission denied for table lineas_base_vision** |
| Cuántas líneas del par | **permission denied for table lineas_base_vision** |

**Limitación documentada.** `member_qa` **no tiene `SELECT`** sobre `modulo9.calibraciones_vision` ni `modulo9.lineas_base_vision`: las tablas existen, pero el privilegio está denegado, así que las comprobaciones del §19 —que la 6 y la 7 existan y que haya **una sola** línea vigente apuntando a la 7— **no pudieron verificarse por SQL**. No se sustituyó la BD por inferencias: queda declarado como no comprobable por privilegios.

Lo que **sí** fue observable por BD es lo más relevante para este fix: las **políticas RLS** desde `pg_policies`, que es catálogo y no requiere ese GRANT. Ahí se confirma la política de `UPDATE` que faltaba.

El oráculo de persistencia se construyó con los **GET de la API**, que son la superficie autoritativa del producto, y es concluyente: el historial devuelve `[7, 6, 4]` y la línea vigente es la 7, consistente para el Ingeniero y para el Administrador.

Para habilitar el diagnóstico completo del §19 hacen falta `GRANT SELECT` a `member_qa` sobre esas dos tablas.

---

## RESULTADO NEWMAN

| Elemento | Valor |
|---|---|
| RUN_ID | `run-20261010-124936` |
| Colección ejecutada | **43 de 43** items, una sola vez |
| Iterations | 1 (0 fallidas) |
| Requests | **43** |
| Failed requests | **0** |
| Assertions | **137** |
| **Failures** | **0** |
| POST VISION funcionales | **3 / 3** |
| POST telemetría (setup) | 1 |
| POST dispositivos (setup) | 1 |
| PATCH de restauración | 1 |
| POST finca / área / especie | **0 / 0 / 0** |
| Reintentos | **0** |
| HTML | `newman/newman-TC-M09-G137.html` · **Cantidad: 1** |

El PRECHECK fue solo de consola (18 requests, 48 assertions, 0 failures, 0 POST funcionales) y no generó ningún reporte.

---

## COMPARACIÓN ANTES VS AHORA

| Dimensión | RUN rechazado anterior | Nueva ejecución |
|---|---|---|
| TC-275 | APROBADO (HTTP 201) | **APROBADO (HTTP 201)** |
| Línea después de TC-275 | publicada y vigente (id 4) | **publicada y vigente (id 6)** |
| Admin ve línea previa | SÍ (200, id 4) | **SÍ (200, id 6)** |
| **TC-276 HTTP** | **409** | **201** |
| **TC-276 error** | **`RECURSO_DUPLICADO`** | **(ninguno)** |
| **TC-276 crea calibración** | **NO** | **SÍ (id 7)** |
| **TC-276 reemplaza línea** | **NO** | **SÍ** |
| TC-277 | APROBADO (403 correcto) | **APROBADO (403, mensaje exacto)** |
| **G137** | **RECHAZADO** | **APROBADO** |

**Causa del rechazo anterior: CORREGIDA.**

---

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO NUEVA.**

| Elemento | Valor |
|---|---|
| Incidencia del 409 `RECURSO_DUPLICADO` | **VALIDADA COMO CORREGIDA** |
| Propuesta | **CERRAR** |
| Incidencia histórica sobre la ausencia de la operación VISION en TEST | **permanece resuelta** |
| Responsable | n/a |
| Causa raíz | **Hipótesis A** — la corrección está desplegada y operativa en TEST: `pol_lineas_base_vision_update` permite que el segundo actor bloquee la fila vigente en el `SELECT ... FOR UPDATE` de `publicar()`, de modo que la segunda calibración del mismo par **actualiza** la línea base en lugar de intentar insertar una duplicada contra el índice único |

No se abre ninguna incidencia nueva.

---

## EVIDENCIAS

```
TC-M09-G137/
└── EvaluacionV2/
    ├── automation/
    │   ├── run-g137-v2.cjs
    │   └── TC-M09-G137.postman_collection.json
    └── RESULTADOS/
        └── run-20261010-124936/            ← RUN ÚNICO Y VIGENTE
            ├── TC-M09-G137_reevaluacion_V2.md
            ├── evidencia.json
            ├── automation_manifest.json
            └── newman/
                └── newman-TC-M09-G137.html
```

**Un solo RUN y un solo informe.** La reorganización del 2026-10-11 dejó `EvaluacionV2` con la
misma estructura que los demás grupos de RF-24 v2.0 (G139 a G143): toda la automatización en
`automation/` —antes la colección estaba en la raíz— y un único RUN en `RESULTADOS/`. Las
carpetas `run-20261010-105849` (la ejecución 1) y las dos de diagnóstico que hubo
(`run-20261010-105259` y `run-20261010-021125`) ya no están; lo que la ejecución 1 demostró se
conserva en la sección **HISTORIAL DE EJECUCIONES** de este informe.

`evidencia.json` consolida: RUN_ID, motivo de la reejecución, git pre/post, ambiente, verificación del fix por SELECT (antes del RUN y al cerrar), contrato OpenAPI VISION, los tres actores con permisos y estado, la estrategia de fixture con su revalidación y la comprobación explícita de ausencia de workarounds, el setup de cámara y observaciones, el estado inicial de línea base e historial, y para cada caso el request, la respuesta, los PRE/POST de línea base e historial, la auditoría RF-10, el oráculo detallado y el resultado; más el resultado Newman, la verificación API final, el diagnóstico de BD con su limitación, la restauración, la comparación antes/después, la causa raíz, la incidencia, la seguridad y el git final.

`automation_manifest.json` registra ruta, función y SHA-256 de los artefactos. El runner y la
colección **cambiaron** respecto de la ejecución 1, para reutilizar el fixture en vez de
crearlo; el manifiesto conserva el `sha256_anterior` de cada uno. Tras la reorganización del
2026-10-11 anota además, para el runner y la colección, su `sha256_en_disco_tras_la_reorganizacion`
y el motivo: la colección se movió a `automation/` y el runner pasó a resolverla con
`__dirname`. El `sha256` principal sigue siendo el de la automatización que produjo estos
artefactos, de modo que el desajuste es explícito y no una incoherencia. **No hay scripts
dentro de `RESULTADOS/`.**

### Restauración

| Recurso | ID | Estado original | Cambio | Durante | Reversión | Final |
|---|---|---|---|---|---|---|
| Cámara de setup | **221** | no existía | registrada ACTIVA (el área no tenía ninguna activa y la API no publica reactivación) | ACTIVA | `PATCH .../desactivar` | **inactiva** |

Recursos preexistentes modificados: **ninguno**. Las calibraciones 6 y 7 y la línea base vigente son resultados válidos del caso y **no se borran**; la finca, el área, la especie y la línea previa al RUN (id 4) se conservan. La red de seguridad del cierre no tuvo que intervenir. **Restauración: PASS.**

### Verificación API final (solo lectura, después del RUN)

| Elemento | Valor |
|---|---|
| `GET /configuracion/calibraciones-vision?area_id=279` | **200**, total **3**, ids `[7, 6, 4]` |
| `GET .../linea-base?area_id=279` (Ingeniero) | **200**, `id_calibracion_vision` **7** |
| `GET .../linea-base?area_id=279` (Administrador) | **200**, `id_calibracion_vision` **7** |
| La vigente es la de TC-276 | **SÍ** |
| Ambas calibraciones conservadas | **SÍ** |
| Línea previa al RUN conservada en el historial | **SÍ** (id 4) |
| ¿Se borró algo? | **nada** |

### Seguridad

Escaneo de todo `EvaluacionV2/`: **limpio**. Credenciales en claro: **0**. No quedaron persistidos `PASSWORD_QA`, la contraseña de BD, JWT, cabeceras `Authorization`/`Bearer`, cookies, `refresh_token`, DSN con contraseña ni el **serial de la cámara**, que por contrato funciona como `access_key` de la ingesta M03. Los seriales se redactan **por patrón**, incluidos los de RUN hermanos que el inventario de dispositivos devuelve.

---

## CONCLUSIÓN

La reevaluación confirma que la corrección informada por Desarrollo se encuentra desplegada y operativa en TEST. La segunda calibración VISION manual sobre el mismo par (área, especie), ejecutada por el Administrador, ya no intenta insertar una línea base duplicada: genera una nueva calibración **EXITOSA** (id 7) y **reemplaza correctamente la línea base vigente**, conservando la calibración anterior (id 6) y la previa al RUN (id 4) en el historial. **TC-M09-275, TC-M09-276 y TC-M09-277 resultan APROBADOS.** Se propone cerrar la incidencia asociada al 409 `RECURSO_DUPLICADO`.

El mecanismo de la corrección quedó identificado y verificado en los dos planos. En el plano de la base de datos, `modulo9.lineas_base_vision` publica ahora la política `pol_lineas_base_vision_update`, que es la que faltaba: sin ella, el `SELECT ... FOR UPDATE` de `publicar()` no devolvía la fila al segundo actor —aunque ambos pudieran leerla— y la operación degeneraba en un `INSERT` que chocaba contra `uq_linea_base_vision_id_infraestructura_id_especie`. El índice único sigue en su sitio, como corresponde; lo que cambió es que ya no se alcanza. En el plano funcional, que es el oráculo definitivo, el reemplazo se demostró dos veces en la misma corrida: primero por el propio Ingeniero, que sustituyó la línea 4 por la 6, y después por el Administrador, que sustituyó la 6 por la 7 habiendo confirmado antes que veía la 6.

El resultado se obtuvo sin ningún atajo: misma área, misma especie, misma finca, misma ventana, ninguna línea base borrada, ninguna finca ni área ni especie creada, ningún DELETE y ningún SQL de escritura. TC-276 fue una segunda calibración real sobre un par que ya tenía línea vigente, que es precisamente lo que había que demostrar. Newman cerró con 137 assertions y 0 failures, el único recurso creado quedó desactivado y el RUN que documentaba el defecto se conserva intacto como baseline. Queda señalada una limitación de entorno que no afecta al veredicto: la cuenta de solo lectura de QA no tiene `SELECT` sobre las tablas VISION, así que la comprobación en base de datos de la fila de línea base no pudo ejercerse y la persistencia se verificó por los GET de la API.
