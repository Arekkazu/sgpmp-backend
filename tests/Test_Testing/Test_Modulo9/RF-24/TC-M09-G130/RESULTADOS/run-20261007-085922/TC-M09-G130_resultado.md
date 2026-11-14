# TC-M09-G130 — Resultado

## Decisión general

**Resultado del grupo:** RECHAZADO

| Caso | Resultado | Motivo |
|---|---|---|
| TC-M09-256 | RECHAZADO | El endpoint devolvió HTTP 404 y no persistió nada, pero el mensaje fue `No existe un dispositivo IoT con ID 999999.` en lugar del mensaje común de referencia que define RF-24 v2.0. |
| TC-M09-257 | RECHAZADO | El endpoint devolvió HTTP 404 y el historial del sensor inexistente siguió en total 0, pero el mensaje fue `No existe un sensor con ID 999999.` en lugar del mensaje común del RF. |

El oráculo se alcanzó en ambos casos: la validación de hardware inexistente **funciona** en lo
esencial —rechaza con el código correcto y no crea calibraciones—, pero el texto del error no es
el que exige el requisito. Conforme al criterio del paquete, un mensaje específico por entidad no
es PASS aunque el HTTP sea 404.

## Entorno

**Ambiente decisorio:** TEST
**Backend:** https://api.inmero.co/back-sigab-test
**Prueba local:** NO
**Rama:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
**RUN_ID:** run-20261007-085922
**Carpeta:** tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/

No se utilizó DEV: TEST expone la funcionalidad y permitió ejecutar ambos casos completos, de
modo que no había indicio de desfase de despliegue que justificara el contraste.

### Preflight OpenAPI

```text
POST /configuracion/sensores/{id_sensor}/calibrar       201, 400, 401, 403, 404, 422, 500
GET  /configuracion/sensores/{id_sensor}/calibraciones  200, 401, 403, 422
GET  /configuracion/dispositivos-iot/{id_dispositivo_iot} 200, 401, 403, 404, 422
```

El endpoint de calibración declara el 404 que ambos casos esperan. Los códigos se registran como
contexto: el oráculo del RF no se ajustó a OpenAPI.

## Actor

**Ingeniero de Campo** — `ingeniero@pecuaria.co` · `id_usuario = 4` · rol `Ingeniero de Campo` ·
cuenta `Activo` · credencial [REDACTED]
Permiso de registro de calibraciones confirmado (recurso 12, acción 1). El `id_usuario` se
descubrió dinámicamente, no se hardcodeó.

**Los dos POST del caso los ejecutó el Ingeniero.**

Se usó además un Administrador (`administador.dev@gmail.com`, credencial [REDACTED]) únicamente
para GET de precondición. Se intentó primero `admin.dev@gmail.com`, que no autenticó (HTTP 401),
y se continuó con el secundario sin probar otras contraseñas.

Conviene explicar por qué el Administrador es necesario justo aquí: para el Ingeniero, incluso un
dispositivo **real** responde 404 por alcance de finca, de modo que su 404 no distinguiría
"no existe" de "fuera de mi alcance". El Administrador ve todos los dispositivos, así que su 404
sí acredita inexistencia.

## Fixture

**IDs efectivos usados** (fixture oficial del caso, validado por GET en este RUN):

```text
sensor real        = 6    (TEMPERATURA, activo, perteneciente al dispositivo 3)
dispositivo real   = 3    (activo)
infraestructura    = 3    (asociación vigente)
valor_referencia   = 22.5000   (dentro del rango 0.0000 – 45.0000)
```

**IDs inexistentes, verificados por GET antes de los POST:**

| Uso | ID | Verificación | Resultado |
|---|---:|---|---|
| dispositivo inexistente | 999999 | `GET /configuracion/dispositivos-iot/999999` con Administrador | HTTP 404, `DISPOSITIVO_NO_ENCONTRADO` |
| sensor inexistente | 999999 | `GET /configuracion/sensores/999999/calibraciones` con Ingeniero | HTTP 200, `total 0`, `items []` |

El sensor inexistente se comportó exactamente como anticipa la matriz. No se creó ni eliminó
ningún dato para conseguir estos IDs.

## TC-M09-256

**Escenario:** dispositivo inexistente en el body, sensor real en la ruta. La única invalidez
intencional es el dispositivo.

### Request

```text
POST /configuracion/sensores/6/calibrar
```

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 999999,
  "id_infraestructura": 3,
  "valor_referencia": 22.5,
  "observaciones": "QA TC-M09-256",
  "fecha_calibracion": "2026-10-07T08:59:25.927Z"
}
```

### Esperado vs obtenido

| Verificación | Esperado | Obtenido | Resultado |
|---|---|---|---|
| ID de dispositivo confirmado inexistente | Sí | 999999 → 404 con Administrador | PASS |
| actor | Ingeniero de Campo | Ingeniero de Campo (id 4) | PASS |
| sensor de ruta válido | Sí | sensor 6, activo | PASS |
| HTTP | 404 | 404 | PASS |
| mensaje | mensaje común de referencia del RF | `No existe un dispositivo IoT con ID 999999.` | **FAIL** |
| `id_calibracion` en la respuesta | ausente | ausente | PASS |
| mismos IDs en el historial | Sí | `[15, 14, 13, 12, 11, 10]` → idéntico | PASS |
| mismo total en el historial | Sí | 6 → 6 | PASS |

**error_code obtenido:** `DISPOSITIVO_NO_ENCONTRADO`

**Mensaje esperado:**
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.

**Mensaje obtenido:**
No existe un dispositivo IoT con ID 999999.

**Diferencia exacta:** el backend emite el mensaje propio de la entidad "dispositivo", con su ID
interpolado, en lugar del mensaje común de referencia. No comparte ningún fragmento con el texto
exigido: falta el prefijo `Error de referencia:`, falta la mención conjunta de sensor o
dispositivo y falta la frase sobre no poder registrar una calibración sobre hardware inexistente.

### Historial PRE/POST del sensor real

```text
PRE : total 6 | ids [15, 14, 13, 12, 11, 10]
POST: total 6 | ids [15, 14, 13, 12, 11, 10]
```

Ninguna calibración creada. No hubo contaminación, de modo que no se activó STOP_ALL y el caso
siguiente pudo ejecutarse.

### Decisión

**RECHAZADO** — siete de las ocho verificaciones pasan; falla la del mensaje, y basta para
rechazar.

## TC-M09-257

**Escenario:** sensor inexistente en la ruta, dispositivo real en el body. La única invalidez
intencional es el sensor.

### Request

```text
POST /configuracion/sensores/999999/calibrar
```

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 22.5,
  "observaciones": "QA TC-M09-257",
  "fecha_calibracion": "2026-10-07T08:59:26.474Z"
}
```

### Esperado vs obtenido

| Verificación | Esperado | Obtenido | Resultado |
|---|---|---|---|
| ID de sensor confirmado inexistente | Sí | 999999 → `total 0`, `items []` | PASS |
| actor | Ingeniero de Campo | Ingeniero de Campo (id 4) | PASS |
| dispositivo del body válido | Sí | dispositivo 3, activo | PASS |
| HTTP | 404 | 404 | PASS |
| mensaje | mensaje común de referencia del RF | `No existe un sensor con ID 999999.` | **FAIL** |
| `id_calibracion` en la respuesta | ausente | ausente | PASS |
| `GET /sensores/999999/calibraciones` | `total = 0` | `total 0`, `items []` | PASS |

**error_code obtenido:** `SENSOR_NO_ENCONTRADO`

**Mensaje esperado:**
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.

**Mensaje obtenido:**
No existe un sensor con ID 999999.

**Diferencia exacta:** igual que en TC-M09-256, pero con la entidad "sensor". Es el mensaje propio
de la entidad en lugar del mensaje común del flujo alterno.

### Historial del sensor inexistente

```text
PRE : total 0 | items []
POST: total 0 | items []
```

El POST rechazado no creó nada: el historial del sensor inexistente sigue vacío.

### Decisión

**RECHAZADO** — seis de las siete verificaciones pasan; falla la del mensaje.

## Resultado Newman

**POST planificados:** 2
**POST ejecutados:** 2
**STOP_ALL:** NO
**Assertions:** 37
**Failures:** 2

Los 2 fallos son exactamente las dos comparaciones de mensaje:

```text
1. 5. TC-M09-256 — message coincide exactamente con el mensaje comun del RF
2. 5. TC-M09-257 — message coincide exactamente con el mensaje comun del RF
```

Ninguna otra assertion falló: identidad y permisos del actor, fixture real completo,
acreditación de los IDs inexistentes, los códigos HTTP 404, la ausencia de `id_calibracion`, la
inmutabilidad del historial del sensor real y el `total 0` del sensor inexistente pasaron todas.

## Incidencia

**INCIDENCIA REQUERIDA:** SÍ
**Grupo responsable:** Desarrollo
**Grupo de prueba:** TC-M09-G130
**Casos afectados:** ambos (TC-M09-256 y TC-M09-257)
**Resultado:** RECHAZADO

**Motivo:**
Ambos escenarios de hardware inexistente devuelven HTTP 404 correctamente y sin persistencia,
pero con el mensaje específico de cada entidad en lugar del mensaje común de referencia que
define RF-24 v2.0 para este flujo alterno.

**Esperado:**
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.

**Obtenido:**

```text
TC-M09-256 (error_code DISPOSITIVO_NO_ENCONTRADO): No existe un dispositivo IoT con ID 999999.
TC-M09-257 (error_code SENSOR_NO_ENCONTRADO):      No existe un sensor con ID 999999.
```

**Causa raíz:**
La validación de existencia de hardware en el registro de calibración emite el mensaje propio de
cada entidad, heredado de la validación genérica de dispositivo y de sensor, y no el mensaje
común que RF-24 v2.0 define para la referencia a hardware inexistente. No es un fallo de
validación ni de integridad: el código HTTP es el correcto, el `error_code` es coherente con la
entidad y ninguno de los dos intentos crea una calibración.

Se asigna a **Desarrollo** porque la evidencia señala la respuesta de la capa de aplicación: el
endpoint detecta correctamente la referencia inválida y la rechaza, pero no emite el texto del
requisito. No se asigna a **DBA**: no hay indicio de migración, schema, constraint ni dato
estructural implicado — la detección de inexistencia funciona y el 404 llega. No se asigna a
**AIoT**, que no interviene en este flujo. No se usa **Por determinar**, porque la causa es
distinguible con la evidencia obtenida.

**Type:** bug
**Severity:** Normal
**Priority:** Normal

Se propone Normal porque el comportamiento de seguridad e integridad es correcto —no se calibra
hardware inexistente y no hay persistencia indebida— y el incumplimiento se limita al texto que
recibe el cliente.

**Incidencia consolidada:** una sola para el grupo. Las dos manifestaciones comparten la misma
causa raíz: el mensaje común del RF no está implementado en la validación de referencia. No se
abren tickets separados.

**Evidencia:**

```text
tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/RESULTADOS/run-20261007-085922/
  evidencia.json          consolida git, OpenAPI, actor, fixture, IDs inexistentes con su
                          verificación, PRE/request/response/POST de cada caso, oráculos,
                          presupuesto de POST y revisión de secretos
  newman.html             reporte sanitizado del flujo completo
  TC-M09-G130_resultado.md  este informe
```

## Conclusión

**TC-M09-G130 queda RECHAZADO**, con ambos casos rechazados, sobre evidencia empírica
exclusivamente de TEST.

Lo que quedó demostrado y conviene reconocer: RF-24 **rechaza efectivamente** las referencias a
hardware inexistente. Con un request válido en todo lo demás, el dispositivo inexistente produjo
HTTP 404 sin tocar el historial del sensor real, y el sensor inexistente produjo HTTP 404
dejando su historial en `total 0`. No se creó ninguna calibración sobre hardware inexistente, y
los `error_code` devueltos son coherentes con la entidad que falta.

Lo que **no** se cumple es el mensaje: RF-24 v2.0 define un texto común de referencia para este
flujo alterno, y el backend responde con el mensaje particular de cada entidad. El paquete
anticipaba exactamente estos dos textos como no aceptables, de modo que no se reinterpretan como
válidos después de observarlos: un 404 con mensaje incorrecto es RECHAZADO.

El grupo no se aprueba por coincidencia parcial, y tampoco se rechazó por revisión de código: la
decisión proviene de la ejecución real de los dos POST en TEST. Para reevaluarlo basta alinear el
mensaje de la validación de referencia con el requisito; según esta corrida, la lógica de
detección y la no persistencia no requieren cambios.
