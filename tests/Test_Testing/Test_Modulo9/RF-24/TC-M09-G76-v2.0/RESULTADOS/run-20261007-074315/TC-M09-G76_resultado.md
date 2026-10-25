# TC-M09-G76-v2.0 — RESULTADO

## DECISIÓN GENERAL

**Grupo:** TC-M09-G76-v2.0
**Resultado:** RECHAZADO

| Caso | Resultado |
|---|---|
| TC-M09-146-v2.0 | RECHAZADO |
| TC-M09-147-v2.0 | RECHAZADO |

## RESUMEN DEL RESULTADO

Los dos POST de calibración planificados se ejecutaron, sin reintentos y sin STOP_ALL. **No
fue necesario ningún PATCH de preparación**: en TEST ya existían 65 dispositivos inactivos y
el dispositivo 47 de la matriz resultó utilizable, así que no se desactivó nada.

Los dos casos aciertan en todo salvo en el mensaje:

- el código HTTP es el exigido en ambos (**422** en TC-146 y **400** en TC-147);
- ninguno de los dos rechazos creó calibraciones;
- el total y los IDs del historial son idénticos antes y después en ambos casos;
- ningún registro histórico fue alterado.

Sin embargo, ninguno de los dos mensajes coincide con el texto exigido por el caso:

- **TC-M09-146-v2.0** devuelve `Solo se pueden calibrar sensores de dispositivos activos.`,
  un texto completamente distinto del FA: no lleva el prefijo `Operación rechazada: `, **no
  incluye el serial del dispositivo** y no indica que deba activarse antes de registrar
  parámetros.
- **TC-M09-147-v2.0** devuelve el texto esperado **menos su prefijo**
  `Conflicto de ubicación: `. El resto de la frase, con el sensor y el área reales, coincide
  literalmente.

Ambos textos son exactamente los que el criterio del grupo señala como no aceptables, de modo
que un HTTP correcto con mensaje que no coincide no se convierte en aprobación. Las dos
diferencias comparten causa raíz, por lo que se consolidan en **una sola incidencia**.

## ANTECEDENTES

RF-24 v2.0.
CU05 — Gestionar Dispositivos IoT, Flujo D.
Objetivo: comprobar que se rechaza calibrar un sensor cuyo dispositivo está inactivo y que se
rechaza informar un área existente distinta de la asociación vigente, sin crear calibraciones
ni alterar el historial.

## ENTORNO

**TEST:** https://api.inmero.co/back-sigab-test
**Rama:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
**RUN_ID:** run-20261007-074315
**Carpeta:** tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76-v2.0/

La carpeta histórica `TC-M09-G76/` se consultó solo como referencia y no fue modificada:
`git diff` y `git status` sobre esa ruta quedan vacíos. La automatización incorpora la
protección programática que aborta si se ejecuta desde una carpeta cuyo nombre no sea
exactamente `TC-M09-G76-v2.0`.

### Preflight OpenAPI

Los endpoints del grupo están desplegados en TEST:

```text
POST  /configuracion/sensores/{id_sensor}/calibrar                     201, 400, 401, 403, 404, 409, 422
GET   /configuracion/sensores/{id_sensor}/calibraciones                200, 401, 403, 404, 422
GET   /configuracion/sensores/{id_sensor}/asociaciones                  200, 401, 403, 404, 422
GET   /configuracion/dispositivos-iot/{id_dispositivo_iot}              200, 401, 403, 404, 422
GET   /configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores     200, 401, 403, 404, 422
GET   /configuracion/infraestructuras/{id_infraestructura}              200, 401, 403, 404, 422
GET   /configuracion/dispositivos-iot/{id}/configuraciones              200, 401, 403, 404, 422
PATCH /configuracion/dispositivos-iot/{id}/desactivar                   200, 401, 403, 404, 409, 422
```

El `422` que exige TC-146 y el `400` que exige TC-147 están declarados por el contrato.

## ACTOR

**Actor funcional:** Ingeniero de campo
**Usuario:** ingeniero@pecuaria.co
**id_usuario:** 4
**Rol confirmado:** Ingeniero de Campo
**Credencial:** [REDACTED]

Permisos confirmados: registrar calibraciones (`12,1`) y consultar historial (`12,2`).
**Los dos POST de calibración los ejecutó el Ingeniero.**

### Administrador de discovery

El Ingeniero no tiene dispositivos en su alcance, así que se usó un Administrador
**exclusivamente para GET de precondición**:

```text
admin.dev@gmail.com          -> no autentica (un intento, según el orden autorizado)
administador.dev@gmail.com   -> autentica (credencial [REDACTED])
```

GET que lo requirieron (5 en total), todos de solo lectura:

```text
GET /configuracion/sensores/rangos-calibracion
GET /configuracion/dispositivos-iot?solo_activos=false
GET /configuracion/dispositivos-iot/47/sensores
GET /configuracion/sensores/29/asociaciones
GET /configuracion/dispositivos-iot/3            (y la asociación del sensor 6)
```

Conviene señalar un detalle del alcance, porque afecta cómo debe hacerse el discovery: para
este actor el listado de dispositivos **no responde 404 sino HTTP 200 con una lista vacía**.
El Administrador no ejecutó ningún POST de calibración ni modificó datos.

## TC-M09-146-v2.0 — DISPOSITIVO INACTIVO

### Fixture

**id_dispositivo:** 47
**serial:** BUGCHECK-REASIGN-001
**es_activo:** false
**id_sensor:** 29 — `SensorBugcheck`, activo, perteneciente al dispositivo 47
**categoría:** PH
**id_infraestructura:** 3 — asociación vigente (`tiene_estado = true`, `fecha_finalizacion = null`)
**rango:** 0.0000 – 14.0000
**valor enviado:** 7.0000

El valor es el punto medio exacto del rango: interior y nunca una frontera. La única
invalidez intencional del request es que el dispositivo está inactivo; el área enviada es la
asociación vigente correcta.

### Preparación de precondición

**Se utilizó PATCH de setup:** NO

No hizo falta. TEST ya contenía 65 dispositivos inactivos y el dispositivo 47 indicado por la
matriz seguía existiendo, inactivo y utilizable. Es por tanto un **fixture preexistente**, no
uno preparado: ningún dispositivo fue desactivado por esta prueba y el presupuesto de PATCH
quedó en 0 de 1.

### Historial PRE

```text
GET /configuracion/sensores/29/calibraciones -> HTTP 200
total: 0 | ids: []
```

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 47,
  "id_infraestructura": 3,
  "valor_referencia": 7.0000,
  "observaciones": "QA TC-M09-146-v2.0",
  "fecha_calibracion": "2026-10-07T07:43:19.087Z"
}
```

### Respuesta

**HTTP esperado:** 422
**HTTP obtenido:** 422
**error_code:** `DISPOSITIVO_INACTIVO`

**Mensaje esperado:**

```text
Operación rechazada: El dispositivo BUGCHECK-REASIGN-001 está inactivo. Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.
```

**Mensaje obtenido:**

```text
Solo se pueden calibrar sensores de dispositivos activos.
```

**Diferencia exacta:** el texto es completamente distinto. Falta el prefijo
`Operación rechazada: `, **no se interpola el serial del dispositivo** y no aparece la
instrucción de activar el dispositivo antes de registrar nuevos parámetros de calibración.

### Historial POST

```text
total: 0 | ids: []
```

Sin IDs nuevos, total sin cambios y sin registros históricos que pudieran alterarse.

### Resultado

**RECHAZADO** — HTTP 422 correcto y sin persistencia, pero el mensaje no coincide con el FA.

## TC-M09-147-v2.0 — ÁREA INCORRECTA

### Fixture

**sensor:** 6 — `Sensor temperatura alevinera-01`, activo, categoría TEMPERATURA
**dispositivo activo:** 3 — `IOT-ALE01-HLA-003`, `es_activo = true`
**área vigente:** 3 — asociación vigente del sensor
**área alternativa:** 1
**GET área alternativa:** 200 (`id_infraestructura = 1`, `es_activo = true`)
**asociada actualmente al sensor:** NO — la única asociación vigente del sensor 6 es al área 3
**rango:** 0.0000 – 45.0000
**valor enviado:** 22.5000 (interior al rango)

El área alternativa es un área **real existente**, no un identificador inventado. No se creó
ni se reasignó ninguna asociación para preparar el caso.

### Historial PRE

```text
GET /configuracion/sensores/6/calibraciones -> HTTP 200
total: 5 | ids: [14, 13, 12, 11, 10]
```

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 1,
  "valor_referencia": 22.5000,
  "observaciones": "QA TC-M09-147-v2.0",
  "fecha_calibracion": "2026-10-07T07:43:19.722Z"
}
```

### Respuesta

**HTTP esperado:** 400
**HTTP obtenido:** 400
**error_code:** `SENSOR_AREA_INVALIDA`

**Mensaje esperado:**

```text
Conflicto de ubicación: El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.
```

**Mensaje obtenido:**

```text
El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.
```

**Diferencia exacta:** falta únicamente el prefijo `Conflicto de ubicación: `. El resto del
texto coincide literalmente, con el sensor y el área reales correctamente interpolados.

### Historial POST

```text
total: 5 | ids: [14, 13, 12, 11, 10]
```

Idéntico al PRE: sin IDs nuevos y con los cinco registros históricos conservando valor,
fecha, usuario y observaciones.

### Resultado

**RECHAZADO** — HTTP 400 correcto y sin persistencia, pero el mensaje no coincide con el FA.

## VERIFICACIÓN DE NO PERSISTENCIA

| Caso | Total PRE | Total POST | IDs nuevos | Históricos alterados |
|---|---:|---:|---|---|
| TC-M09-146-v2.0 | 0 | 0 | ninguno | NO |
| TC-M09-147-v2.0 | 5 | 5 | ninguno | NO |

Verificación final de solo lectura, sin SQL:

- el dispositivo 47 **continúa inactivo** al cierre del RUN;
- ninguna calibración es atribuible a los rechazos, comprobado por coincidencia de
  observaciones y fecha enviada;
- la asociación vigente del sensor 6 **no fue alterada**: sigue siendo una sola, al área 3,
  sobre el dispositivo 3;
- el dispositivo 3 sigue activo;
- los históricos `10`, `11`, `12`, `13` y `14` siguen presentes e íntegros.

No se detectó concurrencia: no apareció ningún ID ajeno entre PRE y POST de ninguno de los
dos casos, por lo que no hubo interferencia que clasificar.

## RESULTADO NEWMAN

**POST calibración planificados:** 2
**POST calibración ejecutados:** 2
**PATCH setup ejecutados:** 0 / 1
**Assertions:** 55
**Failures:** 2
**STOP_ALL:** NO

Los 2 fallos son exactamente las dos comparaciones de mensaje:

```text
1. 15. TC-M09-146-v2.0 — message coincide exactamente con el FA del RF
2. 12. TC-M09-147-v2.0 — message coincide exactamente con el FA del RF
```

Ninguna otra assertion falló: identidad y rol del actor, permisos, existencia e inactividad
del dispositivo de TC-146, serial real, pertenencia del sensor, asociación vigente, área
enviada correcta, rango y valor estrictamente interior, `modo_calibracion=SENSOR` enviado,
dispositivo activo de TC-147, existencia real del área alternativa, que sea distinta de la
vigente y que no esté asociada, los códigos HTTP, la ausencia de persistencia y la integridad
del historial pasaron todas.

## EVIDENCIAS

```text
git_pre.txt
openapi_preflight.json
identidad_actor.json
permisos_actor.json
administrador_discovery.json
fixture_146.json          rango_146.json
fixture_147.json          rango_147.json

146_historial_pre.json    146_request.json    146_response.json    146_historial_post.json
147_historial_pre.json    147_request.json    147_response.json    147_historial_post.json

automation/               copia de la automatización que produjo este RUN
automation_manifest.json  SHA-256 de cada artefacto
verificacion-final-readonly.json
seguridad-evidencias.json
newman/newman-TC-M09-G76-v2.0.html
TC-M09-G76_resultado.md
```

No existen los archivos `setup_146_*` porque no hubo preparación por PATCH.

`seguridad-evidencias.json` reporta la carpeta del RUN limpia: ningún archivo contiene
contraseñas, JWT, `Authorization` con token, cookies, tokens en pares clave-valor ni cadenas
de conexión. El reporte Newman se generó con `omitHeaders`, sin environment ni globals,
omitiendo las variables sensibles, y se sanitizó después.

## OBSERVACIONES

Solo hechos demostrados por esta corrida.

1. **La lógica de validación funciona; los textos no.** Ambos rechazos se producen con el
   código HTTP correcto, con `error_code` coherente (`DISPOSITIVO_INACTIVO` y
   `SENSOR_AREA_INVALIDA`) y sin tocar el historial. El incumplimiento se limita al contenido
   de `message`.

2. **Las dos diferencias no son del mismo tamaño.** En TC-147 falta solo el prefijo; en
   TC-146 el mensaje es otro texto y, sobre todo, **no identifica el dispositivo**, que es
   justamente el dato que el FA pide interpolar para que el operario sepa qué equipo activar.

3. **No se desactivó ningún dispositivo.** El fixture de TC-146 era preexistente: el
   dispositivo 47 ya estaba inactivo, y en TEST hay 65 dispositivos inactivos. El presupuesto
   de PATCH quedó sin usar, de modo que esta prueba no introdujo ningún efecto lateral
   irreversible sobre el ambiente.

4. **Alcance del Ingeniero en el discovery.** Para este actor el listado de dispositivos
   devuelve HTTP 200 con una colección vacía en lugar de un error de autorización. Es un
   detalle relevante para cualquier automatización futura, porque un fallback de lectura
   guiado solo por el código de estado no se activaría y el discovery concluiría por error que
   no existe ningún dispositivo.

5. **`modo_calibracion` no está declarado en el OpenAPI de TEST.** Los dos POST lo enviaron
   como `"SENSOR"`, según exige el caso, y ambos fueron procesados hasta la validación
   correspondiente. G76 no prueba el enum ni la obligatoriedad de ese campo, así que esta
   corrida **no** concluye nada sobre él.

6. **Defecto propio de la automatización, corregido antes del RUN oficial.** Un primer
   intento abortó durante el discovery por dos errores míos: la raíz del repositorio se
   resolvía contando niveles de directorio, y el fallback de lectura auxiliar no contemplaba
   que el Ingeniero recibiera 200 con lista vacía. Ese intento **no ejecutó ninguna escritura**
   (0 POST y 0 PATCH, verificado por la ausencia de cualquier archivo de request o response) y
   se descartó. Los dos defectos se corrigieron y el RUN oficial es el único que llegó a
   enviar POST. No se modificó el producto ni el esperado para conseguirlo.

## INCIDENCIA

**INCIDENCIA REQUERIDA:** SÍ

Una sola incidencia consolidada para TC-M09-G76-v2.0: ambas diferencias provienen de la misma
causa raíz, los mensajes de error del registro de calibración no implementan los textos
definidos por RF-24 v2.0. No se abre un ticket por caso.

**Clasificación propuesta (Taiga):** Type = `bug`, Severity = `Normal`, Priority = `Normal`

**Causa raíz:** mensajes de error desalineados respecto al requisito. No es un fallo de
validación ni de integridad: los códigos HTTP, los `error_code` y la ausencia de persistencia
son correctos.

**Detalle a corregir:**

```text
1. Dispositivo inactivo (error_code DISPOSITIVO_INACTIVO, HTTP 422)
   Obtenido: Solo se pueden calibrar sensores de dispositivos activos.
   Esperado: Operación rechazada: El dispositivo [SERIAL] está inactivo. Debe activar el
             dispositivo antes de proceder con el registro de nuevos parámetros de
             calibración.
   Falta el prefijo, la interpolación del serial y la instrucción de activación.

2. Área no asociada (error_code SENSOR_AREA_INVALIDA, HTTP 400)
   Obtenido: El sensor 6 no está asociado al área 1. Verifique la ubicación física y
             lógica del equipo antes de calibrar.
   Esperado: Conflicto de ubicación: El sensor [ID_SENSOR] no está asociado al área
             [ID_AREA]. Verifique la ubicación física y lógica del equipo antes de calibrar.
   Falta únicamente el prefijo "Conflicto de ubicación: ".
```

No se creó ni actualizó ningún GitHub Issue ni tarjeta de Taiga en esta ejecución.

## CONCLUSIÓN

El grupo **TC-M09-G76-v2.0 queda RECHAZADO**, porque sus dos casos incumplen el esperado. El
hecho de que la mayoría de las verificaciones pasara no se presenta como aprobación.

Lo que quedó demostrado empíricamente en TEST, con el Ingeniero de campo autenticado
(`id_usuario 4`):

- calibrar un sensor de un dispositivo IoT inactivo se rechaza con **HTTP 422**
  (`DISPOSITIVO_INACTIVO`) y no crea ninguna calibración;
- informar un área real existente distinta de la asociación vigente se rechaza con
  **HTTP 400** (`SENSOR_AREA_INVALIDA`) y no crea ninguna calibración;
- el historial no fue alterado en ninguno de los dos casos y las asociaciones y el estado del
  dispositivo siguen igual al cierre del RUN.

Lo que **no** se cumple: los mensajes de ambos rechazos no corresponden a los textos del FA
de RF-24 v2.0. En TC-147 falta solo el prefijo; en TC-146 el texto es distinto y omite el
serial del dispositivo. Por el criterio del grupo, un código HTTP correcto con un mensaje que
no coincide es RECHAZADO, y un mensaje parecido no se reinterpreta como válido después de
verlo.

La evidencia decisiva de TC-146 es la respuesta del POST de calibración con el dispositivo ya
inactivo; el fixture era preexistente y no se preparó desactivando nada. Para reevaluar el
grupo basta alinear los dos mensajes con el requisito: según esta corrida, la lógica de
validación e integridad no requiere cambios.
