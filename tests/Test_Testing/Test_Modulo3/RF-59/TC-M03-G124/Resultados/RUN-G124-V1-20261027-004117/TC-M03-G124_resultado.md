# TC-M03-G124 — BLOQUEADO

## Decisión del caso

TC-M03-249: **BLOQUEADO** (REQUISITO_DEPENDIENTE) — M08 RF-10 no disponible: no se puede comprobar la estructura del archivo exigida por RF-59 CA-10/CA-11.

TC-M03-250: **BLOQUEADO** (REQUISITO_DEPENDIENTE) — M08 RF-10 no disponible: no se puede comprobar la estructura del archivo exigida por RF-59 CA-10/CA-11.

TC-M03-254: **BLOQUEADO** (REQUISITO_DEPENDIENTE) — M08 RF-10 no genera archivos; no se pueden comprobar los umbrales 5.000/5.001 PDF y 50.000/50.001 Excel.

## Identificación

Grupo G124; RF-59/CU04; versión V1; RUN RUN-G124-V1-20261027-004117; ambiente TEST; autorización AUT-G124-V1-20261026; commit TEST no verificado; referencia de código origin/test 254deee6f3d3cb68bd14a76aabdac8fa4afae3fd consultado; commit desplegado en TEST no verificado; Newman 6.2.2; Cypress no requerido (API solamente), 0 ejecuciones. Clasificación del registro: TÉCNICO; consume versión: false.

## Esperado y observado por caso

| Caso | Comprobación | Fuente | Estado | Esperado | Observado | Evidencia |
| --- | --- | --- | --- | --- | --- | --- |
| TC-M03-249 | API-249-01 | API | BLOQUEADO | PDF con encabezado de metadatos (granja, periodo, filtros aplicados, usuario), gráfica de tendencia, tabla de registros con estado de semáforo, resumen estadístico y pie de página con timestamp de generación. | M08 RF-10 no disponible: no se puede comprobar la estructura del archivo exigida por RF-59 CA-10/CA-11 | newman/newman-G124.json |
| TC-M03-250 | API-250-01 | API | BLOQUEADO | Excel con hoja 1 de datos crudos con todos los campos, hoja 2 de resumen estadístico por variable y hoja 3 de alertas correlacionadas, con metadatos en el encabezado de cada hoja. | M08 RF-10 no disponible: no se puede comprobar la estructura del archivo exigida por RF-59 CA-10/CA-11 | newman/newman-G124.json |
| TC-M03-254 | API-254-01 | API | BLOQUEADO | PDF de 5.000 y Excel de 50.000 registros se procesan; a 5.001 y 50.001 se fragmenta la exportación y se informa al usuario. | M08 RF-10 no genera archivos; no se pueden comprobar los umbrales 5.000/5.001 PDF y 50.000/50.001 Excel | newman/newman-G124.json |

## Dependencia M08

RF-59 precondición 8 (Especificacion-Requerimientos-Modulo3.md:5654-5655) requiere generadores funcionales RF-10 de M08. La matriz TC-M03-G124:184-193 anota 503 M08_NO_DISPONIBLE como bloqueo esperado para 249/250 sin alterar los archivos esperados. RF-59 CA-10:6263-6264 y CA-11:6266-6267 conservan el oráculo PDF/Excel. La restricción 13:5703-5716 fija los umbrales y la matriz exige fragmentación. La matriz atribuye esto a CU04 FA-10, pero las anotaciones disponibles cu04_gaps_bd_rf58_rf59.md:92 y curls_m03_cu04_monitoreo_historial.md:317 describen FA-10 como truncado de consultas de 10.000, no fragmentación de exportación; aclaración documental pendiente de QA. FA-11 se refleja en api_reference_m03_telemetria_iot.md:559-567 (400 EXPORTAR_SIN_FILTROS). Si M08 no genera archivos, 254 tampoco puede acreditar los cuatro umbrales. La decisión final de bloqueo corresponde al responsable QA.

## Comprobaciones API/UI y evidencias

Consulta elegida: {"sensorId":6,"inicio":"2026-10-20","fin":"2026-10-27"}. Diagnóstico saneado de selección: {"modo":"seleccion_automatica","intentos":[{"fuente":"sensor_6_7_dias","sensor_id":6,"inicio":"2026-10-20","fin":"2026-10-27","total":3,"muestra_sensor":true,"http":200,"eco":true}],"unidades":[],"sensores_dashboard":0,"alcance_incompleto":false,"seleccion":{"fuente":"sensor_6_7_dias","sensor_id":6,"inicio":"2026-10-20","fin":"2026-10-27","total":3}}. Respuestas saneadas: {"historial":{"http":200,"eco":true,"total":3,"error":null},"PDF":{"http":503,"eco":true,"bytes":197,"sha256":"8a99f1ad3dd400f9b3bd0aed584cc9c201a4e5425ea020c39f84a72c981e6b23","error":{"codigo":"M08_NO_DISPONIBLE","mensaje":"El módulo de exportación (M08) no está disponible en este entorno. Reintente más tarde."},"validacion":null},"EXCEL":{"http":503,"eco":true,"bytes":197,"sha256":"bff3ed673aff9632ad3c6bde3f74589c62f97ee3fec46186416a0154c2853f3d","error":{"codigo":"M08_NO_DISPONIBLE","mensaje":"El módulo de exportación (M08) no está disponible en este entorno. Reintente más tarde."},"validacion":null}}. Comprobaciones API: API-249-01=BLOQUEADO, API-250-01=BLOQUEADO, API-254-01=BLOQUEADO. UI no obligatoria, 0 ejecuciones. Evidencias reales en este RUN: preflight.json, newman/newman-G124.json, newman/newman-G124.html, resultado.json, TC-M03-G124_resultado.md.

## Incidencias de producto

Ninguna discrepancia de producto confirmada en TEST.

## Incidencias técnicas QA

Ninguna.

## Análisis de causas y observaciones

La referencia origin/test no confirma la versión desplegada. Un fallo de Newman, petición, permisos o transporte se separa de las respuestas públicas. RF-59 E5:6056-6068 exige aviso, sugerencia de reducir rango/filtros, bitácora técnica y datos visibles; API sola no acredita toda la interfaz. No se ejecutaron volúmenes masivos ni exportaciones concurrentes.

## Cierre y rollback

Login Productor antes del RUN y los GET pueden registrar sesión o auditoría persistente. No hubo escrituras de escenario. DELETE RUN HTTP 200. Rollback verificado por ausencia de escrituras de escenario y cierre 200: Sin escrituras de escenario; DELETE 200. No acredita reversión de sesión, auditoría ni correos del dashboard.

## Conclusión y próxima acción

BLOQUEADO. Responsable QA debe revisar la dependencia o la incidencia técnica y decidir un intento autorizado cuando M08 esté disponible.
