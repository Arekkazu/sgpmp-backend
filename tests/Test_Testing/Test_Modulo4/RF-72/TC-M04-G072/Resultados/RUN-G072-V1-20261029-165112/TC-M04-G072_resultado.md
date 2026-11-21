# TC-M04-G072 — RECHAZADO

## Identificación

Grupo G072; casos TC-M04-226, TC-M04-227, TC-M04-230; RF-72; versión 1; RUN RUN-G072-V1-20261029-165112; ambiente TEST; autorización AUT-G072-V1-R2-20261029; referencia de codigo origin/test daefc3a5c62771c8952706ae7a7fe128e66b0b02 aportada en la orden, sin verificacion Git local. Node.js y Newman 6.2.2; solo API.

## Decisión del caso

| Caso | Veredicto | Motivo |
|---|---|---|
| TC-M04-226 | APROBADO | A y B registraron evaluaciones contradictorias con HTTP 201; la respuesta de B marcó conflicto y la auditoría registró CONFLICTO_RETROALIMENTACION. La coexistencia no pudo verse en el historial por la incidencia. |
| TC-M04-227 | APROBADO | A, B y C registraron evaluaciones independientes con HTTP 201 y sus identificadores y usuarios constan en respuestas y auditoría; no se observó consolidación en esas fuentes. La coexistencia no pudo verse en el historial por la incidencia. |
| TC-M04-230 | RECHAZADO | La primera discrepancia fue GET /prediccion/historial/885: HTTP 500 ERROR_INTERNO tras 230a-B, cuando debía permitir consultar los dos registros. Los dos pares iguales se registraron con HTTP 201, sin flag ni evento de conflicto. |

RUN oficial: sí; el resultado de TC-M04-230 exige corrección y nueva comprobación autorizada. Los veredictos coinciden con resultado.json; esta revisión documental añade la causa confirmada después de generar ese archivo, sin modificarlo.

## Datos y método

Activo 885; resultados 511a6d66-a862-4822-bf47-2634333531b3, f056f99d-78bf-478d-86f0-5b2ee1a70873, 997b8cda-b608-4bb3-a7d2-ea37cf12b944, d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e, 5dbe4510-af8e-4ea7-8688-7efa0751800d, f7fea6d3-9bc1-49de-a88e-3be75f399b87, 32985675-9bbf-46ae-a37d-dc1833155627, 98c7697c-0cb8-403c-9421-07679e59cac8; patología activa 8. Verificación por historial y auditoría RF-73 de API pública; la matriz sugería BD y no se usó SQL.

## Detalle por caso

### TC-M04-226 — APROBADO

- **Qué se hizo:** Se enviaron CORRECTO por A e INCORRECTO con patología 8 por B sobre 511a6d66-a862-4822-bf47-2634333531b3; se leyeron historial y auditoría.
- **Qué se esperaba:** Dos HTTP 201; B con conflicto y un evento CONFLICTO_RETROALIMENTACION que referencia R1; A intacto (matriz G072, TC-M04-226; RF-72, líneas 4053-4061 y CA-14, 4393-4394).
- **Qué se observó:** HTTP 226-A=201, 226-B=201; registros 226-A: id 382d503d-a5e8-4db0-95dc-b28fba56ab3c, usuario 97, estado CORRECTO, diagnósticos null, conflicto no; 226-B: id 4c179a4b-ca40-40f0-88d0-1264f23c0b4a, usuario 162, estado INCORRECTO, diagnósticos [8], conflicto sí; historial sin lectura registros; eventos de conflicto 1; referencias de auditoría 942708e9-6257-4a3d-aa15-df8b93d58ad3:511a6d66-a862-4822-bf47-2634333531b3. La parte visible solo en historial no estuvo disponible por la incidencia.
- **Por qué APROBADO:** Las respuestas POST y la auditoría RF-73 acreditan el indicador de conflicto, el evento CONFLICTO_RETROALIMENTACION referido al resultado y los dos registros por usuario. La coexistencia de A y B no pudo verse en el historial porque GET respondió 500; esta limitación queda atribuida a INC-M04-G072-230-01.

Comprobación API-226-01: APROBADO; evidencia newman/newman-G072.json y resultado.json.

### TC-M04-227 — APROBADO

- **Qué se hizo:** Se enviaron CORRECTO, PARCIAL e INCORRECTO por A, B y C sobre f056f99d-78bf-478d-86f0-5b2ee1a70873; se leyó historial y auditoría.
- **Qué se esperaba:** Tres registros independientes, íntegros y sin consolidado ni etiqueta ganadora (matriz G072, TC-M04-227; RF-72, líneas 4043-4051 y 4065).
- **Qué se observó:** HTTP 227-A=201, 227-B=201, 227-C=201; registros 227-A: id d172509f-fe78-4a31-a798-023a409292c6, usuario 97, estado CORRECTO, diagnósticos null, conflicto no; 227-B: id 495604ce-3089-48ef-94a9-77fd573c4f6f, usuario 162, estado PARCIAL, diagnósticos [8], conflicto sí; 227-C: id c3a4b25c-df7e-4780-81bb-9a1d2acc3e6e, usuario 163, estado INCORRECTO, diagnósticos [8], conflicto sí; historial sin lectura registros; eventos de conflicto 2; referencias de auditoría f9a3e915-74f7-4fb5-8a6f-31c04b30d966:f056f99d-78bf-478d-86f0-5b2ee1a70873, c5af329b-784a-42da-a2f2-5d25500e73e2:f056f99d-78bf-478d-86f0-5b2ee1a70873. La parte visible solo en historial no estuvo disponible por la incidencia.
- **Por qué APROBADO:** Las respuestas POST y la auditoría RF-73 acreditan tres identificadores y usuarios distintos, sus estados y los eventos de conflicto de B y C; no muestran un cuarto registro ni un consolidado. La coexistencia íntegra no pudo verse en el historial porque GET respondió 500; esta limitación queda atribuida a INC-M04-G072-230-01.

Comprobación API-227-01: APROBADO; evidencia newman/newman-G072.json y resultado.json.

### TC-M04-230 — RECHAZADO

- **Qué se hizo:** A y B enviaron CORRECTO sobre 997b8cda-b608-4bb3-a7d2-ea37cf12b944 e INCORRECTO con la misma patología 8 sobre d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e; se leyeron historial y auditoría.
- **Qué se esperaba:** Dos evaluaciones iguales por resultado coexisten, sin flag ni evento de conflicto (matriz G072, TC-M04-230; RF-72, líneas 4024 y 4053-4061).
- **Qué se observó:** HTTP 230a-A=201, 230a-B=201, 230b-A=201, 230b-B=201; registros 230a-A: id e3199174-5d15-42f3-9faa-a8beecc2af1b, usuario 97, estado CORRECTO, diagnósticos null, conflicto no; 230a-B: id 434fb8db-781e-4931-ade3-9d89218b9078, usuario 162, estado CORRECTO, diagnósticos null, conflicto no; 230b-A: id 484b981a-5a6a-4579-ad87-27a7e2b10fd5, usuario 97, estado INCORRECTO, diagnósticos [8], conflicto no; 230b-B: id c427166c-c902-4b8d-b297-5685d12d9b2d, usuario 162, estado INCORRECTO, diagnósticos [8], conflicto no; historial sin lectura/sin lectura registros; eventos de conflicto 0/0; referencias de auditoría ninguna.
- **Por qué RECHAZADO:** La primera consulta del historial posterior a 230a-B respondió HTTP 500 ERROR_INTERNO e impidió comprobar allí la coexistencia de las dos evaluaciones iguales. El registro de los dos pares sí cumplió la regla de ausencia de conflicto: cuatro POST 201, cuatro flags negativos y cero eventos de conflicto en auditoría. El fallo de consulta incumple RF-72 CA-8 y RF-67.

Comprobación API-230-01: RECHAZADO; evidencia newman/newman-G072.json y resultado.json.

## Intentos Newman

| Intento | HTTP | Registro | Conflicto |
|---|---:|---|---|
| 230a-A | 201 | e3199174-5d15-42f3-9faa-a8beecc2af1b | false |
| 230a-B | 201 | 434fb8db-781e-4931-ade3-9d89218b9078 | false |
| 230b-A | 201 | 484b981a-5a6a-4579-ad87-27a7e2b10fd5 | false |
| 230b-B | 201 | c427166c-c902-4b8d-b297-5685d12d9b2d | false |
| 226-A | 201 | 382d503d-a5e8-4db0-95dc-b28fba56ab3c | false |
| 226-B | 201 | 4c179a4b-ca40-40f0-88d0-1264f23c0b4a | true |
| 227-A | 201 | d172509f-fe78-4a31-a798-023a409292c6 | false |
| 227-B | 201 | 495604ce-3089-48ef-94a9-77fd573c4f6f | true |
| 227-C | 201 | c3a4b25c-df7e-4780-81bb-9a1d2acc3e6e | true |

## Lecturas del historial

| Momento | HTTP | Código y mensaje | Registros visibles por resultado (id/usuario/estado) |
|---|---:|---|---|
| 230a (tras 230a-B) | 500 | ERROR_INTERNO: Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte. | no disponibles |
| 230b (tras 230b-B) | 500 | ERROR_INTERNO: Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte. | no disponibles |
| 226 (tras 226-B) | 500 | ERROR_INTERNO: Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte. | no disponibles |
| 227_parcial (tras 227-B) | 500 | ERROR_INTERNO: Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte. | no disponibles |
| 227_final (tras 227-C) | 500 | ERROR_INTERNO: Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte. | no disponibles |

Primera lectura HTTP 500: 230a, tras 230a-B; disparador de TC-M04-230. El HTTP 500 persistió en todas las lecturas siguientes hasta el DELETE.

## Historial de intentos

- Intento 1, RUN-G072-V1-20261029-161515 (16:15 UTC): TÉCNICO; los nueve POST respondieron 201 y la única lectura posterior del historial respondió 500 ERROR_INTERNO. El log TEST aportado por el responsable QA identifica el rechazo RLS del INSERT. La evidencia nativa se conserva en `Resultados/RUN-G072-V1-20261029-161515/` hasta que el responsable QA decida su limpieza; el DELETE 200 y la comprobación de rollback constan en ese intento.
- Intento 2, RUN-G072-V1-20261029-165112 (16:51 UTC): oficial; el historial respondió 200 antes de los POST y 500 ERROR_INTERNO en sus cinco lecturas posteriores. La auditoría, los nueve POST y las lecturas poscierre respondieron correctamente; el rollback figura verificado en resultado.json.

## Observaciones

OBS-M04-G072-227: la tercera respuesta para f056f99d-78bf-478d-86f0-5b2ee1a70873 indicó conflicto sí al añadirse INCORRECTO tras PARCIAL y CORRECTO. Es una observación; el oráculo de conflicto se decide en TC-M04-226.

OBS-M04-G072-HIST: HTTP 500 persistente desde 230a-B hasta el DELETE en todas las lecturas posteriores.

## Incidencias de producto

### INC-M04-G072-230-01

**Título:** La consulta del historial diagnóstico responde HTTP 500 tras registrar retroalimentaciones: la materialización de eventos viola la RLS de `historial_diagnostico_eventos`.

**Caso, severidad y certeza:** TC-M04-230; **ALTA**, **CONFIRMADA**. En TEST, un Veterinario no puede consultar el historial de un activo en cuanto hay una retroalimentación u otro evento nuevo sin materializar. Esto bloquea la consulta exigida por RF-67 y RF-72 CA-8 (línea 4378), así como la revisión clínica de conflictos prevista en la Regla 3 (líneas 4043-4051). Las escrituras y el rollback comprobados no muestran pérdida de datos; por eso la severidad es ALTA y no CRÍTICA. La certeza se refiere al fallo y al mecanismo de RLS documentado; no anticipa el resultado de una corrección.

**Atención inicial:** Desarrollo, porque la primera discrepancia comprobada es la respuesta 500 de la API de historial y la materialización que intenta insertar está en el código de aplicación. DBA debe participar si se opta por ajustar la política. Esta derivación identifica el primer equipo que debe atender el incidente; la cadena causal se documenta aparte.

**Ambiente y versión:** TEST, versión Alembic `67e33de11180` informada por el responsable QA. Código de referencia `origin/test` `daefc3a5` indicado en la orden; esta revisión no usó Git. La política efectiva de TEST fue consultada en modo solo lectura por el responsable QA el 2026-10-29.

**Pasos para reproducir:**

1. Con un Veterinario autorizado para el activo, consultar `GET /prediccion/historial/{activo}` antes de registrar las nuevas retroalimentaciones; en este RUN, el activo 885 respondió HTTP 200.
2. Hacer que Veterinario A y Veterinario B registren por API retroalimentaciones sobre el mismo resultado; en 230a, ambos registraron `CORRECTO` sobre `997b8cda-b608-4bb3-a7d2-ea37cf12b944` y ambos POST respondieron HTTP 201.
3. Como A, consultar de nuevo `GET /prediccion/historial/885`; la primera lectura posterior a 230a-B respondió HTTP 500 `ERROR_INTERNO`.

**Resultado esperado y obtenido:** El historial debe responder correctamente y poner las retroalimentaciones a disposición de consulta conforme a RF-72 CA-8 y RF-67. En la primera lectura tras 230a-B respondió HTTP 500 `ERROR_INTERNO` y no entregó los registros. Las otras cuatro lecturas del RUN oficial, tras 230b-B, 226-B, 227-B y 227-C, también respondieron HTTP 500 `ERROR_INTERNO`. La parte de ausencia de conflicto de TC-M04-230 sí cumplió: cuatro POST 201, flags de conflicto negativos y cero eventos `CONFLICTO_RETROALIMENTACION` en la auditoría.

**Evidencia:** `Resultados/RUN-G072-V1-20261029-165112/resultado.json` registra GET inicial 200, nueve POST 201, cinco lecturas posteriores 500 `ERROR_INTERNO`, auditorías 200, DELETE 200 y lecturas poscierre 200; `newman/newman-G072.json` y `newman/newman-G072.html` contienen los intercambios y aserciones de este RUN. El primer 500 ocurrió tras 230a-B, alrededor de las 16:51 UTC. El intento técnico `Resultados/RUN-G072-V1-20261029-161515/` registró un solo GET 500 tras los nueve POST, alrededor de las 16:15 UTC. El responsable QA aportó un log del backend TEST de ese intento: `InfrastructureError [ERROR_INTERNO]` en `/prediccion/historial/885`, causado por `ProgrammingError (psycopg2.errors.InsufficientPrivilege): new row violates row-level security policy for table "historial_diagnostico_eventos"`. El log se cita aquí como evidencia aportada; no se incorporó un archivo de log al RUN.

**Causa confirmada:** `src/prediction/application/use_cases/historial_diagnostico/consultar_historial_use_case.py:93-94` llama a `materializar_eventos` en cada consulta. `src/prediction/infrastructure/repositories/historial_diagnostico_repository.py:194-216` intenta insertar en `modulo4.historial_diagnostico_eventos` los eventos aún no materializados, tras comprobar resultado, tipo y fecha. `src/shared/database.py:101-112` fija `app.current_user_id` con la identidad del Veterinario que consulta. En TEST, la tabla tiene RLS activada y forzada: `pol_historial_diagnostico_evento_select` permite SELECT por fincas del usuario; `pol_historial_diagnostico_evento_servicio_select` y `pol_historial_diagnostico_evento_servicio_insert` autorizan al usuario de servicio, y la última usa `WITH CHECK modulo1.fn_es_usuario_servicio()`. No hay política INSERT para usuarios normales. Así, el INSERT de materialización bajo la identidad del Veterinario viola la RLS y la consulta devuelve 500. El backend dispone de `como_sistema` en `src/shared/database.py:184-210`, usado en otro flujo (`src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py:86`); ello no demuestra que sea la corrección apropiada aquí.

**Por qué no es del sandbox:** La política evalúa `app.current_user_id`, que corresponde correctamente al Veterinario de la petición. El INSERT se ejecuta en la consulta ordinaria del historial y la política no autoriza a usuarios normales, con independencia del sandbox. Fuera de él, cualquier Veterinario que consulte un activo visible con eventos nuevos sin materializar queda expuesto al mismo 500. El GET inicial 200, las operaciones de escritura y auditoría correctas y las lecturas poscierre 200 descartan un fallo general del ejecutor o del acceso al activo como explicación de esta discrepancia.

**Por qué G069 funcionó:** Según los hechos aportados en la orden, G069 (`RUN-G069-V1-20261029-125654`, alrededor de las 12:56 UTC) ejecutó el mismo patrón de dos Veterinarios y lectura por A con respuesta 200; G070 (13:38 UTC) y G071 (14:31 UTC) también obtuvieron 200 tras registrar. TEST pasó de Alembic `ebbb160365e5` el 2026-10-28 a `67e33de11180` el 2026-10-29; también cambió la RLS forzada de `resultados_inferencia`. La orden informa que `67e33de11180` no está en `origin/test`, `origin/dev` ni `origin/main`; esta revisión no consultó Git. La aplicación de la política en TEST entre las 14:31 y las 16:15 UTC del 2026-10-29 es una **inferencia** de las respuestas observadas; la base no registra su hora de creación.

**Alcance:** Afecta potencialmente a cualquier activo visible y a cualquier usuario que no sea de servicio cuando existan eventos pendientes de materialización. También compromete las regresiones de G064 a G071 que leen el historial después de registrar, aunque sus ejecuciones anteriores hayan respondido 200. Esta extensión es la consecuencia del mecanismo y de la política informados, no un nuevo resultado de TEST para todos esos grupos.

**Opciones para Desarrollo y DBA:** Evaluar materializar los eventos con identidad de servicio, con el alcance y restauración de identidad apropiados; o definir una política INSERT acotada a eventos de activos visibles para el usuario; o evitar la materialización durante la lectura. La elección requiere revisar seguridad, concurrencia e inmutabilidad y comprobar de nuevo la API pública.

## Problemas técnicos y análisis de causas

No hubo problema del ejecutor ni del sandbox que explique el 500. La causa de producto queda documentada en INC-M04-G072-230-01 con el log TEST, la política efectiva aportada por QA y las rutas de código leídas. No se consultó Git en esta revisión.

## Cierre y rollback

Intento 2; solicitudes 39/312. DELETE HTTP 200. Rollback verificado: DELETE 200; identificadores nuevos ausentes e historial inicial restaurado. Las lecturas poscierre pueden generar HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Reportar INC-M04-G072-230-01 a Desarrollo con la evidencia y el mecanismo RLS documentados. Si Desarrollo y DBA acuerdan una corrección, verificar la consulta pública después de registrar y ejecutar las regresiones afectadas mediante un RUN nuevo autorizado. Mantener los veredictos de este RUN y conservar ambos intentos.

## Herramientas y evidencias

Newman: 1 iteración; 14 solicitudes; 28 aserciones. Sin UI obligatoria.

- preflight.json
- newman/newman-G072.json
- newman/newman-G072.html
- resultado.json
- TC-M04-G072_resultado.md

## Revisión QA (2026-10-29)

Por orden ORD-G072-006 se reescribió la incidencia con pasos, evidencia, severidad y causa confirmada; se aclararon la decisión y el detalle de los tres casos, el cambio de entorno inferido entre G071 y G072 y el alcance potencial. Se dejó constancia del intento técnico y del oficial. Permanecen sin cambios los veredictos TC-M04-226 APROBADO, TC-M04-227 APROBADO y TC-M04-230 RECHAZADO, así como `resultado.json`, `preflight.json`, `contexto_operacion.json` y `newman/`.
