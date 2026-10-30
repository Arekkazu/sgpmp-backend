# TC-M04-G069 — APROBADO

## Identificación

Grupo G069; TC-M04-212, TC-M04-213; RF-72; versión 1; RUN RUN-G069-V1-20261029-125654; ambiente TEST; autorización AUT-G069-V1-20261029; código revisado origin/test daefc3a5; Node.js y Newman verificados. Solo API.

## Decisión del caso

| Caso | Decisión | Motivo |
|---|---|---|
| TC-M04-212 | APROBADO | 201, 409, 409 con mensaje E2; original y auditoría intactos |
| TC-M04-213 | APROBADO | A y B recibieron 201; historial y auditoría muestran dos registros independientes |

RUN oficial: sí. Qué falta: nada. El ensayo local no acredita TEST.

## Precondición de datos

Activo 885; resultados INDIVIDUAL libres hallados 14; páginas de descubrimiento 1; cursor pendiente no. R1 511a6d66-a862-4822-bf47-2634333531b3; R2 f056f99d-78bf-478d-86f0-5b2ee1a70873; reemplazos solo ante duplicado previo o ventana vencida.

## Detalle por caso

### TC-M04-212 — APROBADO

- **Qué se hizo:** Cuenta A sobre R1 511a6d66-a862-4822-bf47-2634333531b3, en orden: CORRECTO (HTTP 201), CORRECTO (HTTP 409), INCORRECTO (HTTP 409).
- **Qué se esperaba:** «El primer registro HTTP 201; ambos intentos posteriores HTTP 409 con el mensaje de retroalimentación ya registrada por este usuario. El original permanece intacto y no se ofrece edición ni reemplazo» (matriz G069, TC-M04-212). RF-72, líneas 4018-4019; E2, líneas 4241-4246; CA-6, líneas 4369-4374.
- **Qué se observó:** A/511a6d66-a862-4822-bf47-2634333531b3 CORRECTO → HTTP 201, código —; A/511a6d66-a862-4822-bf47-2634333531b3 CORRECTO → HTTP 409, código RETROALIMENTACION_DUPLICADA; A/511a6d66-a862-4822-bf47-2634333531b3 INCORRECTO → HTTP 409, código RETROALIMENTACION_DUPLICADA; id_retroalimentacion inicial de A: 464f4077-3d55-435e-aac4-47df1a5da60d; historial tras los intentos: 1 registro de A con estado CORRECTO y el mismo id 464f4077-3d55-435e-aac4-47df1a5da60d; RETROALIMENTACION_REGISTRADA antes de los dos 409: 1 (derivado del 201 inicial), después de ambos 409: 1 (auditoría verificada).
- **Por qué APROBADO:** El primer 201 creó el registro; cada repetición, con el mismo estado y con uno distinto, devolvió 409 RETROALIMENTACION_DUPLICADA y «Ya existe una retroalimentación registrada por este usuario para este resultado.», como exigen E2 y CA-6. El original conservó su id y estado; no aparecieron registros ni eventos nuevos por los rechazos.

### TC-M04-213 — APROBADO

- **Qué se hizo:** Cuentas A y B sobre R2 f056f99d-78bf-478d-86f0-5b2ee1a70873, en orden: A CORRECTO (HTTP 201), B CORRECTO (HTTP 201).
- **Qué se esperaba:** «El registro del veterinario B responde HTTP 201 y coexiste como entidad independiente asociada al mismo resultado» (matriz G069, TC-M04-213). RF-72, línea 4065; salida, línea 4301.
- **Qué se observó:** A/f056f99d-78bf-478d-86f0-5b2ee1a70873 CORRECTO → HTTP 201, código —; B/f056f99d-78bf-478d-86f0-5b2ee1a70873 CORRECTO → HTTP 201, código —; id_retroalimentacion de A: cf669028-23ec-4558-b982-44d8be13972d; de B: 56d18146-ece7-4d11-99c1-b2d8897348c9; historial: A 1 y B 1 registro cada uno; RETROALIMENTACION_REGISTRADA: 2 eventos.
- **Por qué APROBADO:** A obtuvo 201 y B también obtuvo 201 sobre R2; sus id_retroalimentacion son distintos y coexisten dos registros y dos eventos de auditoría. La unicidad se aplica por usuario, no por resultado.

## Tabla de intentos

| Caso | Cuenta | Resultado | Estado enviado | HTTP | Código y mensaje | Persistió |
|---|---|---|---|---|---|---|
| TC-M04-212 | A | 511a6d66-a862-4822-bf47-2634333531b3 | CORRECTO | 201 | — | sí |
| TC-M04-212 | A | 511a6d66-a862-4822-bf47-2634333531b3 | CORRECTO | 409 | RETROALIMENTACION_DUPLICADA: Ya existe una retroalimentación registrada por este usuario para este resultado. | no |
| TC-M04-212 | A | 511a6d66-a862-4822-bf47-2634333531b3 | INCORRECTO | 409 | RETROALIMENTACION_DUPLICADA: Ya existe una retroalimentación registrada por este usuario para este resultado. | no |
| TC-M04-213 | A | f056f99d-78bf-478d-86f0-5b2ee1a70873 | CORRECTO | 201 | — | sí |
| TC-M04-213 | B | f056f99d-78bf-478d-86f0-5b2ee1a70873 | CORRECTO | 201 | — | sí |

## Observaciones

Ninguna.

## Incidencias de producto

Ninguna confirmada.

## Problemas técnicos y análisis de causas

Ninguno. La derivación inicial no atribuye causa raíz.

## Historial de intentos, cierre y rollback

Intento 1; 16 solicitudes. DELETE HTTP 200; rollback verificado: DELETE 200 y ausencia de retroalimentaciones de R1/R2 en historial poscierre. Lecturas poscierre pueden generar HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

G069 APROBADO: RF-72 cumple la unicidad por usuario y admite la segunda perspectiva clínica. Sin incidencias; sin acciones para Desarrollo.

## Herramientas y evidencias

Newman 6.2.2: 1 iteración, 5 solicitudes, 10 aserciones. Login, descubrimiento, verificaciones y cierre con fetch. Sin UI obligatoria.

- preflight.json
- newman/newman-G069.json
- newman/newman-G069.html
- resultado.json
- TC-M04-G069_resultado.md

## Revisión QA (2026-10-29)

Se precisó el detalle de TC-M04-212 y TC-M04-213 con datos de resultado.json, encabezados y listas con decisión, conclusión de grupo aprobado, evidencias completas y celdas «—» sin código ni mensaje. Veredictos, resultado.json y reportes Newman sin cambios.
