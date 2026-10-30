# TC-M04-G068 — RECHAZADO

## Identificación

Grupo G068; casos TC-M04-210, TC-M04-211, TC-M04-245; RF-72; versión 1; RUN RUN-G068-V1-20261029-121139; ambiente TEST; autorización AUT-G068-V1-R2-20261029; código revisado origin/test daefc3a5; Node.js y Newman. Solo API.

## Decisión del caso

| Caso | Decisión | Motivo |
|---|---|---|
| TC-M04-210 | APROBADO | HTTP 404 RESULTADO_INFERENCIA_NO_ENCONTRADO con el mensaje literal de E1; sin retroalimentación ni RETROALIMENTACION_REGISTRADA en historial y auditoría |
| TC-M04-211 | APROBADO | rechazo HTTP 422 ACTIVO_BIOLOGICO_INCONSISTENTE con el mensaje «El activo biológico no corresponde al resultado de inferencia indicado.»; sin registro; RF-72 no fija código |
| TC-M04-245 | RECHAZADO | Con el 885 en BAJA (baja 201, estado BAJA leído, BAJA_REGISTRADA en el sandbox), la retroalimentación sobre f056f99d se aceptó con HTTP 201 y quedó registrada con RETROALIMENTACION_REGISTRADA, cuando RF-72 4112-4113 exige que solo pueda registrarse si el activo existe y es válido. |

RUN oficial: sí. Los tres POST se evaluaron con sus respuestas y lecturas de historial y auditoría; el caso 245 incumplió la restricción de RF-72 con la baja comprobada. El ensayo local no acredita TEST.

Qué falta: ninguno.

## Precondición de datos (semilla y baja temporal)

Activo 885, modelo INDIVIDUAL; otro activo 884 (QA-G88-IND-001). Resultados libres 14; eventos examinados 14; páginas 1; cursor pendiente no. Fase antes: sin fase activa; activo 885 sin fase activa antes de la baja. Fase durante la baja: sin fase activa. Baja HTTP 201; estado durante baja BAJA; BAJA_REGISTRADA en sandbox sí. El buffer local RF-52 puede conservar una copia fuera del sandbox si falla la BD o hay alta carga.

## Detalle por caso

### TC-M04-210 — APROBADO

- Qué se hizo: POST Newman con UUID v4 inexistente.
- Qué se esperaba: Matriz G068 y RF-72 E1 4234-4239: HTTP 404, "El resultado de inferencia no existe o no está disponible."; se cancela sin registro ni evento.
- Qué se observó: HTTP 404; RESULTADO_INFERENCIA_NO_ENCONTRADO; El resultado de inferencia no existe o no está disponible.; persistió no.
- Por qué APROBADO: HTTP 404 RESULTADO_INFERENCIA_NO_ENCONTRADO con el mensaje literal de E1; sin retroalimentación ni RETROALIMENTACION_REGISTRADA en historial y auditoría. Evidencia: API-210-01 en resultado.json.

### TC-M04-211 — APROBADO

- Qué se hizo: POST Newman con resultado libre del 885 y otro activo existente.
- Qué se esperaba: Matriz G068 y RF-72 4161: rechazo indicando que el activo no corresponde al resultado, sin persistir. RF-72 no fija HTTP.
- Qué se observó: HTTP 422; ACTIVO_BIOLOGICO_INCONSISTENTE; El activo biológico no corresponde al resultado de inferencia indicado.; persistió no.
- Por qué APROBADO: rechazo HTTP 422 ACTIVO_BIOLOGICO_INCONSISTENTE con el mensaje «El activo biológico no corresponde al resultado de inferencia indicado.»; sin registro; RF-72 no fija código. Evidencia: API-211-01 en resultado.json.

### TC-M04-245 — RECHAZADO

- Qué se hizo: Baja temporal del 885, lectura de estado y bitácora, y POST condicional en una ejecución Newman.
- Qué se esperaba: Matriz G068 y RF-72 4112-4113: activo dado de baja o inconsistente, registro rechazado y sin persistencia. RF-72 no fija HTTP; incidente administrativo fuera del oráculo.
- Qué se observó: HTTP 201; —; sin mensaje; persistió sí.
- Por qué RECHAZADO: con el 885 en BAJA (baja 201, estado BAJA leído, BAJA_REGISTRADA en el sandbox) la retroalimentación sobre f056f99d se aceptó con HTTP 201 y quedó registrada con RETROALIMENTACION_REGISTRADA, cuando RF-72 4112-4113 exige que solo pueda registrarse si el activo existe y es válido. Evidencia: API-245-01 en resultado.json.

## Tabla de intentos

| Caso | Resultado | Cuerpo resumido | HTTP | Código y mensaje | Persistió |
|---|---|---|---|---|---|
| TC-M04-210 | e2875782 | CORRECTO sin diagnóstico; activo 885 | 404 | RESULTADO_INFERENCIA_NO_ENCONTRADO; El resultado de inferencia no existe o no está disponible. | no |
| TC-M04-211 | 511a6d66 | CORRECTO sin diagnóstico; activo 884 | 422 | ACTIVO_BIOLOGICO_INCONSISTENTE; El activo biológico no corresponde al resultado de inferencia indicado. | no |
| TC-M04-245 | f056f99d | CORRECTO sin diagnóstico; activo 885 | 201 | —; — | sí |

## Observaciones

Ninguna.

## Incidencias de producto

- INC-M04-G068-245-01: MEDIA, certeza CONFIRMADA del incumplimiento observado; atención inicial Desarrollo por la primera discrepancia comprobada en la API pública. El POST aceptó con HTTP 201 y persistió una retroalimentación para el activo 885 en BAJA, con evento RETROALIMENTACION_REGISTRADA. Incumple la restricción explícita de RF-72 4112-4113 y deja una retroalimentación persistente consumible por RF-71 como etiqueta. El resultado de inferencia es anterior a la baja, por lo que el diagnóstico sigue siendo clínicamente coherente; no se observó alteración de otros datos. Impacto parcial: MEDIA. Hipótesis de causa PROBABLE, no confirmada: el caso de uso no consulta el estado del activo (`registrar_retroalimentacion_use_case.py:55-107` y `resultado_inferencia_adapter.py:16-23`, origin/test daefc3a5). Causa raíz NO DETERMINADA.

## Problemas técnicos y análisis de causas

Ninguno. La derivación inicial se basa en la primera discrepancia pública; causa raíz no determinada.

## Historial, cierre y rollback

25 solicitudes. DELETE HTTP 200; rollback verificado: Ausencia de registros y estado/fase 885 concordantes poscierre. Activo 885 poscierre ACTIVO, fase sin fase activa. Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Historial de intentos

- Intento 1, RUN-G068-V1-20261029-115805: TÉCNICO, exit 2. Ocho solicitudes (logins, lecturas y DELETE); no se evaluaron la baja ni los POST de los casos. El activo 885 estaba ACTIVO antes y después. La causa fue una precondición de fase activa en el ejecutor, corregida en ORD-G068-005. Evidencia nativa eliminada por decisión del responsable QA el 2026-10-29.
- Intento 2, RUN-G068-V1-20261029-121139: RUN oficial de esta evaluación; 210 y 211 APROBADOS, 245 RECHAZADO.

## Conclusión y acciones

Desarrollo debe revisar las discrepancias confirmadas en TEST; repetir los casos afectados en un RUN autorizado.

## Herramientas

Newman 6.2.2: 1 iteración, 6 solicitudes y 12 aserciones. Reportes JSON y HTML generados en newman/. Login, descubrimiento, lecturas de verificación y cierre por fetch.

## Evidencias

- preflight.json
- resultado.json
- TC-M04-G068_resultado.md
- newman/newman-G068.json
- newman/newman-G068.html

## Revisión QA (2026-10-29)

Se corrigió la severidad de INC-M04-G068-245-01 de ALTA a MEDIA por el impacto parcial demostrado; se precisaron los motivos de 210, 211 y 245, se trasladó la ausencia de fase activa a la precondición y se añadió el historial de ambos intentos. Veredictos y resultado.json sin cambios.
