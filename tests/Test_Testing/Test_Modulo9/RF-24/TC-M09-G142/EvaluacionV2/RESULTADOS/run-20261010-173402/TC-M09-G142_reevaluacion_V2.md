# TC-M09-G142 — SEGUNDA EVALUACIÓN

**RF-24 v2.0 · CU05 Flujo F · Módulo 9 — Disparo automático de la calibración por visión desde M02**

| | |
|---|---|
| RUN_ID | `run-20261010-173402` (único; no se creó un RUN nuevo) |
| Ejecución | **2** — `REEJECUCION_COMPLETA_POST_FIX` |
| Ambiente decisorio | TEST — `https://api.inmero.co/back-sigab-test` |
| Casos | TC-M09-288 (alta de lote → VISION), TC-M09-289 (cierre de ciclo → VISION) |
| Herramientas | **Newman** ejecutor de los eventos M02 · **Pytest** verificador independiente de solo lectura |
| Rama QA | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| HEAD QA | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| `origin/test` | `4f09cb6953843cbab06319000c14d1b30feb8a56` |
| POST manual de calibración VISION | **0** |

---

## DECISIÓN GENERAL ACTUAL

| Caso | Resultado vigente |
|---|---|
| **TC-M09-288** | **APROBADO** |
| **TC-M09-289** | **APROBADO** |
| **TC-M09-G142** | **APROBADO** |

**Incidencia original (Desarrollo / Integración M02-M09): CORREGIDA** por el **PR #554** ·
**Incidencia nueva: NO**

Los dos disparadores quedaron demostrados funcionalmente en TEST, cada uno con su propia
calibración automática, su línea base y su evento RF-10. Sin ninguna llamada manual a
`POST /configuracion/calibraciones-vision`.

---

## HISTORIAL DE EJECUCIONES

### EJECUCIÓN 1 — SEGUNDA EVALUACIÓN INICIAL

| | |
|---|---|
| Fecha | 2026-10-10 |
| TC-M09-288 | **RECHAZADO** — alta 201 (lote 792) y **ninguna** calibración automática |
| TC-M09-289 | **RECHAZADO** — el lote no tenía ciclo productivo asignable; cierre **422 `SIN_FASE_ACTIVA`** |
| **TC-M09-G142** | **RECHAZADO** |
| Newman | 40 requests · 60 assertions · **8 failures** |
| Pytest | 10 collected · 10 passed |
| Incidencia | **ABIERTA** |

Diagnóstico de entonces: **no existía integración M02 → M09**. Ni el alta ni el cierre
tenían hook hacia el caso de uso VISION, y `OrigenDisparo.AUTOMATICO` no se usaba en
ningún punto del código.

> El Pytest de aquella ejecución era un verificador de hechos: sus 10 passed **no**
> significaban que el grupo hubiera aprobado. El veredicto fue RECHAZADO.

La colección arrastraba además un defecto cosmético: el setup de ciclos accedía a
`items[0].fases` incluso con `items = []`, lo que producía un error de script.

### INTENTO DE EJECUCIÓN 2 DETENIDO EN LA COMPUERTA — 2026-10-11

Antes de esta ejecución hubo un intento que **se detuvo por diseño antes de cualquier POST
funcional**, porque ninguna especie POBLACIONAL tenía simultáneamente ciclo productivo y
fase:

| | |
|---|---|
| `AUTOMATION_PRECHECK` | **PASS** (Newman precheck 11 requests · 19 assertions · 0 failures) |
| `FIXTURE_G142_APTO` | **NO** |
| `TC289_PRECONDICION` | **NO MONTABLE** |
| POST funcionales | **0** |
| Artefactos oficiales | **intactos** |

No cuenta como reejecución funcional. De ese intento salieron tres correcciones del arnés
que esta ejecución ya aprovecha: la guarda de arrays, la compuerta de cualificación de
fixture y el modo de diagnóstico del arnés.

### CORRECCIÓN DE DESARROLLO — PR #554

| | |
|---|---|
| PR | **#554** |
| Puerto | `RecalibracionVisionPort` (`src/biological_assets/domain/repositories/`) |
| Adaptador | `RecalibracionVisionM09Adapter` — corre en `BackgroundTasks` con sesión propia del usuario de servicio |
| Hook de alta | `RegistrarActivoBiologicoUseCase`, condicionado a `activo.tipo == 'POBLACIONAL'` |
| Hook de cierre | `CerrarCicloUseCase`, condicionado a `activo.tipo == 'POBLACIONAL'` |
| Caso de uso M09 | `CalibrarVisionUseCase.execute_automatico(...)` |
| Ventana | `VENTANA_DISPARO_AUTOMATICO = 7 días` |

**Verificado por lectura en `origin/test` (`4f09cb69`), sin cambiar de rama:** los siete
componentes están presentes. El `diff` contra el commit anterior toca exactamente el
puerto, el adaptador, los dos casos de uso de M02, el router, `calibrar_vision_use_case.py`
y `src/shared/database.py`.

Contrato que implementa, leído del código y no supuesto:

* Alta → motivo `Disparo automático M02: nuevo lote <ID>`, momento = `datetime.now(utc)`.
* Cierre → motivo `Disparo automático M02: fin de ciclo del lote <ID>`, momento = `fecha_cierre_dt`.
* Calibración con `origen_disparo = AUTOMATICO` e `id_usuario = None`.
* Evento RF-10 firmado por `id_usuario_servicio(db)`.
* Si el área no tiene cámaras activas, el disparo no aplica y devuelve `None` sin auditar.

**OpenAPI no puede probar este fix**: #554 no agrega ningún endpoint, la integración va por
`BackgroundTasks`. La demostración tiene que ser funcional, y es lo que sigue.

### PREPARACIÓN DE DATOS POR DBA / IMPLEMENTACIÓN

DBA informó haber insertado, con COMMIT, los registros que faltaban, y advirtió que **no
pudo ejecutar su consulta final de verificación por permisos**. QA los validó antes de
usarlos; el resultado está en la sección siguiente.

| Elemento | Valor informado |
|---|---|
| Especie | 78 |
| Ciclo biológico | 54 — «Fase unica QA G142 Aves» |
| Ciclo productivo | 11 — «Ciclo QA G142 Aves» |
| Registro de fase | 21 |
| Duración | 42 días |

La auditoría `CREATE` que DBA registró es de **preparación de datos**; no es evidencia de
auditoría automática VISION y no se cuenta como tal en ninguna parte de este informe.

### EJECUCIÓN 2 — REEJECUCIÓN COMPLETA POST-FIX

| | |
|---|---|
| Fecha/hora | 2026-10-11 05:59–06:01 UTC (2026-10-11 00:59–01:01 −05:00) |
| TC-M09-288 | **APROBADO** |
| TC-M09-289 | **APROBADO** |
| **TC-M09-G142** | **APROBADO** |

---

## AUTOMATION PRECHECK

| Comprobación | Resultado |
|---|---|
| Sintaxis JS del runner e imports de Node | **PASS** |
| OpenAPI de TEST | **PASS** (200; `rutas_ausentes: []`) |
| Rutas, métodos y esquemas usados por el arnés | **PASS** |
| Query params y límites min/max | **PASS** |
| `tamano` de auditoría | **PASS** — contrato máx **50**; el arnés pide **50** |
| Campos de auditoría: usa `resultado`, no `exitoso` | **PASS** |
| Protección de arrays vacíos antes de indexar | **PASS** |
| El runner no duplica la autenticación de la colección | **PASS** (la colección es dueña de su sesión) |
| Correcciones previas del arnés presentes | **PASS** |
| **Newman precheck** | 11 requests · 19 assertions · **0 failures** · **0 escrituras** |
| **AUTOMATION_PRECHECK** | **PASS** |
| **AUTORIZAR_RUN** | **SÍ** |

El precheck es de solo lectura: sin HTML, sin artefactos persistentes y sin un solo POST
funcional.

---

## QUALIFICATION DEL FIXTURE

La compuerta vive en `run-g142-v2.cjs` y corre **antes** de Newman en los dos modos. Resuelve
por SELECT de solo lectura la intersección «especie activa con `tipo_modelo` POBLACIONAL ×
ciclo productivo × ≥1 fase × densidad configurada». Si no hay candidata, aborta sin escribir.

### Verificación de los datos de DBA

| Comprobación | Fuente | Resultado |
|---|---|---|
| Especie **78** existe y está activa | SELECT + API | **PASS** |
| `tipo_modelo = MODELO_AVES` → paradigma POBLACIONAL | SELECT + código (`PARADIGMA_POR_TIPO_MODELO`) | **PASS** |
| `densidad_maxima_por_especie = 50.0000` | SELECT + API | **PASS** |
| Ciclo biológico **54** pertenece a la especie 78, activo, 42 días | SELECT + `GET /configuracion/ciclos?id_especie=78` | **PASS** |
| Ciclo productivo **11** cuelga del ciclo biológico 54, 42 días | SELECT `modulo9.ciclos_productivos` | **PASS** |
| Registro de fase **21** liga el ciclo productivo 11 con el ciclo biológico 54 | SELECT `modulo9.ciclos_productivos_biologicos` | **PASS** |
| Métricas obligatorias del lote | `GET /configuracion/metricas?id_especie=78` → `total 0` | **PASS** (ninguna exigida) |

**La comprobación que de verdad importaba** (§4.4): que exista en SQL no prueba que M02 lo
acepte. `GET /activos-biologicos/792/ciclos-productivos` —lote preexistente de la especie
78, consultado **solo** como diagnóstico de lectura y **no** reutilizado como objetivo—
devolvió:

```json
{"id_activo_biologico": 792, "total": 1, "items": [
  {"id_ciclo_productivo": 11, "nombre": "Ciclo QA G142 Aves",
   "fases": [{"id_ciclos_productivo_biologico": 21, "id_ciclo_biologico": 54,
              "nombre_fase": "Fase unica QA G142 Aves", "duracion_dias": 42}]}]}
```

**`CICLO_ASIGNABLE_M02 = PASS`.**

### Identificadores: cuál pide cada API

Los tres ids son distintos y es fácil confundirlos, así que se resolvieron contra el DTO
vigente (`CambiarFaseDTO`) y no por analogía:

| Campo de la API | Tabla | Valor |
|---|---|---|
| `id_ciclo_productiva` (obligatorio) | `modulo9.ciclos_productivos` | **11** |
| `fase_destino_id` (opcional) | `modulo9.ciclos_productivos_biologicos` | **21** |
| — (no se envía nunca) | `modulo9.ciclos_biologicos` | 54 |

### Reglas de duración y cierre (§4.5)

La duración de 42 días **no** obliga a esperar 42 días, y tampoco había que suponer que el
cierre inmediato estuviera permitido. Se verificó en el código vigente:

* `CambiarFaseUseCase` no impone duración mínima. Con el lote recién creado no hay gestiones
  previas, así que `idx_estandar = 0` y la fase estándar siguiente es la única del ciclo:
  la transición es estándar y **no** requiere `confirmacion_no_estandar`.
* `CerrarCicloUseCase` exige estado que permita el cierre, sin sensores activos asociados,
  **fase activa** (FA-05) y `fecha_cierre` **no anterior** al último evento (FA-04). Nada
  comprueba la duración de la fase.
* `motivo_cierre = finalizacion_lote` es válido para el escenario.
* Con `fecha_cierre = hoy`, `fecha_cierre_dt = ahora` (hora real), que es además el extremo
  de la ventana del disparo automático.

**`REGLAS_FASE_Y_CIERRE = PASS`**, sin modificar fechas, parámetros ni duración, y sin un
solo UPDATE.

### Resumen de la compuerta

| Gate | Resultado |
|---|---|
| `OPENAPI` | **PASS** |
| `AUTH` | **PASS** |
| `AUTOMATION_PRECHECK` | **PASS** |
| `ESPECIE_78` | **PASS** |
| `MODELO_POBLACIONAL` | **PASS** |
| `DENSIDAD` | **PASS** |
| `METRICAS_LOTE` | **PASS** |
| `CICLO_BIOLOGICO_54` | **PASS** |
| `CICLO_PRODUCTIVO_11` | **PASS** |
| `FASE_21` / `FASES_CICLO` | **PASS** / **1** |
| `CICLO_ASIGNABLE_M02` | **PASS** |
| `REGLAS_FASE_Y_CIERRE` | **PASS** |
| **`FIXTURE_G142_APTO`** | **SÍ** |
| **`AUTORIZAR_RUN`** | **SÍ** |

Especies POBLACIONAL activas: 22 · ciclos productivos en el sistema: 9 · con ciclo y ≥1
fase: **1** · y con densidad: **1** → la especie **78**.

**La especie no se eligió por heurística.** La colección la escogía antes por «id más bajo
entre las aptas», y eso habría funcionado por casualidad (78 < 82) mientras la 82 —que no
tiene ciclos— habría roto TC-289. Ahora la compuerta impone la especie que cualificó
contra la BD y la colección la obedece, registrando la razón:
`cualificada por la compuerta: tiene ciclo productivo con fases y densidad`. Los ids 78,
54, 11 y 21 no quedaron incrustados en el arnés.

---

## CONTRATO DE LA INTEGRACIÓN ACTUAL

| Elemento | Esperado | Observado |
|---|---|---|
| `origen_disparo` | `AUTOMATICO` | **`AUTOMATICO`** en las dos |
| `id_usuario` de la calibración | `null` | **`null`** en las dos |
| `fecha_calibracion` | momento del evento M02 | coincide con `T_ALTA` y con el cierre |
| `observaciones` | motivo del disparo | literal esperado en las dos |
| Ventana | 7 días previos al evento | **7.0 días** medidos en las dos |
| Firma del evento RF-10 | usuario de servicio | **132 «Servicio Sistema SGPMP»** |

Sobre la firma (§12 y §76): lo que debe ser nulo es `calibracion.id_usuario`, **no**
`auditoria.id_usuario`, que es obligatorio en `modulo1.eventos`. Que RF-10 vaya firmado por
el usuario de servicio es correcto y no se reporta como discrepancia.

Los 7 días quedan registrados como dato observado de la implementación. La matriz RF-24 no
fija ese tamaño, así que **no** se convierte en criterio contractual de QA fuera de esta
implementación.

---

## FIXTURE ACTUAL

Fixture nuevo. No se reutilizaron el área 291, la cámara 227 ni el lote 792 como objetivo.

| Elemento | Valor |
|---|---|
| Finca | **163** (resuelta dinámicamente entre las del actor: `[162, 163]`) |
| Tipo de área | `Galpón` (del catálogo) |
| **A1_CURRENT** | **309** — `QA-G142-A1-20261011-055926`, activa, especie 78, `MODELO_AVES` |
| **C1_CURRENT** | **248** — CAMARA, activa, 30 fps, asociada a A1 |
| Sufijo del fixture | `20261011-055926` (sello de esta ejecución, no el RUN_ID) |

---

## OBSERVACIONES VISION

| | |
|---|---|
| `N` (`ParametrosLineaBase.min_observaciones`) | **30**, leído del código vigente |
| Enviadas | **40** (N + margen) |
| HTTP | **201** |
| total / aceptadas / duplicadas | **40 / 40 / 0** |
| `apto_para_ia = true` | **40 de 40** |
| Ventana de las observaciones | `2026-10-10T05:59:00Z` → `2026-10-10T09:14:00Z` |
| Dentro de la ventana automática de 7 días | **SÍ** |

`apto_para_ia` no se envió: lo calculó M03. Calidad enviada: cobertura 1.0000, 20 tracks,
0 perdidos, fps efectivo 30.00, `CALIBRADA`. Cámara nueva y exclusiva, de ahí el
`duplicadas = 0`.

---

## TC-M09-288 — ALTA DE LOTE

| | Esperado | Obtenido |
|---|---|---|
| Historial VISION PRE de A1 | vacío | **`[]`** |
| Línea base PRE | 404 | **404** |
| `POST /activos-biologicos` | 201 | **201** |
| **ID_LOTE** | — | **806** |
| `tipo_activo` | POBLACIONAL | **POBLACIONAL** |
| Área / especie del lote | 309 / 78 | **309 / 78** |
| `T_ALTA` | — | **2026-10-11T05:59:47.864Z** |
| POST manual VISION | 0 | **0** |

Una sola ejecución, sin reintento.

## DISPARO AUTOMÁTICO POST ALTA

Observado **solo con GET**, con la cadencia 0/2/5/10/20/30 s.

| | Esperado | Obtenido |
|---|---|---|
| Calibraciones nuevas atribuibles al alta | exactamente 1 | **1** |
| **AUTO_288_ID** | — | **19** |
| `estado` | EXITOSA | **EXITOSA** |
| `origen_disparo` | AUTOMATICO | **AUTOMATICO** |
| `id_usuario` | null | **null** |
| `area_id` / `especie_id` | 309 / 78 | **309 / 78** |
| `n_observaciones` / `n_validas` | 40 / 40 | **40 / 40** |
| `iteraciones` | — | 1 |
| `observaciones` (motivo) | `nuevo lote 806` | **«Disparo automático M02: nuevo lote 806»** |
| `ventana_observacion` | 7 días hasta el evento | **2026-10-04T05:59:47 → 2026-10-11T05:59:47 (7.0 días)** |
| `linea_base` | no nula | **`{densidad_actividad: 12.01, tasa_movimiento: 6.01}`** |
| Línea base vigente tras el alta | AUTO_288 | **200, publicada** |
| Duplicados | ninguno | **ninguno** |

### Auditoría RF-10 del alta

| Campo | Valor |
|---|---|
| `id_evento` | **50308** |
| `tipo_evento` | **30** `CALIBRACION_EXITOSA` (resuelto del catálogo) |
| `resultado` | **exitoso** |
| `modulo` | **MODULO9** |
| `id_usuario` / `nombre_usuario` | **132 / Servicio Sistema SGPMP** |
| `detalle.operacion` | **CALIBRACION_VISION** |
| `detalle.origen_disparo` | **AUTOMATICO** |
| `detalle.id_calibracion_vision` | **19** |
| `detalle.id_infraestructura` / `id_especie` | **309 / 78** |
| `detalle.estado` | **EXITOSA** |

Tiempo hasta la observación: **385.4 s** desde `T_ALTA`, que es cuándo lo miró el
verificador, no cuánto tardó el disparo. RF-24 no fija plazo y no se usa como umbral.

**TC-M09-288: APROBADO.**

---

## TC-M09-289 — FASE Y CIERRE

### Precondición

| | Esperado | Obtenido |
|---|---|---|
| `GET /activos-biologicos/806/ciclos-productivos` | 200, lista no vacía | **200, total 1** |
| Ciclo cualificado presente | ciclo 11 | **11** |
| Fases del ciclo | ≥ 1 | **1** (registro 21) |
| `POST /activos-biologicos/806/fases` | 2xx | **201** |
| Cuerpo enviado | `id_ciclo_productiva: 11` (numérico) | correcto |
| Fase activa confirmada por GET | SÍ | **SÍ** |
| Historial VISION PRE | contiene AUTO_288 | **`[19]`** |
| Línea base PRE | AUTO_288 | **19** |

### Cierre

| | Esperado | Obtenido |
|---|---|---|
| `POST /activos-biologicos/806/cierre` | 2xx | **200** |
| `motivo_cierre` | `finalizacion_lote` | correcto |
| `T_CIERRE` | — | **2026-10-11T06:00:15.367Z** |
| Lote cerrado | SÍ | **SÍ** — `id_estado = 5` (`EstadoActivo.CERRADO`) |
| POST manual VISION | 0 | **0** |

Una sola ejecución, sin reintento.

## DISPARO AUTOMÁTICO POST CIERRE

| | Esperado | Obtenido |
|---|---|---|
| Calibraciones nuevas atribuibles al cierre | exactamente 1 | **1** |
| **AUTO_289_ID** | — | **20** |
| `AUTO_289_ID != AUTO_288_ID` | SÍ | **SÍ (20 ≠ 19)** |
| `estado` | EXITOSA | **EXITOSA** |
| `origen_disparo` | AUTOMATICO | **AUTOMATICO** |
| `id_usuario` | null | **null** |
| `n_observaciones` / `n_validas` | 40 / 40 | **40 / 40** |
| `observaciones` (motivo) | `fin de ciclo del lote 806` | **«Disparo automático M02: fin de ciclo del lote 806»** |
| `ventana_observacion` | 7 días hasta el cierre | **2026-10-04T06:00:14 → 2026-10-11T06:00:14 (7.0 días)** |
| `linea_base` | no nula | **`{densidad_actividad: 12.01, tasa_movimiento: 6.01}`** |
| Línea base vigente final | AUTO_289 | **20** |
| Duplicados | ninguno | **ninguno** |

### Auditoría RF-10 del cierre

| Campo | Valor |
|---|---|
| `id_evento` | **50309** (distinto del de TC-288) |
| `tipo_evento` | **30** `CALIBRACION_EXITOSA` |
| `resultado` | **exitoso** |
| `modulo` | **MODULO9** |
| `id_usuario` / `nombre_usuario` | **132 / Servicio Sistema SGPMP** |
| `detalle.operacion` | **CALIBRACION_VISION** |
| `detalle.origen_disparo` | **AUTOMATICO** |
| `detalle.id_calibracion_vision` | **20** |
| `detalle.estado` | **EXITOSA** |

Tiempo hasta la observación: **357.9 s** desde `T_CIERRE`, como métrica.

**TC-M09-289: APROBADO.**

---

## CALIBRACIONES AUTOMÁTICAS

`GET /configuracion/calibraciones-vision?area_id=309`

| ID | Estado | Origen | `id_usuario` | n/válidas | Iter. | Motivo | Evento M02 |
|---|---|---|---|---|---|---|---|
| **20** | EXITOSA | **AUTOMATICO** | **null** | 40 / 40 | 1 | fin de ciclo del lote 806 | cierre |
| **19** | EXITOSA | **AUTOMATICO** | **null** | 40 / 40 | 1 | nuevo lote 806 | alta |

Cada evento de M02 produjo **una sola** calibración, correlacionada con su evento por
motivo y por `fecha_calibracion`. No hubo disparos duplicados.

## LÍNEA BASE VIGENTE

| Momento | Vigente | Valores |
|---|---|---|
| Antes del alta | **404** (ninguna) | — |
| Tras el alta | **19** | `{densidad_actividad: 12.01, tasa_movimiento: 6.01}` |
| Tras el cierre | **20** | `{densidad_actividad: 12.01, tasa_movimiento: 6.01}` |

Que AUTO_289 reemplace la línea base de AUTO_288 es lo esperado: comparten el par
(área, especie). Los valores coinciden porque las dos ventanas de 7 días abarcan las mismas
40 observaciones.

## AUDITORÍA RF-10

| Caso | `id_evento` | tipo | `resultado` | `modulo` | origen | calibración |
|---|---|---|---|---|---|---|
| TC-M09-288 | **50308** | 30 | exitoso | MODULO9 | AUTOMATICO | 19 |
| TC-M09-289 | **50309** | 30 | exitoso | MODULO9 | AUTOMATICO | 20 |

Dos eventos independientes, uno por disparo. Consultados con `tamano = 50` (el máximo del
contrato) y leyendo `resultado`, que es el campo real. Eventos de tipo 29
(`CALIBRACION_RECHAZADA`) para esta área: **ninguno**.

## BD COMPLEMENTARIA

| | |
|---|---|
| `member_qa`, sesión **READ ONLY** · DML **0** | |
| `modulo9.ciclos_productivos` / `ciclos_biologicos` / `ciclos_productivos_biologicos` / `especies` | **SELECT disponible** — se usó para cualificar el fixture |
| `modulo3.observaciones_vision` / `modulo9.calibraciones_vision` / `modulo9.lineas_base_vision` | **SIN SELECT** |
| **`BD_VISION_COMPLEMENTARIA`** | **NO DISPONIBLE POR PERMISOS QA** |

No bloqueó nada: los endpoints oficiales son el oráculo funcional y bastaron para el
veredicto. El acceso a las tablas de ciclos fue, en cambio, decisivo para cualificar el
fixture antes de escribir.

---

## RESULTADO NEWMAN ACTUAL

| | |
|---|---|
| Requests | **40** |
| Assertions | **69** |
| Failures | **1** |
| Script errors | **0** |
| Failures de producto | **0** |
| Failures de automatización | **1** |
| Presupuesto | alta M02 **1** · cierre M02 **1** · fase **1** · lote M03 **1** · **POST manual VISION 0** · reintentos **0** |
| HTML | `newman/newman-TC-M09-G142.html` |

**El único fallo es de mi automatización, no del producto.** La assertion
`TC-289 · el lote quedo CERRADO` comparaba el valor devuelto contra la cadena `'CERRADO'`,
y el contrato devuelve el **id** de estado: llegó `'5'`, que es precisamente
`EstadoActivo.CERRADO = 5`. El lote **sí** quedó cerrado.

Qué se hizo y qué no:

* **No se repitió ningún POST.** El cierre ya había recibido respuesta y repetirlo daría 409
  sin corresponder al caso.
* **No se maquilló el HTML ni el resumen.** El fallo sigue ahí, con su mensaje real.
* La postcondición se cerró con GET: el verificador independiente comprueba
  `id_estado == 5` o el nombre, y pasa.
* **La assertion ya está corregida**, después de la ejecución y por petición de QA.
  Causa exacta: el cuerpo de `GET /activos-biologicos/{id}` trae `id_estado: 5`,
  `nombre_estado: "CERRADO"` y **`estado: null`**; la assertion leía
  `b.estado || b.id_estado`, así que el `null` la hacía caer al id y comparaba `'5'` contra
  la cadena `'CERRADO'`, ignorando el nombre que venía en `nombre_estado`. Ahora acepta
  `id_estado == 5` (`EstadoActivo.CERRADO`) o un nombre que contenga CERRADO, y registra los
  dos valores.
* **Cómo se validó sin repetir nada funcional:** se evaluó la lógica vieja y la nueva en Node
  contra el cuerpo real de `GET /activos-biologicos/806` —un GET, no un evento—. La vieja da
  `false`; la nueva da `true`. El alta y el cierre **no** se repitieron: ya habían recibido
  respuesta. La assertion se ejercitará de verdad en la próxima ejecución oficial del grupo.
* **Trazabilidad del cambio.** Como la colección se editó después de ejecutar, su SHA-256 en
  disco ya no es el que produjo estos artefactos. El manifest conserva el `sha256` que
  ejecutó y añade `sha256_en_disco_tras_la_ejecucion` junto con el detalle de la corrección,
  en lugar de recalcularlo y dar a entender que esta versión generó el HTML.

### Arnés listo para la próxima ejecución oficial

Revisando qué pasaría al reejecutar el grupo apareció un **bloqueador** que no tenía que ver
con ningún caso: el modo `run` abortaba **siempre** si ya existía el HTML oficial del RUN, lo
que obligaba a borrarlo a mano. Eso choca con la política «mismo RUN lógico, varias
ejecuciones» y convierte cada reejecución en un borrado manual, que es justo como se pierde
evidencia. Ahora la reejecución se declara con `G142_SOBRESCRIBIR_OFICIAL=1`: sin la variable
aborta explicando la política, y con ella avisa por consola antes de sobrescribir. Verificado
ejecutando `run` sin la variable: aborta en la guarda, después de la compuerta y **antes** de
Newman, sin emitir un solo POST y dejando los artefactos intactos.

Se alineó además el precheck con la compuerta: informaba de la especie 82 (0 ciclos) mientras
el RUN corría con la 78, de modo que su reporte de consola no describía el fixture real.
Reejecutado: 11 requests, 20 assertions, 0 failures, 0 escrituras, `especie_id 78`,
`ciclos_de_la_especie 1`, `AUTORIZAR_RUN: SÍ`.

Los tres archivos corregidos después de ejecutar quedan anotados en el manifest con su
`sha256` de ejecución y su `sha256_en_disco_tras_la_ejecucion`. `test_g142_v2.py` coincide,
porque el Pytest se reejecutó con su versión final.

Lo que la próxima ejecución oficial necesita del operador: `G142_DB_PASSWORD` en el proceso
(sin ella la compuerta queda en `NO VERIFICABLE` y no autoriza), `G142_SOBRESCRIBIR_OFICIAL=1`
si se reutiliza este mismo RUN, y que el fixture sembrado por DBA siga vivo —especie 78
activa con densidad, ciclo productivo 11 y su fase 21—. Si alguien desactiva la especie o
retira el ciclo, la compuerta cierra y lo dice antes de escribir.

### Primer intento oficial de esta ejecución, fallido en el setup

Antes del RUN que se reporta aquí hubo un intento que murió en `SETUP 04` con **409** al
crear el área: el `sufijo` del fixture se derivaba del `RUN_ID`, y como la política es
«mismo RUN, nueva ejecución», el nombre `QA-G142-A1-20261010-173402` ya existía de la
ejecución 1 (área 291). Todo lo demás cayó en cascada (40 requests, 44 failures).

Lo verifiqué antes de repetir: **no se creó nada en TEST** —área 409, cámara 400, M03 400,
alta 400, fase 405, cierre 405— y no quedó ningún lote nuevo de la especie 78. El caso
nunca se ejercitó, así que corregir el arnés y repetir es lo que corresponde a un fallo de
automatización previo al evento funcional. El `sufijo` pasa ahora por un sello propio de
cada ejecución.

## RESULTADO PYTEST ACTUAL

| | |
|---|---|
| Collected | **10** |
| Passed | **10** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| POST funcionales emitidos por Pytest | **0** |

El verificador se reforzó en esta ejecución, y conviene decir por qué: tal como venía de la
ejecución 1, **calculaba** el veredicto pero no comprobaba el contrato —`origen_disparo`,
`id_usuario`, estado y motivo estaban fijados a `None` en la evidencia, herencia de cuando
no existía ninguna calibración—. Un verificador que pasa igual con disparo y sin disparo no
verifica nada. Ahora afirma, y falla si no se cumple: una sola calibración por evento,
`estado EXITOSA`, `origen_disparo AUTOMATICO`, `id_usuario` nulo, área y especie correctas,
línea base publicada, motivo literal del evento, `AUTO_289 != AUTO_288`, línea base final
apuntando a AUTO_289, y el evento RF-10 correlacionado con cada calibración con su
`resultado`, `modulo`, `operacion` y `origen_disparo`. Sigue siendo de solo lectura.

Durante ese refuerzo apareció y se corrigió un defecto propio: el evento de auditoría que
el verificador guardaba descartaba `resultado`, `modulo` e `id_usuario`, así que la primera
pasada falló leyendo `resultado = None`. No era del producto.

---

## COMPARACIÓN PRE-FIX VS POST-FIX

| Criterio | PRE-FIX (ejecución 1) | POST-FIX (ejecución 2) |
|---|---|---|
| Hook alta M02→M09 | AUSENTE | **PRESENTE** |
| Hook cierre M02→M09 | AUSENTE | **PRESENTE** |
| Alta válida | 201 | **201** |
| Auto tras alta | **NO** | **SÍ** |
| AUTO_288_ID | ninguno | **19** |
| Origen 288 | — | **AUTOMATICO** |
| Usuario calibración 288 | — | **null** |
| Baseline 288 | 404 | **publicada (19)** |
| Auditoría 288 | **NO** | **SÍ (50308)** |
| Ciclo asignable TC-289 | **NO** | **SÍ (11)** |
| Fase activa | **NO** | **SÍ (registro 21, HTTP 201)** |
| Cierre válido | **NO (422 `SIN_FASE_ACTIVA`)** | **SÍ (200, lote CERRADO)** |
| Auto tras cierre | **NO** | **SÍ** |
| AUTO_289_ID | ninguno | **20** |
| Origen 289 | — | **AUTOMATICO** |
| Usuario calibración 289 | — | **null** |
| Baseline final | 404 | **20** |
| Auditoría 289 | **NO** | **SÍ (50309)** |
| Newman failures | 8 | **1 (de automatización)** |
| TC-288 | RECHAZADO | **APROBADO** |
| TC-289 | RECHAZADO | **APROBADO** |
| G142 | RECHAZADO | **APROBADO** |
| Incidencia | ABIERTA | **CORREGIDA** |

**FIX #554 CONFIRMADO: SÍ**, y confirmado funcionalmente en TEST, no por la presencia del
código en `origin/test`.

---

## ESTADO DE INCIDENCIA

| | |
|---|---|
| Incidencia original | **CORREGIDA** |
| PR | **#554** |
| Responsable | Desarrollo / Integración M02-M09 |
| Type / Severity / Priority | bug / Important / High |
| **Incidencia nueva** | **NO** |

La corrección es completa en lo que el grupo mide: los dos disparadores funcionan, cada uno
produce una única calibración del Sistema con su línea base y su evento RF-10, y ninguno
necesita intervención manual.

La **corrección del arnés de QA** que quedaba pendiente —la assertion del estado del lote—
ya está aplicada y validada contra la respuesta real; el detalle y su efecto en los hashes
están en la sección de Newman. No afecta al veredicto de ningún caso: el lote ya constaba
cerrado por `id_estado = 5` y así lo verificó el Pytest independiente.

---

## RESTAURACIÓN

| | |
|---|---|
| Cámara **248** desactivada por API (`PATCH .../desactivar`) | **HTTP 200** |
| Área **309** | conservada — RF-20 no publica eliminación; queda como dato QA trazable |
| Lote **806** | conservado **CERRADO** (evidencia del caso) |
| Calibraciones 19 y 20, línea base, observaciones, historial de fases | **conservados** |
| SQL DML ejecutado por QA en TEST | **0** |
| DML de preparación por DBA | realizado y confirmado por DBA, fuera de la automatización de QA |

---

## EVIDENCIAS

```
TC-M09-G142/EvaluacionV2/
├── automation/
│   ├── run-g142-v2.cjs                            (runner + compuerta de fixture)
│   ├── TC-M09-G142.postman_collection.json        (ejecutor de los eventos M02)
│   ├── TC-M09-G142.precheck.postman_collection.json
│   └── test_g142_v2.py                            (verificador independiente, solo lectura)
└── RESULTADOS/
    └── run-20261010-173402/
        ├── TC-M09-G142_reevaluacion_V2.md         (este informe)
        ├── evidencia.json                         (+ historial_ejecuciones)
        ├── newman-resumen.json
        ├── pytest.xml
        ├── automation_manifest.json               (execution_number 2, SHA-256)
        └── newman/
            └── newman-TC-M09-G142.html
```

No se creó otro RUN, ni artefactos `post-fix`, `retry` o `V3`, ni un informe nuevo. La
carpeta histórica `run-20261010-160823` no existe y no se recreó.

| Seguridad | |
|---|---|
| Contraseñas / JWT / `Authorization` / cookies / `refresh_token` persistidos | **NO** |
| Serial y `access_key` de la cámara | **NO** (redactados por patrón) |
| Credenciales de PostgreSQL | **NO** (llegan por entorno al proceso) |
| Coincidencias de secretos en el RUN | **0** (verificado por grep) |
| Permisos SQL modificados | **NINGUNO** |
| Comandos git de escritura | **NINGUNO** (solo `fetch`, `rev-parse`, `show`, `status`, `branch`, `diff`, `grep`) |

---

## CONCLUSIÓN

El PR #554 funciona, y esta vez se pudo demostrar. Un alta válida de lote POBLACIONAL en un
área con cámara activa y observaciones aptas produjo, sin ninguna intervención manual, la
calibración **19** con `origen_disparo = AUTOMATICO`, `id_usuario = null`, estado EXITOSA,
40 de 40 observaciones válidas, su línea base publicada y el evento RF-10 **50308** firmado
por el usuario de servicio. El cierre del ciclo de ese mismo lote produjo la calibración
**20**, distinta, con el motivo del cierre, su propia línea base vigente y el evento
**50309**. Cada evento disparó exactamente una calibración, y el motivo de cada una la
correlaciona con su evento de M02. `POST /configuracion/calibraciones-vision` se ejecutó
**cero** veces en todo el grupo.

Lo que hizo falta para llegar aquí fue, sobre todo, no dar nada por bueno. DBA informó de
datos preparados pero no pudo verificarlos; QA los validó uno por uno y, lo más importante,
comprobó que **M02 realmente ofrece** el ciclo 11 como asignable, que es lo que en la
ejecución 1 se descubrió demasiado tarde. También se resolvió qué id pide cada API —11 para
`id_ciclo_productiva`, 21 para `fase_destino_id`, y 54 no se envía nunca— y se verificó en
el código que los 42 días de duración no impiden cerrar el mismo día.

Dos cosas que conviene no perder de vista. La primera: la compuerta de cualificación ahora
impone la especie, en lugar de dejar que la colección la adivine por «id más bajo»; con la
heurística anterior el grupo habría podido elegir la especie 82 y volver a estrellarse en
TC-289 por un motivo que nada tiene que ver con el disparo. La segunda: el verificador de
Pytest se reforzó para que compruebe el contrato en vez de describirlo; tal como estaba,
habría dado 10 passed con disparo y sin disparo.

**TC-M09-G142: APROBADO.** Incidencia original **CORREGIDA** por el PR #554, sin incidencia
nueva. El resultado RECHAZADO de la ejecución 1 se conserva íntegro en el historial de este
informe y en `historial_ejecuciones` de la evidencia.
