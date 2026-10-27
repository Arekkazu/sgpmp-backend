# TC-M03-G127 — APROBADO

## Decisión del caso

Caso agrupado: **TC-M03-G127 (RF-59/CU04)**. Caso original: **TC-M03-256**. Decisión: **APROBADO**.

Motivo: el evento RF-63 **HISTORIAL_CONSULTADO** `cfca1f87-0c58-4bd4-8fcf-65f117ec7f4b` contiene usuario, rol, filtros con rango temporal, cantidad de registros, timestamp y `exportado=false`, conforme a CA-16 (Modulo3.md:6281-6284).

| Dato exigido | Valor observado | Cumple |
| --- | --- | --- |
| Usuario y rol | `id_usuario=35`; `id_rol=2` | Sí |
| Filtros y rango temporal | `sensor_id=6`; `fecha_inicio=2026-10-20`; `fecha_fin=2026-10-27`; `por_pagina=37` | Sí |
| Cantidad de registros | `registros_devueltos=3`, igual al total del historial | Sí |
| Timestamp | `2026-10-27T00:57:43.108627Z`, dentro de la ventana de auditoría | Sí |
| Indicador de exportación | `exportado=false` | Sí |

RUN oficial: **sí** (registro QA **OFICIAL**; DELETE HTTP 200; rollback verificado para ausencia de escrituras de negocio del escenario). Qué falta: el formato de exportación **NO APLICA** mientras M08 responda 503 `M08_NO_DISPONIBLE`; reevaluar ese formato cuando exista M08. Nada más pendiente.

## Identificación

Grupo G127; caso TC-M03-256; RF-59/CU04; versión V1; RUN RUN-G127-V1-20261027-005735; ambiente TEST; autorización AUT-G127-V1-20261027; commit TEST no verificado; referencia de código origin/test leída, no acredita despliegue. Newman 6.2.2; Cypress no requerido, 0 ejecuciones. Clasificación OFICIAL; consume versión true.

## Esperado y observado por caso

La matriz TC-M03-G127:194-195 espera un registro con usuario, filtros aplicados, rango temporal, cantidad de registros y timestamp; el formato se comprueba solo cuando exista exportación. RF-59 Fase 8:5982-5990, Postcondición 6:6224-6226 y CA-16:6281-6284.

| Caso | Comprobación | Estado | Esperado | Observado | Evidencia |
| --- | --- | --- | --- | --- | --- |
| TC-M03-256 | API-256-01 | APROBADO | Evento RF-63 completo de la consulta del RUN | APROBADO: Evento cfca1f87-0c58-4bd4-8fcf-65f117ec7f4b contiene los datos exigidos por CA-16. Valores observados: {"id_evento":"cfca1f87-0c58-4bd4-8fcf-65f117ec7f4b","id_usuario":35,"id_rol":2,"sensor_id":6,"fecha_inicio":"2026-10-20","fecha_fin":"2026-10-27","por_pagina":37,"registros_devueltos":3,"timestamp":"2026-10-27T00:57:43.108627Z","exportado":false} | newman/newman-G127.json |

## Comprobaciones API/UI y evidencias

Consulta elegida: {"inicio":"2026-10-20","fin":"2026-10-27","sensorId":6}. Selección saneada: [{"sensor_id":6,"inicio":"2026-10-20","fin":"2026-10-27","total":3,"muestra_sensor":true,"http":200,"eco":true}]. Respuesta del historial: {"http":200,"eco":true,"total":3,"registros_devueltos":3}. Auditoría: {"busquedas":1,"filtro":{"tipo_evento":"HISTORIAL_CONSULTADO","rf_origen":"RF59","id_usuario":35,"fecha_desde":"2026-10-27T00:57:30.090Z","fecha_hasta":"2026-10-27T00:59:40.090Z"},"total_ultimo":2,"estado":"APROBADO","motivo":"Evento cfca1f87-0c58-4bd4-8fcf-65f117ec7f4b contiene los datos exigidos por CA-16","valores":{"id_evento":"cfca1f87-0c58-4bd4-8fcf-65f117ec7f4b","id_usuario":35,"id_rol":2,". Exportación informativa: {"estado":"NO_APLICA","http":503,"eco":true,"error":{"codigo":"M08_NO_DISPONIBLE","mensaje":"El módulo de exportación (M08) no está disponible en este entorno. Reintente más tarde."},"formato_solicitado":"PDF","eventos_fallida":0}. UI no obligatoria, cero ejecuciones. Evidencias reales: preflight.json, newman/newman-G127.json, newman/newman-G127.html, resultado.json, TC-M03-G127_resultado.md.

## Incidencias de producto

Ninguna discrepancia de producto confirmada en TEST.

## Incidencias técnicas QA

Ninguna.

## Análisis de causas y observaciones

La primera lectura de RF-63 se hizo después de la consulta. Se correlacionó con usuario, sensor, por_pagina=37 y ventana temporal; el resultado de una selección previa no se usa como evento del caso. CA-16 también exige “si se exportó” para cualquier consulta; la ausencia de `exportado=false` habría rechazado la consulta normal, pero en este RUN estaba presente. M08 respondió 503 M08_NO_DISPONIBLE: el formato de exportación NO APLICA; esto no bloquea la consulta. La bitácora RF-63 usa commit en la sesión de la petición; el evento puede persistir fuera del rollback del RUN.

Desviación de alcance observada por el orquestador al revisar y reportada al responsable QA: después del 503 de exportación, el ejecutor hizo un GET `/iot/auditoria?tipo_evento=EXPORTACION_FALLIDA&id_usuario=35&rf_origen=RF59` dentro del RUN (HTTP 200, eco true, 0 eventos). SOL-G127-002 solo preveía búsquedas de formato si la exportación respondía 200. Fue solo lectura, quedó dentro del presupuesto (5 de 14 solicitudes directas) y no influyó en la decisión de API-256-01.

## Cierre y rollback

Login Productor y Administrador anteriores a las peticiones del RUN pueden persistir sesión o auditoría. No hubo escrituras de negocio. DELETE RUN HTTP 200. Rollback verificado solo para ausencia de escrituras de escenario y cierre: Sin escrituras de negocio del escenario; DELETE 200. Auditoría RF-63 y sesiones pueden persistir. La persistencia de auditoría y sesiones no se considera revertida.

La lectura extra de bitácora `EXPORTACION_FALLIDA` fue un GET dentro del RUN, sin escritura de negocio y sin efecto en el veredicto ni en el alcance verificado del rollback.

## Conclusión y acción

APROBADO. Sin incidencias de producto; la observación sobre el formato de exportación no aplica mientras M08 responda 503 `M08_NO_DISPONIBLE`. Reevaluar el formato cuando exista M08.
