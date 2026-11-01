# TC-M04-G072 — APROBADO

## Identificación

Grupo G072; casos TC-M04-226, TC-M04-227, TC-M04-230; RF-72 y control RF-67; versión 2; RUN RUN-G072-V2-20261101-052705; ambiente TEST; autorización AUT-G072-V2-20261101; código de TEST c31f8a6d920e y migración 7efe47d6c76a informados por QA, sin verificación Git local. Node.js y Newman 6.2.2; solo API.

## Decisión del caso

| Caso | Veredicto | Motivo |
|---|---|---|
| TC-M04-226 | APROBADO | El segundo registro contradice al primero; el indicador, el evento y la conservación de A se cotejan en respuestas y lecturas públicas. |
| TC-M04-227 | APROBADO | Cada respuesta se coteja por identificador, usuario, estado y diagnóstico con un registro de historial; no hay cuarto registro ni evento de consolidación. |
| TC-M04-230 | APROBADO | Cada par conserva sus dos registros y las respuestas y auditoría no señalan conflicto. |

RUN oficial: sí. Qué falta: nada.

## Datos y método

Activo 885; resultados 511a6d66-a862-4822-bf47-2634333531b3, f056f99d-78bf-478d-86f0-5b2ee1a70873, 997b8cda-b608-4bb3-a7d2-ea37cf12b944, d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e, 5dbe4510-af8e-4ea7-8688-7efa0751800d, f7fea6d3-9bc1-49de-a88e-3be75f399b87, 32985675-9bbf-46ae-a37d-dc1833155627, 98c7697c-0cb8-403c-9421-07679e59cac8; patología activa 8. Verificación por historial y auditoría RF-73 de API pública; sin consulta SQL.

## Detalle por caso

### TC-M04-226 — APROBADO

- **Qué se hizo:** Se enviaron CORRECTO por A e INCORRECTO con patología 8 por B sobre 511a6d66-a862-4822-bf47-2634333531b3; se leyeron historial y auditoría.
- **Qué se esperaba:** Dos HTTP 201; B con conflicto y un evento CONFLICTO_RETROALIMENTACION que referencia R1; A intacto y ambos en historial HTTP 200 (TC-M04-226; RF-72, líneas 4053-4061 y CA-14, 4393-4394).
- **Qué se observó:** HTTP 226-A=201, 226-B=201; registros 226-A: id e0ae6f3d-798e-4efc-aef9-8ec4ca057ffb, usuario 97, estado CORRECTO, diagnósticos ninguno, conflicto no; 226-B: id 175d420e-c645-40eb-9bf4-1762f089d3f7, usuario 162, estado INCORRECTO, diagnósticos 8, conflicto sí; historial 2 registros; eventos de conflicto 1; referencias de auditoría 6499564d-e722-494c-ac9b-17542aba74af:511a6d66-a862-4822-bf47-2634333531b3.
- **Por qué APROBADO:** El segundo registro contradice al primero; el indicador, el evento y la conservación de A se cotejan en respuestas y lecturas públicas.
- **V1 → V2:** V1 APROBADO con coexistencia no comprobable en historial; V2 APROBADO con coexistencia verificada en historial.

Comprobación API-226-01: APROBADO; evidencia newman/newman-G072.json y resultado.json.

### TC-M04-227 — APROBADO

- **Qué se hizo:** Se enviaron CORRECTO, PARCIAL e INCORRECTO por A, B y C sobre f056f99d-78bf-478d-86f0-5b2ee1a70873; se leyó historial y auditoría.
- **Qué se esperaba:** Tres registros independientes, íntegros y sin consolidado ni etiqueta ganadora, visibles en historial HTTP 200 (TC-M04-227; RF-72, líneas 4043-4051 y 4065).
- **Qué se observó:** HTTP 227-A=201, 227-B=201, 227-C=201; registros 227-A: id 74f624ea-ea4c-464d-a40b-00be175b7320, usuario 97, estado CORRECTO, diagnósticos ninguno, conflicto no; 227-B: id 616d9074-f240-4d78-84a4-eb9231b349f2, usuario 162, estado PARCIAL, diagnósticos 8, conflicto sí; 227-C: id 863dfe26-664e-48ad-a27f-37d6f513bea3, usuario 163, estado INCORRECTO, diagnósticos 8, conflicto sí; historial 3 registros; eventos de conflicto 2; referencias de auditoría 2e51b72c-7ccb-4d2a-860b-f721ea40aa46:f056f99d-78bf-478d-86f0-5b2ee1a70873, b9d208b6-25c7-4efc-8da6-92c30583dd5f:f056f99d-78bf-478d-86f0-5b2ee1a70873.
- **Por qué APROBADO:** Cada respuesta se coteja por identificador, usuario, estado y diagnóstico con un registro de historial; no hay cuarto registro ni evento de consolidación.
- **V1 → V2:** V1 APROBADO con coexistencia no comprobable en historial; V2 APROBADO con coexistencia verificada en historial.

Comprobación API-227-01: APROBADO; evidencia newman/newman-G072.json y resultado.json.

### TC-M04-230 — APROBADO

- **Qué se hizo:** A y B enviaron CORRECTO sobre 997b8cda-b608-4bb3-a7d2-ea37cf12b944 e INCORRECTO con la misma patología 8 sobre d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e; se leyeron historial y auditoría.
- **Qué se esperaba:** Dos evaluaciones iguales por resultado coexisten tras HTTP 201, sin flag ni evento de conflicto; historial inicial y posterior HTTP 200 (TC-M04-230; RF-72, líneas 4024 y 4053-4061).
- **Qué se observó:** HTTP 230a-A=201, 230a-B=201, 230b-A=201, 230b-B=201; registros 230a-A: id 30987145-d035-46ea-b808-0e9148db456b, usuario 97, estado CORRECTO, diagnósticos ninguno, conflicto no; 230a-B: id c1224fe4-3802-46f8-b427-89495a61fd7a, usuario 162, estado CORRECTO, diagnósticos ninguno, conflicto no; 230b-A: id eea5c708-fa7b-499c-bc22-cd8a73bc7989, usuario 97, estado INCORRECTO, diagnósticos 8, conflicto no; 230b-B: id a2ac9be4-97f1-45b4-9dd5-3172f42b24cd, usuario 162, estado INCORRECTO, diagnósticos 8, conflicto no; historial 2/2 registros; eventos de conflicto 0/0; referencias de auditoría ninguna.
- **Por qué APROBADO:** Cada par conserva sus dos registros y las respuestas y auditoría no señalan conflicto.
- **V1 → V2:** V1 RECHAZADO por GET 500 tras 230a-B; V2 APROBADO según la lectura y los registros de este RUN.

Comprobación API-230-01: APROBADO; evidencia newman/newman-G072.json y resultado.json.

## Intentos Newman

| Intento | HTTP | Registro | Conflicto |
|---|---:|---|---|
| 230a-A | 201 | 30987145-d035-46ea-b808-0e9148db456b | false |
| 230a-B | 201 | c1224fe4-3802-46f8-b427-89495a61fd7a | false |
| 230b-A | 201 | eea5c708-fa7b-499c-bc22-cd8a73bc7989 | false |
| 230b-B | 201 | a2ac9be4-97f1-45b4-9dd5-3172f42b24cd | false |
| 226-A | 201 | e0ae6f3d-798e-4efc-aef9-8ec4ca057ffb | false |
| 226-B | 201 | 175d420e-c645-40eb-9bf4-1762f089d3f7 | true |
| 227-A | 201 | 74f624ea-ea4c-464d-a40b-00be175b7320 | false |
| 227-B | 201 | 616d9074-f240-4d78-84a4-eb9231b349f2 | true |
| 227-C | 201 | 863dfe26-664e-48ad-a27f-37d6f513bea3 | true |

## Lecturas del historial

GET inicial: HTTP 200, lectura completa.

| Momento | HTTP | Código y mensaje | Registros visibles por resultado (id/usuario/estado) |
|---|---:|---|---|
| 230a (tras 230a-B) | 200 | —:  | 511a6d66-a862-4822-bf47-2634333531b3: 0; f056f99d-78bf-478d-86f0-5b2ee1a70873: 0; 997b8cda-b608-4bb3-a7d2-ea37cf12b944: c1224fe4-3802-46f8-b427-89495a61fd7a/162/CORRECTO, 30987145-d035-46ea-b808-0e9148db456b/97/CORRECTO; d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e: 0; 5dbe4510-af8e-4ea7-8688-7efa0751800d: 0; f7fea6d3-9bc1-49de-a88e-3be75f399b87: 0; 32985675-9bbf-46ae-a37d-dc1833155627: 0; 98c7697c-0cb8-403c-9421-07679e59cac8: 0 |
| 230b (tras 230b-B) | 200 | —:  | 511a6d66-a862-4822-bf47-2634333531b3: 0; f056f99d-78bf-478d-86f0-5b2ee1a70873: 0; 997b8cda-b608-4bb3-a7d2-ea37cf12b944: c1224fe4-3802-46f8-b427-89495a61fd7a/162/CORRECTO, 30987145-d035-46ea-b808-0e9148db456b/97/CORRECTO; d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e: eea5c708-fa7b-499c-bc22-cd8a73bc7989/97/INCORRECTO, a2ac9be4-97f1-45b4-9dd5-3172f42b24cd/162/INCORRECTO; 5dbe4510-af8e-4ea7-8688-7efa0751800d: 0; f7fea6d3-9bc1-49de-a88e-3be75f399b87: 0; 32985675-9bbf-46ae-a37d-dc1833155627: 0; 98c7697c-0cb8-403c-9421-07679e59cac8: 0 |
| 226 (tras 226-B) | 200 | —:  | 511a6d66-a862-4822-bf47-2634333531b3: e0ae6f3d-798e-4efc-aef9-8ec4ca057ffb/97/CORRECTO, 175d420e-c645-40eb-9bf4-1762f089d3f7/162/INCORRECTO; f056f99d-78bf-478d-86f0-5b2ee1a70873: 0; 997b8cda-b608-4bb3-a7d2-ea37cf12b944: c1224fe4-3802-46f8-b427-89495a61fd7a/162/CORRECTO, 30987145-d035-46ea-b808-0e9148db456b/97/CORRECTO; d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e: eea5c708-fa7b-499c-bc22-cd8a73bc7989/97/INCORRECTO, a2ac9be4-97f1-45b4-9dd5-3172f42b24cd/162/INCORRECTO; 5dbe4510-af8e-4ea7-8688-7efa0751800d: 0; f7fea6d3-9bc1-49de-a88e-3be75f399b87: 0; 32985675-9bbf-46ae-a37d-dc1833155627: 0; 98c7697c-0cb8-403c-9421-07679e59cac8: 0 |
| 227_parcial (tras 227-B) | 200 | —:  | 511a6d66-a862-4822-bf47-2634333531b3: e0ae6f3d-798e-4efc-aef9-8ec4ca057ffb/97/CORRECTO, 175d420e-c645-40eb-9bf4-1762f089d3f7/162/INCORRECTO; f056f99d-78bf-478d-86f0-5b2ee1a70873: 74f624ea-ea4c-464d-a40b-00be175b7320/97/CORRECTO, 616d9074-f240-4d78-84a4-eb9231b349f2/162/PARCIAL; 997b8cda-b608-4bb3-a7d2-ea37cf12b944: c1224fe4-3802-46f8-b427-89495a61fd7a/162/CORRECTO, 30987145-d035-46ea-b808-0e9148db456b/97/CORRECTO; d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e: eea5c708-fa7b-499c-bc22-cd8a73bc7989/97/INCORRECTO, a2ac9be4-97f1-45b4-9dd5-3172f42b24cd/162/INCORRECTO; 5dbe4510-af8e-4ea7-8688-7efa0751800d: 0; f7fea6d3-9bc1-49de-a88e-3be75f399b87: 0; 32985675-9bbf-46ae-a37d-dc1833155627: 0; 98c7697c-0cb8-403c-9421-07679e59cac8: 0 |
| 227_final (tras 227-C) | 200 | —:  | 511a6d66-a862-4822-bf47-2634333531b3: e0ae6f3d-798e-4efc-aef9-8ec4ca057ffb/97/CORRECTO, 175d420e-c645-40eb-9bf4-1762f089d3f7/162/INCORRECTO; f056f99d-78bf-478d-86f0-5b2ee1a70873: 863dfe26-664e-48ad-a27f-37d6f513bea3/163/INCORRECTO, 74f624ea-ea4c-464d-a40b-00be175b7320/97/CORRECTO, 616d9074-f240-4d78-84a4-eb9231b349f2/162/PARCIAL; 997b8cda-b608-4bb3-a7d2-ea37cf12b944: c1224fe4-3802-46f8-b427-89495a61fd7a/162/CORRECTO, 30987145-d035-46ea-b808-0e9148db456b/97/CORRECTO; d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e: eea5c708-fa7b-499c-bc22-cd8a73bc7989/97/INCORRECTO, a2ac9be4-97f1-45b4-9dd5-3172f42b24cd/162/INCORRECTO; 5dbe4510-af8e-4ea7-8688-7efa0751800d: 0; f7fea6d3-9bc1-49de-a88e-3be75f399b87: 0; 32985675-9bbf-46ae-a37d-dc1833155627: 0; 98c7697c-0cb8-403c-9421-07679e59cac8: 0 |

No hubo lectura HTTP 500.

## Control complementario de aislamiento RF-67

Estado NO_CONCLUYENTE. Activo 811 de finca 3; Veterinario A recibió HTTP 200 y 0 eventos. Respuesta HTTP 200 sin prueba concluyente de segregación. Este control no modifica los oráculos de 226, 227 y 230.

## Seguimiento de la corrección

Issue #869 / PR #871: política RLS de INSERT del historial diagnóstico informada por Desarrollo y DBA. INC-M04-G072-230-01: CORREGIDA según la evidencia de este RUN. Esta clasificación no atribuye causa raíz al resultado actual.

## Historial de intentos

- RUN-G072-V1-20261029-161515: intento técnico conservado, GET posterior 500 ERROR_INTERNO.
- RUN-G072-V1-20261029-165112: V1 oficial; 226 y 227 APROBADO con limitación del historial, 230 RECHAZADO por GET 500 tras 230a-B.
- Intento 3, RUN-G072-V2-20261101-052705: oficial; clasificación según las lecturas registradas en este RUN.

## Observaciones

OBS-M04-G072-227: la tercera respuesta para f056f99d-78bf-478d-86f0-5b2ee1a70873 indicó conflicto sí al añadirse INCORRECTO tras PARCIAL y CORRECTO. Es una observación; el oráculo de conflicto se decide en TC-M04-226.

OBS-M04-G072-HIST: el HTTP 500 del intento 1 no se reprodujo.

## Incidencias de producto

Ninguna.

## Problemas técnicos y análisis de causas

Ninguno. Los fallos técnicos se separan de discrepancias de producto. El antecedente RLS de V1 proviene del informe QA; se contrasta con la evidencia de este RUN.

## Cierre y rollback

Intento 3; solicitudes 46/414. DELETE HTTP 200. Rollback verificado: DELETE 200; identificadores nuevos ausentes e historial inicial restaurado. Las lecturas poscierre pueden generar HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Los tres casos cumplen; revisar además el control RF-67 y archivar evidencia.

## Herramientas y evidencias

Newman: 1 iteración; 14 solicitudes; 28 aserciones. Sin UI obligatoria.

- preflight.json
- newman/newman-G072.json
- newman/newman-G072.html
- resultado.json
- TC-M04-G072_reevaluacion_V2.md
