# TC-M09-G74-v2.0 — RESULTADO

## DECISIÓN GENERAL

**Grupo:** TC-M09-G74-v2.0
**Caso:** TC-M09-141-v2.0
**Resultado general:** APROBADO

| Caso | Resultado |
|---|---|
| TC-M09-141-v2.0 | APROBADO |

## RESUMEN DEL RESULTADO

El Ingeniero de Campo autenticado registró una calibración sobre el sensor 6 (TEMPERATURA)
del dispositivo IoT 3 (activo) con `valor_referencia = 22.5000`, valor interior al rango
vigente `0.0000 – 45.0000`. El POST oficial devolvió **HTTP 201** y generó
`id_calibracion = 12`, identificador que no existía en el historial PRE (`[11, 10]`) y que
aparece en el historial POST (`[12, 11, 10]`).

Los seis valores funcionales esperados coinciden tanto en la respuesta del POST como en el
registro recuperado del historial: `id_dispositivo_iot = 3`, `id_sensor = 6`,
`id_usuario = 4` (Ingeniero autenticado), `fecha_calibracion` en el mismo instante
enviado, `valor_referencia` equivalente a `22.5000` y `observaciones = QA TC-M09-141-v2.0`.

Se ejecutó **un único POST** y no hubo reintentos. Newman reporta **34 assertions, 0
failures**, cubriendo las 27 verificaciones mínimas exigidas para el grupo.

Se registra una observación técnica relevante que no afecta el resultado del caso: el
contrato desplegado en TEST no declara `modo_calibracion`, y el backend aceptó el campo sin
procesarlo ni devolverlo. El detalle está en OBSERVACIONES.

## ANTECEDENTES

RF-24 v2.0.
CU05 — Gestionar Dispositivos IoT, Flujo D.
Objetivo: registrar una calibración SENSOR válida con un Ingeniero de campo y comprobar que
el registro queda disponible en el historial oficial del sensor.

## ENTORNO

**Ambiente decisorio:** TEST
**Backend:** https://api.inmero.co/back-sigab-test
**Rama QA:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
**RUN_ID:** run-20261007-064935
**Fecha/hora:** 2026-10-07T06:49:35Z (inicio del RUN) — 2026-10-07T06:49:38Z (cierre)

**Carpeta del caso:** `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G74-v2.0/`

Estado del repositorio: rama correcta y `HEAD` alineado con `origin/test` (divergencia
0 / 0). Durante el RUN no se ejecutó ninguna operación de escritura de git y no se modificó
código productivo.

La automatización de v2.0 reside en su propia carpeta `TC-M09-G74-v2.0/`
(`TC-M09-G74-v2.0.postman_collection.json`, `run-newman.cjs`, `README.md`), adaptada antes
de iniciar el RUN y dejada sin commit. La carpeta histórica `TC-M09-G74/` **no fue
modificada**: conserva su colección, su runner, su README y sus resultados previos
exactamente como estaban en el commit, verificado con `git diff` sin diferencias.

## ACTOR / IDENTIDAD TÉCNICA

**Actor:** Ingeniero de campo
**Usuario:** ingeniero@pecuaria.co
**id_usuario:** 4
**Rol confirmado:** Ingeniero de Campo (`GET /usuarios/me`)
**Credencial:** [REDACTED]

Permisos confirmados mediante `GET /sesiones/me/permisos`: lectura de dispositivos
(`11,2`), registro de calibraciones (`12,1`) y consulta de historial (`12,2`).

### Uso de Administrador auxiliar (solo lectura)

En TEST el Ingeniero no tiene dispositivos en su alcance: `GET
/configuracion/dispositivos-iot` devuelve `total 0` incluso con `solo_activos=false`, que es
el valor por defecto del contrato. Por esa razón, para ese actor:

```text
GET /configuracion/dispositivos-iot/3        -> 404 DISPOSITIVO_NO_ENCONTRADO
GET /configuracion/sensores/6/asociaciones   -> 404 SENSOR_NO_ENCONTRADO
```

Se utilizó una sesión de Administrador (`administador.dev@gmail.com`, credencial
[REDACTED]) **exclusivamente** para esos dos GET de reconfirmación del fixture. El primer
administrador (`admin.dev@gmail.com`) no autenticó y no se probaron contraseñas
adicionales.

El Administrador **no ejecutó ninguna escritura**: el login, los permisos, el historial PRE,
el POST de calibración y el historial POST se realizaron con el Ingeniero.

## CONFIGURACIÓN UTILIZADA / FIXTURE

**modo_calibracion:** SENSOR (enviado en el body oficial; ver OBSERVACIONES)
**id_sensor:** 6
**categoría:** TEMPERATURA
**nombre del sensor:** Sensor temperatura alevinera-01
**id_dispositivo_iot:** 3
**serial del dispositivo:** IOT-ALE01-HLA-003
**estado dispositivo:** `es_activo = true`
**id_infraestructura:** 3 (área asociada al sensor, asociación vigente)
**rango TEST:** 0.0000 – 45.0000
**valor_referencia:** 22.5000
**fecha_calibracion:** 2026-10-07T06:49:37.209Z
**observaciones:** QA TC-M09-141-v2.0

Nota de fixture: el `id_infraestructura` propio del dispositivo 3 es `1`. El `3` del caso
corresponde al área asociada al sensor 6, que es la asociación verificada como vigente
(`tiene_estado = true`, `fecha_finalizacion = null`). No se exigió que el área del
dispositivo coincidiera con `id_infraestructura = 3`.

Todos los IDs fueron reconfirmados por GET en esta corrida; no se asumieron válidos por
haber estado vigentes antes.

## TC-M09-141-v2.0 — REGISTRAR CALIBRACIÓN SENSOR VÁLIDA

### Precondiciones verificadas

| Precondición | Resultado |
|---|---|
| Rama `qa/juan-esteban-rf24-v2` correcta | VERIFICADA |
| Sin cambios productivos no autorizados | VERIFICADA |
| Carpeta del caso v2.0 `TC-M09-G74-v2.0/` preparada | VERIFICADA |
| Automatización adaptada a v2.0 antes del RUN | VERIFICADA |
| Backend TEST accesible | VERIFICADA |
| `POST /configuracion/sensores/{id_sensor}/calibrar` desplegado | VERIFICADA |
| `GET /configuracion/sensores/{id_sensor}/calibraciones` desplegado | VERIFICADA |
| Ingeniero autentica | VERIFICADA (HTTP 200) |
| Actor confirmado como Ingeniero de Campo | VERIFICADA |
| `actor_id` obtenido | VERIFICADA (`id_usuario = 4`) |
| Dispositivo 3 existe y está activo | VERIFICADA (GET auxiliar de Administrador) |
| Sensor 6 existe y pertenece al dispositivo 3 | VERIFICADA |
| Sensor 6 corresponde a TEMPERATURA y está activo | VERIFICADA |
| Asociación con infraestructura 3 vigente | VERIFICADA (GET auxiliar de Administrador) |
| 22.5000 dentro del rango permitido | VERIFICADA (0.0000 – 45.0000) |

### Historial PRE

```text
GET /configuracion/sensores/6/calibraciones -> HTTP 200
total: 2
id_calibracion presentes: [11, 10]
```

El `id_calibracion = 12` obtenido después **no** figura en este snapshot.

### Request

POST /configuracion/sensores/6/calibrar

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 22.5000,
  "observaciones": "QA TC-M09-141-v2.0",
  "fecha_calibracion": "2026-10-07T06:49:37.209Z"
}
```

Encabezado `Authorization`: [REDACTED]. No se agregaron `ganancia` ni `offset`, que el caso
oficial no solicita. POST ejecutados: **1**. Reintentos: **0**.

### Respuesta

**HTTP:** 201
**id_calibracion:** 12

```json
{
  "id_calibracion": 12,
  "id_dispositivo_iot": 3,
  "id_sensor": 6,
  "valor_referencia": "22.5000",
  "ganancia": "1.0000",
  "offset": "22.5000",
  "fecha_calibracion": "2026-10-07T06:49:37.209000Z",
  "id_usuario": 4,
  "observaciones": "QA TC-M09-141-v2.0"
}
```

RF-24 v2.0 no fija un código de éxito concreto: se aceptó el 2xx y se registra el 201 real
devuelto por la implementación. `ganancia` y `offset` los derivó el backend (no fueron
enviados) y no forman parte del oráculo del caso.

### Historial POST

```text
GET /configuracion/sensores/6/calibraciones -> HTTP 200
total: 3
id_calibracion presentes: [12, 11, 10]
```

El `id_calibracion = 12` fue localizado por ID en el historial y conserva los seis valores
funcionales esperados. Los registros previos (`11`, `10`) se conservan íntegros.

El contexto de totales (`2 → 3`) se registra como evidencia informativa y no se utilizó
como oráculo, dado que podrían existir calibraciones concurrentes de otros testers.

## RESULTADO DEL ORÁCULO

| Verificación | Esperado | Obtenido | Resultado |
|---|---|---|---|
| HTTP éxito | 2xx | 201 | PASS |
| id_calibracion nuevo | Sí | 12 (ausente en PRE) | PASS |
| id_dispositivo_iot | 3 | 3 | PASS |
| id_sensor | 6 | 6 | PASS |
| id_usuario | Ingeniero autenticado | 4 | PASS |
| fecha_calibracion | Mismo instante enviado | 2026-10-07T06:49:37.209000Z ≡ enviado | PASS |
| valor_referencia | 22.5000 | "22.5000" | PASS |
| observaciones | QA TC-M09-141-v2.0 | QA TC-M09-141-v2.0 | PASS |
| Registro en historial | Presente por ID | Presente (id 12) | PASS |

Comparaciones realizadas semánticamente: la fecha por instante temporal y el valor de
referencia por valor decimal.

## RESULTADO NEWMAN

**Assertions:** 34
**Failures:** 0

Requests ejecutados: 11 — ninguno fallido. Cubre las 27 verificaciones mínimas del grupo:
identidad y rol del actor, los tres permisos, existencia y estado del dispositivo,
pertenencia/estado/categoría del sensor, vigencia de la asociación, rango técnico y valor
interior, historial PRE, código 2xx del POST, los seis valores funcionales de la respuesta,
ausencia del ID en PRE, historial POST y persistencia del registro con sus seis valores.

## EVIDENCIAS

- `newman/newman-TC-M09-141-v2.0.html` — reporte Newman sanitizado
- `TC-M09-141-v2.0.json` — artefacto con fixture efectivo, oráculo recalculado y assertions
- `evidencia/historial_pre.json`
- `evidencia/request_calibracion.json` — body funcional, `Authorization` redactado
- `evidencia/response_calibracion.json`
- `evidencia/historial_post.json`

Auditoría de la carpeta del RUN: no contiene contraseñas, JWT, refresh tokens, cookies ni
valores de `Authorization`.

## OBSERVACIONES

### `modo_calibracion` no existe en el contrato desplegado en TEST

Comprobado empíricamente sobre `GET /openapi.json` de TEST en esta corrida: el request
schema del POST (`RegistrarCalibracionDTO`) declara únicamente

```text
id_dispositivo_iot, id_infraestructura, valor_referencia,
ganancia, offset, fecha_calibracion, observaciones
```

con `required = id_dispositivo_iot, id_infraestructura, fecha_calibracion`. La cadena
`modo_calibracion` no aparece en ninguna parte del spec, y no existe esquema ni enum de
modalidad de calibración.

El body oficial se envió una sola vez incluyendo `modo_calibracion = "SENSOR"`, conforme al
caso. El backend respondió **201** y la respuesta **no devuelve** el campo. Es decir, el
campo fue **aceptado y descartado silenciosamente**: la calibración se registró en la única
modalidad que la implementación soporta.

Consecuencias que conviene declarar con precisión:

1. La cadena funcional del caso (actor → fixture → POST → persistencia → historial) está
   verificada empíricamente y es correcta.
2. La **modalidad SENSOR no queda discriminada** por la implementación desplegada: no hay
   comportamiento distinguible asociado a `modo_calibracion`, porque el contrato no lo
   procesa.
3. Al ignorarse campos no declarados, un cliente podría enviar cualquier valor en
   `modo_calibracion` y obtener el mismo resultado, sin rechazo ni advertencia.

Esta observación proviene exclusivamente del comportamiento desplegado y no de revisión de
código.

### Alcance de dispositivos del Ingeniero en TEST

El Ingeniero (`id_usuario = 4`) no tiene ningún dispositivo en su alcance: `GET
/configuracion/dispositivos-iot` devuelve `total 0` con `solo_activos=false`. Esto hace que
el detalle de dispositivo (RF-21) y el historial de asociaciones (RF-22) respondan 404 para
ese actor, pese a que el dispositivo 3 existe y está activo, el sensor 6 le pertenece y el
propio Ingeniero ya tenía dos calibraciones registradas sobre ese sensor (ids 10 y 11).

Los endpoints de RF-24 (sensores del dispositivo, calibrar, historial de calibraciones) sí
son accesibles para el Ingeniero, por lo que esto no impidió ejecutar el caso, pero obligó a
reconfirmar dos precondiciones con un Administrador de solo lectura.

### Valores derivados por la implementación

El registro persistido quedó con `ganancia = 1.0000` y `offset = 22.5000` sin que el caso
los enviara. Son valores derivados por la implementación; no forman parte del oráculo de
TC-M09-141-v2.0 y no se evaluaron como PASS/FAIL.

## INCIDENCIA

**INCIDENCIA REQUERIDA:** SÍ

Una sola incidencia consolidada para el grupo TC-M09-G74-v2.0. No corresponde a un fallo
del caso ejecutado, que resultó APROBADO, sino a la brecha entre RF-24 v2.0 y el contrato
desplegado.

**Clasificación propuesta (Taiga):** Type = `bug`, Severity = `Normal`, Priority = `Normal`

**Causa raíz:** contrato / implementación incompleta respecto al requisito.

**Descripción:** RF-24 v2.0 define `modo_calibracion` como entrada obligatoria del registro
de calibración, con `SENSOR` entre sus valores. El contrato desplegado en TEST no declara
ese campo en `RegistrarCalibracionDTO` ni en ninguna otra parte de `openapi.json`, y el
endpoint acepta el campo sin procesarlo ni reflejarlo en la respuesta. En consecuencia la
modalidad no es discriminable por ningún cliente y los valores no válidos no se rechazan.

**Punto secundario incluido en la misma incidencia:** el Ingeniero de campo no ve ningún
dispositivo IoT en TEST (`total 0`), lo que provoca 404 en el detalle de dispositivo
(RF-21) y en el historial de asociaciones (RF-22) para un fixture que sí existe y está
activo. Conviene confirmar si el alcance por pertenencia de ese actor en TEST es el
esperado.

No se creó ni actualizó ningún GitHub Issue ni tarjeta de Taiga en esta ejecución.

## CONCLUSIÓN

**TC-M09-141-v2.0 queda APROBADO** sobre evidencia empírica del RUN
`run-20261007-064935` en TEST. El Ingeniero de campo autenticado (`id_usuario = 4`) registró
con un único POST una calibración sobre el sensor 6 (TEMPERATURA, activo, perteneciente al
dispositivo 3 activo y asociado de forma vigente a la infraestructura 3), con un valor
interior al rango oficial. El endpoint devolvió 201 y `id_calibracion = 12`; los seis
valores funcionales esperados son correctos tanto en la respuesta como en el registro
recuperado del historial, y el identificador no existía antes de la escritura. Newman
confirma 34 assertions sin fallos.

La aprobación se limita a lo verificado: la cadena funcional de registro y persistencia de
la calibración. **No** acredita el comportamiento diferenciado de la modalidad
`modo_calibracion = SENSOR`, porque el contrato desplegado en TEST no implementa ese campo y
lo descarta silenciosamente. Ese punto queda como incidencia consolidada para el grupo y
debe resolverse antes de considerar RF-24 v2.0 cubierto en su totalidad.

La automatización del caso quedó adaptada a v2.0 y reutilizable en la carpeta
`TC-M09-G74-v2.0/`, con un único POST por RUN, protección contra sobrescritura de corridas y
sanitización de secretos. La automatización histórica de `TC-M09-G74/` se mantiene intacta.
