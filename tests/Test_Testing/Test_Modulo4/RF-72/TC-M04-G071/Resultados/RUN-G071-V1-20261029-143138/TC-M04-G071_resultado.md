# TC-M04-G071 — APROBADO

## Identificación

Grupo G071; casos TC-M04-219, TC-M04-220, TC-M04-221, TC-M04-222, TC-M04-246; RF-72; versión 1; RUN RUN-G071-V1-20261029-143138; ambiente TEST; autorización AUT-G071-V1-20261029; commit revisado origin/test daefc3a5c62771c8952706ae7a7fe128e66b0b02. Node.js y Newman 6.2.2; solo API.

## Decisión del caso

| Caso | Veredicto | Decisión en lenguaje llano |
|---|---|---|
| TC-M04-219 | APROBADO | Los tres registros recibieron identificadores UUID distintos y quedaron en el historial. |
| TC-M04-220 | APROBADO | El resultado no cambió tras el registro INCORRECTO. |
| TC-M04-221 | APROBADO | No existe forma de editar ni borrar: PUT, PATCH y DELETE respondieron 404/405 y el registro siguió igual. |
| TC-M04-222 | APROBADO | Resultado, usuario, fecha y activo siempre presentes; sin token 401 e incompletos 400. |
| TC-M04-246 | APROBADO | El registro no alteró el resultado, las alertas, las versiones de modelo, la configuración del motor ni las inferencias. |

RUN oficial: sí. Qué falta: nada.

## Precondición de datos

El activo 885 aportó resultados recientes de MODELO_ESPECIES_MEDIANAS, versión 43. Para 219 se seleccionaron 511a6d66, f056f99d y 997b8cda; el tercer registro sirvió también para 221. Para 220 se usó d1f3cc43 y para 246, 5dbe4510. El caso 222 contrastó el alta del primer resultado de 219; los intentos incompletos usaron los reemplazos f7fea6d3 (sin activo) y 32985675 (sin resultado). resultado.json conserva las fechas e identificadores completos. La patología real 8, distinta de la estimada 10 del caso 220, se envió en los POST INCORRECTO de 220 y 246.

## Detalle por caso

### TC-M04-219 — APROBADO

- **Qué se hizo:** Se enviaron tres POST CORRECTO para los resultados 511a6d66, f056f99d y 997b8cda, y se consultó el historial del activo 885.
- **Qué se esperaba:** Tres UUID válidos, únicos y distintos, presentes en el historial (matriz G071, caso 219; RF-72, Salida, líneas 4301-4305).
- **Qué se observó:** Los tres POST devolvieron HTTP 201 y los UUID 8d020402-ccec-419f-b323-9dd605765999, abf573da-0224-464f-9c5d-44927dc980c6 y d58c197e-5184-44d9-a76a-d024665ad829. La lectura posterior del historial fue completa y contenía los tres registros.
- **Por qué APROBADO:** Cada alta produjo un UUID con formato válido; ninguno se repitió y los registros se pudieron localizar en el historial.

Comprobación API-219-01: APROBADO; evidencias newman/newman-G071.json y resultado.json.

### TC-M04-220 — APROBADO

- **Qué se hizo:** Se leyó el resultado d1f3cc43 antes y después de registrar INCORRECTO con patología real 8, distinta de la estimada.
- **Qué se esperaba:** El resultado conserva riesgo, enfermedad estimada, probabilidades, fecha y versión del modelo (matriz G071, caso 220; RF-72, inmutabilidad, líneas 4015-4016; CA-2, línea 4361).
- **Qué se observó:** El POST devolvió HTTP 201. Antes y después se leyeron riesgo 1, patología estimada 10 (Intoxicación hídrica), probabilidades de riesgo 0: 0.15, 1: 0.6, 2: 0.15 y 3: 0.1; probabilidad de enfermedad 10: 0.55; confianza global 0.85; fecha 2026-10-24T19:06:22Z y versión 43. Todos esos valores fueron iguales en ambas lecturas.
- **Por qué APROBADO:** El diagnóstico real diferente quedó en la retroalimentación; la comparación campo por campo no mostró alteración del resultado.

Comprobación API-220-01: APROBADO; evidencias newman/newman-G071.json y resultado.json.

### TC-M04-221 — APROBADO

- **Qué se hizo:** Se intentaron PUT, PATCH y DELETE sobre el registro d58c197e; también PATCH y DELETE en la ruta base. Se consultaron OpenAPI y el historial posterior.
- **Qué se esperaba:** No existe edición ni eliminación y el registro permanece idéntico (matriz G071, caso 221; RF-72, líneas 4018-4019; CA-6, líneas 4369-4374; RNF-04, líneas 4407-4408).
- **Qué se observó:** PUT, PATCH y DELETE por identificador respondieron HTTP 404 en los tres intentos; PATCH y DELETE en la base respondieron HTTP 405 en ambos. OpenAPI devolvió HTTP 200 sin operaciones de edición ni eliminación. El registro d58c197e-5184-44d9-a76a-d024665ad829 conservó sus campos en el historial.
- **Por qué APROBADO:** Ningún intento de modificación tuvo éxito, la API no ofreció una operación para alterar el dato y la lectura posterior confirmó que permanecía igual.

Comprobación API-221-01: APROBADO; evidencias newman/newman-G071.json y resultado.json.

### TC-M04-222 — APROBADO

- **Qué se hizo:** Se contrastaron la respuesta y el historial del registro 511a6d66; se enviaron tres POST negativos: sin token, sin activo para f7fea6d3 y sin resultado para el activo 885.
- **Qué se esperaba:** Resultado, usuario, fecha y activo son obligatorios; se rechazan registros anónimos o incompletos (matriz G071, caso 222; RF-72, trazabilidad, líneas 4080-4085; CA-7, línea 4376; RNF-05, líneas 4410-4411).
- **Qué se observó:** El alta HTTP 201 mostró en respuesta e historial los mismos valores: resultado 511a6d66-a862-4822-bf47-2634333531b3, usuario 97, fecha 2026-10-29T14:31:40.670157Z y activo 885. Sin token se obtuvo HTTP 401; sin activo y sin resultado, HTTP 400 cada uno. El historial posterior no mostró registros nuevos de esos intentos.
- **Por qué APROBADO:** La trazabilidad requerida acompañó al registro en ambas lecturas; los intentos sin autenticación o datos obligatorios fueron rechazados sin persistencia.

Comprobación API-222-01: APROBADO; evidencias newman/newman-G071.json y resultado.json.

### TC-M04-246 — APROBADO

- **Qué se hizo:** Se compararon resultado, alertas, versiones, configuración del motor e inferencias antes y después de registrar INCORRECTO para 5dbe4510 con patología real 8.
- **Qué se esperaba:** El registro se limita a análisis posterior y reentrenamiento; no recalcula el resultado ni modifica alertas o comportamiento posterior (matriz G071, caso 246; RF-72, uso analítico, líneas 4115-4116).
- **Qué se observó:** El POST devolvió HTTP 201. El resultado 5dbe4510-af8e-4ea7-8688-7efa0751800d conservó su snapshot; hubo 0 alertas antes y después y 14 inferencias antes y después, con las mismas identidades. La versión 43 siguió ACTIVO; el motor mantuvo versión activa 43 y config_version 3 en ambas lecturas.
- **Por qué APROBADO:** No hubo cambio observable en el resultado, las alertas, las versiones o la configuración; tampoco aparecieron inferencias nuevas durante la comprobación.

Comprobación API-246-01: APROBADO; evidencias newman/newman-G071.json y resultado.json.

## Intentos Newman

| Intento | HTTP | Código | Mensaje |
|---|---:|---|---|
| 219-1 | 201 | — | — |
| 219-2 | 201 | — | — |
| 219-3 | 201 | — | — |
| 219-read | 200 | — | — |
| 220-before | 200 | — | — |
| 220-post | 201 | — | — |
| 220-after | 200 | — | — |
| 222-anon | 401 | TOKEN_REQUERIDO | Se requiere autenticación. Proporciona un token Bearer válido. |
| 222-no-asset | 400 | VAL_ENTRADA | Errores de validacion en la solicitud |
| 222-no-result | 400 | VAL_ENTRADA | Errores de validacion en la solicitud |
| 221-put-id | 404 | — | — |
| 221-patch-id | 404 | — | — |
| 221-delete-id | 404 | — | — |
| 221-patch-base | 405 | — | — |
| 221-delete-base | 405 | — | — |
| 221-openapi | 200 | — | — |
| 246-before-history | 200 | — | — |
| 246-before-versions | 200 | — | — |
| 246-before-motor | 200 | — | — |
| 246-post | 201 | — | — |
| 246-after-history | 200 | — | — |
| 246-after-versions | 200 | — | — |
| 246-after-motor | 200 | — | — |

## Observaciones

OBS-M04-G071-246 — Los resultados de la semilla no tenían alertas derivadas. La comprobación cubre que no se crea ni cambia ninguna alerta del activo; no demuestra la conservación de una alerta existente. El comportamiento de inferencias posteriores se verificó mediante la versión activa, la configuración del motor y la ausencia de resultados nuevos, sin ejecutar una inferencia. La verificación se hizo por API dentro del sandbox; la matriz sugería BD y no se usó SQL.

La auditoría respondió HTTP 200 y mostró 8 eventos en la página consultada; es un dato de ejecución, separado del criterio del caso 246.

## Incidencias de producto

Ninguna.

## Problemas técnicos y análisis de causas

Ninguno. La revisión de código en origin/test solo orienta la prueba; no demuestra un defecto en TEST ni identifica causa raíz.

## Cierre y rollback

Intento 1; solicitudes 32/149. DELETE HTTP 200. Rollback verificado: DELETE 200; identificadores nuevos ausentes y eventos de retroalimentación, inferencia y alerta iguales al descubrimiento. Las lecturas posteriores pueden generar HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Los cinco casos cumplen sus oráculos. Archivar las evidencias del RUN y conservar la observación de alcance de TC-M04-246 para una futura comprobación con alertas existentes e inferencia posterior, si el responsable QA la ordena.

## Herramientas y evidencias

Newman: 1 iteración; 23 solicitudes; 46 aserciones. Sin UI obligatoria.

- preflight.json
- newman/newman-G071.json
- newman/newman-G071.html
- resultado.json
- TC-M04-G071_resultado.md

## Revisión QA (2026-10-29)

Se aclararon motivos, precondición, acciones y razonamiento por caso; se separó la observación de alcance y se añadieron los intentos Newman con código y mensaje ausentes marcados «—». Los cinco veredictos, resultado.json y newman/ permanecen sin cambios.
