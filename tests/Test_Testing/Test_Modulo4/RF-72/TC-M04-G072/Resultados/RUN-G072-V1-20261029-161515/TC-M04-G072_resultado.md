# TC-M04-G072 — NO OFICIAL

## Identificación

Grupo G072; casos TC-M04-226, TC-M04-227, TC-M04-230; RF-72; versión 1; RUN RUN-G072-V1-20261029-161515; ambiente TEST; autorización AUT-G072-V1-20261029; commit revisado origin/test daefc3a5c62771c8952706ae7a7fe128e66b0b02. Node.js y Newman 6.2.2; solo API.

## Decisión del caso

| Caso | Veredicto | Motivo |
|---|---|---|
| TC-M04-226 | NO_CONCLUYENTE | Falta lectura pública completa para concluir |
| TC-M04-227 | NO_CONCLUYENTE | Falta lectura pública completa para concluir |
| TC-M04-230 | NO_CONCLUYENTE | Falta lectura pública completa para concluir |

RUN oficial: no. Qué falta: completar respuestas y lecturas públicas, y verificar el rollback.

## Datos y método

Activo 885; resultados 511a6d66-a862-4822-bf47-2634333531b3, f056f99d-78bf-478d-86f0-5b2ee1a70873, 997b8cda-b608-4bb3-a7d2-ea37cf12b944, d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e, 5dbe4510-af8e-4ea7-8688-7efa0751800d, f7fea6d3-9bc1-49de-a88e-3be75f399b87, 32985675-9bbf-46ae-a37d-dc1833155627, 98c7697c-0cb8-403c-9421-07679e59cac8; patología activa 8. Verificación por historial y auditoría RF-73 de API pública; la matriz sugería BD y no se usó SQL.

## Detalle por caso

### TC-M04-226 — NO_CONCLUYENTE

- **Qué se hizo:** Se enviaron CORRECTO por A e INCORRECTO con patología 8 por B sobre 511a6d66-a862-4822-bf47-2634333531b3; se leyeron historial y auditoría.
- **Qué se esperaba:** Dos HTTP 201; B con conflicto y un evento CONFLICTO_RETROALIMENTACION que referencia R1; A intacto (matriz G072, TC-M04-226; RF-72, líneas 4053-4061 y CA-14, 4393-4394).
- **Qué se observó:** HTTP 226-A=201, 226-B=201; registros 226-A: id df6e414a-8df8-4f0d-b922-638181b4f1ba, usuario 97, estado CORRECTO, diagnósticos null, conflicto no; 226-B: id 621fc875-f611-4d97-b4fa-ce8e4b117294, usuario 162, estado INCORRECTO, diagnósticos [8], conflicto sí; historial sin lectura registros; eventos de conflicto 1; referencias de auditoría cec0a97e-29a0-4aa0-9b48-0d34c6658781:511a6d66-a862-4822-bf47-2634333531b3.
- **Por qué NO_CONCLUYENTE:** Falta lectura pública completa para concluir

Comprobación API-226-01: NO_CONCLUYENTE; evidencia newman/newman-G072.json y resultado.json.

### TC-M04-227 — NO_CONCLUYENTE

- **Qué se hizo:** Se enviaron CORRECTO, PARCIAL e INCORRECTO por A, B y C sobre f056f99d-78bf-478d-86f0-5b2ee1a70873; se leyó historial y auditoría.
- **Qué se esperaba:** Tres registros independientes, íntegros y sin consolidado ni etiqueta ganadora (matriz G072, TC-M04-227; RF-72, líneas 4043-4051 y 4065).
- **Qué se observó:** HTTP 227-A=201, 227-B=201, 227-C=201; registros 227-A: id ee505c5b-56bb-43ed-9970-cbf9dc4e54de, usuario 97, estado CORRECTO, diagnósticos null, conflicto no; 227-B: id 6eedab1a-6caf-4c17-b762-26e525710d8a, usuario 162, estado PARCIAL, diagnósticos [8], conflicto sí; 227-C: id f75fa305-dbed-40fb-b425-723959342aee, usuario 163, estado INCORRECTO, diagnósticos [8], conflicto sí; historial sin lectura registros; eventos de conflicto 2; referencias de auditoría 5c70749d-a68d-467e-97ba-d66cc5e9c812:f056f99d-78bf-478d-86f0-5b2ee1a70873, e05b5df1-d341-49bc-bc62-47a1ace05a00:f056f99d-78bf-478d-86f0-5b2ee1a70873.
- **Por qué NO_CONCLUYENTE:** Falta lectura pública completa para concluir

Comprobación API-227-01: NO_CONCLUYENTE; evidencia newman/newman-G072.json y resultado.json.

### TC-M04-230 — NO_CONCLUYENTE

- **Qué se hizo:** A y B enviaron CORRECTO sobre 997b8cda-b608-4bb3-a7d2-ea37cf12b944 e INCORRECTO con la misma patología 8 sobre d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e; se leyeron historial y auditoría.
- **Qué se esperaba:** Dos evaluaciones iguales por resultado coexisten, sin flag ni evento de conflicto (matriz G072, TC-M04-230; RF-72, líneas 4024 y 4053-4061).
- **Qué se observó:** HTTP 230a-A=201, 230a-B=201, 230b-A=201, 230b-B=201; registros 230a-A: id 181d484c-6ee8-4677-8aab-0c8e5f8471fa, usuario 97, estado CORRECTO, diagnósticos null, conflicto no; 230a-B: id 7fcdea7b-2369-45d8-8e5c-6743b57b4603, usuario 162, estado CORRECTO, diagnósticos null, conflicto no; 230b-A: id 33f7d22b-ca73-44ea-88aa-d8845a0510eb, usuario 97, estado INCORRECTO, diagnósticos [8], conflicto no; 230b-B: id 9ea85588-d518-4bf9-8deb-833cfd31ad1c, usuario 162, estado INCORRECTO, diagnósticos [8], conflicto no; historial sin lectura/sin lectura registros; eventos de conflicto 0/0; referencias de auditoría ninguna.
- **Por qué NO_CONCLUYENTE:** Falta lectura pública completa para concluir

Comprobación API-230-01: NO_CONCLUYENTE; evidencia newman/newman-G072.json y resultado.json.

## Intentos Newman

| Intento | HTTP | Registro | Conflicto |
|---|---:|---|---|
| 226-A | 201 | df6e414a-8df8-4f0d-b922-638181b4f1ba | false |
| 226-B | 201 | 621fc875-f611-4d97-b4fa-ce8e4b117294 | true |
| 227-A | 201 | ee505c5b-56bb-43ed-9970-cbf9dc4e54de | false |
| 227-B | 201 | 6eedab1a-6caf-4c17-b762-26e525710d8a | true |
| 227-C | 201 | f75fa305-dbed-40fb-b425-723959342aee | true |
| 230a-A | 201 | 181d484c-6ee8-4677-8aab-0c8e5f8471fa | false |
| 230a-B | 201 | 7fcdea7b-2369-45d8-8e5c-6743b57b4603 | false |
| 230b-A | 201 | 33f7d22b-ca73-44ea-88aa-d8845a0510eb | false |
| 230b-B | 201 | 9ea85588-d518-4bf9-8deb-833cfd31ad1c | false |

## Observaciones

OBS-M04-G072-227: la tercera respuesta para f056f99d-78bf-478d-86f0-5b2ee1a70873 indicó conflicto sí al añadirse INCORRECTO tras PARCIAL y CORRECTO. Es una observación; el oráculo de conflicto se decide en TC-M04-226.

## Incidencias de producto

Ninguna.

## Problemas técnicos y análisis de causas

Ninguno. La revisión de origin/test orienta la prueba y no demuestra por sí sola un defecto en TEST ni una causa raíz.

## Cierre y rollback

Intento 1; solicitudes 35/152. DELETE HTTP 200. Rollback verificado: DELETE 200; identificadores nuevos ausentes e historial inicial restaurado. Las lecturas poscierre pueden generar HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Resolver los impedimentos técnicos o lecturas pendientes y repetir con autorización particular.

## Herramientas y evidencias

Newman: 1 iteración; 9 solicitudes; 18 aserciones. Sin UI obligatoria.

- preflight.json
- newman/newman-G072.json
- newman/newman-G072.html
- resultado.json
- TC-M04-G072_resultado.md
