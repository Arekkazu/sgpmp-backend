# TC-M04-G067 — RECHAZADO

## Identificación

Grupo G067; casos TC-M04-205, TC-M04-206, TC-M04-207, TC-M04-208, TC-M04-209; RF-72; versión 1; RUN RUN-G067-V1-20261029-055824; ambiente TEST; autorización AUT-G067-V1-20261029; código revisado origin/test daefc3a5; Node.js. Solo API.

## Decisión del caso

| Caso | Decisión | Motivo |
|---|---|---|
| TC-M04-205 | RECHAZADO | DESCONOCIDO y cadena vacía cumplieron con HTTP 422 y sin persistencia. El valor numérico recibió HTTP 400 VAL_ENTRADA («El valor ingresado debe ser un texto.»), pero E3 exige HTTP 422 y mensaje de estado no válido. `correcto` en minúsculas recibió HTTP 201 y se guardó como CORRECTO, aunque la matriz y E3 exigen HTTP 422 sin persistencia. |
| TC-M04-206 | APROBADO con observación | 206-ausente: Rechazo completo sin persistencia; observación HTTP 400 en lugar del 422 recomendado |
| TC-M04-207 | APROBADO | 207-omitido: HTTP, mensaje, historial y auditoría concordantes; 207-vacio: HTTP, mensaje, historial y auditoría concordantes |
| TC-M04-208 | APROBADO | 208-omitido: HTTP, mensaje, historial y auditoría concordantes; 208-vacio: HTTP, mensaje, historial y auditoría concordantes |
| TC-M04-209 | APROBADO | Los cuatro intentos, 209-correcto-sin, 209-correcto-con, 209-sin-evento-sin y 209-sin-evento-con, recibieron HTTP 201 y quedaron registrados; historial y auditoría concordantes. |

RUN oficial: sí. Qué falta: ninguna comprobación obligatoria. El ensayo local no es evidencia TEST.

## Precondición de datos (semilla)

72 eventos examinados; se requieren cuatro resultados distintos para 209, uno libre compartido para rechazos y uno reservado para el valor en minúsculas, más reemplazos. Modelo INDIVIDUAL; patologías activas 8-14, excluida 7. La semilla no se modifica.

## Detalle por caso

### TC-M04-205 — RECHAZADO

- Qué se hizo: 205-inexistente, 205-vacio, 205-numerico, 205-minusculas sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 dominio cerrado 4070-4072, E3 4248-4252 y CA-3 4363; matriz G067: DESCONOCIDO, correcto, cadena vacía y número deben devolver HTTP 422 de estado no válido, sin persistir.
- Qué se observó: 205-inexistente: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; mensaje de estado no válido; no persistió. 205-vacio: f7fea6d3; HTTP 422; ESTADO_RETROALIMENTACION_INVALIDO; mensaje de estado no válido; no persistió. 205-numerico: f7fea6d3; HTTP 400; VAL_ENTRADA; mensaje general «Errores de validacion en la solicitud» y detalle de campo «El valor ingresado debe ser un texto.»; no persistió. 205-minusculas: 511a6d66; HTTP 201; sin código de error; persistió como CORRECTO, valor del dominio; el registro fue revertido por DELETE HTTP 200 y la lectura pública poscierre no lo encontró.
- Por qué RECHAZADO: `correcto` en minúsculas fue aceptado con HTTP 201 y normalizado a CORRECTO, pese a que la matriz y E3 exigen HTTP 422 sin persistencia. El valor numérico recibió HTTP 400 VAL_ENTRADA y el detalle «El valor ingresado debe ser un texto.», cuando E3 fija HTTP 422 y el mensaje de estado no válido. DESCONOCIDO y la cadena vacía sí cumplieron. Evidencia: API-205-01 en resultado.json.

### TC-M04-206 — APROBADO con observación

- Qué se hizo: 206-ausente sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 entrada obligatoria 4162; matriz G067: estado ausente se rechaza sin persistir indicando el campo. Decisión QA 2026-10-29: HTTP 400 completo se aprueba con observación; 422 recomendado.
- Qué se observó: 206-ausente: f7fea6d3; HTTP 400; VAL_ENTRADA; mensaje general «Errores de validacion en la solicitud» y detalle de campo «Este campo es obligatorio.»; persistió no.
- Por qué APROBADO con observación: 206-ausente: Rechazo completo sin persistencia; observación HTTP 400 en lugar del 422 recomendado. Evidencia: API-206-01 en resultado.json.

### TC-M04-207 — APROBADO

- Qué se hizo: 207-omitido, 207-vacio sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 obligatoriedad condicional 4074-4078, E4 4254-4258 y CA-4 4365; matriz G067: PARCIAL sin lista y con [] devuelve HTTP 422 de diagnóstico obligatorio, sin persistir.
- Qué se observó: 207-omitido: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no; 207-vacio: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no.
- Por qué APROBADO: 207-omitido: HTTP, mensaje, historial y auditoría concordantes; 207-vacio: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-207-01 en resultado.json.

### TC-M04-208 — APROBADO

- Qué se hizo: 208-omitido, 208-vacio sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 obligatoriedad condicional 4074-4078, E4 4254-4258 y CA-4 4365; matriz G067: INCORRECTO sin lista y con [] devuelve HTTP 422 de diagnóstico obligatorio, sin persistir.
- Qué se observó: 208-omitido: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no; 208-vacio: f7fea6d3; HTTP 422; DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación.; persistió no.
- Por qué APROBADO: 208-omitido: HTTP, mensaje, historial y auditoría concordantes; 208-vacio: HTTP, mensaje, historial y auditoría concordantes. Evidencia: API-208-01 en resultado.json.

### TC-M04-209 — APROBADO

- Qué se hizo: 209-correcto-sin, 209-correcto-con, 209-sin-evento-sin, 209-sin-evento-con sobre resultados INDIVIDUAL libres.
- Qué se esperaba: RF-72 obligatoriedad condicional 4074-4078 y entradas 4162-4163; matriz G067: CORRECTO y SIN_EVENTO con y sin diagnóstico, sobre cuatro resultados distintos, devuelven HTTP 201 con registro. No se comprueba conservación del diagnóstico.
- Qué se observó: 209-correcto-sin: f056f99d; HTTP 201; sin código; ; persistió sí; 209-correcto-con: 997b8cda; HTTP 201; sin código; ; persistió sí; 209-sin-evento-sin: d1f3cc43; HTTP 201; sin código; ; persistió sí; 209-sin-evento-con: 5dbe4510; HTTP 201; sin código; ; persistió sí.
- Por qué APROBADO: los cuatro intentos, 209-correcto-sin, 209-correcto-con, 209-sin-evento-sin y 209-sin-evento-con, recibieron HTTP 201 y quedaron registrados; historial y auditoría concordantes. Evidencia: API-209-01 en resultado.json.

## Tabla de intentos

| Intento | Resultado | Cuerpo resumido | HTTP | Código y mensaje | Persistió |
|---|---|---|---|---|---|
| 209-correcto-sin | f056f99d | {"estado_retroalimentacion":"CORRECTO"} | 201 | — | sí |
| 209-correcto-con | 997b8cda | {"estado_retroalimentacion":"CORRECTO","diagnosticos_reales":[8]} | 201 | — | sí |
| 209-sin-evento-sin | d1f3cc43 | {"estado_retroalimentacion":"SIN_EVENTO"} | 201 | — | sí |
| 209-sin-evento-con | 5dbe4510 | {"estado_retroalimentacion":"SIN_EVENTO","diagnosticos_reales":[9]} | 201 | — | sí |
| 207-omitido | f7fea6d3 | {"estado_retroalimentacion":"PARCIAL"} | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 207-vacio | f7fea6d3 | {"estado_retroalimentacion":"PARCIAL","diagnosticos_reales":[]} | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 208-omitido | f7fea6d3 | {"estado_retroalimentacion":"INCORRECTO"} | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 208-vacio | f7fea6d3 | {"estado_retroalimentacion":"INCORRECTO","diagnosticos_reales":[]} | 422 | DIAGNOSTICO_REQUERIDO; El diagnóstico clínico es obligatorio para este tipo de retroalimentación. | no |
| 206-ausente | f7fea6d3 | {"diagnosticos_reales":[8]} | 400 | VAL_ENTRADA; Errores de validacion en la solicitud; Este campo es obligatorio. | no |
| 205-inexistente | f7fea6d3 | {"estado_retroalimentacion":"DESCONOCIDO","diagnosticos_reales":[8]} | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-vacio | f7fea6d3 | {"estado_retroalimentacion":"","diagnosticos_reales":[8]} | 422 | ESTADO_RETROALIMENTACION_INVALIDO; El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO. | no |
| 205-numerico | f7fea6d3 | {"estado_retroalimentacion":123,"diagnosticos_reales":[8]} | 400 | VAL_ENTRADA; Errores de validacion en la solicitud; El valor ingresado debe ser un texto. | no |
| 205-minusculas | 511a6d66 | {"estado_retroalimentacion":"correcto","diagnosticos_reales":[8]} | 201 | — | sí |

## Observaciones

OBS-M04-G067-206: HTTP 400 completo, sin persistencia, para estado ausente; RF-72 4162 no fija código para la ausencia y QA permite observación.

## Incidencias de producto

- INC-M04-G067-205-01 — `correcto` en minúsculas: severidad BAJA; discrepancia CONFIRMADA por API pública (HTTP 201 y persistencia como CORRECTO frente al HTTP 422 sin persistencia exigido por matriz y E3). El estado guardado pertenece al dominio y conserva el significado clínico; el impacto es menor, aunque se incumple el dominio literal. Atención inicial: Desarrollo, por la primera discrepancia comprobada en API pública. Hipótesis de causa probable: normalización con `.upper()` en `retroalimentacion_clinica.py:45` (código revisado `origin/test daefc3a5`); causa raíz no confirmada.
- INC-M04-G067-205-02 — valor numérico: severidad BAJA; discrepancia CONFIRMADA por API pública (HTTP 400 VAL_ENTRADA y «El valor ingresado debe ser un texto.» frente al HTTP 422 y mensaje de estado no válido exigidos por E3). Hubo rechazo completo sin persistencia: solo difieren código y mensaje, con posible impacto en clientes que interpreten el código. Atención inicial: Desarrollo, por la primera discrepancia comprobada en API pública. Hipótesis de causa probable: la ruta no declara `x-codigo-validacion 422` (`error_handlers.py:193-200`); causa raíz no confirmada.

## Problemas técnicos y análisis de causas

Ninguno. Derivación inicial según primera discrepancia pública; causa raíz no atribuida.

## Historial, cierre y rollback

62 solicitudes. DELETE HTTP 200; rollback verificado por lectura pública: Registros del RUN ausentes en historial público poscierre. Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

Desarrollo debe revisar las discrepancias API confirmadas en TEST y repetir los casos afectados en un RUN autorizado.

## Herramientas

Newman 6.2.2: 13 iteraciones, 13 solicitudes y 26 aserciones. Reportes reales saneados en newman/. Login, descubrimiento, lecturas y cierre por fetch.

## Evidencias

- preflight.json
- resultado.json
- TC-M04-G067_resultado.md
- newman/newman-G067-POST-209-1.json
- newman/newman-G067-POST-209-1.html
- newman/newman-G067-POST-209-2.json
- newman/newman-G067-POST-209-2.html
- newman/newman-G067-POST-209-3.json
- newman/newman-G067-POST-209-3.html
- newman/newman-G067-POST-209-4.json
- newman/newman-G067-POST-209-4.html
- newman/newman-G067-POST-207-1.json
- newman/newman-G067-POST-207-1.html
- newman/newman-G067-POST-207-2.json
- newman/newman-G067-POST-207-2.html
- newman/newman-G067-POST-208-1.json
- newman/newman-G067-POST-208-1.html
- newman/newman-G067-POST-208-2.json
- newman/newman-G067-POST-208-2.html
- newman/newman-G067-POST-206-1.json
- newman/newman-G067-POST-206-1.html
- newman/newman-G067-POST-205-1.json
- newman/newman-G067-POST-205-1.html
- newman/newman-G067-POST-205-2.json
- newman/newman-G067-POST-205-2.html
- newman/newman-G067-POST-205-3.json
- newman/newman-G067-POST-205-3.html
- newman/newman-G067-POST-205-4.json
- newman/newman-G067-POST-205-4.html

## Revisión QA (2026-10-29)

Se completaron los motivos recortados de 205 y 209, se precisaron las observaciones de 205 y 206, y se sustituyó `?;` por «—» en respuestas 201 sin código de error. Las incidencias recibieron los identificadores INC-M04-G067-205-01 y INC-M04-G067-205-02; sus severidades pasaron de ALTA y MEDIA a BAJA, respectivamente, por persistencia normalizada dentro del dominio y por rechazo completo sin persistencia. Los veredictos de los cinco casos no cambiaron. `resultado.json` permanece sin cambios y conserva los motivos originales del ejecutor, incluida su descripción histórica de «registro inválido» para 205-minusculas; la evidencia estructurada del mismo archivo registra `estado_persistido: CORRECTO`.
