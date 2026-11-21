# TC-M09-G75-v2.0 — RESULTADO

## DECISIÓN GENERAL

**Grupo:** TC-M09-G75-v2.0
**Resultado general:** RECHAZADO

| Caso | Resultado |
|---|---|
| TC-M09-142-v2.0 | APROBADO |
| TC-M09-143-v2.0 | APROBADO |
| TC-M09-144-v2.0 | RECHAZADO |
| TC-M09-145-v2.0 | RECHAZADO |

## RESUMEN DEL RESULTADO

Se ejecutaron los 7 POST planificados, sin reintentos y sin STOP_ALL.

Los dos casos de aceptación pasan: el mínimo técnico `0.0000` y el máximo técnico `45.0000`
se aceptan con HTTP 201, generan `id_calibracion = 13` y `14` respectivamente, y ambos
registros quedan persistidos y recuperables en el historial con todos sus valores
funcionales correctos.

Los dos casos de validación fallan, y fallan **únicamente por el mensaje de error**. Las
cinco variantes inválidas (`-0.0001`, `45.0001`, `""`, `null`, `"abc"`) devuelven
correctamente **HTTP 400** y **ninguna persiste**: el total y los IDs del historial son
idénticos antes y después de cada intento. Sin embargo, ninguno de los cinco mensajes
coincide con el texto que exige el caso, por lo que, conforme al criterio del paquete, cada
variante falla y arrastra a su caso:

- **TC-M09-144-v2.0** (LOW y HIGH): el mensaje omite el prefijo `Valor fuera de límites: ` y
  añade un fragmento `(permitido 0.0000–45.0000)` que el esperado no contempla.
- **TC-M09-145-v2.0** (EMPTY, NULL y ABC): el mensaje omite el prefijo `Error de formato: ` y
  además **no incluye la parte final que identifica la entrada rechazada**
  (`Verifique la entrada '<valor>'.`). Las tres variantes devuelven el mismo texto, de modo
  que el mensaje no distingue qué valor fue rechazado.

La lógica de validación del backend es correcta en rango, en formato y en no persistencia;
la desalineación está en los textos de los mensajes respecto a RF-24 v2.0. Como las cinco
diferencias provienen de la misma causa raíz, se consolidan en **una sola incidencia**.

## ANTECEDENTES

RF-24 v2.0.
CU05 — Gestionar Dispositivos IoT, Flujo D.
Objetivo: validar límites y formato de `valor_referencia` sobre una calibración SENSOR.

## ENTORNO

**Ambiente decisorio:** TEST
**Backend:** https://api.inmero.co/back-sigab-test
**Rama QA:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
**RUN_ID:** run-20261007-072226
**Carpeta:** tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0/

La carpeta histórica `TC-M09-G75/` no fue modificada: se leyó solo como referencia y su
estado en git quedó sin diferencias. Todos los cambios de esta prueba están bajo
`TC-M09-G75-v2.0/`. La automatización incorpora una protección programática que aborta si se
ejecuta desde cualquier carpeta cuyo nombre no sea exactamente `TC-M09-G75-v2.0`.

### Preflight OpenAPI

Los tres endpoints del grupo están desplegados en TEST:

```text
POST /configuracion/sensores/{id_sensor}/calibrar          códigos declarados: 201, 400, 401, 403, 404, 409, 422
GET  /configuracion/sensores/{id_sensor}/calibraciones     códigos declarados: 200, 401, 403, 404, 422
GET  /configuracion/sensores/rangos-calibracion            códigos declarados: 200, 401, 403
```

## ACTOR

**Actor funcional:** Ingeniero de campo
**Usuario:** ingeniero@pecuaria.co
**id_usuario:** 4
**Rol confirmado:** Ingeniero de Campo
**Credencial:** [REDACTED]

Permisos confirmados: lectura de dispositivos (`11,2`), registro de calibraciones (`12,1`) y
consulta de historial (`12,2`). **Los 7 POST los ejecutó el Ingeniero.**

### Administrador usado para discovery

El Ingeniero no tiene dispositivos en su alcance en TEST, por lo que dos GET de precondición
le responden 404. Se usó un Administrador **solo** para esas lecturas:

```text
admin.dev@gmail.com          -> no autentica (un solo intento, según el orden autorizado)
administador.dev@gmail.com   -> autentica (credencial [REDACTED])
```

GET que lo requirieron, ambos de solo lectura:

```text
GET /configuracion/dispositivos-iot/3        (detalle de dispositivo, RF-21)
GET /configuracion/sensores/6/asociaciones   (historial de asociaciones, RF-22)
```

El Administrador **no ejecutó ningún POST** y no modificó datos.

## FIXTURE EFECTIVO

**Origen:** fixture oficial del caso, validado por GET (no se requirió alternativa)

**id_sensor:** 6 — `Sensor temperatura alevinera-01`
**categoría:** TEMPERATURA
**id_dispositivo_iot:** 3 — serial `IOT-ALE01-HLA-003`
**id_infraestructura:** 3 — asociación vigente (`tiene_estado = true`, `fecha_finalizacion = null`)
**estado:** dispositivo `es_activo = true`; sensor `es_activo = true`
**rango vigente:** 0.0000 – 45.0000 (leído de `GET /configuracion/sensores/rangos-calibracion`)
**paso de frontera:** 0.0001

Valores del RUN, calculados con aritmética decimal exacta sobre `numeric(10,4)` mediante
`BigInt` (nunca coma flotante binaria):

```text
min_ok   = 0.0000
max_ok   = 45.0000
low_bad  = -0.0001
high_bad = 45.0001
```

La colección reconfirmó que el rango no cambió entre el discovery y los POST, y la
verificación de cierre confirmó que tampoco cambió durante el RUN.

## TC-M09-142-v2.0 — MÍNIMO

### PRE

```text
GET /configuracion/sensores/6/calibraciones -> HTTP 200
total: 3 | ids: [12, 11, 10]
```

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 0.0000,
  "observaciones": "QA TC-M09-142-v2.0",
  "fecha_calibracion": "2026-10-07T07:22:35.282Z"
}
```

### Respuesta

```text
HTTP 201
id_calibracion: 13
valor_referencia: "0.0000"
id_dispositivo_iot: 3 | id_sensor: 6 | id_usuario: 4
observaciones: "QA TC-M09-142-v2.0"
fecha_calibracion: mismo instante enviado
```

### Historial POST

```text
total: 4 | ids: [13, 12, 11, 10]
```

El `id_calibracion = 13` no estaba en PRE, aparece en POST y conserva los valores del caso.
Los registros previos se conservan.

### Resultado

**APROBADO**

## TC-M09-143-v2.0 — MÁXIMO

### PRE

```text
total: 4 | ids: [13, 12, 11, 10]
```

La calibración de TC-M09-142-v2.0 (`id 13`) sigue presente con sus mismos valores.

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 3,
  "id_infraestructura": 3,
  "valor_referencia": 45.0000,
  "observaciones": "QA TC-M09-143-v2.0",
  "fecha_calibracion": "2026-10-07T07:22:35.877Z"
}
```

### Respuesta

```text
HTTP 201
id_calibracion: 14
valor_referencia: "45.0000"
id_dispositivo_iot: 3 | id_sensor: 6 | id_usuario: 4
observaciones: "QA TC-M09-143-v2.0"
fecha_calibracion: mismo instante enviado
```

### Historial POST

```text
total: 5 | ids: [14, 13, 12, 11, 10]
```

El `id 14` queda persistido con sus valores y el `id 13` de TC-M09-142-v2.0 permanece
intacto, comparado campo por campo.

### Resultado

**APROBADO**

## TC-M09-144-v2.0 — FUERA DE RANGO

| Variante | Valor | HTTP esperado | HTTP obtenido | Mensaje | Persistencia | Resultado |
|---|---:|---:|---:|---|---|---|
| LOW | -0.0001 | 400 | 400 | FAIL | NO | RECHAZADO |
| HIGH | 45.0001 | 400 | 400 | FAIL | NO | RECHAZADO |

`error_code` obtenido en ambas: `VALOR_FUERA_DE_RANGO` (se registra; el caso no exige un
`error_code` concreto).

### Comparación exacta de mensajes

**LOW — esperado:**

```text
Valor fuera de límites: El ajuste de -0.0001 excede los rangos de seguridad para la variable TEMPERATURA. Verifique el estándar de calibración utilizado.
```

**LOW — obtenido:**

```text
El ajuste de -0.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.
```

**HIGH — esperado:**

```text
Valor fuera de límites: El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA. Verifique el estándar de calibración utilizado.
```

**HIGH — obtenido:**

```text
El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.
```

**Diferencias exactas, idénticas en ambas variantes:**

1. falta el prefijo `Valor fuera de límites: `;
2. se añade ` (permitido 0.0000–45.0000)` después del nombre de la variable.

El valor y la variable sí se interpolan correctamente, y la frase final coincide. No se
acepta como PASS un mensaje aproximado.

### Persistencia

Ninguna de las dos variantes creó calibraciones: total e IDs idénticos entre PRE y POST
(`5 | [14, 13, 12, 11, 10]` en ambos extremos de cada variante), y no apareció ningún ID
nuevo. Las calibraciones de TC-142 y TC-143 siguen presentes e intactas.

### Resultado

**RECHAZADO** — ambas variantes cumplen HTTP y no persistencia, pero el mensaje no coincide.

## TC-M09-145-v2.0 — FORMATO

| Variante | Valor | HTTP esperado | HTTP obtenido | Mensaje | Persistencia | Resultado |
|---|---|---:|---:|---|---|---|
| EMPTY | `""` | 400 | 400 | FAIL | NO | RECHAZADO |
| NULL | `null` | 400 | 400 | FAIL | NO | RECHAZADO |
| ABC | `"abc"` | 400 | 400 | FAIL | NO | RECHAZADO |

`error_code` obtenido en las tres: `VALOR_CALIBRACION_INVALIDO`.

### Comparación exacta de mensajes

**Esperado por variante:**

```text
EMPTY: Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada ''.
NULL:  Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada 'null'.
ABC:   Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada 'abc'.
```

**Obtenido en las tres variantes, idéntico:**

```text
El valor de referencia debe ser un número decimal válido.
```

**Diferencias exactas:**

1. falta el prefijo `Error de formato: `;
2. falta por completo la parte final `Verifique la entrada '<valor>'.`, de modo que el
   mensaje no identifica la entrada rechazada;
3. como consecuencia, las tres variantes son indistinguibles por el mensaje.

### Persistencia

Ninguna de las tres variantes creó calibraciones: total e IDs idénticos entre PRE y POST en
cada una, sin IDs nuevos. Las válidas previas siguen intactas.

La variante **NULL**, obligatoria en v2.0, se ejecutó y está documentada.

### Resultado

**RECHAZADO** — las tres variantes cumplen HTTP y no persistencia, pero el mensaje no
coincide.

## VERIFICACIÓN DE INMUTABILIDAD

Comprobado en `verificacion-final-readonly.json` (solo GET, sin SQL):

- **TC-142 sigue presente:** sí — `id_calibracion 13`, valores sin cambios.
- **TC-143 sigue presente:** sí — `id_calibracion 14`, valores sin cambios.
- **IDs creados por intentos inválidos:** ninguno. Ninguna de las cinco variantes inválidas
  persistió, verificado también por coincidencia de observaciones y fecha enviada.
- **Históricos alterados:** NO — los registros preexistentes `10`, `11` y `12` siguen
  presentes.
- **Rango modificado durante el RUN:** NO — 0.0000 – 45.0000 al cierre.
- **Fixture modificado:** NO.
- **Historial final del sensor 6:** total 5 — ids `[14, 13, 12, 11, 10]`.
- **Concurrencia detectada:** ninguna. No apareció ningún ID ajeno entre PRE y POST de
  ninguna variante, por lo que no hubo interferencia que clasificar.

## RESULTADO NEWMAN

**Assertions:** 100
**Failures:** 5
**POST planificados:** 7
**POST ejecutados:** 7
**STOP_ALL:** NO

Los 5 fallos son exactamente las cinco comparaciones de mensaje de las variantes inválidas:

```text
1. TC-M09-144-v2.0 LOW   — message coincide exactamente con el esperado del RF
2. TC-M09-144-v2.0 HIGH  — message coincide exactamente con el esperado del RF
3. TC-M09-145-v2.0 EMPTY — message coincide exactamente con el esperado del RF
4. TC-M09-145-v2.0 NULL  — message coincide exactamente con el esperado del RF
5. TC-M09-145-v2.0 ABC   — message coincide exactamente con el esperado del RF
```

Ninguna otra assertion falló: identidad, permisos, fixture, rango, códigos HTTP,
persistencia de las válidas, ausencia de persistencia de las inválidas e inmutabilidad
pasaron todas.

## EVIDENCIAS

```text
git_pre.txt
openapi_preflight.json
identidad_actor.json
permisos_actor.json
fixture_descubierto.json
rango_temperatura.json
automation/            copia de la automatización que produjo este RUN
automation_manifest.json  SHA-256 de cada artefacto

142_historial_pre.json      142_request.json      142_response.json      142_historial_post.json      142_calibracion_creada.json
143_historial_pre.json      143_request.json      143_response.json      143_historial_post.json      143_calibracion_creada.json
144_low_historial_pre.json  144_low_request.json  144_low_response.json  144_low_historial_post.json
144_high_historial_pre.json 144_high_request.json 144_high_response.json 144_high_historial_post.json
145_empty_historial_pre.json 145_empty_request.json 145_empty_response.json 145_empty_historial_post.json
145_null_historial_pre.json  145_null_request.json  145_null_response.json  145_null_historial_post.json
145_abc_historial_pre.json   145_abc_request.json   145_abc_response.json   145_abc_historial_post.json

TC-M09-G75-v2.0.json          artefacto con el oráculo por variante y por caso
verificacion-final-readonly.json
seguridad-evidencias.json
newman/newman-TC-M09-G75-v2.0.html
TC-M09-G75_resultado.md
```

`seguridad-evidencias.json` reporta la carpeta del RUN limpia: ningún archivo contiene
contraseñas, JWT, `Authorization` con token, cookies, tokens en pares clave-valor ni cadenas
de conexión. El reporte Newman se generó con `omitHeaders`, sin datos de environment ni
globals, omitiendo las variables sensibles, y se sanitizó después.

## OBSERVACIONES

Solo hechos demostrados por esta corrida.

1. **La validación funciona; el texto no.** En las cinco variantes inválidas el backend
   rechazó correctamente con HTTP 400 y no persistió nada. El incumplimiento se limita al
   contenido de `message`.

2. **Los mensajes de TC-144 interpolan bien los datos** (valor y variable) y añaden
   información útil de rango, pero no respetan el texto exigido por el caso. La decisión se
   toma contra el esperado suministrado, no contra la utilidad del texto.

3. **Los mensajes de TC-145 no identifican la entrada rechazada.** Las tres variantes
   devuelven el mismo texto, de modo que por el mensaje no es posible distinguir si se envió
   `""`, `null` o `"abc"`. Esto es lo que más se aparta del esperado del caso.

4. **`modo_calibracion` no está declarado en el OpenAPI de TEST.** Los 7 bodies lo enviaron
   como `"SENSOR"`, según exige el caso. G75-v2.0 evalúa límites y formato de
   `valor_referencia`, así que esta corrida **no** determina si el discriminador de modalidad
   está implementado, y no se afirma nada al respecto a partir de este RUN.

5. **Valores derivados por la implementación.** Los registros creados quedaron con
   `ganancia = 1.0000` y `offset` igual al valor de referencia, sin que la prueba los
   enviara. No forman parte del oráculo del grupo y no se evaluaron.

6. **Corrección en el escáner de secretos, posterior a los POST.** La primera pasada marcó
   tres archivos de `automation/` por vocabulario del propio código (`contrasena: password`
   es una referencia a una variable; `set-cookie` es el propio patrón del escáner), con
   `credencialesEnClaro = 0` en todos los casos: ningún valor real de secreto estuvo
   presente en ninguna evidencia. Se ajustó el criterio para que en los archivos de código
   solo cuenten valores de secreto, y la verificación se repitió **solo con GET**, sin
   reejecutar ningún POST. `automation_manifest.json` conserva el SHA-256 original de los
   artefactos que produjeron los 7 POST (colección, `helpers.cjs`, `run-newman.cjs`) y
   registra ambos hashes de `verificar-cierre.cjs`, que no participa en los POST.

7. **`git_pre.txt` regenerado tras corregir un defecto de la automatización.** La captura
   original falló: el runner resolvía la raíz del repositorio contando niveles de directorio y
   todos los comandos git devolvieron `not a git repository`, de modo que esa evidencia de
   estado quedó inservible. El defecto se corrigió en `run-newman.cjs` y el archivo se regeneró
   con comandos de **solo lectura**, sin reejecutar ningún POST; lleva una nota de corrección en
   su encabezado y refleja el estado posterior al RUN, con el mismo commit `30ddd72`. No afecta
   el oráculo del grupo: el estado de la rama se verificó de forma independiente antes y después
   de la corrida.

## INCIDENCIA

**INCIDENCIA REQUERIDA:** SÍ

Una sola incidencia consolidada para TC-M09-G75-v2.0: las cinco diferencias provienen de la
misma causa raíz, la desalineación entre los mensajes de error implementados y los textos
exigidos por RF-24 v2.0. No se abren tickets por variante.

**Clasificación propuesta (Taiga):** Type = `bug`, Severity = `Normal`, Priority = `Normal`

**Causa raíz:** los mensajes de error del registro de calibración no implementan
literalmente los textos definidos por RF-24 v2.0. No es un fallo de validación: el rango, el
formato y la no persistencia se comportan correctamente.

**Detalle a corregir:**

```text
1. Valor fuera de rango (error_code VALOR_FUERA_DE_RANGO)
   Falta el prefijo "Valor fuera de límites: " y se añade " (permitido <min>–<max>)".
   Esperado: Valor fuera de límites: El ajuste de <valor> excede los rangos de seguridad
             para la variable <variable>. Verifique el estándar de calibración utilizado.

2. Formato inválido (error_code VALOR_CALIBRACION_INVALIDO)
   Falta el prefijo "Error de formato: " y falta la parte final que identifica la entrada.
   Esperado: Error de formato: El valor de referencia debe ser un número decimal válido.
             Verifique la entrada '<valor ingresado>'.
   Afecta por igual a "", null y "abc", que hoy devuelven un texto idéntico.
```

**Alcance:** no se creó ni actualizó ningún GitHub Issue ni tarjeta de Taiga en esta
ejecución. La decisión de abrir el ticket queda a cargo de Juan Esteban.

## CONCLUSIÓN

El grupo **TC-M09-G75-v2.0 queda RECHAZADO**, porque dos de sus cuatro casos no cumplen el
esperado. No se presenta como aprobado por el hecho de que la mayoría de las verificaciones
pasara.

Lo que sí quedó demostrado empíricamente en TEST, con el Ingeniero de campo autenticado
(`id_usuario 4`) sobre el fixture oficial dispositivo 3 / sensor 6 / infraestructura 3
(TEMPERATURA, rango 0.0000 – 45.0000, leído en TEST):

- el mínimo técnico exacto se acepta y persiste (`id_calibracion 13`);
- el máximo técnico exacto se acepta y persiste (`id_calibracion 14`);
- la frontera inferior `-0.0001` se rechaza con 400 y no persiste;
- la frontera superior `45.0001` se rechaza con 400 y no persiste;
- `""`, `null` y `"abc"` se rechazan con 400 y no persisten;
- las calibraciones válidas creadas permanecen intactas al final del RUN;
- los registros históricos preexistentes no fueron alterados y el rango no cambió.

Lo que **no** se cumple: los mensajes de error de las cinco variantes inválidas no
corresponden a los textos exigidos por RF-24 v2.0. Por el criterio del grupo, un HTTP 400
correcto con un mensaje que no coincide no es un PASS, y un mensaje parecido no se
reinterpreta como válido después de verlo.

En consecuencia TC-M09-142-v2.0 y TC-M09-143-v2.0 quedan APROBADOS, y TC-M09-144-v2.0 y
TC-M09-145-v2.0 quedan RECHAZADOS por una única causa raíz consolidada en una sola
incidencia. Para reevaluar el grupo basta alinear los dos mensajes de error con el
requisito; la lógica de validación no requiere cambios según esta corrida.
