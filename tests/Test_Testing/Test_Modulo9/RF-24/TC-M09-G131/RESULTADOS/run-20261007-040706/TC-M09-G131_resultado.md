# TC-M09-G131 — Resultado

## Decisión general

**TC-M09-G131: RECHAZADO.** El caso TC-M09-259 envió una calibración sin la clave obligatoria `modo_calibracion`. TEST respondió **HTTP 201**, devolvió `id_calibracion = 16` y el historial del sensor incorporó ese ID. RF-24 v2.0 exige rechazar esa entrada con **algún HTTP 4xx** y no persistirla. La decisión proviene de la respuesta y del historial observados en TEST; no se fijó un código ni un mensaje exactos como criterio de aprobación.

| Caso | Variante | Resultado | Motivo concreto |
|---|---|---|---|
| TC-M09-258 | Sensor de otro dispositivo | **APROBADO** | TEST devolvió 422 y los IDs del historial del sensor 3 permanecieron `[3, 9]`. |
| TC-M09-259 | `modo_calibracion` ausente | **RECHAZADO** | TEST devolvió 201; el historial del sensor 6 pasó de seis a siete registros y apareció el ID 16. |
| TC-M09-260 | `"OTRO"` | **NO EJECUTADO** | `STOP_ALL` tras comprobar la creación indebida en TC-M09-259. |
| TC-M09-260 | `""` | **NO EJECUTADO** | `STOP_ALL` tras comprobar la creación indebida en TC-M09-259. |

Este informe amplía la explicación del RUN a petición del usuario. No se repitió ningún POST ni se modificaron `evidencia.json` o `newman.html`.

## Entorno, contrato y actores

| Dato | Valor |
|---|---|
| Ambiente decisorio | TEST, `https://api.inmero.co/back-sigab-test` |
| Prueba local | NO |
| RUN_ID | `run-20261007-040706` |
| Rama | `qa/juan-esteban-rf24-v2` |
| HEAD y `origin/test` | `30ddd72144102a60af006b265a20cb18c1c72c85`; divergencia `0 / 0` |
| Actor de los POST | `ingeniero@pecuaria.co`, `id_usuario = 4`, rol Ingeniero de Campo, cuenta Activo |
| Permisos del Ingeniero | Recurso 12, acciones 1, 2 y 3, consultados por API |

El preflight de `GET /openapi.json` confirmó que TEST expone `POST /configuracion/sensores/{id_sensor}/calibrar` y `GET /configuracion/sensores/{id_sensor}/calibraciones`. El esquema desplegado `RegistrarCalibracionDTO` **no declara** `modo_calibracion`, no lo incluye en `required` y no publica el dominio `SENSOR | VISION`. Esto es un dato de diagnóstico del contrato desplegado; por sí solo no se usó para declarar el caso fallido.

Para validar los fixtures por GET se intentó primero `admin.dev@gmail.com`, que no autenticó (HTTP 401). `administador.dev@gmail.com` sí autenticó y pudo consultar el detalle que devolvía 404 al Ingeniero. El Administrador se utilizó solo para lecturas de discovery. **Los dos POST funcionales los envió el Ingeniero.** Contraseñas, JWT, cookies y cabeceras de autorización no se guardaron en los artefactos.

## Fixtures verificados antes de los POST

| Caso | Sensor | Dispositivo propietario | Área asociada vigente | Categoría y rango | Dato que hace inválida la petición |
|---|---:|---:|---:|---|---|
| TC-M09-258 | 3, activo | 1, activo | 1, asociación 3 vigente | OXIGENO, `0.0000–20.0000` | El body usa el dispositivo **3**, también activo, distinto del propietario 1. `10.0000` está dentro del rango. |
| TC-M09-259/260 | 6, activo | 3, activo | 3, asociación 6 vigente | TEMPERATURA, `0.0000–45.0000` | Dispositivo, área y `22.5000` son válidos; en TC-M09-259 falta exclusivamente `modo_calibracion`. |

Los dispositivos, sensores, áreas y asociaciones se comprobaron mediante GET de TEST. La consulta SELECT de diagnóstico a la BD realizada antes del RUN no se empleó para decidir el fixture ni sustituyó estas validaciones de API. No se crearon ni reasignaron datos de fixture.

## Esperado frente a obtenido

### TC-M09-258 — Sensor de otro dispositivo: APROBADO

Se envió `POST /configuracion/sensores/3/calibrar` con `modo_calibracion = "SENSOR"`, `id_dispositivo_iot = 3`, `id_infraestructura = 1` y `valor_referencia = 10.0000`. El sensor 3 pertenece al dispositivo **1**. Por ello, la incompatibilidad sensor–dispositivo era la invalidez evaluada; el valor numérico y el área no introducían una invalidez previa.

- **Esperado:** cualquier HTTP 4xx y ningún cambio en el historial del sensor 3.
- **Obtenido:** HTTP **422**, código real `SENSOR_DISPOSITIVO_INVALIDO`, mensaje real «El sensor 3 no pertenece al dispositivo 3.»
- **Persistencia:** PRE `total = 2`, IDs `[3, 9]`; POST `total = 2`, IDs `[3, 9]`.
- **Decisión:** aprobado porque se cumplieron ambas partes del oráculo. El 422 y el mensaje se registran como observación, sin convertirlos en un esperado exacto.

### TC-M09-259 — Discriminador ausente: RECHAZADO

Se envió `POST /configuracion/sensores/6/calibrar` con dispositivo 3, área 3, `valor_referencia = 22.5000`, observación `QA TC-M09-259` y fecha ISO actual. El JSON **no contenía la clave `modo_calibracion`**. El fixture era válido por lo demás: sensor y dispositivo activos, propiedad coherente, asociación vigente y valor dentro del rango.

- **Esperado por RF-24 v2.0:** cualquier HTTP 4xx y ausencia de una nueva calibración. El requisito no fija código HTTP ni mensaje concretos.
- **Obtenido de TEST:** HTTP **201 Created** y `id_calibracion = 16` en la respuesta. La aserción 4xx de Newman falló porque recibió 201.
- **Persistencia PRE:** `total = 6`, IDs `[10, 11, 12, 13, 14, 15]`.
- **Persistencia POST:** `total = 7`, IDs `[10, 11, 12, 13, 14, 15, 16]`.
- **Cambio comprobado:** apareció únicamente el ID **16**. La respuesta 201 y el nuevo ID en un GET independiente del historial prueban que la petición inválida fue aceptada y persistida; no es solo una respuesta HTTP equivocada.
- **Decisión:** rechazado porque fallaron las dos partes del oráculo: no hubo 4xx y sí hubo persistencia. No se borró la calibración 16.

**Posible mecanismo del defecto.** El OpenAPI de TEST no incluye `modo_calibracion` en el DTO de entrada. En la rama evaluada, [`RegistrarCalibracionDTO`](../../../../../../../src/configuration/infrastructure/dto/registrar_calibracion_dto.py) tampoco define ese campo. Al no existir como campo requerido del DTO, su ausencia no produce un error de validación y la calibración puede llegar al caso de uso y guardarse. [`BaseDTO`](../../../../../../../src/shared/base_dto.py) tampoco declara `extra="forbid"`; esto sería relevante al evaluar valores enviados en TC-M09-260, pero esas variantes no se ejecutaron y no se les atribuye aquí un resultado. La ausencia del campo en el OpenAPI desplegado y el 201 observado sostienen la hipótesis para TC-M09-259. **No se verificó el SHA exacto desplegado en TEST**, por lo que la correspondencia precisa entre ese despliegue y el archivo de la rama permanece pendiente de confirmación. La causa funcional demostrada por API es que TEST no hace obligatorio `modo_calibracion` para esta operación.

El resultado no se explica por un fixture inválido: el mismo flujo validó el sensor, su dispositivo, su área y el rango antes del POST, y el historial lo incorporó. Tampoco hay indicio de fallo de persistencia o de infraestructura: la escritura se completó. La hipótesis principal es una omisión de contrato/validación de entrada, responsabilidad probable de **Desarrollo**.

### TC-M09-260 — `"OTRO"` y vacío: NO EJECUTADOS

Las dos variantes estaban planificadas con el fixture válido del sensor 6. No se envió ninguno de esos POST. Tras comprobar que TC-M09-259 creó la calibración 16, se activó `STOP_ALL` para evitar generar otras calibraciones inválidas. Por tanto, **no existe evidencia empírica en este RUN** para aprobar o rechazar las variantes `"OTRO"` y `""`. Deben reevaluarse después de corregir o aclarar la validación del discriminador, usando un RUN_ID nuevo.

## Persistencia y STOP_ALL

| Caso | Total PRE → POST | IDs PRE → POST | Conclusión |
|---|---|---|---|
| TC-M09-258 | `2 → 2` | `[3, 9] → [3, 9]` | Sin persistencia. |
| TC-M09-259 | `6 → 7` | `[10, 11, 12, 13, 14, 15] → [10, 11, 12, 13, 14, 15, 16]` | Persistencia inesperada del ID 16. |
| TC-M09-260 / `"OTRO"` | Sin PRE/POST | Sin POST | No ejecutado por `STOP_ALL`. |
| TC-M09-260 / `""` | Sin PRE/POST | Sin POST | No ejecutado por `STOP_ALL`. |

**STOP_ALL: SÍ**, activado inmediatamente después de reconciliar el historial de TC-M09-259. Presupuesto: **4 POST planificados, 2 ejecutados**, sin reintentos automáticos. El rechazo concluyente de TC-M09-259 determina el resultado RECHAZADO del grupo; las variantes pendientes conservan su estado NO EJECUTADO.

## Incidencia requerida

**INCIDENCIA REQUERIDA:** SÍ  
**Título propuesto:** RF-24 v2.0 permite crear una calibración SENSOR sin `modo_calibracion`.  
**Grupo responsable:** Desarrollo (asignación probable; confirmar código desplegado).  
**Grupo de prueba:** TC-M09-G131.  
**Casos afectados:** TC-M09-259 demostrado; TC-M09-260 pendiente, sin atribuirle resultado.  
**Resultado:** RECHAZADO.  
**Type:** bug.  
**Severity:** Important.  
**Priority:** High.

**Motivo:** el backend de TEST aceptó un request al que le faltaba un discriminador obligatorio según RF-24 v2.0 y creó una calibración que el caso requería rechazar.

**Esperado:** 4xx y ningún ID nuevo en el historial del sensor 6.

**Obtenido:** 201; respuesta con `id_calibracion = 16`; historial de seis a siete registros con el ID 16 añadido.

**Causa raíz probable:** falta la obligatoriedad de `modo_calibracion` en el contrato/validación de entrada del POST. El OpenAPI desplegado y el DTO de la rama coinciden en omitirlo; falta verificar el SHA exacto del backend desplegado para identificar el cambio de código responsable con certeza. Se propone **Desarrollo** porque el defecto aparece al aceptar la entrada inválida. No hay evidencia de una migración, constraint o dato estructural faltante que justifique asignarlo a DBA; AIoT no interviene en esta validación.

**Severidad propuesta:** Important, porque permite persistir una calibración que RF-24 v2.0 define como inválida. La incidencia es una sola para el defecto demostrado de TC-M09-259; no se atribuye a TC-M09-260 una falla que no se ejecutó.

**Evidencia:** [evidencia.json](evidencia.json) registra OpenAPI, actor, fixtures, request, HTTP, aserciones Newman, historiales PRE/POST y `STOP_ALL`; [newman.html](newman.html) resume los POST ejecutados. No se creó un ticket externo como parte de este RUN.

## Conclusión

**G131 queda RECHAZADO** porque TC-M09-259 recibió 201 y persistió la calibración 16 pese a omitir `modo_calibracion`. TC-M09-258 sí aprobó al recibir 4xx sin persistencia. TC-M09-260 no fue ejecutado por la protección `STOP_ALL` y permanece pendiente de reevaluación.
