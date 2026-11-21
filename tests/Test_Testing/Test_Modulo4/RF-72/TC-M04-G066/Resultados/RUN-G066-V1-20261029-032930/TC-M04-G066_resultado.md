# TC-M04-G066 — APROBADO

## Identificación

Grupo G066; casos TC-M04-200, TC-M04-201, TC-M04-202, TC-M04-203, TC-M04-204; RF-72; versión 1; RUN RUN-G066-V1-20261029-032930; ambiente TEST; autorización AUT-G066-V1-20261029; código revisado origin/test daefc3a5; Node.js. Solo API.

## Decisión del caso

Las listas de 1 a 3 patologías se registraron con 201 conservando el orden y la principal; la lista de 4 se rechazó sin persistir indicando el máximo (HTTP 400 en lugar del 422 recomendado); las patologías inexistentes, la lista mixta y la patología inactiva se rechazaron con 422 sin persistir nada.

| Caso | Estado | Motivo claro |
|---|---|---|
| TC-M04-200 | APROBADO | Una patología activa registrada con HTTP 201 como principal y sin secundarias. |
| TC-M04-201 | APROBADO | Tres patologías activas registradas con HTTP 201 en orden: principal y dos comorbilidades. |
| TC-M04-202 | APROBADO con observación | Listas de 1 a 3 registradas con HTTP 201; lista de 4 rechazada sin persistir, con OBS-M04-G066-202 por HTTP 400 en lugar del 422 recomendado. |
| TC-M04-203 | APROBADO | Patología inexistente, sola o mezclada, rechazada con HTTP 422 sin persistencia parcial. |
| TC-M04-204 | APROBADO | Patología inactiva rechazada con HTTP 422 sin persistencia. |

Apto para registro QA: sí. Un ensayo local nunca constituye evidencia TEST.

## Precondición de datos (semilla)

72 eventos examinados; 9/9 intentos con resultado. Se necesitan 5 resultados distintos para 201 y uno libre para rechazos, todos INDIVIDUAL y sin retroalimentación del Veterinario. Catálogo: 33 activas, 16 inactivas; contingencia no utilizada. La semilla externa no se modifica.

## Detalle por caso

### TC-M04-200 — APROBADO

- Qué se hizo: Se envió INCORRECTO con una patología activa: 511a6d66 [7].
- Qué se esperaba: RF-72, línea 4163 y CA-12 (4387–4388): una patología activa en INCORRECTO se registra con HTTP 201; es la principal y no hay secundarias.
- Qué se observó: 511a6d66 [7] → HTTP 201; [7] en respuesta, historial y auditoría.
- Por qué APROBADO: HTTP 201; una sola patología, por posición principal, conservada en respuesta, historial y auditoría; sin secundarias. Evidencia: API-200-01 en resultado.json.

### TC-M04-201 — APROBADO

- Qué se hizo: Se envió INCORRECTO con tres patologías activas en orden: f056f99d [7, 8, 9].
- Qué se esperaba: RF-72, línea 4163 y CA-12 (4387–4388): tres patologías activas se registran con HTTP 201 en orden; la primera es principal y las otras dos, comorbilidades.
- Qué se observó: f056f99d [7, 8, 9] → HTTP 201; [7, 8, 9] en respuesta, historial y auditoría, en el mismo orden.
- Por qué APROBADO: HTTP 201; 7 quedó principal y 8 y 9 como comorbilidades por posición; respuesta, historial y auditoría conservaron el orden. Evidencia: API-201-01 en resultado.json.

### TC-M04-202 — APROBADO con observación

- Qué se hizo: Se enviaron cuatro listas, de 1 a 4 patologías: 997b8cda [7]; d1f3cc43 [7, 8]; 5dbe4510 [7, 8, 9]; f7fea6d3 [7, 8, 9, 10].
- Qué se esperaba: RF-72, línea 4163 y CA-12 (4387–4388): se registran listas de uno a tres; cuatro exceden el máximo y no deben persistir. La matriz recomienda HTTP 422 para el exceso.
- Qué se observó: 997b8cda [7] → HTTP 201; d1f3cc43 [7, 8] → HTTP 201; 5dbe4510 [7, 8, 9] → HTTP 201. f7fea6d3 [7, 8, 9, 10] → HTTP 400, VAL_ENTRADA: “Errores de validacion en la solicitud”; campo diagnosticos_reales y máximo de 3 verificados; sin registro en historial ni auditoría.
- Por qué APROBADO con observación: Las listas de 1, 2 y 3 tuvieron HTTP 201 y conservaron su orden; la de 4 se rechazó con campo y máximo, sin persistencia. OBS-M04-G066-202: HTTP 400 en lugar del 422 recomendado, según decisión QA del 2026-10-29. Evidencia: API-202-01 en resultado.json.

### TC-M04-203 — APROBADO

- Qué se hizo: Se probó el ID inexistente y una lista mixta: f7fea6d3 [1064]; f7fea6d3 [7, 8, 1064].
- Qué se esperaba: RF-72, líneas 4067–4068, E5 (4260–4264) y CA-5 (4367): una patología inexistente, sola o mezclada con válidas, se rechaza con HTTP 422 sin persistencia parcial.
- Qué se observó: f7fea6d3 [1064] → HTTP 422 y f7fea6d3 [7, 8, 1064] → HTTP 422; primera respuesta DIAGNOSTICO_NO_VALIDO: “La patología con id 1064 no es válida o no está activa en el sistema.”; segunda DIAGNOSTICO_NO_VALIDO: “La patología con id 1064 no es válida o no está activa en el sistema.”; sin registro, tampoco de las patologías válidas de la lista mixta.
- Por qué APROBADO: Ambos intentos devolvieron HTTP 422 con patología no válida; historial y auditoría no muestran registro ni de las válidas mezcladas. Evidencia: API-203-01 en resultado.json.

### TC-M04-204 — APROBADO

- Qué se hizo: Se envió la patología inactiva: f7fea6d3 [16].
- Qué se esperaba: RF-72, líneas 4067–4068, E5 (4260–4264) y CA-5 (4367): una patología existente pero inactiva se rechaza con HTTP 422 sin persistencia.
- Qué se observó: f7fea6d3 [16] → HTTP 422; DIAGNOSTICO_NO_VALIDO: “La patología con id 16 no es válida o no está activa en el sistema.”; sin registro. No se necesitó contingencia.
- Por qué APROBADO: La patología inactiva devolvió HTTP 422 con mensaje de no válida o inactiva; historial y auditoría no muestran registro. Evidencia: API-204-01 en resultado.json.

## Observaciones

- OBS-M04-G066-202 (TC-M04-202): La lista de 4 respondió HTTP 400 VAL_ENTRADA en vez del 422 recomendado. RF-72, línea 4163, fija el rango 1–3, sin código para el exceso; por decisión QA del 2026-10-29 queda como observación, igual que OBS-M04-G065-224. Hipótesis, no causa demostrada: la ruta no declara x-codigo-validacion 422 (src/shared/error_handlers.py:193–200, 298–324; src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py:36–50).
- RF-72 exige que la patología exista y esté activa en el catálogo (4067-4068, 4163); no exige que corresponda a la especie del activo, y el sistema no lo comprueba.

## Incidencias de producto

Sin incidencias de producto.

## Problemas técnicos y causas

Ninguno. Las incidencias se orientan por la primera discrepancia comprobada; la causa raíz no se presume.

## Historial, cierre y rollback

47 solicitudes. DELETE HTTP 200; rollback verificado por lectura pública: Registros del RUN ausentes en historial público poscierre. Las lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Las cinco comprobaciones API se aprobaron. Conservar evidencias; registrar OBS-M04-G066-202 y la precisión general de RF-72 sobre especie.

## Evidencias

Este RUN se ejecutó por API con fetch; Newman no se ejecutó (desviación de la herramienta indicada en la matriz, Postman + Newman). La evidencia funcional completa está en resultado.json. El ejecutor se corrigió el 2026-10-29 para usar Newman en las ejecuciones siguientes (ORD-G066-006).

- preflight.json
- resultado.json
- TC-M04-G066_resultado.md
