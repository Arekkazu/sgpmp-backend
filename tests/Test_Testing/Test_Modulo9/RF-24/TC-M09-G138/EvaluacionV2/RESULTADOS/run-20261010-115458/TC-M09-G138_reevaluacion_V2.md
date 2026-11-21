# TC-M09-G138 — SEGUNDA EVALUACIÓN

RF-24 v2.0 · Módulo 9 · CU05 — Gestionar Dispositivos IoT, **Flujo F (precondiciones VISION)**
Casos **TC-M09-278**, **TC-M09-279**, **TC-M09-280** y **TC-M09-281**
RUN_ID: **run-20261010-115458** · Ambiente decisorio: **TEST** · Herramientas: **API - Postman / Newman**

---

## DECISIÓN GENERAL

| Elemento | Resultado |
|---|---|
| TC-M09-278 — área sin cámara | **APROBADO** |
| TC-M09-279 — única cámara inactiva | **APROBADO** |
| TC-M09-280 — modelo de paradigma INDIVIDUAL | **APROBADO** |
| TC-M09-281 — `tipo_modelo_asignado` nulo | **APROBADO** |
| **TC-M09-G138** | **APROBADO** |
| Causa del rechazo anterior | **CORREGIDA** |
| INCIDENCIA REQUERIDA | **NO** |

Las cuatro precondiciones negativas del área se validan correctamente. Los cuatro rechazos responden **HTTP 422** con `error_code VISION_NO_DISPONIBLE` y el **mensaje literal del contrato construido con el ID real de su propia área**, y **ninguno publica línea base**: las cuatro áreas siguen sin línea vigente y sin ninguna calibración VISION. Newman cerró con **0 failures** y todo el fixture quedó revertido.

---

## RESUMEN

| Caso | Área | Invalidez aislada | HTTP | `error_code` | Mensaje exacto | Línea base PRE → POST | Resultado |
|---|---|---|---|---|---|---|---|
| TC-M09-278 | **284** | sin ninguna cámara asociada | **422** | `VISION_NO_DISPONIBLE` | **SÍ** | 404 → 404 | **APROBADO** |
| TC-M09-279 | **285** | única cámara asociada, inactiva | **422** | `VISION_NO_DISPONIBLE` | **SÍ** | 404 → 404 | **APROBADO** |
| TC-M09-280 | **286** | modelo de paradigma INDIVIDUAL | **422** | `VISION_NO_DISPONIBLE` | **SÍ** | 404 → 404 | **APROBADO** |
| TC-M09-281 | **287** | `tipo_modelo_asignado` nulo | **422** | `VISION_NO_DISPONIBLE` | **SÍ** | 404 → 404 | **APROBADO** |

Presupuesto respetado: **4 POST** `/configuracion/calibraciones-vision` (1 por caso), **0 reintentos**, **0 POST** `/iot/telemetria/vision`, **0** PUT, **0** DELETE, **0** SQL DML. **STOP_ALL: NO.**

---

## BASELINE — PRIMERA EVALUACIÓN

Único baseline oficial: **run-20261007-101353** (ambiente TEST)
Fuente: `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G138/RESULTADOS/run-20261007-101353/TC-M09-G138_resultado.md`

| Caso | Resultado |
|---|---|
| TC-M09-278 | RECHAZADO / NO EJECUTABLE FUNCIONALMENTE |
| TC-M09-279 | RECHAZADO / NO EJECUTABLE FUNCIONALMENTE |
| TC-M09-280 | RECHAZADO / NO EJECUTABLE FUNCIONALMENTE |
| TC-M09-281 | RECHAZADO / NO EJECUTABLE FUNCIONALMENTE |
| **TC-M09-G138** | **RECHAZADO** |

Causa compartida: **TEST no publicaba ninguna operación de calibración VISION**. No se ejecutó ningún POST VISION, y los HTTP, los mensajes y los efectos sobre la línea base de las cuatro variantes quedaron no observables.

---

## ENTORNO

| Elemento | Valor |
|---|---|
| Ambiente decisorio | **TEST** |
| Backend | `https://api.inmero.co/back-sigab-test` |
| Contraste DEV | **no utilizado** (0 peticiones): TEST publica la operación y los cuatro casos pasaron |
| BD TEST | consultada **solo SELECT** como diagnóstico complementario; **0 DML** |
| Newman HTML | **1** (`newman/newman-TC-M09-G138.html`) |
| Pytest | no aplica |

---

## RAMA

| Elemento | Valor |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| Commit | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| Divergencia HEAD…origin/test | `0 0` |
| `RESULTADOS/` de la primera evaluación | `(vacío = intacta)` |
| Operaciones git de escritura | **ninguna**: sin `add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `stash`, `switch` ni `checkout` |

---

## CONTRATO VISION ACTUAL

Primer control del caso. **Las tres operaciones existen en TEST**:

| Operación | Estado |
|---|---|
| `POST /configuracion/calibraciones-vision` | **PRESENTE** |
| `GET /configuracion/calibraciones-vision` | **PRESENTE** |
| `GET /configuracion/calibraciones-vision/linea-base` | **PRESENTE** |

| Elemento del contrato | Valor observado |
|---|---|
| `CalibrarVisionDTO` | `modo_calibracion`, `area_id`, `ventana_observacion`, `fecha_calibracion`, `observaciones` |
| Dominio de `modo_calibracion` | `["VISION"]` (`const: "VISION"`) |
| Códigos declarados por el POST | `201, 400, 401, 403, 404, 422, 500` — incluye el **422** de precondición |

El §14 no se activó: no hubo que detenerse ni contrastar DEV.

---

## ACTOR

Sin contraseñas. Los `id_usuario` se resolvieron por API.

| Actor | Correo | `id_usuario` | Rol | Estado | Login | Permisos recurso 12 | Papel |
|---|---|---|---|---|---|---|---|
| Ingeniero de Campo | `ingeniero@pecuaria.co` | **4** | Ingeniero de Campo | Activo | **PASS** (200) | `[1, 2, 3]` — incluye **CREATE** | ejecuta los **4** POST VISION funcionales |
| Administrador | `administador.dev@gmail.com` | **104** | Administrador | Activo | **PASS** (200) | `[1, 2, 3]` | crea y revierte el fixture, consulta RF-10. **No** ejecuta los POST funcionales |

El Administrador alternativo (`admin.dev@gmail.com`) **no se usó**: el principal autentica. No se probaron otras contraseñas.

**Propiedad de sesiones.** La colección es dueña de sus sesiones: hace sus propios logins y publica los tokens en `{{engineer_session}}` y `{{admin_session}}`. El runner **no obtiene ningún token ni lo inyecta**, porque TEST aplica sesión única por usuario. Cada actor inicia sesión una sola vez en el RUN.

---

## PREFLIGHT VALIDADO

PRECHECK Newman de **solo lectura** previo al RUN: solo GET y los logins, sin reporter HTML, sin crear `RESULTADOS`, sin dejar archivos, solo consola.

```
PRECHECK_G138

POST calibraciones-vision:   PRESENTE
GET historial:               PRESENTE
GET línea-base:              PRESENTE
Contrato (body y dominio):   PASS
Ingeniero:                   PASS
Administrador:               PASS
Especie AVES del catálogo:   PASS
Tipo de área:                PASS
Finca compartida:            PASS (ambos actores acceden)
Failures automatización:     0
POST VISION funcionales:     0
POST telemetria/vision:      0
AUTORIZAR_RUN:               SÍ
```

Newman del PRECHECK: 12 requests, 0 fallidos, 34 assertions, 0 fallidas. No creó ninguna especie, área ni cámara.

---

## ESTRATEGIA DE FIXTURES

### Qué se reutilizó y qué hubo que crear

Se prefirieron datos existentes. Se **reutilizaron** del catálogo: la **finca 162** (activa y visible a los dos actores), la **especie 41 «Ave Qa Je»** (`MODELO_AVES`, activa) y el **tipo de área «Galpón»**.

Ningún área preexistente de TEST sirve, y el descubrimiento lo deja registrado:

| Perfil | Candidatos preexistentes | Por qué no sirve |
|---|---|---|
| A2 — AVES + poblacional + **0 cámaras** | **ninguno** | toda área AVES activa ya tiene al menos una cámara asociada |
| A3 — AVES + poblacional + **1 cámara inactiva** | áreas 161, 278, 279 | **todas tienen ya una línea base vigente** (ids 1, 2 y 4). El §19 prefiere áreas sin línea base previa, para poder demostrar literalmente que no se registra ninguna |
| A4 — modelo **INDIVIDUAL** + cámara activa | **ninguno** | no había **ni una** especie de paradigma INDIVIDUAL activa en el catálogo, y el área solo admite un `tipo_modelo_asignado` que **coincida** con el de su especie (`INCOHERENCIA_ESPECIE_MODELO`) |
| A5 — AVES + **modelo nulo** + cámara activa | **ninguno** | ninguna área junta especie AVES con `tipo_modelo_asignado` nulo y cámara activa |

### Recursos creados, todos con endpoint oficial y reversión oficial

| Recurso | ID | Endpoint de creación | Reversión |
|---|---|---|---|
| Especie de paradigma INDIVIDUAL | **111** «Especie Qa Grandes …», `MODELO_ESPECIES_GRANDES` | `POST /configuracion/especies` | `PATCH /configuracion/especies/{id}/desactivar` |
| Área **A2** | **284** | `POST /configuracion/infraestructuras` | `PATCH .../infraestructuras/{id}/desactivar` |
| Área **A3** | **285** | idem | idem |
| Área **A4** | **286** | idem | idem |
| Área **A5** | **287** | idem | idem |
| Cámara de A3 (**inactiva** de origen) | **218** | `POST /configuracion/dispositivos-iot` | ninguna escritura: nació inactiva |
| Cámara de A4 (activa) | **219** | idem | `PATCH .../dispositivos-iot/{id}/desactivar` |
| Cámara de A5 (activa) | **220** | idem | idem |

**Cuatro áreas distintas, una por caso** — IDs reales diferentes, sin reutilizar ni alterar repetidamente una misma área: TC-278 → 284, TC-279 → 285, TC-280 → 286, TC-281 → 287.

**No se modificó ningún recurso preexistente de TEST.** No se usó SQL para preparar ni corregir nada.

### Escrituras, contadas por separado (§46)

| Tipo | Cantidad |
|---|---|
| POST de setup | **8** (1 especie + 4 áreas + 3 cámaras) |
| PATCH de setup | **0** |
| PATCH de restauración | **7** (2 cámaras + 4 áreas + 1 especie) |
| **POST funcionales VISION** | **4** |
| POST `/iot/telemetria/vision` | **0** |
| PUT / DELETE / SQL DML | 0 / 0 / 0 |

### Ventana de observación

Común a los cuatro casos, estructuralmente válida y sin ninguna invalidez adicional:

| Elemento | Valor |
|---|---|
| inicio | **2026-10-10T15:55:03.121Z** |
| fin | **2026-10-10T16:53:03.121Z** |
| Criterio | `fin > inicio`, ambos en el pasado |

### No se cargaron observaciones

**`POST /iot/telemetria/vision`: 0 ejecuciones.** Los cuatro rechazos ocurren **antes** del cálculo de la línea base, así que G138 no depende de M03 y no se prepararon 30 ni 40 observaciones. El runner aborta si la colección intentara incluir ese endpoint.

---

## TC-M09-278 — ÁREA SIN CÁMARA

**Área 284** «QA-G138-A2-20261010-115458» · Actor: Ingeniero · Ejecutado **una** vez.

| Precondición | Verificado |
|---|---|
| Área activa | **SÍ** |
| Especie | **41** «Ave Qa Je», grupo **AVES** |
| `tipo_modelo_asignado` | **MODELO_AVES** → paradigma **POBLACIONAL** |
| Cámaras **asociadas** | **0** (no solo cero activas: ninguna asociada) |
| Cámaras activas | 0 |
| Invalidez aislada | **no hay cámara** |

```json
{"modo_calibracion":"VISION","area_id":284,
 "ventana_observacion":{"inicio":"2026-10-10T15:55:03.121Z","fin":"2026-10-10T16:53:03.121Z"},
 "observaciones":"QA TC-M09-278","fecha_calibracion":"2026-10-10T16:55:11.562Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | **422** | **422** |
| ¿400 / 403 / 404 / 5xx? | no aceptables | **ninguno** |
| `error_code` | (se registra) | **`VISION_NO_DISPONIBLE`** |
| Mensaje | literal con el ID real | **idéntico, carácter por carácter** |
| `id_calibracion_vision` | ausente | **ausente** |
| Línea base PRE | sin línea vigente | **HTTP 404** |
| Línea base POST | sigue sin línea vigente | **HTTP 404** |
| Línea base nueva | **NO** | **NO** |
| Historial PRE → POST | sin cambios | **0 → 0**, nuevas `[]`, exitosas `[]` |

**Mensaje obtenido:**

> Calibración por visión no disponible: El área 284 no cuenta con observaciones de cámara aptas o no tiene un modelo poblacional asignado. Verifique las cámaras (RF-21/22) y la configuración del área (RF-20).

**Resultado: APROBADO** (oráculo completo en `true`, 16 criterios).

---

## TC-M09-279 — ÚNICA CÁMARA INACTIVA

**Área 285** «QA-G138-A3-20261010-115458» · Ejecutado **una** vez.

| Precondición | Verificado |
|---|---|
| Área activa | **SÍ** |
| Especie / modelo | **41** AVES / **MODELO_AVES** (POBLACIONAL) |
| Cámaras asociadas | **exactamente 1** (id **218**) |
| Cámaras **activas** | **0** — la única asociada está **inactiva** |
| Invalidez aislada | **la única cámara está inactiva** |

La cámara se registró **inactiva desde el origen** (`es_activo: false` en el registro), así que la condición es inequívoca y **no hubo estado previo que alterar**: no se desactivó ninguna cámara preexistente y, por tanto, **no hay restauración de estado pendiente** para este caso. El §28 solo exige reactivar cuando QA desactiva una cámara que estaba activa.

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | **422** | **422** |
| `error_code` | (se registra) | **`VISION_NO_DISPONIBLE`** |
| Mensaje | literal con el ID real (285) | **idéntico** |
| Línea base PRE → POST | 404 → 404 | **404 → 404** |
| Línea base nueva | **NO** | **NO** |
| Historial PRE → POST | sin cambios | **0 → 0** |
| Restauración de la cámara | PASS o no aplica | **NO APLICA** (nació inactiva; verificado por GET que sigue inactiva) |

**Resultado: APROBADO.**

---

## TC-M09-280 — MODELO INDIVIDUAL

**Área 286** «QA-G138-A4-20261010-115458» · Ejecutado **una** vez.

| Precondición | Verificado |
|---|---|
| Área activa | **SÍ** |
| Especie | **111** «Especie Qa Grandes …», `tipo_modelo` **MODELO_ESPECIES_GRANDES** |
| `tipo_modelo_asignado` | **MODELO_ESPECIES_GRANDES** → paradigma **INDIVIDUAL** |
| Cámaras asociadas / **activas** | 1 / **1** (id **219**, activa) |
| Invalidez aislada | **modelo no poblacional** |

La cámara **activa** es deliberada: sin ella habría dos precondiciones inválidas y el caso no aislaría el paradigma. El paradigma se deriva del tipo de modelo (`PARADIGMA_POR_TIPO_MODELO`): `MODELO_ESPECIES_GRANDES` → `INDIVIDUAL`.

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | **422** | **422** |
| `error_code` | (se registra) | **`VISION_NO_DISPONIBLE`** |
| Mensaje | literal con el ID real (286) | **idéntico** |
| Línea base PRE → POST | 404 → 404 | **404 → 404** |
| Línea base nueva | **NO** | **NO** |
| Historial PRE → POST | sin cambios | **0 → 0** |

**Resultado: APROBADO.**

---

## TC-M09-281 — MODELO NULO

**Área 287** «QA-G138-A5-20261010-115458» · Ejecutado **una** vez.

| Precondición | Verificado |
|---|---|
| Área activa | **SÍ** |
| Especie | **41** «Ave Qa Je», grupo **AVES** — **presente**, no nula |
| `tipo_modelo_asignado` | **null** |
| Cámaras asociadas / **activas** | 1 / **1** (id **220**, activa) |
| Invalidez aislada | **ausencia de `tipo_modelo_asignado`** |

El área **sí** tiene especie, como exige el §36: lo único que falta es el modelo. `RegistrarInfraestructuraDTO` admite `tipo_modelo_asignado` nulo con especie presente, así que la combinación es legítima y aísla exactamente esa carencia.

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | **422** | **422** |
| `error_code` | (se registra) | **`VISION_NO_DISPONIBLE`** |
| Mensaje | literal con el ID real (287) | **idéntico** |
| Línea base PRE → POST | 404 → 404 | **404 → 404** |
| Línea base nueva | **NO** | **NO** |
| Historial PRE → POST | sin cambios | **0 → 0** |

**Resultado: APROBADO.**

---

## VERIFICACIÓN DE NO PUBLICACIÓN DE LÍNEA BASE

Los cuatro son rechazos de precondición: **cero** líneas base nuevas y **cero** calibraciones VISION exitosas.

| Caso | Área | Línea base PRE | Línea base POST | Nueva | Historial PRE → POST | Calibraciones nuevas | Exitosas |
|---|---|---|---|---|---|---|---|
| TC-M09-278 | 284 | HTTP 404 | HTTP 404 | **NO** | 0 → 0 | `[]` | `[]` |
| TC-M09-279 | 285 | HTTP 404 | HTTP 404 | **NO** | 0 → 0 | `[]` | `[]` |
| TC-M09-280 | 286 | HTTP 404 | HTTP 404 | **NO** | 0 → 0 | `[]` | `[]` |
| TC-M09-281 | 287 | HTTP 404 | HTTP 404 | **NO** | 0 → 0 | `[]` | `[]` |

**Líneas base indebidas: ninguna. STOP_ALL: NO.** La preferencia del §41 se cumplió literalmente: PRE 404 y POST 404 en las cuatro áreas, lo que permite afirmar sin matices que *no se registra línea base para el área*.

### Auditoría RF-10 de los rechazos

| `id_evento` | `tipo_evento` | Resultado | Área | `codigo_http` | `codigo_error` |
|---|---|---|---|---|---|
| **46448** | 29 | fallido | **284** | 422 | `VISION_NO_DISPONIBLE` |
| **46451** | 29 | fallido | **285** | 422 | `VISION_NO_DISPONIBLE` |
| **46454** | 29 | fallido | **286** | 422 | `VISION_NO_DISPONIBLE` |
| **46455** | 29 | fallido | **287** | 422 | `VISION_NO_DISPONIBLE` |

**Eventos de calibración VISION exitosa en las áreas del caso: 0.** Los cuatro rechazos quedaron auditados con resultado FALLIDO, lo que RFC-006 contempla y **no** constituye una línea base: se distingue la auditoría del rechazo (esperable) de la calibración exitosa o la línea base (ambas prohibidas aquí).

---

## RESTAURACIÓN DE FIXTURES

Reversión oficial de todo lo creado, en orden inverso: cámaras, áreas y por último la especie.

| Recurso | ID | Estado original | Cambio | Estado durante | Restauración | Estado final |
|---|---|---|---|---|---|---|
| Cámara de A3 | 218 | no existía | registrada **INACTIVA** de origen | INACTIVA | ninguna escritura; verificado por GET | **inactiva** |
| Cámara de A4 | 219 | no existía | registrada ACTIVA | ACTIVA | `PATCH .../desactivar` | **inactiva** |
| Cámara de A5 | 220 | no existía | registrada ACTIVA | ACTIVA | `PATCH .../desactivar` | **inactiva** |
| Área A2 | 284 | no existía | creada (AVES + MODELO_AVES, 0 cámaras) | ACTIVA | `PATCH .../desactivar` | **inactiva** |
| Área A3 | 285 | no existía | creada (AVES + MODELO_AVES, 1 cámara inactiva) | ACTIVA | `PATCH .../desactivar` | **inactiva** |
| Área A4 | 286 | no existía | creada (MODELO_ESPECIES_GRANDES + cámara activa) | ACTIVA | `PATCH .../desactivar` | **inactiva** |
| Área A5 | 287 | no existía | creada (AVES + modelo nulo + cámara activa) | ACTIVA | `PATCH .../desactivar` | **inactiva** |
| Especie INDIVIDUAL | 111 | no existía | registrada `MODELO_ESPECIES_GRANDES` | ACTIVA | `PATCH .../desactivar` | **inactiva** |

| Elemento | Valor |
|---|---|
| Recursos modificados | **8**, todos creados en este RUN |
| Recursos **preexistentes** modificados | **ninguno** |
| Todos restaurados | **SÍ** |
| Pendientes | **ninguno** |
| Red de seguridad del cierre | no hizo falta intervenir (cámaras `[]`, áreas `[]`, especie «no necesaria») |
| **Resultado** | **PASS** |

La cuenta del Productor no participa en G138 y no se modificó ninguna cuenta.

---

## CUADRO COMPARATIVO

| Criterio | TC-278 | TC-279 | TC-280 | TC-281 |
|---|---|---|---|---|
| Área | **284** | **285** | **286** | **287** |
| Especie | AVES (41) | AVES (41) | ESPECIES_GRANDES (111) | AVES (41) |
| Modelo | POBLACIONAL (`MODELO_AVES`) | POBLACIONAL (`MODELO_AVES`) | INDIVIDUAL (`MODELO_ESPECIES_GRANDES`) | **null** |
| Cámaras asociadas | **0** | **1** | 1 | 1 |
| Cámaras activas | **0** | **0** | **1** | **1** |
| Invalidez aislada | Sin cámara | Cámara inactiva | Modelo individual | Modelo nulo |
| HTTP esperado | 422 | 422 | 422 | 422 |
| HTTP obtenido | **422** | **422** | **422** | **422** |
| `error_code` | `VISION_NO_DISPONIBLE` | `VISION_NO_DISPONIBLE` | `VISION_NO_DISPONIBLE` | `VISION_NO_DISPONIBLE` |
| Mensaje exacto | **SÍ** | **SÍ** | **SÍ** | **SÍ** |
| Línea base PRE | HTTP 404 | HTTP 404 | HTTP 404 | HTTP 404 |
| Línea base POST | HTTP 404 | HTTP 404 | HTTP 404 | HTTP 404 |
| Línea base nueva | **NO** | **NO** | **NO** | **NO** |
| Resultado | **APROBADO** | **APROBADO** | **APROBADO** | **APROBADO** |

---

## RESULTADO NEWMAN

| Elemento | Valor |
|---|---|
| RUN_ID | `run-20261010-115458` |
| Colección ejecutada | **55 de 55** items, una sola vez |
| Iterations | 1 (0 fallidas) |
| Requests | **55** |
| Failed requests | **0** |
| Assertions | **179** |
| **Failures** | **0** |
| POST VISION funcionales | **4 / 4** |
| POST `/iot/telemetria/vision` | **0** |
| Reintentos | **0** |
| STOP_ALL | **NO** |
| HTML | `newman/newman-TC-M09-G138.html` · **Cantidad: 1** |

Newman verde y sin failures del grupo: el §50 se cumple en su forma estricta.

---

## COMPARACIÓN PRIMERA VS SEGUNDA

| Caso | Primera evaluación | Segunda evaluación | Cambio |
|---|---|---|---|
| TC-M09-278 | RECHAZADO / no ejecutable | **APROBADO** | RECHAZADO → APROBADO |
| TC-M09-279 | RECHAZADO / no ejecutable | **APROBADO** | RECHAZADO → APROBADO |
| TC-M09-280 | RECHAZADO / no ejecutable | **APROBADO** | RECHAZADO → APROBADO |
| TC-M09-281 | RECHAZADO / no ejecutable | **APROBADO** | RECHAZADO → APROBADO |
| **G138** | **RECHAZADO** | **APROBADO** | RECHAZADO → APROBADO |

| Dimensión | Primera | Segunda |
|---|---|---|
| Endpoint VISION | AUSENTE | **PRESENTE** |
| POST ejecutados | 0 | **4** |
| HTTP 422 observables | NO | **4 de 4** |
| Mensajes observables | NO | **4 de 4 con el literal exacto** |
| Línea base verificable | NO | **SÍ** — PRE y POST verificados por API en las 4 áreas; **0** líneas base indebidas |

**Causa anterior: CORREGIDA.**

---

## CONTRASTE DEV

**No aplica.** El §60 pide contrastar DEV si TEST no publica el endpoint o si devuelve un comportamiento incompatible con una corrección aparentemente presente en DEV. TEST publica las tres operaciones y los cuatro casos pasaron, así que no se envió ninguna petición a DEV (**0 peticiones**).

---

## DIAGNÓSTICO BD

Consultada como **diagnóstico complementario**, en sesión **READ ONLY**, con `psycopg2` invocado en línea desde el runner. **Solo SELECT · 0 DML.**

| Consulta | Resultado |
|---|---|
| Privilegios del rol QA sobre las tablas del caso | **ejecutada**, 4 filas |
| Áreas del fixture | **denegada**: `permission denied for function fn_fincas_del_usuario` |
| Cámaras por área del fixture | **denegada**: `permission denied for function fn_es_usuario_servicio` |
| Líneas base de las áreas | **denegada**: `permission denied for table lineas_base_vision` |
| Calibraciones VISION de las áreas | **denegada**: `permission denied for table calibraciones_vision` |

**Limitación documentada.** Las tablas existen, pero la cuenta de solo lectura `member_qa` **no tiene `SELECT`** sobre las tablas VISION ni `EXECUTE` sobre las funciones de RLS, lo que además bloquea consultar `infraestructuras` y `dispositivos_iot`. Por eso el oráculo se construyó con los **GET de la API**, que son la superficie autoritativa del producto, y **no se sustituyó la BD por ninguna inferencia**: lo que no pudo comprobarse por SQL queda declarado como no comprobable por privilegios. La BD no es el oráculo principal de este grupo, así que la limitación no afecta al veredicto.

Para habilitar el diagnóstico del §59 hacen falta `GRANT SELECT` a `member_qa` sobre `modulo9.calibraciones_vision`, `modulo9.lineas_base_vision`, `modulo9.infraestructuras` y `modulo9.dispositivos_iot`, y `GRANT EXECUTE` sobre las funciones de RLS.

---

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

| Elemento | Valor |
|---|---|
| Causa anterior | **CORREGIDA** |
| Propuesta | **validar y cerrar** la incidencia previa de G138 (ausencia de la operación VISION en TEST), que abarcaba los cuatro casos |
| Responsable | n/a |
| Causa raíz (redeterminada, no copiada del baseline) | **Hipótesis A** — los cuatro rechazos responden HTTP 422 con el mensaje literal del contrato y el ID real de su área, y ninguno publica línea base: la operación VISION está expuesta en TEST y las cuatro precondiciones negativas del área se validan correctamente |

Las demás hipótesis se descartan con la evidencia de esta corrida: **B** (VISION ausente en TEST y presente en DEV) no aplica — TEST publica las tres operaciones; **C** (una precondición devuelve 2xx) no se reprodujo — ninguna respuesta bajó de 400; **D** (422 con mensaje incorrecto) no se reprodujo — los cuatro mensajes coinciden literalmente, con el ID real sustituido; **E** (se crea línea base pese al 422) no se reprodujo — las cuatro áreas siguen con 404 y el historial intacto.

---

## EVIDENCIAS

```
TC-M09-G138/
└── EvaluacionV2/
    ├── automation/
    │   └── run-g138-v2.cjs
    ├── TC-M09-G138.postman_collection.json
    └── RESULTADOS/
        ├── run-20261010-115458/            ← RUN OFICIAL
        │   ├── TC-M09-G138_reevaluacion_V2.md
        │   ├── evidencia.json
        │   ├── automation_manifest.json
        │   └── newman/
        │       └── newman-TC-M09-G138.html
        └── run-20261010-115305/            ← diagnóstico, NO oficial
            └── EJECUCION_INVALIDA_POR_ERROR_QA.md
```

`evidencia.json` consolida: RUN_ID, git pre/post, ambiente, contrato OpenAPI VISION, los dos actores con permisos y estado, la estrategia de fixtures con su descubrimiento y el detalle de lo reutilizado y lo creado, la ventana, y para cada caso el fixture verificado, las cámaras por área, la línea base PRE, el request, la respuesta, la línea base POST, el historial PRE/POST, el oráculo detallado y el resultado; más la verificación de no publicación de línea base con la auditoría RF-10, el resultado Newman, la restauración recurso por recurso, el diagnóstico de BD con su limitación de privilegios, la comparación primera/segunda, la causa raíz, la incidencia, la seguridad y el git final.

`automation_manifest.json` registra ruta, función y SHA-256 de los **4** artefactos: el runner y la colección de EvaluacionV2, y la colección y el runner de la primera evaluación (reutilizados en solo lectura, no modificados). **No hay scripts dentro de `RESULTADOS/`.**

### Ejecución descartada

**`run-20261010-115305`** — EJECUCIÓN INVÁLIDA POR ERROR QA, conservada solo como diagnóstico y con su marcador. El fixture y los cuatro casos funcionales fueron correctos (los cuatro 422 con mensaje exacto y sin línea base), pero el paso de restauración intentaba desactivar la cámara de A3, que había nacido inactiva; el backend respondió correctamente **422 `DISPOSITIVO_YA_INACTIVO`** y eso dejó 2 failures de automatización en el HTML. Como el §50 no admite Newman rojo con failures del grupo, se invalidó, se corrigió el paso —ahora es una verificación por GET, sin escritura— y se ejecutó el RUN oficial. Todo el fixture de esa tentativa quedó revertido.

### Seguridad

Escaneo de todo `EvaluacionV2/`: **limpio**. Hallazgos: **ninguno**. Credenciales en claro: **0**. No quedaron persistidos `PASSWORD_QA`, la contraseña de BD, JWT, cabeceras `Authorization`/`Bearer`, cookies, `refresh_token`, DSN con contraseña ni los **seriales de las cámaras** del fixture, que por contrato funcionan como `access_key` de la ingesta M03.

El escaneo detectó un filtrado real y se corrigió: el inventario de dispositivos devuelve **todas** las cámaras de TEST, incluidas las de la tentativa descartada, de modo que sus seriales aparecían en la evidencia y en el HTML. El saneado pasó a redactar los seriales **por patrón** (`QA-M09-G1xx-…`) y no solo los del RUN en curso, y se re-sanearon los artefactos afectados. Verificado: **0** apariciones de serial en todo `EvaluacionV2/`.

El reporter `htmlextra` se ejecutó con `omitHeaders`, sin environment ni globals y omitiendo las variables sensibles; el HTML se sanitizó después de generarse.

---

## CONCLUSIÓN

**TC-M09-G138: APROBADO.**

Lo que bloqueaba la primera evaluación está resuelto: TEST **ya publica** la operación de calibración VISION con su historial y su consulta de línea base vigente, y el 422 de precondición está declarado en el contrato. Eso convirtió en ejecutable lo que antes solo podía declararse ausente, y permitió someter a prueba las cuatro precondiciones negativas del área en lugar de inferirlas.

**Las cuatro se validan correctamente y cada una por su propio motivo.** Un área poblacional de aves sin ninguna cámara asociada, otra cuya única cámara está inactiva, otra con un modelo de paradigma individual y cámara activa, y otra con especie de aves presente pero sin modelo asignado: las cuatro reciben **HTTP 422** con `VISION_NO_DISPONIBLE` y **el mensaje literal del contrato con el ID real de su propia área**, sin que ninguna llegue al cálculo. El diseño del fixture es lo que da valor al resultado: cada caso usa un área distinta, creada para él, con **una sola** precondición inválida, de modo que el 422 es atribuible a esa causa y no a una mezcla.

**Ningún rechazo tuvo efecto de escritura.** Las cuatro áreas empezaron y terminaron con 404 en la consulta de línea base y con el historial en cero, no apareció ninguna calibración VISION —ni exitosa ni de otro tipo— y STOP_ALL no se activó. Los cuatro rechazos sí quedaron auditados en RF-10 con resultado FALLIDO y `codigo_http 422`, que es lo esperable por RFC-006 y no constituye línea base.

El grupo se cierra sin deuda operativa: Newman en verde con 179 assertions y 0 failures, un único HTML oficial, los ocho recursos creados revertidos por desactivación oficial y verificados, ningún recurso preexistente de TEST modificado, cero SQL de escritura y cero observaciones M03 cargadas. Queda señalada una limitación de entorno que no afecta al veredicto pero conviene corregir: la cuenta de solo lectura de QA no tiene `SELECT` sobre las tablas VISION, así que el diagnóstico de BD del §59 no pudo ejercerse y la verificación se apoyó en los GET de la API.
