# TC-M09-G132 — SEGUNDA EVALUACIÓN

RF-24 v2.0 · Módulo 9 · Casos **TC-M09-261** y **TC-M09-262**
RUN_ID: **run-20261010-001830** · Ambiente decisorio: **TEST** · Herramientas: **API - Postman / Newman**

---

## DECISIÓN GENERAL

| Elemento | Resultado |
|---|---|
| TC-M09-261 (NaN, Infinity, -Infinity) | **APROBADO** |
| TC-M09-262 (precisión 22.1234) | **APROBADO** |
| **TC-M09-G132** | **APROBADO** |
| Causa del rechazo anterior | **CORREGIDA** |
| INCIDENCIA REQUERIDA | **NO** |

Los tres valores no finitos se tratan ahora como **formato decimal inválido**: responden HTTP 400 con el mensaje literal exigido por la matriz, sin crear ningún registro. El valor de cuatro decimales 22.1234 se persistió sin pérdida ni redondeo, exacto tanto en la respuesta como en el historial recuperado por GET.

---

## RESUMEN

| Caso | Variante | Esperado | Obtenido | Resultado |
|---|---|---|---|---|
| TC-M09-262 | 22.1234 | 2xx + 22.1234 exacto en respuesta e historial | HTTP 201, `id_calibracion` 31, 22.1234 exacto en ambos | **APROBADO** |
| TC-M09-261 | `"NaN"` | 400 + mensaje literal de formato + sin persistencia | HTTP 400, mensaje literal exacto, `VALOR_CALIBRACION_INVALIDO`, 0 registros | **APROBADO** |
| TC-M09-261 | `"Infinity"` | 400 + mensaje literal de formato + sin persistencia | HTTP 400, mensaje literal exacto, `VALOR_CALIBRACION_INVALIDO`, 0 registros | **APROBADO** |
| TC-M09-261 | `"-Infinity"` | 400 + mensaje literal de formato + sin persistencia | HTTP 400, mensaje literal exacto, `VALOR_CALIBRACION_INVALIDO`, 0 registros | **APROBADO** |

Presupuesto respetado: **4 POST** `/calibrar` planificados, **4 ejecutados** (1 exitoso + 3 rechazos), **0 reintentos**, **0** PATCH/PUT/DELETE, **STOP_ALL: NO**.

---

## BASELINE — PRIMERA EVALUACIÓN

Único baseline oficial: **run-20261007-042408**
Fuente: `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G132/RESULTADOS/run-20261007-042408/TC-M09-G132_resultado.md`

| Variante | Resultado | Obtenido entonces | Persistencia |
|---|---|---|---|
| NaN | RECHAZADO | HTTP **500** — «Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.» | NINGUNA |
| Infinity | RECHAZADO | HTTP 400 pero mensaje de **VALOR FUERA DE RANGO** — «El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.» | NINGUNA |
| -Infinity | RECHAZADO | HTTP 400 pero mensaje de **VALOR FUERA DE RANGO** (mismo texto con `-Infinity`) | NINGUNA |
| TC-M09-262 | APROBADO | HTTP 201, `id_calibracion` 17, respuesta 22.1234, historial 22.1234 | id 17 |
| **TC-M09-G132** | **RECHAZADO** | — | — |

El defecto demostrado entonces **no era de persistencia**: ninguno de los tres valores especiales creó calibraciones. El defecto era la **clasificación**: NaN produjo un error interno, e Infinity y -Infinity se clasificaron como fuera de rango cuando los tres debían tratarse como formato decimal inválido.

---

## ENTORNO

| Elemento | Valor |
|---|---|
| Ambiente decisorio | **TEST** |
| Backend | `https://api.inmero.co/back-sigab-test` |
| Contraste DEV | **No utilizado** (0 peticiones) — TEST pasó completamente |
| OpenAPI | `GET /openapi.json` → HTTP 200 |
| BD TEST | **No utilizada**, ninguna conexión abierta, 0 sentencias |
| Prueba local | NO |

---

## RAMA

| Elemento | Valor |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| Commit HEAD | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| Divergencia HEAD…origin/test | `0 0` |
| `git status --short` | solo las siete carpetas `EvaluacionV2/` sin seguimiento (G75, G76, G77, G80, G130, G131, G132) |
| `RESULTADOS/` de la primera evaluación | `(vacío = intacta)` |
| Operaciones git de escritura | **ninguna**: sin `add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `stash`, `switch` ni `checkout` |

---

## ACTOR

| Elemento | Valor |
|---|---|
| Correo | `ingeniero@pecuaria.co` |
| `id_usuario` | **4** (descubierto dinámicamente, no hardcodeado) |
| Rol | Ingeniero de Campo |
| Estado de cuenta | Activo |
| Login | HTTP 200 |
| Permisos recurso 12 | `[1, 2, 3]` (incluye la acción 1 de calibración) · 47 permisos en total |
| Papel | ejecuta los **4** POST `/calibrar` |
| Administrador | **no utilizado**: el Ingeniero resolvió por GET todas las precondiciones, no hizo falta el actor auxiliar de discovery |

**Propiedad de sesiones.** La colección Newman es dueña de su sesión: hace su propio login y publica el token en `{{session_value}}`. El runner **no obtiene ningún token ni lo inyecta**, porque TEST aplica sesión única por usuario. En el cierre el runner se autentica por separado y **solo para GET**.

---

## PREFLIGHT VALIDADO

PRECHECK Newman de **solo lectura** previo al RUN: sin reporter HTML, sin crear `RESULTADOS`, sin dejar archivos, solo consola. Se excluyeron de la colección los **4 POST `/calibrar`** y sus **4 historiales de poscondición** (dependen del `id` que crea su propio POST, por lo que sin POST no son evaluables).

```
PRECHECK_G132

Ingeniero:               PASS
Permisos:                PASS
Fixture:                 PASS
Rango:                   PASS
OpenAPI:                 CONSULTADO
Colección:               PASS
Failures automatización: 0
POST calibrar:           0
AUTORIZAR_RUN:           SÍ
```

Newman del PRECHECK: 13 requests, 0 fallidos, 28 assertions, 0 fallidas.

**Representación verificada antes de enviar nada** (reglas 21 y 22): el PRECHECK no envía los valores especiales; solo comprueba que la colección está construida con exactamente las entradas del caso.

| Variante | `valor_referencia` que se enviará | Tipo JSON |
|---|---|---|
| TC-M09-262 | `22.1234` | number |
| TC-M09-261 NaN | `"NaN"` | string |
| TC-M09-261 Infinity | `"Infinity"` | string |
| TC-M09-261 -Infinity | `"-Infinity"` | string |

Ninguna entrada se convirtió silenciosamente a `null`, `0` ni cadena vacía. El runner aborta si lo detecta. Tampoco se introdujeron 5 o más decimales, notación científica, `null` ni `"abc"`: están fuera del alcance del RF.

### Contrato OpenAPI (diagnóstico, no sustituye a la prueba)

| Elemento | Valor observado |
|---|---|
| `valor_referencia` | `anyOf: [number, string(pattern), string, null]` |
| Patrón de cadena publicado | `^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$` |
| ¿Ese patrón admitiría NaN/Infinity? | **NO** |
| `modo_calibracion` | `{"type":"string","const":"SENSOR"}` |
| `required` del DTO | `["id_dispositivo_iot","id_infraestructura","fecha_calibracion","modo_calibracion"]` |
| Códigos del POST `/calibrar` | `201, 400, 401, 403, 404, 422, 500` |
| Códigos del historial | `200, 401, 403, 404, 422` |

El contrato no expresa explícitamente la detección de valores no finitos; el patrón de cadena publicado no los admitiría. Es un dato diagnóstico: la decisión la dan los POST reales.

---

## FIXTURE

| Elemento | Valor | Verificación |
|---|---|---|
| Sensor | **6** | activo, categoría TEMPERATURA, `id_dispositivo_iot` 3 |
| Dispositivo | **3** (`IOT-ALE01-HLA-003`) | `es_activo: true` |
| Infraestructura / área | **3** | `es_activo: true` |
| Asociación vigente | sensor 6 → dispositivo 3 → área 3 | `tiene_estado: true`, `fecha_finalizacion: null` |
| Rango TEMPERATURA | **0 – 45** | publicado por `GET /configuracion/sensores/rangos-calibracion` |
| 22.1234 dentro del rango | **SÍ** | el rango nunca puede ser el motivo del rechazo de TC-M09-261 |

Fixture reutilizado de la primera evaluación, íntegramente válido. La **única** invalidez de cada variante de TC-M09-261 es el formato del valor de referencia.

---

## TC-M09-262 — PRECISIÓN

**Actor:** Ingeniero · **Endpoint:** `POST /configuracion/sensores/6/calibrar`

Body realmente enviado:

```json
{"modo_calibracion":"SENSOR","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":22.1234,"observaciones":"QA TC-M09-262","fecha_calibracion":"2026-10-10T05:18:35.203Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 2xx | **201** |
| `id_calibracion` | real | **31** |
| Valor en la respuesta | 22.1234 exacto | `22.1234` (number, escala observable 4) → normalizado **`22.1234`** |
| Exactitud de la respuesta | SÍ | **SÍ** |
| Valor en el historial (`GET` del id 31) | 22.1234 exacto | `22.1234` (escala observable 4) → normalizado **`22.1234`** |
| Exactitud del historial | SÍ | **SÍ** |
| Historial PRE / POST | +1 atribuible | **14 → 15**, IDs nuevos `[31]` |
| Registro corresponde al RUN | SÍ | `observaciones = "QA TC-M09-262"`, `id_usuario = 4`, `fecha_calibracion = 2026-10-10T05:18:35.203000Z` |
| Registros históricos previos | intactos | **intactos** (snapshot por id, valor, fecha, usuario y observaciones) |

### Método de comparación decimal

La comparación es **decimal exacta por normalización textual** (signo, ceros a la izquierda, ceros finales). **No** se usó `Number(valor) === 22.1234` como evidencia de precisión, ni ninguna aritmética de punto flotante binario.

Verificación de que la normalización no es permisiva — ninguno de los valores prohibidos por la matriz pasa:

| Candidato | ¿Igual a 22.1234? |
|---|---|
| `22.123` | NO |
| `22.1230` | NO |
| `22.1235` | NO |
| `22.12` | NO |

Escala observable: **4**. Valor exacto: **SÍ**. No hubo redondeo ni pérdida.

Oráculo completo de TC-M09-262: `http_2xx`, `id_calibracion_devuelto`, `respuesta_decimal_exacto`, `registro_recuperado_por_get`, `historial_decimal_exacto`, `persistio_exactamente_una`, `registro_de_este_run`, `historial_previo_intacto`, `assertions_funcionales_todas_pass` → **todos true**.

**Resultado: APROBADO.** La persistencia del id 31 es la **esperada** de un camino exitoso y **no se eliminó**.

---

## TC-M09-261 — NaN

Body realmente enviado:

```json
{"modo_calibracion":"SENSOR","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":"NaN","observaciones":"QA TC-M09-261","fecha_calibracion":"2026-10-10T05:18:35.779Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 400 | **400** |
| Mensaje | `Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada 'NaN'.` | **idéntico, carácter por carácter** |
| Comparación | literal estricta | prohibido `contains`, `startsWith`, regex y equivalencia semántica; se usó igualdad estricta |
| `error_code` | (se registra, no se exige) | `VALOR_CALIBRACION_INVALIDO` |
| Clasificación observada | formato decimal inválido | **formato decimal inválido** |
| `id_calibracion` en la respuesta | ausente | **ausente** |
| Historial total PRE / POST | iguales | **15 / 15** |
| IDs PRE / POST | iguales | iguales (`[31,30,29,28,21,19,18,17,16,15,14,13,12,11,10]`) |
| IDs nuevos | ninguno | **`[]`** |
| Registros históricos | intactos | **intactos** |

**Resultado: APROBADO.** Ejecutado una sola vez, sin reintentos.

---

## TC-M09-261 — Infinity

Body realmente enviado:

```json
{"modo_calibracion":"SENSOR","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":"Infinity","observaciones":"QA TC-M09-261","fecha_calibracion":"2026-10-10T05:18:36.384Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 400 | **400** |
| Mensaje | `Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada 'Infinity'.` | **idéntico, carácter por carácter** |
| `error_code` | (se registra) | `VALOR_CALIBRACION_INVALIDO` |
| Clasificación observada | formato decimal inválido | **formato decimal inválido** — ya **no** se clasifica como fuera de rango |
| `id_calibracion` | ausente | **ausente** |
| Historial total PRE / POST | iguales | **15 / 15** |
| IDs nuevos | ninguno | **`[]`** |
| Registros históricos | intactos | **intactos** |

**Resultado: APROBADO.**

---

## TC-M09-261 — -Infinity

Body realmente enviado:

```json
{"modo_calibracion":"SENSOR","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":"-Infinity","observaciones":"QA TC-M09-261","fecha_calibracion":"2026-10-10T05:18:36.959Z"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 400 | **400** |
| Mensaje | `Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada '-Infinity'.` | **idéntico, carácter por carácter** |
| `error_code` | (se registra) | `VALOR_CALIBRACION_INVALIDO` |
| Clasificación observada | formato decimal inválido | **formato decimal inválido** — ya **no** se clasifica como fuera de rango |
| `id_calibracion` | ausente | **ausente** |
| Historial total PRE / POST | iguales | **15 / 15** |
| IDs nuevos | ninguno | **`[]`** |
| Registros históricos | intactos | **intactos** |

**Resultado: APROBADO.**

TC-M09-261 exige que **las tres** variantes pasen. Las tres pasaron → **TC-M09-261: APROBADO**.

---

## CUADRO COMPARATIVO DE VARIANTES

| Criterio | NaN | Infinity | -Infinity | 22.1234 |
|---|---|---|---|---|
| Tipo | Rechazo | Rechazo | Rechazo | Éxito |
| HTTP esperado | 400 | 400 | 400 | 2xx |
| HTTP obtenido | **400** | **400** | **400** | **201** |
| `error_code` | `VALOR_CALIBRACION_INVALIDO` | `VALOR_CALIBRACION_INVALIDO` | `VALOR_CALIBRACION_INVALIDO` | N/A |
| Mensaje exacto | **SÍ** | **SÍ** | **SÍ** | N/A |
| `id_calibracion` creado | **NO** | **NO** | **NO** | **SÍ (31)** |
| PRE | 15 | 15 | 15 | 14 |
| POST | 15 | 15 | 15 | 15 |
| IDs inválidos sin cambios | **SÍ** | **SÍ** | **SÍ** | N/A |
| Valor almacenado | N/A | N/A | N/A | **22.1234** |
| Exactamente 22.1234 | N/A | N/A | N/A | **SÍ** |
| Resultado | **APROBADO** | **APROBADO** | **APROBADO** | **APROBADO** |

---

## VERIFICACIÓN DE PERSISTENCIA

| Elemento | Esperado | Obtenido |
|---|---|---|
| Calibraciones válidas nuevas | **1** | **1** (`id_calibracion` 31) |
| Calibraciones inválidas nuevas | **0** | **0** |
| IDs creados en este RUN | `[31]` | `[31]` |
| IDs indebidos | ninguno | **ninguno** |
| STOP_ALL | NO | **NO** |

IDs nuevos por variante: TC-M09-262 → `[31]`; NaN → `[]`; Infinity → `[]`; -Infinity → `[]`.

**Correlación:** por `id_calibracion` devuelto, `observaciones`, `id_usuario` y `fecha`. **Nunca** por `total + 1`, para no depender de ausencia de concurrencia.

### Verificación final (solo lectura, después del RUN)

Login nuevo y exclusivamente GET; 0 escrituras, 0 SQL.

| Elemento | Valor |
|---|---|
| `GET /configuracion/sensores/6/calibraciones` | HTTP 200, total **15**, IDs `[31,30,29,28,21,19,18,17,16,15,14,13,12,11,10]` |
| Registro de TC-M09-262 sigue presente | **SÍ** — id 31, `valor_referencia` 22.1234, escala 4, exacto, `observaciones "QA TC-M09-262"`, `id_usuario` 4 |
| Calibraciones con `observaciones = "QA TC-M09-262"` | `[31, 17]` — el **17** es de la primera evaluación |
| Calibraciones con `observaciones = "QA TC-M09-261"` | **ninguna** |
| Asociación vigente del sensor 6 | dispositivo 3 / área 3, sin cambios |
| POST extra ejecutados | **0** |
| Borrados | **ninguno** |

**Nota sobre la calibración 17.** La creó la **primera** evaluación en su TC-M09-262. Sigue existiendo y **no proviene de este RUN**; no se borró, porque este grupo no ejecuta borrados ni SQL de escritura. Si se quiere depurar, es una decisión aparte.

---

## RESULTADO NEWMAN

| Elemento | Valor |
|---|---|
| RUN_ID | `run-20261010-001830` |
| Colección ejecutada | 21 de 21 items, una sola vez |
| Iterations | 1 (0 fallidas) |
| Requests | **21** |
| Failed requests | **0** |
| Assertions | **61** |
| Failures | **0** |
| POST planificados | **4** |
| POST ejecutados | **4** |
| POST exitosos esperados | **1** (obtenidos: 1) |
| POST rechazados esperados | **3** (obtenidos: 3) |
| PATCH / PUT / DELETE | 0 / 0 / 0 |
| Reintentos | **0** |
| STOP_ALL | **NO** |
| HTML | `newman/newman-TC-M09-G132.html` |
| Cantidad HTML | **1** |

Ningún failure fue ocultado ni reinterpretado como problema de automatización: el RUN salió verde porque las cuatro peticiones cumplieron su oráculo.

---

## COMPARACIÓN PRIMERA VS SEGUNDA

| Variante | Primera evaluación | Segunda evaluación | Cambio |
|---|---|---|---|
| NaN | RECHAZADO — HTTP 500 | **APROBADO** — HTTP 400 + mensaje literal | RECHAZADO → APROBADO |
| Infinity | RECHAZADO — mensaje de rango | **APROBADO** — HTTP 400 + mensaje literal | RECHAZADO → APROBADO |
| -Infinity | RECHAZADO — mensaje de rango | **APROBADO** — HTTP 400 + mensaje literal | RECHAZADO → APROBADO |
| TC-M09-262 | APROBADO | **APROBADO** | SIN CAMBIO |
| **G132** | **RECHAZADO** | **APROBADO** | RECHAZADO → APROBADO |

### Detalle

| Dimensión | Primera | Segunda |
|---|---|---|
| NaN HTTP | 500 | **400** |
| NaN mensaje | Error interno | **formato decimal inválido (literal exacto)** |
| Infinity HTTP | 400 | **400** |
| Infinity mensaje | Fuera de rango | **formato decimal inválido (literal exacto)** |
| -Infinity HTTP | 400 | **400** |
| -Infinity mensaje | Fuera de rango | **formato decimal inválido (literal exacto)** |
| Persistencia inválidos | Ninguna | **Ninguna** |
| 22.1234 respuesta | Exacto | **Exacto** |
| 22.1234 historial | Exacto | **Exacto** |

Presupuesto: primera 4 planificados / 4 ejecutados / STOP_ALL NO · segunda **4 / 4 / NO**.

**Causa anterior: CORREGIDA.**

---

## CONTRASTE DEV

**No aplica.** TEST pasó completamente: los tres valores no finitos dieron HTTP 400 con el mensaje literal y la precisión de 22.1234 se conservó. No se envió ninguna petición a DEV (0 peticiones). TEST mantiene la decisión oficial.

---

## DIAGNÓSTICO BD

**No aplica.** La BD no es el oráculo principal y no apareció ninguna discrepancia de persistencia: los historiales PRE/POST por variante fueron consistentes y el valor exacto 22.1234 se verificó por GET del `id_calibracion` devuelto. **No se abrió ninguna conexión** ni se ejecutó ninguna sentencia. La credencial de BD entregada en el paquete no quedó persistida en ningún artefacto.

---

## EVIDENCIAS

```
TC-M09-G132/
└── EvaluacionV2/
    ├── automation/
    │   └── run-g132-v2.cjs
    ├── TC-M09-G132.postman_collection.json
    └── RESULTADOS/
        └── run-20261010-001830/
            ├── TC-M09-G132_reevaluacion_V2.md
            ├── evidencia.json
            ├── automation_manifest.json
            └── newman/
                └── newman-TC-M09-G132.html
```

`evidencia.json` consolida: RUN_ID, git pre/post, ambiente, actor, permisos, fixture, rango, contrato OpenAPI, representación enviada por variante, PRE/request/response/POST de TC-M09-262 y de las tres variantes de TC-M09-261, IDs de calibración, comparaciones literales de mensaje, comparación decimal, resultado Newman, comparación primera/segunda, causa raíz, seguridad y verificación final de solo lectura.

`automation_manifest.json` registra ruta, función y SHA-256 de: el runner, la colección de EvaluacionV2, la colección original y el runner original de la primera evaluación. **No hay `automation/` dentro de `RESULTADOS/`.**

### Seguridad

Escaneo de los 5 archivos de `EvaluacionV2/`: **limpio**. No quedaron persistidos password de API, password de BD, JWT, cabeceras `Authorization`/`Bearer`, cookies, `refresh_token` ni cadenas de conexión. Las contraseñas existieron solo en memoria de proceso. El reporter `htmlextra` se ejecutó con `omitHeaders`, sin environment ni globals y omitiendo las variables sensibles; el HTML se sanitizó después de generarse.

---

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

| Elemento | Valor |
|---|---|
| Causa anterior | **CORREGIDA** |
| Propuesta | **Validar y cerrar** la incidencia previa de TC-M09-261 (valores no finitos no rechazados como formato decimal inválido) |
| Responsable | n/a |
| Causa raíz (redeterminada, no copiada del baseline) | **Hipótesis A** — los tres valores no finitos responden HTTP 400 con el mensaje literal de formato decimal inválido: la detección de `NaN`, `Infinity` y `-Infinity` **antes** de la validación de rango está implementada y desplegada en TEST |

Se descartan las demás hipótesis con evidencia de esta corrida: **B** (NaN → 500) no se reprodujo; **C** (Infinity clasificado como fuera de rango) no se reprodujo; **D** (desfase DEV/TEST) no aplica, porque TEST ya es correcto y no hizo falta contrastar.

---

## CONCLUSIÓN

**TC-M09-G132: APROBADO.**

La corrección anunciada para G132 está efectivamente desplegada en TEST y se comprobó empíricamente, no por lectura del contrato. `NaN`, `Infinity` y `-Infinity` —enviados tal cual, como cadenas, sin conversión silenciosa— se rechazan los tres con HTTP 400 y el **mensaje literal exacto** de formato decimal inválido, con `error_code VALOR_CALIBRACION_INVALIDO`, sin devolver `id_calibracion` y sin alterar el historial del sensor 6 en total, IDs ni contenido de los registros previos. Lo que antes era un error interno en un caso y una clasificación equivocada en dos pasó a ser un rechazo de formato correcto en los tres.

En paralelo, el camino exitoso conserva la precisión: 22.1234 se almacenó y se recuperó con sus cuatro decimales intactos, verificado por comparación decimal exacta y no por igualdad de punto flotante. Al cerrar el RUN existe exactamente **una** calibración nueva atribuible al grupo (id 31, la de TC-M09-262) y **cero** atribuibles a los valores inválidos. Esa calibración se conserva, como exige el paquete.

Newman quedó verde: 21 requests, 0 fallidos, 61 assertions, 0 failures, con un único HTML persistente. No se usó DEV, no se usó la BD, no se ejecutó ningún PATCH/PUT/DELETE, no se borró nada y no se tocó ningún archivo de la primera evaluación.
