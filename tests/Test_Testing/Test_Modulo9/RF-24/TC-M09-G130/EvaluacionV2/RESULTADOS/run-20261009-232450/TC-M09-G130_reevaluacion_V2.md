# TC-M09-G130 — SEGUNDA EVALUACIÓN

## DECISIÓN GENERAL

**Grupo:** TC-M09-G130
**Casos:** TC-M09-256 y TC-M09-257
**Requisito:** RF-24 v2.0
**Ambiente decisorio:** TEST
**RUN_ID:** `run-20261009-232450`
**Resultado del grupo:** **APROBADO**

| Caso | Resultado |
|---|---|
| TC-M09-256 | APROBADO |
| TC-M09-257 | APROBADO |

El grupo se declara APROBADO con el Newman oficial **en verde**: 16 requests y 37 assertions,
0 fallidas. No hay ninguna failure que clasificar ni reinterpretar.

## RESUMEN

Se ejecutó un PRECHECK Newman de solo lectura que pasó con 0 failures y autorizó el RUN. A
continuación se ejecutó la colección completa una única vez, con los 2 POST de calibración
planificados, 0 PATCH/PUT/DELETE, 0 reintentos y sin STOP_ALL.

Los dos escenarios de hardware inexistente devuelven ahora el mensaje común que exige el
requisito:

- **TC-M09-256** — dispositivo inexistente en el body (999999) y sensor real en la ruta (6):
  **HTTP 404**, `error_code` `DISPOSITIVO_NO_ENCONTRADO`, mensaje **literalmente igual** al
  común del RF, sin `id_calibracion` y sin tocar el historial del sensor real (total 14 e IDs
  idénticos antes y después).
- **TC-M09-257** — sensor inexistente en la ruta (999999) y dispositivo real en el body (3):
  **HTTP 404**, `error_code` `SENSOR_NO_ENCONTRADO`, mensaje **literalmente igual**, sin
  `id_calibracion`, y el historial del sensor inexistente mantiene idéntico comportamiento
  antes y después del POST.

La comparación de mensajes fue literal, carácter a carácter. No se recortó, adaptó ni
reinterpretó ningún texto después de ver las respuestas.

Durante el PRECHECK se detectó un cambio de contrato en el endpoint auxiliar de historial para
sensores inexistentes: ya no responde 200 con `total 0`, sino 404 `SENSOR_NO_ENCONTRADO`. QA
autorizó expresamente actualizar ese criterio auxiliar, por tratarse de una evolución
deliberada del contrato de seguridad y no de un defecto de G130. **El esperado funcional de los
POST de calibración no fue modificado.** Se detalla en la sección correspondiente.

## BASELINE — PRIMERA EVALUACIÓN

Único baseline histórico: **`run-20261007-085922`**
(`tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/RESULTADOS/run-20261007-085922/TC-M09-G130_resultado.md`),
consultado solo como referencia y no modificado.

| Caso | Resultado | HTTP | `error_code` | Persistencia | Mensaje |
|---|---|---|---|---|---|
| TC-M09-256 | RECHAZADO | 404 correcto | `DISPOSITIVO_NO_ENCONTRADO` | Ninguna | **Incorrecto** |
| TC-M09-257 | RECHAZADO | 404 correcto | `SENSOR_NO_ENCONTRADO` | Ninguna | **Incorrecto** |
| **Grupo** | **RECHAZADO** | | | | |

La lógica de rechazo ya era correcta. Mensajes obtenidos entonces:

```text
TC-M09-256: No existe un dispositivo IoT con ID 999999.
TC-M09-257: No existe un sensor con ID 999999.
```

Mensaje común exigido por RF-24 v2.0 para ambos casos:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

El único incumplimiento era el **mensaje**, y es exactamente lo que esta reevaluación vuelve a
medir. En la primera evaluación el historial del sensor inexistente respondía 200 con `total 0`.

## ENTORNO

| | |
|---|---|
| Ambiente decisorio | TEST |
| Backend TEST | `https://api.inmero.co/back-sigab-test` |
| Herramientas | **API - Postman / Newman** (las que especifica la matriz) |
| Reportes Newman HTML persistentes | **1** |
| BD | **no utilizada** — no forma parte del oráculo de G130 |
| DEV | no utilizado — 0 peticiones |

## RAMA

```text
rama:    qa/juan-esteban-segunda-evaluacion-rf24-v2.0
commit:  1e3a3848f23ac514339abbf37a34c26bbfbd0ff8
HEAD vs origin/test: 0 / 0 (sin divergencia)

git status --short, antes y después del RUN:
  ?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/EvaluacionV2/
  ?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0/EvaluacionV2/
  ?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76-v2.0/EvaluacionV2/
  ?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77-v2.0/EvaluacionV2/
  ?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G80-v2.0/EvaluacionV2/
```

No se ejecutó ninguna operación git de escritura: sin `add`, `commit`, `push`, `merge`,
`rebase`, `reset`, `clean`, `stash`, `switch` ni `checkout`. Los `RESULTADOS/` de la primera
evaluación quedan sin diferencias. Las otras entradas corresponden a grupos ya cerrados.

## ACTOR

| | |
|---|---|
| Rol esperado y confirmado | **Ingeniero de Campo** |
| Usuario | `ingeniero@pecuaria.co` |
| `id_usuario` | **4** — descubierto dinámicamente desde `GET /usuarios/me`, no hardcodeado |
| `estado_cuenta` | Activo |
| Autenticación | **PASS** (HTTP 200) |
| Permiso de calibraciones | recurso 12, acción 1 → **confirmado** (47 permisos en total) |
| Credencial | [REDACTED] — solo en memoria de proceso |

**Los 2 POST `/calibrar` los ejecutó exclusivamente el Ingeniero de Campo.**

Administrador auxiliar: `administador.dev@gmail.com`, login HTTP 200, rol Administrador. El
**alternativo no fue necesario** (el principal autenticó al primer intento, así que no se probó
`admin.dev@gmail.com` ni ninguna otra contraseña). Su único uso fue un GET de confirmación
adicional del dispositivo inexistente. **No ejecutó ningún POST `/calibrar`.**

### Propiedad de las sesiones

**La colección Newman es dueña de sus sesiones.** Hace sus propios `POST /sesiones/` y publica
los tokens en `{{ing_session}}` y `{{admin_session}}`. El runner **no inicia sesión antes de
Newman y no inyecta ningún token**: solo pasa configuración. El motivo es la política de
**sesión única por usuario** de TEST. La única autenticación del runner ocurre en el modo de
cierre, **después** del RUN y exclusivamente para GET.

## PREFLIGHT VALIDADO

Se ejecutó un **PRECHECK Newman de solo lectura** antes del RUN, con la colección filtrada en
memoria sin los dos `POST /calibrar`. No escribió nada de negocio, no generó HTML, no creó la
carpeta de resultados y no dejó archivos: su salida fue solo por consola.

```text
PRECHECK_G130

Ingeniero:                        PASS
Permisos:                         PASS
Fixture real:                     PASS
Dispositivo 999999 inexistente:   PASS
Sensor 999999 inexistente:        PASS
GET historial sensor 999999:      PASS — contrato actual 404 SENSOR_NO_ENCONTRADO
Rango:                            PASS

Failures:                         0
POST /calibrar:                   0

AUTORIZAR_RUN:                    SÍ
```

Newman del PRECHECK: 14 requests y 31 assertions, 0 fallidas. No se persiste ningún reporte de
esta validación.

## FIXTURE REAL

**Fixture oficial del caso reutilizado, sin cambios.**

| | Valor observado |
|---|---|
| `id_sensor` real | 6 — `Sensor temperatura alevinera-01`, `es_activo = true`, pertenece al dispositivo 3 |
| categoría | TEMPERATURA |
| `id_dispositivo_iot` real | 3 — `IOT-ALE01-HLA-003`, `es_activo = true` (HTTP 200) |
| asociación vigente | sensor 6 ↔ dispositivo 3 ↔ **área 3**, `tiene_estado = true`, `fecha_finalizacion = null` |
| `id_infraestructura` | 3 |
| rango vigente TEMPERATURA | **0 – 45** |
| `valor_referencia` | **22.5000** — estrictamente interior al rango |
| `modo_calibracion` | `SENSOR` |

En cada caso el request es válido en todo lo demás: la **única invalidez intencional** es el ID
inexistente que corresponde a ese escenario.

## VERIFICACIÓN DE IDs INEXISTENTES

No se creó, modificó ni eliminó ningún dato para obtener estos IDs, y **no se alteró ninguna
secuencia**. Ambos IDs siguen siendo 999999: no hizo falta sustituirlos.

### Dispositivo 999999

El paquete advierte que un 404 del Ingeniero no demuestra inexistencia por sí solo, porque su
alcance podría ocultar recursos. En el estado actual de TEST eso ya no ocurre, y la
acreditación se obtiene con un **par discriminante del mismo actor**:

```text
Ingeniero → GET /configuracion/dispositivos-iot/3        HTTP 200   (dispositivo REAL visible)
Ingeniero → GET /configuracion/dispositivos-iot/999999   HTTP 404   DISPOSITIVO_NO_ENCONTRADO
```

Como el mismo actor lee el dispositivo real con 200 y el 999999 con 404, su 404 **no se
confunde con falta de alcance**: acredita inexistencia.

Confirmación adicional con el Administrador, prevista por el paquete:

```text
Administrador → GET /configuracion/dispositivos-iot/999999   HTTP 404   DISPOSITIVO_NO_ENCONTRADO
```

Esta confirmación **corrobora pero ya no discrimina**: en el estado actual de TEST el
Administrador responde 404 incluso sobre el dispositivo real 3 y sobre el sensor 6, de modo que
su 404 por sí solo no distinguiría inexistencia de falta de alcance. Es la situación inversa a
la de la primera evaluación, y por eso la acreditación principal recae hoy en el Ingeniero.

**Inexistencia confirmada: SÍ.**

### Sensor 999999

```text
Ingeniero → GET /configuracion/sensores/999999/calibraciones   HTTP 404   SENSOR_NO_ENCONTRADO
```

**Inexistencia confirmada: SÍ.** El comportamiento cambió respecto a la primera evaluación y se
documenta en la sección siguiente.

## CAMBIO DE CONTRATO DEL ENDPOINT DE HISTORIAL

**Primera evaluación:**

```text
GET /configuracion/sensores/999999/calibraciones
→ HTTP 200
→ total 0
→ items []
```

**Segunda evaluación:**

```text
GET /configuracion/sensores/999999/calibraciones
→ HTTP 404
→ error_code SENSOR_NO_ENCONTRADO
```

**Clasificación: CAMBIO INTENCIONAL DEL CONTRATO DE SEGURIDAD — NO DEFECTO DE G130.**

**Motivo:** el historial de calibraciones ahora valida previamente la existencia y el alcance
del sensor para evitar la exposición de recursos ajenos mediante IDOR. Se verificó que el
comportamiento es estable y general, no un fallo puntual ni específico de 999999:

```text
sensor 999999  → 404 SENSOR_NO_ENCONTRADO   (3 intentos consecutivos, idéntico)
sensor 888888  → 404 SENSOR_NO_ENCONTRADO
sensor 1234567 → 404 SENSOR_NO_ENCONTRADO
sensor 999998  → 404 SENSOR_NO_ENCONTRADO
sensor 6 (real)→ 200, total 14              (contraste: el sensor real sí se lee)
```

**Conclusión:** QA adapta el criterio auxiliar de TC-M09-257 al contrato vigente. El criterio
de inexistencia del sensor pasa a ser `HTTP 404 SENSOR_NO_ENCONTRADO`, y la no persistencia se
acredita por otras dos vías, descritas en el caso. **El esperado funcional del POST de
calibración no fue modificado:** sigue exigiendo HTTP 404 y el mensaje común exacto del RF.

> El criterio auxiliar de historial de TC-M09-257 fue actualizado por QA para alinearlo con el
> contrato de seguridad vigente del endpoint. El esperado funcional del POST de calibración no
> fue modificado.

## TC-M09-256

**Escenario:** dispositivo inexistente en el body, sensor real en la ruta. La única invalidez
intencional es el dispositivo.

### Historial PRE del sensor real

```text
GET /configuracion/sensores/6/calibraciones -> HTTP 200
total: 14 | ids: [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
```

### Request

`POST /configuracion/sensores/6/calibrar`, ejecutado por el Ingeniero de Campo:

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 999999,
  "id_infraestructura": 3,
  "valor_referencia": 22.5000,
  "observaciones": "QA TC-M09-256",
  "fecha_calibracion": "2026-10-10T04:24:54.994Z"
}
```

Ejecutado exactamente una vez, sin reintentos.

### Respuesta

```text
HTTP esperado:   404
HTTP obtenido:   404
error_code:      DISPOSITIVO_NO_ENCONTRADO
id_calibracion:  ausente en la respuesta
```

**Mensaje esperado y obtenido, idénticos:**

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

Comparación literal: coincide carácter a carácter. Ya es el mensaje **común** del RF y no el
mensaje propio de la entidad «dispositivo» con su ID interpolado.

### Historial POST del sensor real

```text
total: 14 | ids: [30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
```

Sin IDs nuevos, total idéntico y los catorce registros conservando valor, fecha, usuario y
observaciones.

### Resultado

**APROBADO** — oráculo completo en verde: dispositivo inexistente acreditado, sensor de ruta
válido, única invalidez el dispositivo, HTTP 404, mensaje literal, sin `id_calibracion`, total
e IDs sin cambios, historial intacto y las 8 assertions funcionales del caso en PASS.

## TC-M09-257

**Escenario:** sensor inexistente en la ruta, dispositivo real en el body. La única invalidez
intencional es el sensor.

### Historial PRE del sensor inexistente

```text
GET /configuracion/sensores/999999/calibraciones -> HTTP 404
error_code: SENSOR_NO_ENCONTRADO
```

Criterio auxiliar según el contrato vigente, autorizado por QA (ver «CAMBIO DE CONTRATO DEL
ENDPOINT DE HISTORIAL»).

### Request

`POST /configuracion/sensores/999999/calibrar`, ejecutado por el Ingeniero de Campo:

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 22.5000,
  "observaciones": "QA TC-M09-257",
  "fecha_calibracion": "2026-10-10T04:24:55.354Z"
}
```

Ejecutado exactamente una vez, sin reintentos.

### Respuesta

```text
HTTP esperado:   404
HTTP obtenido:   404
error_code:      SENSOR_NO_ENCONTRADO
id_calibracion:  ausente en la respuesta
```

**Mensaje esperado y obtenido, idénticos:**

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

### Historial POST del sensor inexistente

```text
GET /configuracion/sensores/999999/calibraciones -> HTTP 404
error_code: SENSOR_NO_ENCONTRADO
```

Comportamiento **idéntico** al PRE: el POST rechazado no cambió nada.

### No persistencia

Como el endpoint de historial ya no entrega `total = 0` para sensores inexistentes, la no
persistencia se acredita por las vías que indicó QA:

| Vía | Comprobación | Resultado |
|---|---|---|
| A | la respuesta del POST no contiene `id_calibracion` | **PASS** |
| B | los GET PRE y POST siguen respondiendo 404 `SENSOR_NO_ENCONTRADO` | **PASS** |
| C | diagnóstico BD complementario | **no utilizado** — la matriz no exige BD y la API resolvió el oráculo sin ambigüedad |

### Resultado

**APROBADO** — oráculo completo en verde: sensor inexistente acreditado, dispositivo del body
válido, única invalidez el sensor, HTTP 404, mensaje literal, sin `id_calibracion`, el historial
mantiene el contrato y su comportamiento PRE/POST es idéntico, con las 8 assertions funcionales
del caso en PASS.

## CUADRO COMPARATIVO DE LOS DOS CASOS

| Criterio | TC-M09-256 | TC-M09-257 |
|---|---|---|
| Escenario | Dispositivo inexistente | Sensor inexistente |
| Sensor en ruta | 6 | 999999 |
| Dispositivo body | 999999 | 3 |
| Infraestructura | 3 | 3 |
| Valor | 22.5000 | 22.5000 |
| ID inexistente confirmado | **SÍ** | **SÍ** |
| HTTP esperado | 404 | 404 |
| HTTP obtenido | **404** | **404** |
| `error_code` | DISPOSITIVO_NO_ENCONTRADO | SENSOR_NO_ENCONTRADO |
| Mensaje exacto | **SÍ** | **SÍ** |
| `id_calibracion` creado | **NO** | **NO** |
| Historial PRE | total 14, ids `[30, 29, 28, 21, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]` | HTTP 404 `SENSOR_NO_ENCONTRADO` (contrato vigente) |
| Historial POST | total 14, mismos ids | HTTP 404 `SENSOR_NO_ENCONTRADO` (idéntico al PRE) |
| IDs PRE = POST | **SÍ** | N/A — el contrato vigente no expone lista; comportamiento PRE/POST idéntico |
| Persistencia nueva | **NO** | **NO** |
| Assertions funcionales | 8 ejecutadas, 0 fallidas | 8 ejecutadas, 0 fallidas |
| Resultado | **APROBADO** | **APROBADO** |

## VERIFICACIÓN DE NO PERSISTENCIA

Verificación final de **solo lectura**, hecha después del RUN, sin SQL y con **0 escrituras**:

| Comprobación | Resultado |
|---|---|
| TC-256 — historial del sensor 6 permanece igual | **SÍ** — HTTP 200, total **14**, ids idénticos al PRE |
| TC-257 — `GET /sensores/999999/calibraciones` mantiene el contrato | **SÍ** — HTTP 404 `SENSOR_NO_ENCONTRADO` |
| Fixture sensor 6 sin cambios | **SÍ** |
| Dispositivo 3 sin cambios | **SÍ** — HTTP 200, `es_activo = true` |
| Dispositivo 999999 sigue inexistente | **SÍ** — HTTP 404 |
| Asociación del sensor 6 al área 3 sin cambios | **SÍ** — única asociación vigente: dispositivo 3 / área 3 |
| Rango TEMPERATURA sin cambios | **SÍ** — 0 – 45 |
| Calibraciones atribuibles a los casos (`QA TC-M09-256` / `QA TC-M09-257`) | **ninguna** |
| Ninguna calibración creada por estos casos | **SÍ** |
| POST extra ejecutados | **0** |

No se borró nada después: ambos POST eran rechazos esperados y no crearon datos, de modo que no
hubo nada que limpiar. No se usó sandbox.

## RESULTADO NEWMAN

```text
RUN_ID:                        run-20261009-232450
HTML:                          newman/newman-TC-M09-G130.html
Colección ejecutada:           16 de 16 items

Iterations:                    1
Requests:                      16
Failed requests:               0
Assertions:                    37
Failures:                      0

POST /calibrar planificados:   2
POST /calibrar ejecutados:     2
PATCH:                         0
PUT:                           0
DELETE:                        0
Reintentos:                    0
STOP_ALL:                      NO

Cantidad de HTML Newman:       1
```

El Newman oficial termina **limpio**: 0 requests fallidos y 0 assertions fallidas. No hay
failures de ningún tipo —ni de producto, ni de automatización, ni de ambiente— y por tanto no
hay nada que clasificar ni reinterpretar para aprobar el grupo. Las assertions funcionales no
se modificaron: el `message` se comparó con **igualdad literal**.

## COMPARACIÓN PRIMERA VS SEGUNDA EVALUACIÓN

| Caso | Primera evaluación | Segunda evaluación | Cambio |
|---|---|---|---|
| TC-M09-256 | RECHAZADO | **APROBADO** | RECHAZADO → APROBADO |
| TC-M09-257 | RECHAZADO | **APROBADO** | RECHAZADO → APROBADO |
| G130 | RECHAZADO | **APROBADO** | RECHAZADO → APROBADO |

| Elemento | Primera evaluación | Segunda evaluación | Interpretación |
|---|---|---|---|
| GET historial sensor 999999 | 200, total 0 | **404 SENSOR_NO_ENCONTRADO** | Cambio contractual de seguridad aceptado |
| POST TC-256 HTTP | 404 | **404** | Sin cambio, correcto |
| POST TC-256 mensaje | Incorrecto | **Correcto (literal)** | Corregido |
| POST TC-257 HTTP | 404 | **404** | Sin cambio, correcto |
| POST TC-257 mensaje | Incorrecto | **Correcto (literal)** | Corregido |
| Persistencia TC-256 | Ninguna | **Ninguna** | Sin cambio, correcto |
| Persistencia TC-257 | Ninguna | **Ninguna** | Sin cambio, correcto |

| Caso | Dimensión | Primera | Segunda |
|---|---|---|---|
| TC-256 | HTTP | 404 correcto | **404 correcto** |
| TC-256 | No persistencia | Correcta | **Correcta** |
| TC-256 | Mensaje | Incorrecto | **Correcto (literal)** |
| TC-257 | HTTP | 404 correcto | **404 correcto** |
| TC-257 | No persistencia | Correcta | **Correcta** |
| TC-257 | Mensaje | Incorrecto | **Correcto (literal)** |

`error_code`: TC-256 sigue devolviendo `DISPOSITIVO_NO_ENCONTRADO` y TC-257
`SENSOR_NO_ENCONTRADO`. La matriz no exige cambiarlos: se registran, y el criterio principal es
HTTP + mensaje + no persistencia.

### MENSAJES ANTES VS AHORA

**TC-M09-256**

ANTES:

```text
No existe un dispositivo IoT con ID 999999.
```

AHORA:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

ESPERADO:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

----------------------------------------

**TC-M09-257**

ANTES:

```text
No existe un sensor con ID 999999.
```

AHORA:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

ESPERADO:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

**CAUSA DEL RECHAZO ANTERIOR: CORREGIDA** en ambos casos.

### Causa raíz determinada en esta corrida

No se copió la causa raíz de la primera evaluación: se volvió a determinar con la evidencia
actual. De las cuatro hipótesis del paquete aplica la **D**:

> **Ambos mensajes comunes son correctos.** La causa anterior —el flujo emitía el mensaje propio
> de cada entidad, heredado de la validación genérica de dispositivo y de sensor, en lugar del
> mensaje común de referencia que RF-24 v2.0 define para este flujo alterno— está corregida y
> desplegada en TEST.

No aplica la A (HTTP correcto con mensaje específico antiguo), ni la B (desfase entre DEV y
TEST), ni la C (cambio en HTTP o en persistencia): el HTTP, el `error_code` y la ausencia de
persistencia se mantienen correctos y el mensaje ya es el del requisito.

## CONTRASTE DEV

No aplica. TEST pasó completamente: ambos casos devolvieron 404 con el mensaje común exacto y
sin persistencia, con el Newman oficial en verde. No hubo 5xx, ni mensaje anterior conservado,
ni indicio de desfase de despliegue. **0 peticiones contra DEV.**

## DIAGNÓSTICO BD

**BD utilizada: NO.** La matriz de G130 no exige base de datos y la API resolvió ambos oráculos
sin ambigüedad: los IDs inexistentes quedaron acreditados por GET —con el par discriminante del
Ingeniero para el dispositivo y el 404 del contrato vigente para el sensor— y la no persistencia
quedó acreditada por la respuesta de cada POST y por los GET PRE/POST. **No se abrió ninguna
conexión** y no se ejecutó ninguna sentencia.

Las credenciales de solo lectura que entregó QA no se utilizaron. La contraseña de BD **no
aparece como literal en ningún artefacto**: el saneado la cubre únicamente si se entrega por
variable de entorno, de modo que no queda persistida ni en el runner ni en la evidencia.

## EVIDENCIAS

Estructura final:

```text
TC-M09-G130/EvaluacionV2/
├── automation/
│   └── run-g130-v2.cjs                   runner único (modos precheck / run / close)
├── TC-M09-G130.postman_collection.json    copia de la colección funcional
└── RESULTADOS/
    └── run-20261009-232450/
        ├── TC-M09-G130_reevaluacion_V2.md  este informe
        ├── evidencia.json                  evidencia consolidada
        ├── automation_manifest.json        ruta, función y SHA-256 de cada artefacto
        └── newman/
            └── newman-TC-M09-G130.html     único reporte Newman persistente
```

Un solo HTML de Newman. **No existe ninguna copia de `automation/` dentro de `RESULTADOS/`.**
Toda la evidencia vive en un único `evidencia.json`.

`evidencia.json` contiene: RUN_ID, git antes y después, ambiente, el actor y la propiedad de las
sesiones, permisos, fixture real con su rango, la verificación de los dos IDs inexistentes con
su acreditación, y para cada caso el historial PRE, el request enviado, la respuesta cruda con
`error_code` e `id_calibracion`, la comparación literal del mensaje, el historial POST, el
oráculo campo por campo y las assertions funcionales con su detalle; más el resumen de Newman,
la verificación final de solo lectura, el contraste DEV, el diagnóstico BD, la comparación
contra la primera evaluación, la causa raíz y el escaneo de seguridad.

### Automatización

```text
EvaluacionV2/automation/run-g130-v2.cjs
    Runner único, con tres modos internos: precheck (Newman de solo lectura, sin HTML ni
    archivos), run (RUN oficial con los 2 POST y el único HTML) y close (oráculo por caso,
    verificación final de solo lectura y consolidación de evidencia). No inyecta tokens a
    Newman y no ejecuta PATCH, PUT ni DELETE.

EvaluacionV2/TC-M09-G130.postman_collection.json
    Copia de la colección funcional de la primera evaluación.
```

Reutilizados en solo lectura, sin modificar:

```text
TC-M09-G130/TC-M09-G130.postman_collection.json   colección funcional original
TC-M09-G130/run-newman.cjs                        runner del baseline; NO se usa en esta
                                                  reevaluación. Se registra por trazabilidad.
```

### Equivalencia de la colección, verificada automáticamente

```text
items funcionales byte-idénticos: TODOS (10 de 10)
  Login Ingeniero · Identidad Ingeniero · Permisos Ingeniero · Login Administrador auxiliar
  Fixture sensor real del dispositivo · Fixture rango de la categoría
  256 Historial PRE · 256 POST calibrar · 256 Historial POST · 257 POST calibrar

POST /calibrar: 2 -> 2      PATCH/PUT/DELETE: 0      items: 15 -> 16
```

Los cambios son de **infraestructura** y de **criterio auxiliar autorizado**, y ninguno toca el
oráculo funcional:

1. **Actor de lectura.** `Fixture dispositivo real`, `Fixture asociación vigente` y
   `Confirmar dispositivo inexistente` pasan de `{{admin_session}}` a `{{ing_session}}`, porque
   hoy el Administrador responde 404 incluso sobre el dispositivo real 3 y el sensor 6, mientras
   el Ingeniero discrimina existencia. Se verificó que los dos items de fixture son idénticos al
   original **salvo el header**, y que el de inexistencia conserva URL, método y body.
2. **Confirmación adicional del Administrador.** Se añadió un GET con `{{admin_session}}` sobre
   el dispositivo inexistente, tal como contempla el paquete, que solo registra.
3. **Criterio auxiliar del historial del sensor inexistente**, actualizado por autorización
   expresa de QA al contrato vigente `404 SENSOR_NO_ENCONTRADO`, en los items
   `Confirmar sensor inexistente (historial PRE)` y
   `257 Historial POST del sensor inexistente`. Conservan URL, método y body.

**Se mantuvieron sin cambios** los dos casos, los IDs inexistentes, las URLs, los bodies, el
orden, los esperados de los POST, la cantidad de POST y las assertions funcionales de HTTP 404,
mensaje común exacto, ausencia de `id_calibracion` y no persistencia, incluida la inmutabilidad
del historial del sensor real en TC-256.

### Seguridad

Ninguna contraseña aparece en el informe, en `evidencia.json`, en el HTML de Newman, en
`automation_manifest.json`, en el runner, en la colección ni en Git: se usaron solo en memoria
de proceso. El reporte Newman se generó con `omitHeaders`, sin datos de environment ni de
globals, omitiendo las variables sensibles (`ing_secret`, `admin_secret`, `ing_session`,
`admin_session`), y se sanitizó después de generarse.

El escaneo final sobre todo `EvaluacionV2/` revisó 5 archivos y no encontró contraseñas de API
ni de BD, JWT, `Authorization` con token real, cookies, `refresh_token` ni cadenas de conexión.
El escaneo cubre tanto las credenciales de API como la de BD entregada por QA.

Una nota de transparencia: una primera pasada del cierre marcó el propio runner por contener la
contraseña de BD como literal —la había escrito para poder saneaarla—, lo que incumple la regla
de no persistirla. Se corrigió tomándola de una variable de entorno, se verificó que ya no
aparece en el código y se repitió el escaneo, que quedó limpio. Ningún POST se reejecutó por
esa corrección.

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

Los dos casos pasan y el Newman oficial está en verde. No se observó ningún defecto del producto
dentro del alcance de TC-M09-256 y TC-M09-257.

**Causa anterior: CORREGIDA.** La incidencia consolidada de la primera evaluación —ambos
escenarios de hardware inexistente devolvían el mensaje específico de cada entidad en lugar del
mensaje común de referencia de RF-24 v2.0— queda **verificada como resuelta**. Se propone su
validación y cierre.

**No se abre incidencia** por el cambio de contrato de
`GET /configuracion/sensores/{id}/calibraciones` a `404 SENSOR_NO_ENCONTRADO`: QA lo aceptó
expresamente como contrato vigente y evolución deliberada del control de alcance frente a IDOR.

Esta ejecución no creó, actualizó ni cerró ningún GitHub Issue ni tarjeta de Taiga: la decisión
es de Juan Esteban.

## CONCLUSIÓN

El grupo **TC-M09-G130 queda APROBADO**, con sus dos casos aprobados, en TEST, que es el
ambiente decisorio. El resultado se obtuvo por ejecución real con Postman/Newman, con el reporte
oficial **sin un solo failure**.

Demostrado empíricamente en TEST, con el Ingeniero de Campo autenticado (`id_usuario 4`), 2 POST
de calibración, 0 reintentos, 0 PATCH/PUT/DELETE y sin STOP_ALL:

- con el **dispositivo 999999 acreditado inexistente** —el Ingeniero lee el dispositivo real 3
  con 200 y el 999999 con 404, par que descarta la falta de alcance— el POST sobre el sensor
  real 6 se rechaza con **HTTP 404** y el **mensaje común literal** del requisito, sin
  `id_calibracion` y dejando el historial del sensor real idéntico (total 14, mismos IDs,
  registros intactos);
- con el **sensor 999999 acreditado inexistente** el POST se rechaza con **HTTP 404** y el mismo
  **mensaje común literal**, sin `id_calibracion`, y el historial de ese sensor mantiene
  idéntico comportamiento antes y después;
- ninguna calibración quedó atribuida a los casos, el fixture real no fue alterado y el rango
  TEMPERATURA sigue en 0 – 45;
- no se creó, modificó ni eliminó ningún dato para preparar los IDs inexistentes, y no se usó
  base de datos.

La causa del rechazo de la primera evaluación está **CORREGIDA**: el cambio frente a aquella
corrida es exclusivamente el contenido de `message`, que ahora es el texto común de referencia
en los dos escenarios. La lógica de detección de hardware inexistente y la no persistencia eran
correctas antes y lo siguen siendo.

Durante el PRECHECK apareció un cambio de contrato en el endpoint auxiliar de historial para
sensores inexistentes —de 200 con `total 0` a 404 `SENSOR_NO_ENCONTRADO`—. No se reinterpretó por
iniciativa propia: se detuvo la ejecución, se consultó, y QA autorizó expresamente actualizar ese
criterio auxiliar por tratarse de una evolución deliberada del contrato de seguridad. El esperado
funcional de los POST no se tocó, de modo que la aprobación del grupo no depende de esa
adaptación sino de que ambos rechazos devuelven hoy el código y el mensaje que exige el
requisito.
