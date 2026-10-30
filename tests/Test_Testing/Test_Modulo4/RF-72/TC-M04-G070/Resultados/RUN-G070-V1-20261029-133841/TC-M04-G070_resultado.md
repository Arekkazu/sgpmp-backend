# TC-M04-G070 — RECHAZADO

## Identificación

Grupo G070; casos TC-M04-214, TC-M04-215, TC-M04-216, TC-M04-217, TC-M04-218; RF-72; versión 1; RUN RUN-G070-V1-20261029-133841; ambiente TEST; autorización AUT-G070-V1-20261029; commit revisado origin/test daefc3a5. Node.js y Newman 6.2.2; solo API.

## Decisión del caso

| Caso | Veredicto | Decisión en lenguaje llano |
|---|---|---|
| TC-M04-214 | APROBADO | La fecha asignada por el servidor cumple la regla temporal. |
| TC-M04-215 | APROBADO | Los límites de 89, 90 y 91 días cumplen la regla. |
| TC-M04-216 | RECHAZADO | Falta configurar la ventana desde M09. |
| TC-M04-217 | RECHAZADO | Falta ampliar la ventana para un resultado concreto. |
| TC-M04-218 | APROBADO | El rechazo explica el vencimiento y cómo pedir asistencia. |

RUN oficial: sí.

Qué falta: nada.

## Precondición de datos (semilla de ventana)

Antigüedad calculada al descubrimiento como floor((hora actual UTC − fecha_inferencia)/24 h), equivalente a .days del backend. Según el contexto de la semilla, su COMMIT fue el 2026-10-29 13:34:38 UTC y el RUN comenzó a las 13:38 UTC. Las fechas sembradas son anteriores al alta del activo 885 (2026-10-24) y al registro de la versión 43 (2026-10-21); ningún caso de G070 verifica esa coherencia histórica.

| Tramo | Resultado | Fecha inferencia | Días backend | Horas | En tramo |
|---|---|---|---|---|---|
| reciente | 511a6d66-a862-4822-bf47-2634333531b3 | 2026-10-28T00:06:22Z | 1 | 37.539 | sí |
| d89 | 11e12f40-37f7-4793-a744-b843fe391546 | 2026-08-01T12:34:36.477639Z | 89 | 2137.069 | sí |
| d90 | ac952c1d-5574-4223-92ab-2df8a8ac9e32 | 2026-07-31T12:34:36.477639Z | 90 | 2161.069 | sí |
| d90h | fb07d478-2993-45a0-8636-02e62fd22c82 | 2026-07-31T01:34:36.477639Z | 90 | 2172.069 | sí |
| d91 | 7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff | 2026-07-30T12:34:36.477639Z | 91 | 2185.069 | sí |
| d120a | cb261b4f-071e-4cfb-afcf-8846fae738be | 2026-07-01T13:34:36.477639Z | 120 | 2880.069 | sí |
| d120b | 2363c367-bdc5-4680-9c88-6d5d67b78b0f | 2026-07-01T11:34:36.477639Z | 120 | 2882.069 | sí |

Candidatos observados de 88 a 121 días, incluidos los que quedaron fuera de tramo:

| Resultado | Fecha inferencia | Días backend | Horas |
|---|---|---|---|
| 11e12f40-37f7-4793-a744-b843fe391546 | 2026-08-01T12:34:36.477639Z | 89 | 2137.069 |
| ac952c1d-5574-4223-92ab-2df8a8ac9e32 | 2026-07-31T12:34:36.477639Z | 90 | 2161.069 |
| fb07d478-2993-45a0-8636-02e62fd22c82 | 2026-07-31T01:34:36.477639Z | 90 | 2172.069 |
| 7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff | 2026-07-30T12:34:36.477639Z | 91 | 2185.069 |
| cb261b4f-071e-4cfb-afcf-8846fae738be | 2026-07-01T13:34:36.477639Z | 120 | 2880.069 |
| 2363c367-bdc5-4680-9c88-6d5d67b78b0f | 2026-07-01T11:34:36.477639Z | 120 | 2882.069 |

## Detalle por caso

### TC-M04-214 — APROBADO

- **Qué se hizo:** Se envió POST /prediccion/retroalimentacion para 511a6d66-a862-4822-bf47-2634333531b3 con timestamp_retroalimentacion anterior a su inferencia (2026-10-28T00:06:22Z); se contrastó la respuesta con historial y auditoría.
- **Qué se esperaba:** E7: HTTP 422 sin persistencia; si la API ignora el campo, HTTP 201 con fecha del servidor posterior a la inferencia y distinta de la enviada (RF-72, línea 4166; E7, líneas 4272–4276).
- **Qué se observó:** 511a6d66-a862-4822-bf47-2634333531b3: HTTP 201; fecha_retroalimentacion del servidor 2026-10-29T13:38:43.889162Z. resultado.json confirma fecha distinta de la enviada y registro en historial y auditoría.
- **Por qué APROBADO:** El campo anterior no alteró la fecha almacenada: la asignación del servidor satisface la consistencia temporal y la alternativa admitida por el oráculo.

### TC-M04-215 — APROBADO

- **Qué se hizo:** Se registraron resultados de 89 días (11e12f40-37f7-4793-a744-b843fe391546; 2137.069 h), 90 días (ac952c1d-5574-4223-92ab-2df8a8ac9e32; 2161.069 h) y se intentó uno de 91 días (7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff; 2185.069 h). Se observó aparte el de 90 días más 12 horas (fb07d478-2993-45a0-8636-02e62fd22c82; 2172.069 h).
- **Qué se esperaba:** 89 y 90 días: HTTP 201; 91 días: HTTP 422 E9 y sin registro. El de 90 días más 12 horas es observación, sin oráculo fijado (RF-72, líneas 4096–4108; E9, líneas 4285–4297; CA-13, líneas 4390–4391).
- **Qué se observó:** 89 d: 11e12f40-37f7-4793-a744-b843fe391546: HTTP 201; 90 d: ac952c1d-5574-4223-92ab-2df8a8ac9e32: HTTP 201; 91 d: 7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff: HTTP 422 FUERA_DE_VENTANA_TEMPORAL, mensaje «La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff. La ventana válida para este resultado venció el 2026-10-28. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo.». Sin registro ni auditoría de registro para 91 días según resultado.json. Observación 90 d + 12 h: fb07d478-2993-45a0-8636-02e62fd22c82: HTTP 201.
- **Por qué APROBADO:** Los tres límites con oráculo dieron la respuesta exigida y el vencido no se persistió. La aceptación del intento adicional se informa por separado porque la matriz no fija su frontera.

### TC-M04-216 — RECHAZADO

- **Qué se hizo:** El Administrador consultó GET /openapi.json y GET /configuracion/parametros para buscar lectura y cambio de ventana_retroalimentacion_dias desde M09.
- **Qué se esperaba:** M09 debe permitir al Administrador configurar de 7 a 365 días, con rechazos de 6 y 366 y comportamiento de 7/8 y 365/366; la ausencia de operación pública acredita la función ausente (RF-72, líneas 4102–4104).
- **Qué se observó:** GET /openapi.json: HTTP 200; GET /configuracion/parametros: HTTP 200. No se halló ruta de lectura o cambio de esa ventana ni el parámetro en la respuesta de configuración.
- **Por qué RECHAZADO:** No hay control público para ejecutar los límites configurables. La lectura dinámica del parámetro por el backend no reemplaza la configuración administrativa: hoy solo consta un script fuera de línea con conexión directa a BD.

### TC-M04-217 — RECHAZADO

- **Qué se hizo:** Se intentó registrar el resultado vencido cb261b4f-071e-4cfb-afcf-8846fae738be y se revisó OpenAPI en busca de una ampliación justificada por resultado; 2363c367-bdc5-4680-9c88-6d5d67b78b0f sirvió de segundo control vencido.
- **Qué se esperaba:** Antes de la ampliación: 422 E9; después, solo el resultado ampliado debe aceptar 201, con justificación y auditoría, mientras el segundo sigue rechazado. Sin operación expuesta, se constata la funcionalidad ausente (RF-72, línea 4110).
- **Qué se observó:** Primer resultado: cb261b4f-071e-4cfb-afcf-8846fae738be: HTTP 422 FUERA_DE_VENTANA_TEMPORAL; segundo: 2363c367-bdc5-4680-9c88-6d5d67b78b0f: HTTP 422 FUERA_DE_VENTANA_TEMPORAL. resultado.json confirma ausencia de registro en ambos y falta de operación de ampliación por resultado en OpenAPI.
- **Por qué RECHAZADO:** El rechazo inicial cumple el control previo, pero falta el mecanismo puntual que permitiría registrar una excepción justificada y auditable.

### TC-M04-218 — APROBADO

- **Qué se hizo:** Se inspeccionó el cuerpo del POST vencido para 2363c367-bdc5-4680-9c88-6d5d67b78b0f y se comparó su fecha límite con fecha_inferencia 2026-07-01T11:34:36.477639Z más 90 días en la zona del usuario.
- **Qué se esperaba:** E9 debe indicar días de ventana, identificador del resultado, fecha exacta de vencimiento y contacto al administrador (E9, línea 4294).
- **Qué se observó:** 2363c367-bdc5-4680-9c88-6d5d67b78b0f: HTTP 422 FUERA_DE_VENTANA_TEMPORAL; mensaje «La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 2363c367-bdc5-4680-9c88-6d5d67b78b0f. La ventana válida para este resultado venció el 2026-09-29. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo.».
- **Por qué APROBADO:** El mensaje contiene los 90 días, el identificador, la fecha de vencimiento y el contacto exigidos; 2026-09-29 coincide con fecha_inferencia más 90 días en America/Bogota.

## Intentos Newman

| Nombre | Resultado | HTTP | Código | Mensaje | Persistió |
|---|---|---|---|---|---|
| G070-214 | 511a6d66-a862-4822-bf47-2634333531b3 | 201 | — | — | sí |
| G070-215-89 | 11e12f40-37f7-4793-a744-b843fe391546 | 201 | — | — | sí |
| G070-215-90 | ac952c1d-5574-4223-92ab-2df8a8ac9e32 | 201 | — | — | sí |
| G070-215-90H | fb07d478-2993-45a0-8636-02e62fd22c82 | 201 | — | — | no comprobado |
| G070-215-91 | 7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 7d597a54-2d05-43d6-a12b-ad8a7c8ac4ff. La ventana válida para este resultado venció el 2026-10-28. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. | no |
| G070-217-120A | cb261b4f-071e-4cfb-afcf-8846fae738be | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia cb261b4f-071e-4cfb-afcf-8846fae738be. La ventana válida para este resultado venció el 2026-09-29. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. | no |
| G070-218-120B | 2363c367-bdc5-4680-9c88-6d5d67b78b0f | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 2363c367-bdc5-4680-9c88-6d5d67b78b0f. La ventana válida para este resultado venció el 2026-09-29. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. | no |

## Observaciones

OBS-M04-G070-215 — El resultado de 90 días y 12 horas (2172.069 h, más de 90×24 h) recibió HTTP 201 porque el backend cuenta días completos de 24 h. La matriz no fija este punto como oráculo y RF-72 habla de 90 días calendario; Desarrollo y el responsable QA deben confirmar la frontera deseada.

El backend lee el parámetro de ventana dinámicamente; hoy el cambio solo consta por script fuera de línea con acceso directo a BD. Esta lectura de código es hipótesis de implementación, no comprobación de configuración desde M09.

## Incidencias de producto

- **INC-M04-G070-216-01 — MEDIA; certeza CONFIRMADA en la superficie pública de TEST; atención inicial Desarrollo.** La ventana no se puede configurar desde M09 por el Administrador. Los 90 días por defecto y los rechazos funcionan, pero cambiarla exige un script técnico con acceso a BD fuera del producto; sin riesgo demostrado para los datos. Primera discrepancia: OpenAPI y GET /configuracion/parametros no ofrecen escritura pública de ventana_retroalimentacion_dias; M09 no puede configurarla. La derivación atiende la API pública y no atribuye causa raíz.
- **INC-M04-G070-217-01 — MEDIA; certeza CONFIRMADA en la superficie pública de TEST; atención inicial Desarrollo.** No existe la excepción por resultado: un veterinario no puede registrar retroalimentación justificada fuera de plazo; cambiar la ventana global por script afectaría a todos los resultados; sin riesgo demostrado para los datos. Primera discrepancia: Ambos resultados de 120 días rechazados con E9 y sin registro; OpenAPI no expone ampliación puntual por Administrador. La derivación atiende la API pública y no atribuye causa raíz.

## Problemas técnicos y análisis de causas

Ninguno. Hipótesis de causa, no confirmada: configurar_parametros_mlops_use_case.py:6 y scripts/configurar_parametros_dev14.py muestran configuración por script sin endpoint; en origin/test daefc3a5 no se identificó operación de ampliación. La revision de codigo previa, citada en README, incluye: src/configuration/application/use_cases/configuracion_global/configurar_parametros_mlops_use_case.py, scripts/configurar_parametros_dev14.py, src/configuration/infrastructure/routers/configuracion_global_router.py, src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py. En este cierre no se releyeron esos archivos funcionales. La derivación inicial no atribuye causa raíz.

## Cierre y rollback

Intento 1; solicitudes 17/142. DELETE HTTP 200. Rollback verificado: DELETE 200 y ausencia de nuevos registros en historial poscierre. Las lecturas posteriores pueden generar HISTORIAL_CONSULTADO fuera del sandbox.

## Conclusión y acciones

G070 RECHAZADO por 216 y 217: faltan las funciones administrativas. 214, 215 y 218 cumplen. Desarrollo debe exponer la configuración de la ventana en M09 y la excepción por resultado auditada en RF-73. Desarrollo y el responsable QA deben confirmar la frontera observada en 215.

## Herramientas y evidencias

Newman: 1 iteración; 7 solicitudes; 14 aserciones. Sin UI obligatoria.

- preflight.json
- newman/newman-G070.json
- newman/newman-G070.html
- resultado.json
- TC-M04-G070_resultado.md

## Revisión QA (2026-10-29)

Se ajustaron estructura, datos por caso, observación en lenguaje llano y severidades documentales ALTA → MEDIA con justificación de impacto. Los veredictos, resultado.json y newman/ no cambiaron. resultado.json conserva la severidad ALTA original como evidencia histórica; la valoración vigente para estas dos incidencias es MEDIA en este informe.
