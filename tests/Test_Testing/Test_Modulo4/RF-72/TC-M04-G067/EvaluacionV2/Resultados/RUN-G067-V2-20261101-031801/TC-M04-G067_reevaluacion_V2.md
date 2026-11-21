# TC-M04-G067 — APROBADO

## Identificación

Grupo G067; casos TC-M04-205, TC-M04-206, TC-M04-207, TC-M04-208, TC-M04-209; RF-72; versión 2; RUN RUN-G067-V2-20261101-031801; ambiente TEST; autorización AUT-G067-V2-20261101; commit de TEST no verificado por este ejecutor; Node.js. Solo API.

## Decisión del caso

| Caso | Decisión | Motivo |
|---|---|---|
| TC-M04-205 | APROBADO | 205-inexistente: HTTP, mensaje, historial y auditoría concordantes; 205-vacio: HTTP, mensaje, historial y auditoría concordantes; 205-numerico: HTTP, mensaje, historial y auditoría concordantes; 205-capitalizado: HTTP, mensaje, historial y auditoría concordantes; 205-nulo: HTTP, mensaje, historial y auditoría concordantes; 205-lista: HTTP, mensaje, historial y auditoría concordantes; 205-minusculas: HTTP, mensaje, historial y auditoría concordantes |
| TC-M04-206 | APROBADO | 206-ausente: HTTP, mensaje, historial y auditoría concordantes |
| TC-M04-207 | APROBADO | 207-omitido: HTTP, mensaje, historial y auditoría concordantes; 207-vacio: HTTP, mensaje, historial y auditoría concordantes |
| TC-M04-208 | APROBADO | 208-omitido: HTTP, mensaje, historial y auditoría concordantes; 208-vacio: HTTP, mensaje, historial y auditoría concordantes |
| TC-M04-209 | APROBADO | 209-correcto-sin: HTTP, mensaje, historial y auditoría concordantes; 209-correcto-con: HTTP, mensaje, historial y auditoría concordantes; 209-sin-evento-sin: HTTP, mensaje, historial y auditoría concordantes; 209-sin-evento-con: HTTP, mensaje, historial y auditoría concordantes |

RUN oficial: sí. Qué falta: ninguna comprobación obligatoria. El ensayo local no es evidencia TEST.

## Precondición de datos (semilla)

72 eventos examinados; se requieren cuatro resultados distintos para 209, uno libre compartido para rechazos y resultados de reemplazo. Modelo INDIVIDUAL; patologías activas 8-14, excluida 7. La semilla no se modifica.

## Detalle por caso

### TC-M04-205 — APROBADO

- Qué se hizo: 205-inexistente, 205-vacio, 205-numerico, 205-capitalizado, 205-nulo, 205-lista, 205-minusculas sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 dominio cerrado 4070-4072, E3 4248-4252 y CA-3 4363: DESCONOCIDO, cadena vacía, 123, correcto, Correcto, null y lista [CORRECTO] deben devolver HTTP 422 ESTADO_RETROALIMENTACION_INVALIDO con mensaje de estado no válido, sin persistencia ni auditoría de registro exitoso.
- Qué se observó: 205-inexistente: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no; 205-vacio: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no; 205-numerico: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no; 205-capitalizado: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no; 205-nulo: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no; 205-lista: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no; 205-minusculas: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.; persistió no.
- Por qué APROBADO: 205-inexistente: HTTP, mensaje, historial y auditoría concordantes; 205-vacio: HTTP, mensaje, historial y auditoría concordantes; 205-numerico: HTTP, mensaje, historial y auditoría concordantes; 205-capitalizado: HTTP, mensaje, historial y auditoría concordantes; 205-nulo: HTTP, mensaje, historial y auditoría concordantes; 205-lista: HTTP, mensaje, historial y auditoría concordantes; 205-minusculas: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-205-01 en resultado.json.

### TC-M04-206 — APROBADO

- Qué se hizo: 206-ausente sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 entrada obligatoria 4162: estado ausente debe devolver HTTP 422 VAL_ENTRADA identificando estado_retroalimentacion, sin persistir. Decisión QA 2026-10-29: HTTP 400 completo se aprueba con observación.
- Qué se observó: 206-ausente: f7fea6d3; HTTP 422; VAL_ENTRADA; Errores de validacion en la solicitud; Este campo es obligatorio.; persistió no.
- Por qué APROBADO: 206-ausente: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-206-01 en resultado.json.

### TC-M04-207 — APROBADO

- Qué se hizo: 207-omitido, 207-vacio sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 obligatoriedad condicional 4074-4078, E4 4254-4258 y CA-4 4365: PARCIAL sin lista y con [] devuelve HTTP 422 de diagnóstico obligatorio, sin persistir.
- Qué se observó: 207-omitido: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no; 207-vacio: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no.
- Por qué APROBADO: 207-omitido: HTTP, mensaje, historial y auditoría concordantes; 207-vacio: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-207-01 en resultado.json.

### TC-M04-208 — APROBADO

- Qué se hizo: 208-omitido, 208-vacio sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 obligatoriedad condicional 4074-4078, E4 4254-4258 y CA-4 4365: INCORRECTO sin lista y con [] devuelve HTTP 422 de diagnóstico obligatorio, sin persistir.
- Qué se observó: 208-omitido: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no; 208-vacio: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no.
- Por qué APROBADO: 208-omitido: HTTP, mensaje, historial y auditoría concordantes; 208-vacio: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-208-01 en resultado.json.

### TC-M04-209 — APROBADO

- Qué se hizo: 209-correcto-sin, 209-correcto-con, 209-sin-evento-sin, 209-sin-evento-con sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 obligatoriedad condicional 4074-4078 y entradas 4162-4163: CORRECTO y SIN_EVENTO con y sin diagnóstico, sobre cuatro resultados distintos, devuelven HTTP 201 con registro en historial. No se comprueba conservación del diagnóstico.
- Qué se observó: 209-correcto-sin: f056f99d; HTTP 201; —; persistió sí como CORRECTO; 209-correcto-con: 997b8cda; HTTP 201; —; persistió sí como CORRECTO; 209-sin-evento-sin: d1f3cc43; HTTP 201; —; persistió sí como SIN_EVENTO; 209-sin-evento-con: 5dbe4510; HTTP 201; —; persistió sí como SIN_EVENTO.
- Por qué APROBADO: 209-correcto-sin: HTTP, mensaje, historial y auditoría concordantes; 209-correcto-con: HTTP, mensaje, historial y auditoría concordantes; 209-sin-evento-sin: HTTP, mensaje, historial y auditoría concordantes; 209-sin-evento-con: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-209-01 en resultado.json.

## Comparación V1 → V2

| Caso | V1 oficial | V2 | Lectura |
|---|---|---|---|
| TC-M04-205 | RECHAZADO | APROBADO | Siete variantes rechazadas sin persistencia ni auditoría exitosa. |
| TC-M04-206 | APROBADO con observación | APROBADO | OBS-M04-G067-206 CERRADA. |
| TC-M04-207 | APROBADO | APROBADO | Regresión de diagnóstico obligatorio. |
| TC-M04-208 | APROBADO | APROBADO | Regresión de diagnóstico obligatorio. |
| TC-M04-209 | APROBADO | APROBADO | Regresión de cuatro registros válidos. |

Corrección informada por Desarrollo en issue #862 / PR #871. INC-M04-G067-205-01 e INC-M04-G067-205-02 CORREGIDAS por esta reevaluación.


## Tabla de intentos

| Intento | Resultado | Cuerpo resumido | HTTP | Código y mensaje | Persistió |
|---|---|---|---|---|---|
| 209-correcto-sin | f056f99d | estado CORRECTO; diagnóstico omitido | 201 | — | sí |
| 209-correcto-con | 997b8cda | estado CORRECTO; diagnósticos 1 | 201 | — | sí |
| 209-sin-evento-sin | d1f3cc43 | estado SIN_EVENTO; diagnóstico omitido | 201 | — | sí |
| 209-sin-evento-con | 5dbe4510 | estado SIN_EVENTO; diagnósticos 1 | 201 | — | sí |
| 207-omitido | f7fea6d3 | estado PARCIAL; diagnóstico omitido | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 207-vacio | f7fea6d3 | estado PARCIAL; diagnósticos 0 | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 208-omitido | f7fea6d3 | estado INCORRECTO; diagnóstico omitido | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 208-vacio | f7fea6d3 | estado INCORRECTO; diagnósticos 0 | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 206-ausente | f7fea6d3 | estado estado ausente; diagnósticos 1 | 422 | VAL_ENTRADA; Errores de validacion en la solicitud; Este campo es obligatorio. | no |
| 205-inexistente | f7fea6d3 | estado DESCONOCIDO; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-vacio | f7fea6d3 | estado cadena vacía; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-numerico | f7fea6d3 | estado 123; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-capitalizado | f7fea6d3 | estado Correcto; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-nulo | f7fea6d3 | estado null; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-lista | f7fea6d3 | estado lista [CORRECTO]; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-minusculas | f7fea6d3 | estado correcto; diagnósticos 1 | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |

## Observaciones

Sin observaciones de producto.

## Incidencias de producto

Sin incidencias de producto.

## Problemas técnicos y análisis de causas

Ninguno. Derivación inicial según primera discrepancia pública; causa raíz no atribuida.

## Historial, cierre y rollback

75 solicitudes. DELETE HTTP 200; rollback verificado por lectura pública: Registros del RUN ausentes en historial público poscierre. Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Cinco comprobaciones API aprobadas; conservar evidencias y la observación si aplica.

## Herramientas

Newman 6.2.2: 1 ejecución, 1 iteraciones, 16 solicitudes y 32 aserciones. Un JSON y un HTML reales saneados en newman/. Login, descubrimiento, lecturas y cierre por fetch.

## Evidencias

- preflight.json
- resultado.json
- TC-M04-G067_reevaluacion_V2.md
- newman/newman-G067.json
- newman/newman-G067.html
