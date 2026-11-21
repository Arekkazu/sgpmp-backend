# TC-M04-G068 — APROBADO

## Identificación

Grupo G068; casos TC-M04-210, TC-M04-211, TC-M04-245; RF-72; versión 2; RUN RUN-G068-V2-20261101-033408; ambiente TEST; autorización AUT-G068-V2-20261101; Commit de TEST: no verificado por el ejecutor; corrección informada en issue #863 / PR #871. Node.js y Newman. Solo API.

## Decisión del caso

| Caso | Decisión | Motivo |
|---|---|---|
| TC-M04-210 | APROBADO | HTTP 404 RESULTADO_INFERENCIA_NO_ENCONTRADO con el mensaje «El resultado de inferencia no existe o no está disponible.»; sin retroalimentación ni RETROALIMENTACION_REGISTRADA en historial y auditoría |
| TC-M04-211 | APROBADO | rechazo HTTP 422 ACTIVO_BIOLOGICO_INCONSISTENTE con el mensaje «El activo biológico no corresponde al resultado de inferencia indicado.»; sin registro; RF-72 no fija código |
| TC-M04-245 | APROBADO | rechazo HTTP 422 ACTIVO_EN_BAJA con el mensaje «El activo biológico 885 está en estado BAJA y no admite retroalimentación clínica.»; sin registro en historial ni auditoría |

RUN oficial: sí. Cada caso tuvo POST y comprobación de historial y auditoría; los veredictos se basan en las respuestas y la persistencia observadas. El ensayo local no acredita TEST.

Qué falta: ninguno.

## Precondición de datos (semilla y baja temporal)

Activo 885, modelo INDIVIDUAL; otro activo 928 (QA-G98-IND-001). Resultados libres 14; eventos examinados 14; páginas 1; cursor pendiente no. Fase antes: sin fase activa; Activo 885 sin fase activa antes de la baja. durante: sin fase activa. Baja HTTP 201; estado durante baja BAJA; BAJA_REGISTRADA en sandbox sí. El buffer local RF-52 puede conservar una copia fuera del sandbox si falla la BD o hay alta carga.

## Detalle por caso

### TC-M04-210 — APROBADO

- Qué se hizo: POST Newman con UUID v4 inexistente.
- Qué se esperaba: Resultado esperado del caso y RF-72 E1 4234-4239: HTTP 404, "El resultado de inferencia no existe o no está disponible."; se cancela sin registro ni evento.
- Qué se observó: HTTP 404; RESULTADO_INFERENCIA_NO_ENCONTRADO; El resultado de inferencia no existe o no está disponible.; persistió no.
- Por qué APROBADO: HTTP 404 RESULTADO_INFERENCIA_NO_ENCONTRADO con el mensaje «El resultado de inferencia no existe o no está disponible.»; sin retroalimentación ni RETROALIMENTACION_REGISTRADA en historial y auditoría. Evidencia: API-210-01 en resultado.json.

### TC-M04-211 — APROBADO

- Qué se hizo: POST Newman con resultado libre del 885 y otro activo existente.
- Qué se esperaba: Resultado esperado del caso y RF-72 4161: rechazo indicando que el activo no corresponde al resultado, sin persistir. RF-72 no fija HTTP.
- Qué se observó: HTTP 422; ACTIVO_BIOLOGICO_INCONSISTENTE; El activo biológico no corresponde al resultado de inferencia indicado.; persistió no.
- Por qué APROBADO: rechazo HTTP 422 ACTIVO_BIOLOGICO_INCONSISTENTE con el mensaje «El activo biológico no corresponde al resultado de inferencia indicado.»; sin registro; RF-72 no fija código. Evidencia: API-211-01 en resultado.json.

### TC-M04-245 — APROBADO

- Qué se hizo: Baja temporal del 885, lectura de estado y bitácora, y POST condicional en una ejecución Newman.
- Qué se esperaba: Resultado esperado del caso y RF-72 restricción 4112-4113: con baja acreditada, rechazo 4xx que identifique el activo, sin retroalimentación ni RETROALIMENTACION_REGISTRADA. La corrección de Desarrollo informa 422 ACTIVO_EN_BAJA y campo id_activo_biologico; RF-72 no fija HTTP.
- Qué se observó: HTTP 422; ACTIVO_EN_BAJA; El activo biológico 885 está en estado BAJA y no admite retroalimentación clínica.; persistió no.
- Por qué APROBADO: rechazo HTTP 422 ACTIVO_EN_BAJA con el mensaje «El activo biológico 885 está en estado BAJA y no admite retroalimentación clínica.»; sin registro en historial ni auditoría. Evidencia: API-245-01 en resultado.json.

## Tabla de intentos

| Caso | Resultado | Cuerpo resumido | HTTP | Código y mensaje | Persistió |
|---|---|---|---|---|---|
| TC-M04-210 | dee00456 | CORRECTO sin diagnóstico; activo 885 | 404 | RESULTADO_INFERENCIA_NO_ENCONTRADO; El resultado de inferencia no existe o no está disponible. | no |
| TC-M04-211 | 511a6d66 | CORRECTO sin diagnóstico; activo 928 | 422 | ACTIVO_BIOLOGICO_INCONSISTENTE; El activo biológico no corresponde al resultado de inferencia indicado. | no |
| TC-M04-245 | f056f99d | CORRECTO sin diagnóstico; activo 885 | 422 | ACTIVO_EN_BAJA; El activo biológico 885 está en estado BAJA y no admite retroalimentación clínica. | no |



## Comparación V1 → V2

| Caso | V1 oficial | V2 |
|---|---|---|
| TC-M04-210 | APROBADO | APROBADO |
| TC-M04-211 | APROBADO | APROBADO |
| TC-M04-245 | RECHAZADO | APROBADO |

V1: RUN-G068-V1-20261029-121139. INC-M04-G068-245-01: CORREGIDA según comprobación pública V2. Corrección informada por Desarrollo en issue #863 / PR #871.

## Observaciones

Ninguna.

## Incidencias de producto

Sin incidencias de producto.

## Problemas técnicos y análisis de causas

Ninguno. La derivación inicial se basa en la primera discrepancia pública; causa raíz no determinada.

## Historial, cierre y rollback

25 solicitudes. DELETE HTTP 200; rollback verificado: Ausencia de registros y estado/fase 885 concordantes poscierre. Activo 885 poscierre ACTIVO, fase sin fase activa. Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Conservar la evidencia del cierre y comunicar al responsable QA la reevaluación V2.

## Herramientas

Newman 6.2.2: 1 iteración, 6 solicitudes y 14 aserciones. Reportes JSON y HTML generados en newman/. Login, descubrimiento, lecturas de verificación y cierre por fetch.

## Evidencias

- preflight.json
- resultado.json
- TC-M04-G068_reevaluacion_V2.md
- newman/newman-G068.json
- newman/newman-G068.html
