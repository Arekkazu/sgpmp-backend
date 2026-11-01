# TC-M04-G070 — reevaluación V2 APROBADO

## Identificación

Grupo G070; TC-M04-214, TC-M04-215, TC-M04-216, TC-M04-217, TC-M04-218; RF-72; versión 2; RUN-G070-V2-20261101-045537; ambiente TEST; autorización AUT-G070-V2-R3-20261101. Reevaluación de V1 por issue #865 / PR #871; commit de código desplegado: no verificado; Alembic de TEST informado en contexto: c31f8a6d920e. Node.js y Newman 6.2.2; API pública.

## Decisión del caso

| Caso | Veredicto | Motivo |
|---|---|---|
| TC-M04-214 | APROBADO | Campo anterior ignorado; 201 y timestamp del servidor posterior a inferencia y distinto del enviado; registro y auditoría comprobados |
| TC-M04-215 | APROBADO | 89 y 90 HTTP 201; 91 HTTP 422 E9 sin persistencia ni auditoría de registro |
| TC-M04-216 | APROBADO | Rango, validaciones, RBAC, GET y lectura dinámica de RF-72 comprobados; ventana restaurada a 90 |
| TC-M04-217 | APROBADO | A ampliado aceptado; B vencido rechazado; global 90; RF-73, validaciones y RBAC comprobados |
| TC-M04-218 | APROBADO | E9 contiene 90 días, id, fecha límite 2026-09-29 y contacto al administrador |

RUN oficial: sí. Qué falta: nada para la decisión de esta versión.

## V1 → V2

| Caso | V1 | V2 | Incidencia |
|---|---|---|---|
| TC-M04-214 | APROBADO | APROBADO | Regresión |
| TC-M04-215 | APROBADO | APROBADO | Regresión |
| TC-M04-216 | RECHAZADO | APROBADO | CORREGIDA |
| TC-M04-217 | RECHAZADO | APROBADO | CORREGIDA |
| TC-M04-218 | APROBADO | APROBADO | Regresión |

Intentos técnicos anteriores V2: [intento 1](api/antecedentes/intento_1.json) quedó en preflight, sin peticiones; [intento 2](api/antecedentes/intento_2.json) tuvo 214–216 APROBADO y 217–218 NO_CONCLUYENTE por selección de datos fuera del tramo, con DELETE 200 y configuración restaurada a 90. Los [SHA-256 originales](api/antecedentes/indice.json) documentan la procedencia. La eliminación de ambas carpetas técnicas fue autorizada por el responsable QA el 2026-11-01 y queda a cargo del orquestador; los extractos permanecen en el RUN oficial.

INC-M04-G070-216-01 e INC-M04-G070-217-01 se consideran corregidas solo cuando sus respectivos casos quedan APROBADOS en un RUN oficial de TEST.

## Precondición de datos

COMMIT de la semilla: 2026-11-01T04:30:40.915Z. Hora de descubrimiento: 2026-11-01T04:55:39.000Z. La antigüedad se calcula frente a la hora observada del servidor; el sandbox fija now() al inicio. A (122 días completos) y B (122 días completos) deben estar vencidos, libres de retroalimentación previa y ser distintos de los resultados de 215.

| Tramo | Resultado | Inferencia | Días completos | Horas | Disponible |
|---|---|---|---|---|---|
| reciente | 511a6d66-a862-4822-bf47-2634333531b3 | 2026-10-28T00:06:22Z | 4 | 100.821 | sí |
| d89 | d929c162-d834-4d8c-b130-a05c88b40694 | 2026-08-04T03:30:38.781945Z | 89 | 2137.417 | sí |
| d90 | 7c215bf1-fbe3-4d94-97ac-454cb4d6eb19 | 2026-08-03T03:30:38.781945Z | 90 | 2161.417 | sí |
| d90h | 8f7c7542-4d94-4679-ac0f-807141e19980 | 2026-08-02T16:30:38.781945Z | 90 | 2172.417 | sí |
| d91 | 50e68201-2a59-4699-9c4a-db825c9ebc49 | 2026-08-02T03:30:38.781945Z | 91 | 2185.417 | sí |
| vencido A | 2363c367-bdc5-4680-9c88-6d5d67b78b0f | 2026-07-01T11:34:36.477639Z | 122 | 2945.351 | sí |
| vencido B | cb261b4f-071e-4cfb-afcf-8846fae738be | 2026-07-01T13:34:36.477639Z | 122 | 2943.351 | sí |

## Detalle por caso

### TC-M04-214 — APROBADO

- **Qué se hizo:** G070-214: HTTP 201
- **Qué se esperaba:** Fecha del servidor posterior a la inferencia; E7 422 sin persistencia si se admite timestamp anterior.
- **Qué se observó:** Campo anterior ignorado; 201 y timestamp del servidor posterior a inferencia y distinto del enviado; registro y auditoría comprobados.
- **Por qué APROBADO:** Las comprobaciones públicas y la persistencia observada satisfacen el oráculo indicado.

### TC-M04-215 — APROBADO

- **Qué se hizo:** G070-215-89: HTTP 201; G070-215-90: HTTP 201; G070-215-90H: HTTP 201; G070-215-91: HTTP 422, FUERA_DE_VENTANA_TEMPORAL
- **Qué se esperaba:** W89 y W90: 201; W91: 422 FUERA_DE_VENTANA_TEMPORAL sin registro. W90H se observa aparte.
- **Qué se observó:** 89 y 90 HTTP 201; 91 HTTP 422 E9 sin persistencia ni auditoría de registro.
- **Por qué APROBADO:** Las comprobaciones públicas y la persistencia observada satisfacen el oráculo indicado.

### TC-M04-216 — APROBADO

- **Qué se hizo:** GET configuración: HTTP 200, valor 90; PATCH 6: HTTP 400, PARAMETRO_MLOPS_INVALIDO; PATCH 366: HTTP 400, PARAMETRO_MLOPS_INVALIDO; PATCH decimal: HTTP 400, PARAMETRO_MLOPS_INVALIDO; PATCH ajeno: HTTP 400, PARAMETRO_RETROALIMENTACION_INVALIDO; PATCH 7: HTTP 200, valor 7; GET configuración: HTTP 200, valor 7; PATCH 8: HTTP 200, valor 8; GET configuración: HTTP 200, valor 8; PATCH 365: HTTP 200, valor 365; GET configuración: HTTP 200, valor 365; RF-72 W91 con 365: HTTP 201; PATCH restaurar 90: HTTP 200, valor 90; GET configuración: HTTP 200, valor 90; PATCH Veterinario 90: HTTP 403, ACCESO_DENEGADO; GET configuración: HTTP 200, valor 90
- **Qué se esperaba:** M09 configura 7–365: 6 y 366 rechazados; 7, 8 y 365 aceptados y visibles en GET; decimales y nombres ajenos rechazados; RF-72 usa el nuevo valor; Veterinario no actualiza (403).
- **Qué se observó:** Rango, validaciones, RBAC, GET y lectura dinámica de RF-72 comprobados; ventana restaurada a 90.
- **Por qué APROBADO:** Las comprobaciones públicas y la persistencia observada satisfacen el oráculo indicado.

### TC-M04-217 — APROBADO

- **Qué se hizo:** A antes: HTTP 422, FUERA_DE_VENTANA_TEMPORAL; ampliar A: HTTP 201; auditoría ampliación: HTTP 200; A después: HTTP 201; B después: HTTP 422, FUERA_DE_VENTANA_TEMPORAL; global después: HTTP 200; justificación corta: HTTP 422, VAL_ENTRADA; días 0: HTTP 422, VAL_ENTRADA; días 366: HTTP 422, VAL_ENTRADA; ampliación Veterinario: HTTP 403, ACCESO_DENEGADO
- **Qué se esperaba:** Antes de ampliar, A vencido se rechaza. Tras ampliar A por el Administrador, A da 201, B sigue 422 E9, la ventana global sigue en 90, RF-73 registra autor y justificación; entradas inválidas se rechazan y Veterinario recibe 403.
- **Qué se observó:** A ampliado aceptado; B vencido rechazado; global 90; RF-73, validaciones y RBAC comprobados.
- **Por qué APROBADO:** Las comprobaciones públicas y la persistencia observada satisfacen el oráculo indicado.

### TC-M04-218 — APROBADO

- **Qué se hizo:** B (122 días completos): HTTP 422, FUERA_DE_VENTANA_TEMPORAL
- **Qué se esperaba:** E9 contiene 90 días, id de resultado, fecha límite exacta y contacto al administrador.
- **Qué se observó:** E9 contiene 90 días, id, fecha límite 2026-09-29 y contacto al administrador.
- **Por qué APROBADO:** Las comprobaciones públicas y la persistencia observada satisfacen el oráculo indicado.

## Tabla de intentos

| Caso | Operación | HTTP | Código | Mensaje |
|---|---|---|---|---|
| TC-M04-214 | G070-214 | 201 | — |  |
| TC-M04-215 | G070-215-89 | 201 | — |  |
| TC-M04-215 | G070-215-90 | 201 | — |  |
| TC-M04-215 | G070-215-90H | 201 | — |  |
| TC-M04-215 | G070-215-91 | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 50e68201-2a59-4699-9c4a-db825c9ebc49. La ventana válida para este resultado venció el 2026-10-30. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. |
| TC-M04-218 | B (122 días completos) | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia cb261b4f-071e-4cfb-afcf-8846fae738be. La ventana válida para este resultado venció el 2026-09-29. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. |
| TC-M04-216 | PATCH 6 | 400 | PARAMETRO_MLOPS_INVALIDO | La configuración del parámetro ventana_retroalimentacion_dias es inválida. |
| TC-M04-216 | PATCH 366 | 400 | PARAMETRO_MLOPS_INVALIDO | La configuración del parámetro ventana_retroalimentacion_dias es inválida. |
| TC-M04-216 | PATCH decimal | 400 | PARAMETRO_MLOPS_INVALIDO | La configuración del parámetro ventana_retroalimentacion_dias es inválida. |
| TC-M04-216 | PATCH ajeno | 400 | PARAMETRO_RETROALIMENTACION_INVALIDO | Solo se admiten los parámetros de RF-72: ventana_retroalimentacion_dias. No pertenecen: parametro_no_admitido. |
| TC-M04-216 | PATCH 7 | 200 | — |  |
| TC-M04-216 | PATCH 8 | 200 | — |  |
| TC-M04-216 | PATCH 365 | 200 | — |  |
| TC-M04-216 | RF-72 W91 con 365 | 201 | — |  |
| TC-M04-216 | PATCH restaurar 90 | 200 | — |  |
| TC-M04-216 | PATCH Veterinario 90 | 403 | ACCESO_DENEGADO | Acceso denegado. Su rol no tiene permisos para realizar esta operación. |
| TC-M04-217 | A antes | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 2363c367-bdc5-4680-9c88-6d5d67b78b0f. La ventana válida para este resultado venció el 2026-09-29. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. |
| TC-M04-217 | ampliar A | 201 | — |  |
| TC-M04-217 | A después | 201 | — |  |
| TC-M04-217 | B después | 422 | FUERA_DE_VENTANA_TEMPORAL | La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia cb261b4f-071e-4cfb-afcf-8846fae738be. La ventana válida para este resultado venció el 2026-09-29. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo. |
| TC-M04-217 | justificación corta | 422 | VAL_ENTRADA | Errores de validacion en la solicitud |
| TC-M04-217 | días 0 | 422 | VAL_ENTRADA | Errores de validacion en la solicitud |
| TC-M04-217 | días 366 | 422 | VAL_ENTRADA | Errores de validacion en la solicitud |
| TC-M04-217 | ampliación Veterinario | 403 | ACCESO_DENEGADO | Acceso denegado. Su rol no tiene permisos para realizar esta operación. |

## Observaciones y límites

OBS-M04-G070-215: W90H (2172.417 h) recibió HTTP 201. La frontera de 90 días y 12 horas está pendiente de definición entre QA y Análisis; no cambia el veredicto de 215. La caducidad de la ampliación no puede verificarse en un único RUN de sandbox: now() está fijo y la API solo autoriza al menos un día desde el presente. No afecta el veredicto de 217. La semilla disponible no contiene resultados de 7/8 ni 365/366 días; los límites del parámetro se comprueban por PATCH/GET y el efecto en el registro con W91 al pasar de 90 a 365.

## Incidencias de producto

Ninguna incidencia de producto nueva.

## Problemas técnicos y análisis de causas

Ninguno. La derivación inicial se basa en la primera discrepancia API comprobada; causa raíz no determinada. README documenta una revisión previa de src/configuration/infrastructure/routers/parametros_retroalimentacion_router.py, src/configuration/application/use_cases/configuracion_global/parametros_retroalimentacion_use_case.py, src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py, src/prediction/application/use_cases/retroalimentacion/ampliar_ventana_retroalimentacion_use_case.py y alembic/versions/6bd01d026ac4_rf72_ampliacion_ventana_retroalimentacion.py. En ORD-G070-011 no se releyó código funcional.

## Cierre y rollback

Intento 4; solicitudes 45/209. DELETE HTTP 200. Rollback verificado: DELETE 200; sin nuevos registros, configuración en 90 y evento de ampliación ausente cuando fue identificable. La configuración se restauró por PATCH y GET antes de 217: sí.

## Conclusión y acciones

Los cinco casos cumplen la reevaluación. Registrar como corregidas las incidencias 216 y 217 y acordar con Análisis la frontera observada en 215.

## Herramientas y evidencias

Newman: 1 iteración; 6 solicitudes; 12 aserciones. Sin UI obligatoria según los casos originales.

- preflight.json
- newman/newman-G070.json
- newman/newman-G070.html
- resultado.json
- TC-M04-G070_reevaluacion_V2.md
