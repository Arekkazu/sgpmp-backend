# TC-M09-G131 — SEGUNDA EVALUACIÓN

## DECISIÓN GENERAL

**Grupo:** TC-M09-G131
**Casos:** TC-M09-258, TC-M09-259 y TC-M09-260
**Requisito:** RF-24 v2.0
**Ambiente decisorio:** TEST
**RUN_ID:** `run-20261009-234932`
**Resultado del grupo:** **APROBADO**

| Caso | Variante | Resultado |
|---|---|---|
| TC-M09-258 | Sensor pertenece a otro dispositivo | **APROBADO** |
| TC-M09-259 | `modo_calibracion` ausente | **APROBADO** |
| TC-M09-260 | `modo_calibracion = "OTRO"` | **APROBADO** |
| TC-M09-260 | `modo_calibracion = ""` | **APROBADO** |

Las cuatro variantes se ejecutaron —ninguna quedó pendiente por STOP_ALL— y las cuatro
cumplieron el oráculo de la matriz: **rechazo 4xx y ninguna persistencia**. El Newman oficial
terminó en verde: 26 requests y 74 assertions, 0 fallidas.

## RESUMEN

Se ejecutó un PRECHECK Newman de solo lectura que pasó con 0 failures de automatización y
autorizó el RUN. A continuación se ejecutó la colección completa una única vez, con los 4 POST
planificados, 0 reintentos, 0 PATCH/PUT/DELETE y **sin STOP_ALL**.

Ninguno de los cuatro POST creó una calibración:

| Variante | HTTP | `error_code` | `id_calibracion` | Historial PRE → POST |
|---|---:|---|---|---|
| TC-M09-258 | **422** | `SENSOR_DISPOSITIVO_INVALIDO` | ausente | 2 → 2, IDs `[9, 3]` idénticos |
| TC-M09-259 | **400** | `VAL_ENTRADA` | ausente | 14 → 14, IDs idénticos |
| TC-M09-260 `"OTRO"` | **400** | `VAL_ENTRADA` | ausente | 14 → 14, IDs idénticos |
| TC-M09-260 `""` | **400** | `VAL_ENTRADA` | ausente | 14 → 14, IDs idénticos |

El punto central de la reevaluación era TC-M09-259: en la primera evaluación la ausencia de
`modo_calibracion` fue aceptada con **HTTP 201** y persistió la calibración 16. Ahora el mismo
request —con la clave **completamente ausente**, verificado sobre el body realmente enviado—
se rechaza con **HTTP 400** y no crea nada. En consecuencia las dos variantes de TC-M09-260,
que la primera evaluación no pudo ejecutar, se ejecutaron por primera vez y también fueron
rechazadas.

Los códigos obtenidos (422 en TC-258 y 400 en las tres variantes de discriminador) se registran
como observación. **No se convirtieron en requisito**: RF-24 no fija código ni mensaje exactos
para estos escenarios, y 400 y 422 son ambos PASS mientras haya rechazo 4xx y no persistencia.

## BASELINE — PRIMERA EVALUACIÓN

Único baseline: **`run-20261007-040706`**
(`tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G131/RESULTADOS/run-20261007-040706/TC-M09-G131_resultado.md`),
consultado solo como referencia y no modificado.

| Caso | Variante | Resultado | Detalle |
|---|---|---|---|
| TC-M09-258 | — | **APROBADO** | HTTP 422 `SENSOR_DISPOSITIVO_INVALIDO`; historial del sensor 3 sin cambios |
| TC-M09-259 | — | **RECHAZADO** | **HTTP 201**, `id_calibracion = 16`; historial del sensor 6 pasó de 6 a 7 registros |
| TC-M09-260 | `"OTRO"` | **NO EJECUTADO** | STOP_ALL tras la persistencia indebida de TC-M09-259 |
| TC-M09-260 | `""` | **NO EJECUTADO** | STOP_ALL tras la persistencia indebida de TC-M09-259 |
| **Grupo** | | **RECHAZADO** | |

Presupuesto de la primera evaluación: 4 POST planificados, **2 ejecutados**, STOP_ALL **SÍ**.

Contrato OpenAPI entonces: `RegistrarCalibracionDTO` **no declaraba** `modo_calibracion`, no lo
incluía en `required` y no publicaba su dominio.

## ENTORNO

| | |
|---|---|
| Ambiente decisorio | TEST |
| Backend TEST | `https://api.inmero.co/back-sigab-test` |
| Herramientas | **API - Postman / Newman** (las que especifica la matriz) |
| Reportes Newman HTML persistentes | **1** |
| BD | **no utilizada** — no es herramienta principal de este caso |
| DEV | no utilizado — 0 peticiones |

## RAMA

```text
rama:    qa/juan-esteban-segunda-evaluacion-rf24-v2.0
commit:  1e3a3848f23ac514339abbf37a34c26bbfbd0ff8
HEAD vs origin/test: 0 / 0 (sin divergencia)

git status --short, antes y después del RUN: solo carpetas EvaluacionV2/ sin seguimiento
  ?? .../TC-M09-G130/EvaluacionV2/      ?? .../TC-M09-G131/EvaluacionV2/
  ?? .../TC-M09-G75-v2.0/EvaluacionV2/  ?? .../TC-M09-G76-v2.0/EvaluacionV2/
  ?? .../TC-M09-G77-v2.0/EvaluacionV2/  ?? .../TC-M09-G80-v2.0/EvaluacionV2/
```

No se ejecutó ninguna operación git de escritura: sin `add`, `commit`, `push`, `merge`,
`rebase`, `reset`, `clean`, `stash`, `switch` ni `checkout`. Los `RESULTADOS/` de la primera
evaluación quedan sin diferencias. Las demás entradas corresponden a grupos ya cerrados.

## ACTOR

| | |
|---|---|
| Rol esperado y confirmado | **Ingeniero de Campo** |
| Usuario | `ingeniero@pecuaria.co` |
| `id_usuario` | **4** — obtenido dinámicamente de `GET /usuarios/me`, no hardcodeado |
| `estado_cuenta` | Activo |
| Autenticación | **PASS** (HTTP 200) |
| Permisos recurso 12 | `[1, 2, 3]` → incluye la acción 1 de registrar calibraciones (47 permisos en total) |
| Credencial | [REDACTED] — solo en memoria de proceso |

**Los 4 POST `/calibrar` los ejecutó exclusivamente el Ingeniero de Campo.**

**Administrador: no utilizado.** El Ingeniero resolvió por GET todas las precondiciones de los
dos fixtures, así que no hizo falta el actor auxiliar de lectura. Tampoco se probó ninguna otra
cuenta ni contraseña.

### Propiedad de la sesión

**La colección Newman es dueña de la sesión.** Hace su propio `POST /sesiones/` y publica el
token en `{{session_value}}`. El runner **no obtiene tokens y no los inyecta**: solo pasa
configuración (correo, secreto, IDs de fixture y los cuatro bodies). El motivo es la política
de **sesión única por usuario** de TEST. La única autenticación del runner ocurre en el modo de
cierre, **después** del RUN y exclusivamente para GET.

Esto exigió rehacer la colección, y se explica en «EVIDENCIAS»: la de la primera evaluación era
un único item genérico cuyo body, sensor y **token** inyectaba el runner desde fuera, justo el
patrón que la regla corregida desde G76 prohíbe.

## PREFLIGHT VALIDADO

Se ejecutó un **PRECHECK Newman de solo lectura** antes de cualquier POST, con la colección
filtrada en memoria sin los cuatro `POST /calibrar`. No escribió nada, no generó HTML, no creó
la carpeta de resultados y no dejó archivos: su salida fue solo por consola.

```text
PRECHECK_G131

Ingeniero:                  PASS
Permisos:                   PASS
Fixture TC258:              PASS
Fixture sensor6:            PASS
Rangos:                     PASS
OpenAPI consultado:         PASS

Failures automatización:    0
POST calibrar:              0

AUTORIZAR_RUN:              SÍ
```

Newman del PRECHECK: 22 requests y 66 assertions, 0 fallidas. No se persiste ningún reporte de
esta validación.

## CONTRATO OPENAPI ACTUAL

Observación **diagnóstica** del contrato desplegado en TEST. Por sí sola no decide el
resultado: el objetivo funcional se determina por los POST reales.

```text
GET /openapi.json → HTTP 200

RegistrarCalibracionDTO
  properties: [id_dispositivo_iot, id_infraestructura, valor_referencia, ganancia,
               offset, fecha_calibracion, observaciones, modo_calibracion]
  required  : [id_dispositivo_iot, id_infraestructura, fecha_calibracion, modo_calibracion]

  modo_calibracion declarado : SÍ
  required                   : SÍ
  default                    : (sin default)
  dominio                    : ["SENSOR"]
  definición                 : {"type":"string","const":"SENSOR","title":"Modo Calibracion"}
```

| Observación | Valor |
|---|---|
| Campo presente | **SÍ** |
| `required` | **SÍ** |
| Default automático | **no** — sin default |
| Dominio del endpoint SENSOR | **`const: "SENSOR"`** — este endpoint solo admite `SENSOR` |
| Riesgo de regresión / corrección no desplegada | **NO** |

El contrato coincide con lo que anticipaba el diagnóstico previo: el campo es obligatorio, no
tiene default y el endpoint de calibración de sensores está restringido a `SENSOR`. Existe
además un enum global `ModoCalibracion = ["SENSOR","VISION"]`, pero este DTO fija `const:
"SENSOR"`: el flujo VISION tiene su propio endpoint. **No se añadió ninguna variante
`modo_calibracion = "VISION"` a G131**, ni se consideró un fallo que este endpoint no la acepte.

Si el contrato hubiera seguido mostrando el estado anterior, no se habría cambiado el esperado
funcional: el PRECHECK habría registrado «RIESGO DE REGRESIÓN / CORRECCIÓN NO DESPLEGADA» y
habría autorizado igualmente el RUN, porque G131 debe comprobarlo empíricamente.

## FIXTURES

### TC-M09-258 — sensor de otro dispositivo

| | Valor observado |
|---|---|
| `id_sensor` | **3** — OXIGENO, `es_activo = true` |
| Dispositivo **propietario real** | **1** — `IOT-EST01-HLA-001`, `es_activo = true` |
| Dispositivo enviado en el body | **3** — `IOT-ALE01-HLA-003`, `es_activo = true` |
| Asociación vigente | sensor 3 ↔ dispositivo **1** ↔ área **1**, `tiene_estado = true`, `fecha_finalizacion = null` |
| Área 1 | `es_activo = true` |
| Rango OXIGENO | **0 – 20** |
| `valor_referencia` | **10.0000** — dentro del rango |

La **única invalidez intencional** es la inconsistencia sensor–dispositivo: el sensor pertenece
al dispositivo 1, pero el body envía el dispositivo 3, que también es real y está activo. El
valor y el área no introducen ninguna invalidez previa.

### TC-M09-259 y TC-M09-260 — fixture completamente válido

| | Valor observado |
|---|---|
| `id_sensor` | **6** — TEMPERATURA, `es_activo = true`, pertenece al dispositivo 3 |
| `id_dispositivo_iot` | **3** — `IOT-ALE01-HLA-003`, `es_activo = true` |
| Asociación vigente | sensor 6 ↔ dispositivo 3 ↔ área **3**, `tiene_estado = true`, `fecha_finalizacion = null` |
| Área 3 | `es_activo = true` |
| Rango TEMPERATURA | **0 – 45** |
| `valor_referencia` | **22.5000** — dentro del rango |

Fixture válido en todo. En cada variante la **única invalidez** es `modo_calibracion`: ausente
en TC-259, `"OTRO"` en TC-260-A y `""` en TC-260-B.

### Historial de partida

No se asumió continuidad con la primera evaluación: cada variante tomó su **PRE propio**
inmediatamente antes de su POST.

```text
sensor 3 (TC-258)         PRE: total 2  | ids [9, 3]
sensor 6 (TC-259/260)     PRE: total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
```

La calibración **16**, creada indebidamente por la primera evaluación, **sigue existiendo** en
el historial del sensor 6. Su presencia **no es criterio de este RUN**: solo cuentan los IDs
nuevos surgidos durante esta corrida. No se borró ningún registro.

## TC-M09-258

**Escenario:** el sensor pertenece a otro dispositivo.

### Request

`POST /configuracion/sensores/3/calibrar`, ejecutado por el Ingeniero de Campo:

```json
{"modo_calibracion":"SENSOR","id_dispositivo_iot":3,"id_infraestructura":1,"valor_referencia":10.0000,"observaciones":"QA TC-M09-258","fecha_calibracion":"2026-10-10T04:49:37.968Z"}
```

Ejecutado exactamente una vez, sin reintentos.

### Respuesta

```text
HTTP esperado:   4xx (RF-24 no fija un código concreto)
HTTP obtenido:   422   → dentro de 4xx
error_code:      SENSOR_DISPOSITIVO_INVALIDO
message:         El sensor 3 no pertenece al dispositivo 3.
id_calibracion:  ausente en la respuesta
```

El `error_code` y el mensaje se registran como observación; no se exigen.

### Historial PRE → POST (sensor 3)

```text
PRE : total 2 | ids [9, 3]
POST: total 2 | ids [9, 3]
```

Sin IDs nuevos, total idéntico y los dos registros conservando valor, fecha, usuario y
observaciones.

### Resultado

**APROBADO** — 4xx y sin persistencia, con las 8 assertions funcionales del caso en PASS.

## TC-M09-259

**Escenario:** `modo_calibracion` ausente. Es el caso que la primera evaluación rechazó.

### Request

`POST /configuracion/sensores/6/calibrar`, ejecutado por el Ingeniero de Campo:

```json
{"id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":22.5000,"observaciones":"QA TC-M09-259","fecha_calibracion":"2026-10-10T04:49:38.557Z"}
```

**La clave `modo_calibracion` está completamente ausente:** no aparece con valor, ni con
`null`, ni vacía. Se verificó sobre el **texto del body realmente enviado**, no sobre la
plantilla:

```text
clave modo_calibracion presente en el body enviado: false
```

El runner además aborta por diseño si el body de esta variante llegara a contener la clave.
Ejecutado exactamente una vez, sin reintentos.

### Respuesta

```text
HTTP esperado:   4xx (RF-24 no fija un código concreto)
HTTP obtenido:   400   → dentro de 4xx
error_code:      VAL_ENTRADA
message:         Errores de validacion en la solicitud
id_calibracion:  ausente en la respuesta
```

### Historial PRE → POST (sensor 6)

```text
PRE : total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
POST: total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
```

Sin IDs nuevos, total idéntico y los catorce registros intactos. **STOP_ALL no se activó**, de
modo que las variantes de TC-M09-260 pudieron ejecutarse.

### Resultado

**APROBADO** — clave totalmente ausente, 4xx, sin `id_calibracion`, sin persistencia e
historial idéntico, con las 8 assertions funcionales del caso en PASS.

## TC-M09-260 — OTRO

**Escenario:** `modo_calibracion = "OTRO"` (valor fuera del dominio). **Primera ejecución
real:** la primera evaluación nunca llegó a enviarlo.

### Request

`POST /configuracion/sensores/6/calibrar`, con **PRE propio** tomado justo antes:

```json
{"modo_calibracion":"OTRO","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":22.5000,"observaciones":"QA TC-M09-260","fecha_calibracion":"2026-10-10T04:49:39.117Z"}
```

### Respuesta

```text
HTTP esperado:   4xx
HTTP obtenido:   400   → dentro de 4xx
error_code:      VAL_ENTRADA
message:         Errores de validacion en la solicitud
id_calibracion:  ausente en la respuesta
```

### Historial PRE → POST (sensor 6)

```text
PRE : total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
POST: total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
```

### Resultado

**APROBADO** — 4xx y sin persistencia, con las 8 assertions funcionales en PASS. No se activó
STOP_ALL, de modo que la variante vacía pudo ejecutarse.

## TC-M09-260 — VACÍO

**Escenario:** `modo_calibracion = ""`. **Primera ejecución real.**

### Request

`POST /configuracion/sensores/6/calibrar`, con **PRE propio** tomado justo antes:

```json
{"modo_calibracion":"","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":22.5000,"observaciones":"QA TC-M09-260","fecha_calibracion":"2026-10-10T04:49:39.678Z"}
```

### Respuesta

```text
HTTP esperado:   4xx
HTTP obtenido:   400   → dentro de 4xx
error_code:      VAL_ENTRADA
message:         Errores de validacion en la solicitud
id_calibracion:  ausente en la respuesta
```

### Historial PRE → POST (sensor 6)

```text
PRE : total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
POST: total 14 | ids [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
```

### Resultado

**APROBADO** — 4xx y sin persistencia, con las 8 assertions funcionales en PASS.

**Resultado de TC-M09-260: APROBADO**, porque **ambas** variantes pasaron.

## CUADRO COMPARATIVO DE LOS CASOS

| Criterio | TC-258 | TC-259 | TC-260 "OTRO" | TC-260 "" |
|---|---|---|---|---|
| Invalidez | Sensor/dispositivo | Campo ausente | Valor fuera dominio | Valor vacío |
| Sensor | 3 | 6 | 6 | 6 |
| Dispositivo | 3 | 3 | 3 | 3 |
| Área | 1 | 3 | 3 | 3 |
| Valor | 10.0000 | 22.5000 | 22.5000 | 22.5000 |
| HTTP esperado | 4xx | 4xx | 4xx | 4xx |
| HTTP obtenido | **422** | **400** | **400** | **400** |
| `error_code` | SENSOR_DISPOSITIVO_INVALIDO | VAL_ENTRADA | VAL_ENTRADA | VAL_ENTRADA |
| `id_calibracion` | ausente | ausente | ausente | ausente |
| Total PRE | 2 | 14 | 14 | 14 |
| Total POST | 2 | 14 | 14 | 14 |
| IDs iguales | **SÍ** | **SÍ** | **SÍ** | **SÍ** |
| Persistencia | **NO** | **NO** | **NO** | **NO** |
| Assertions funcionales | 8 / 0 fallidas | 8 / 0 fallidas | 8 / 0 fallidas | 8 / 0 fallidas |
| Resultado | **APROBADO** | **APROBADO** | **APROBADO** | **APROBADO** |

Nota sobre los códigos: 422 en TC-258 y 400 en las tres variantes del discriminador. Ambos son
PASS. **No se rechaza por usar 400 en vez de 422 ni al contrario**: el criterio es rechazo 4xx
más ausencia de persistencia.

## VERIFICACIÓN DE NO PERSISTENCIA

Por variante, con PRE propio y reconciliación inmediata tras cada POST:

| Variante | Total PRE → POST | IDs nuevos | Históricos alterados |
|---|---|---|---|
| TC-M09-258 (sensor 3) | 2 → 2 | ninguno | NO |
| TC-M09-259 (sensor 6) | 14 → 14 | ninguno | NO |
| TC-M09-260 "OTRO" (sensor 6) | 14 → 14 | ninguno | NO |
| TC-M09-260 "" (sensor 6) | 14 → 14 | ninguno | NO |

**Persistencia inesperada total: 0 nuevas calibraciones.** STOP_ALL no se activó en ningún
momento.

Verificación final de **solo lectura**, después del RUN, sin SQL y con **0 escrituras**:

| Comprobación | Resultado |
|---|---|
| Historial del sensor 3 sin cambios atribuibles a TC-258 | **SÍ** — HTTP 200, total 2, ids `[9, 3]`, igual al PRE |
| Historial del sensor 6 sin IDs nuevos de TC-259 / TC-260 | **SÍ** — HTTP 200, total 14, mismos ids |
| Asociación vigente del sensor 3 | sin cambios — dispositivo 1 / área 1 |
| Asociación vigente del sensor 6 | sin cambios — dispositivo 3 / área 3 |
| Calibraciones con las observaciones del grupo en el sensor 3 | **ninguna** |
| Calibraciones con las observaciones del grupo en el sensor 6 | **id 16** — creada por la **primera** evaluación, no por este RUN |
| POST extra ejecutados | **0** |

Sobre la calibración 16: lleva `observaciones = "QA TC-M09-259"` porque la creó la primera
evaluación. Se registra explícitamente para que no se confunda con un ID nuevo. **No surgió en
este RUN** —los IDs nuevos por variante son `[]` en las cuatro— y **no se borró**: no se ejecutó
ningún DELETE ni SQL.

## RESULTADO NEWMAN

```text
RUN_ID:                run-20261009-234932
HTML:                  newman/newman-TC-M09-G131.html
Colección ejecutada:   26 de 26 items

Iterations:            1
Requests:              26
Failed requests:       0
Assertions:            74
Failures:              0

POST planificados:     4
POST ejecutados:       4
PATCH / PUT / DELETE:  0
Reintentos:            0
STOP_ALL:              NO

Cantidad HTML:         1
```

El Newman oficial termina **limpio**. Las assertions funcionales se mantuvieron en el criterio
de la matriz —rango 4xx, ausencia de `id_calibracion`, total e IDs de historial PRE/POST
iguales e integridad de los registros previos— sin exigir 400 ni 422 exactos ni mensaje exacto.
Los failures de automatización se eliminaron antes mediante el PRECHECK, no reinterpretando
nada después.

## COMPARACIÓN PRIMERA VS SEGUNDA

| Caso | Primera evaluación | Segunda evaluación | Cambio |
|---|---|---|---|
| TC-M09-258 | APROBADO | **APROBADO** | SIN CAMBIO |
| TC-M09-259 | RECHAZADO | **APROBADO** | RECHAZADO → APROBADO |
| TC-M09-260 "OTRO" | NO EJECUTADO | **APROBADO** | NO EJECUTADO → APROBADO |
| TC-M09-260 "" | NO EJECUTADO | **APROBADO** | NO EJECUTADO → APROBADO |
| **G131** | **RECHAZADO** | **APROBADO** | RECHAZADO → APROBADO |

| Dimensión | Primera evaluación | Segunda evaluación |
|---|---|---|
| TC-258 rechazo 4xx | PASS — HTTP 422 | **PASS — HTTP 422** |
| TC-258 no persistencia | PASS | **PASS** |
| TC-259 campo ausente | **HTTP 201** | **HTTP 400 — 4xx correcto** |
| TC-259 persistencia | **ID 16 creado** | **sin persistencia — IDs PRE = POST** |
| TC-260 "OTRO" | No ejecutado | **HTTP 400, sin persistencia** |
| TC-260 "" | No ejecutado | **HTTP 400, sin persistencia** |

Presupuesto: la primera evaluación ejecutó **2 de 4** POST con STOP_ALL **SÍ**; esta segunda
ejecutó **4 de 4** con STOP_ALL **NO**.

### Contrato OpenAPI: primera vs segunda

| Contrato | Primera evaluación | Segunda evaluación |
|---|---|---|
| `modo_calibracion` declarado | **NO** | **SÍ** |
| `required` | **NO** | **SÍ** |
| Default automático | no verificable / comportamiento equivalente a opcional | **(sin default)** |
| Dominio publicado | **no** | **`["SENSOR"]`** (`const: "SENSOR"`) |
| Ausencia rechazada | **NO — respondió 201** | **SÍ — HTTP 400** |

**CAUSA DEL RECHAZO ANTERIOR: CORREGIDA.**

### Causa raíz determinada en esta corrida

No se copió la causa raíz de la primera evaluación: se volvió a determinar con la evidencia
actual. De las cuatro hipótesis del paquete aplica la **A**:

> **Todo rechazado correctamente.** El defecto anterior —`modo_calibracion` no era obligatorio
> y su ausencia se aceptaba y persistía— está corregido y desplegado en TEST. El contrato
> publica el campo como `required`, sin default, y el endpoint lo restringe a `SENSOR`; las tres
> variantes del discriminador se rechazan con 4xx y ninguna persiste.

No aplica la B (TC-259 volvería a aceptar la ausencia), ni la C (validación de dominio
incompleta: `"OTRO"` y `""` también se rechazan), ni la D (desfase entre DEV y TEST: TEST pasa).

## CONTRASTE DEV

No aplica. TEST pasó completamente: las cuatro variantes fueron rechazadas con 4xx y sin
persistencia, con el Newman oficial en verde. No hubo 5xx, ni comportamiento funcional
inesperado, ni contradicción con el contrato actual. **0 peticiones contra DEV.**

## DIAGNÓSTICO BD

**BD no utilizada.** La matriz no la exige y no apareció ninguna duda de persistencia: la API
entregó historiales PRE/POST consistentes por variante, ninguna respuesta devolvió
`id_calibracion` y los IDs nuevos fueron `[]` en las cuatro. **No se abrió ninguna conexión** y
no se ejecutó ninguna sentencia. Las credenciales de solo lectura entregadas por QA no se
usaron, y su contraseña no aparece como literal en ningún artefacto.

## EVIDENCIAS

Estructura final:

```text
TC-M09-G131/EvaluacionV2/
├── automation/
│   └── run-g131-v2.cjs                    runner único (modos precheck / run / close)
├── TC-M09-G131.postman_collection.json     colección de EvaluacionV2
└── RESULTADOS/
    └── run-20261009-234932/
        ├── TC-M09-G131_reevaluacion_V2.md  este informe
        ├── evidencia.json                  evidencia consolidada
        ├── automation_manifest.json        ruta, función y SHA-256 de cada artefacto
        └── newman/
            └── newman-TC-M09-G131.html     único reporte Newman persistente
```

Un solo HTML de Newman. **No existe ninguna copia de `automation/` dentro de `RESULTADOS/`.**
Toda la evidencia vive en un único `evidencia.json`.

`evidencia.json` contiene: RUN_ID, git antes y después, ambiente, actor y propiedad de la
sesión, permisos, contrato OpenAPI observado, los dos fixtures verificados con sus rangos, y
para cada variante el historial PRE, el **texto del body realmente enviado**, la comprobación de
si la clave `modo_calibracion` estaba presente, la respuesta cruda con `error_code`, `message` e
`id_calibracion`, el historial POST, los IDs nuevos, la integridad de los históricos, el oráculo
campo por campo y las assertions funcionales con su detalle; más el resumen de Newman con
STOP_ALL, la verificación final de solo lectura, el contraste DEV, el diagnóstico BD, la
comparación contra la primera evaluación, la causa raíz y el escaneo de seguridad.

### Automatización y colección

```text
EvaluacionV2/automation/run-g131-v2.cjs
    Runner único, con tres modos internos: precheck (Newman de solo lectura, sin HTML ni
    archivos), run (RUN oficial con los 4 POST y el único HTML) y close (oráculo por variante,
    verificación final de solo lectura y consolidación de evidencia). No obtiene ni inyecta
    tokens y no ejecuta PATCH, PUT ni DELETE.

EvaluacionV2/TC-M09-G131.postman_collection.json
    Colección de EvaluacionV2: 26 items.
```

Reutilizados en solo lectura, sin modificar:

```text
TC-M09-G131/TC-M09-G131.postman_collection.json   colección de la primera evaluación
TC-M09-G131/run-newman.cjs                        runner del baseline; NO se usa en esta
                                                  reevaluación. Se registra por trazabilidad.
```

**Por qué la colección se rehízo, y qué se conservó.** La de la primera evaluación era un
**único item genérico** (`Calibrar — variante seleccionada por el runner`) cuyo body, sensor y
**token** (`Bearer {{token}}`) inyectaba el runner desde fuera, invocando Newman cuatro veces.
Ese patrón es exactamente el que la regla de sesiones corregida desde G76 prohíbe. La colección
de EvaluacionV2 despliega por tanto las **cuatro variantes como items propios** y pasa a ser
dueña de su sesión.

Se conservó del plan original, sin cambios:

```text
los cuatro casos y su orden   TC-258 · TC-259 · TC-260 "OTRO" · TC-260 ""
los cuatro bodies             mismos campos, mismos valores y literales de cuatro decimales
                              (10.0000 y 22.5000), con la clave ausente en TC-259
las URLs                      POST /configuracion/sensores/{sensor}/calibrar
                              GET  /configuracion/sensores/{sensor}/calibraciones
el criterio de rechazo        pm.expect(pm.response.code).to.be.within(400, 499)
                              presente en los 4 items de POST, igual que en el original
las verificaciones de no persistencia   total e IDs de historial PRE/POST por variante,
                              con PRE propio y STOP_ALL si alguna persistiera
```

Verificación automática: 4 `POST /calibrar`, el criterio 4xx presente en los 4, 0
PATCH/PUT/DELETE, ningún `{{token}}` inyectado desde fuera y un único login dentro de la
colección.

### Seguridad

Ninguna contraseña aparece en el informe, en `evidencia.json`, en el HTML de Newman, en
`automation_manifest.json`, en el runner, en la colección ni en Git: se usaron solo en memoria
de proceso. El reporte Newman se generó con `omitHeaders`, sin datos de environment ni de
globals, omitiendo las variables sensibles (`ing_secret`, `session_value`), y se sanitizó
después de generarse. El escaneo final sobre todo `EvaluacionV2/` revisó 5 archivos y no
encontró contraseñas de API ni de BD, JWT, `Authorization` con token real, cookies,
`refresh_token` ni cadenas de conexión.

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

Las cuatro variantes pasan, el Newman oficial está en verde y la persistencia inesperada es 0.
No se observó ningún defecto del producto dentro del alcance de TC-M09-258, TC-M09-259 y
TC-M09-260.

**Causa anterior: CORREGIDA.** La incidencia de la primera evaluación —«RF-24 v2.0 permite crear
una calibración SENSOR sin `modo_calibracion`», *Important / High*, asignada a Desarrollo— queda
**verificada como resuelta**: el campo es obligatorio en el contrato desplegado, su ausencia se
rechaza con HTTP 400 y no persiste nada. Se propone su validación y cierre.

Queda además cubierto el punto que la primera evaluación dejó abierto: las variantes `"OTRO"` y
`""` de TC-M09-260, que entonces no se ejecutaron por STOP_ALL, se ejecutaron ahora y también
son rechazadas, de modo que la validación de dominio del discriminador está completa.

Esta ejecución no creó, actualizó ni cerró ningún GitHub Issue ni tarjeta de Taiga: la decisión
es de Juan Esteban.

## CONCLUSIÓN

El grupo **TC-M09-G131 queda APROBADO**, con sus tres casos aprobados, en TEST, que es el
ambiente decisorio. El resultado se obtuvo por ejecución real con Postman/Newman, con el reporte
oficial **sin un solo failure**.

Demostrado empíricamente en TEST, con el Ingeniero de Campo autenticado (`id_usuario 4`), 4 POST
de calibración, 0 reintentos, 0 PATCH/PUT/DELETE y sin STOP_ALL:

- **TC-M09-258 sigue funcionando:** con el sensor 3 —cuyo propietario real es el dispositivo 1—
  y el body enviando el dispositivo 3, la petición se rechaza con **HTTP 422**
  (`SENSOR_DISPOSITIVO_INVALIDO`) y el historial del sensor 3 queda idéntico;
- **`modo_calibracion` es ahora realmente obligatorio:** con la clave **completamente ausente**
  del body enviado —verificado sobre el texto real de la petición— la respuesta es **HTTP 400**
  (`VAL_ENTRADA`), sin `id_calibracion`, y el historial del sensor 6 no cambia. Donde la primera
  evaluación obtuvo 201 y persistió la calibración 16, ahora hay rechazo y cero persistencia;
- **`"OTRO"` es rechazado:** HTTP 400, sin persistencia. Es la primera vez que esta variante se
  ejecuta de verdad;
- **`""` es rechazado:** HTTP 400, sin persistencia. También primera ejecución real;
- **ninguno de los cuatro POST creó una calibración:** los IDs nuevos son `[]` en las cuatro
  variantes, los totales e IDs de historial coinciden PRE y POST, y los registros previos
  quedaron intactos.

La causa del rechazo anterior está **CORREGIDA**, y la causa raíz determinada con la evidencia
de esta corrida es que la obligatoriedad y el dominio de `modo_calibracion` ya están
implementados y desplegados: el contrato publica el campo como `required`, sin default, y el
endpoint de calibración de sensores lo restringe a `SENSOR`.

Los códigos observados no se convirtieron en requisito: 422 para la inconsistencia
sensor–dispositivo y 400 para las tres variantes del discriminador son igualmente válidos,
porque el oráculo de la matriz es rechazo 4xx más ausencia de persistencia. Tampoco se añadió
ninguna variante `VISION`: ese flujo tiene su propio endpoint y queda fuera del alcance de G131.

Por último, la calibración 16 que la primera evaluación creó indebidamente sigue en el historial
del sensor 6. Se deja constancia de que **no proviene de este RUN** y de que **no se eliminó**:
este grupo no ejecuta borrados ni SQL, y su limpieza, si QA la considera necesaria, es una
decisión aparte.
