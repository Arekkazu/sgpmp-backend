# TC-M09-G135 — Resultado

RUN_ID: run-20261007-095851 · TEST · APROBADO · 6/6 POST de calibración.

## Decisión general

| Caso | Rechazo esperado | HTTP obtenido | Evento FALLIDO | Resultado | Motivo |
|---|---:|---:|---|---|---|
| TC-M09-268 | 403 | 403 | Sí | APROBADO | HTTP 403, historial intacto y evento RF-10 38827 completo/correlacionado. |
| TC-M09-269 | 422 | 422 | Sí | APROBADO | HTTP 422, historial intacto y evento RF-10 38829 completo/correlacionado. |
| TC-M09-270 | 400 | 400 | Sí | APROBADO | HTTP 400, historial intacto y evento RF-10 38831 completo/correlacionado. |
| TC-M09-271 | 400 | 400 | Sí | APROBADO | HTTP 400, historial intacto y evento RF-10 38833 completo/correlacionado. |
| TC-M09-272 | 400 | 400 | Sí | APROBADO | HTTP 400, historial intacto y evento RF-10 38835 completo/correlacionado. |
| TC-M09-273 | 404 | 404 | Sí | APROBADO | HTTP 404, historial intacto y evento RF-10 38837 completo/correlacionado. |

## Entorno y actores

- Backend: https://api.inmero.co/back-sigab-test
- Rama: qa/juan-esteban-rf24-v2; HEAD: 30ddd72144102a60af006b265a20cb18c1c72c85; origin/test: 30ddd72144102a60af006b265a20cb18c1c72c85; divergencia HEAD...origin/test: 0	0.
- Estado Git previo: ?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G130/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G131/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G132/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G133/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G134/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G135/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G74-v2.0/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G76-v2.0/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G77-v2.0/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G79-v2.0/
?? tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G80-v2.0/. Diff: (vacío); staged: (vacío).
- Ingeniero: {"correo":"ingeniero@pecuaria.co","id_usuario":4,"rol":"Ingeniero de Campo","estado":"Activo","permisos_calibracion":[1,2,3]}.
- Productor: {"correo":"m2m.nuevo@ejemplo.com","id_usuario":35,"rol":"Productor","estado":"Activo","permisos_calibracion":[2]}.
- Administrador de lectura RF-10: {"correo":"administador.dev@gmail.com","id_usuario":104,"rol":"Administrador","estado":"Activo","auditoria_http":206,"intentos":[{"correo":"admin.dev@gmail.com","problema":"login admin.dev@gmail.com: HTTP 423"},{"correo":"administador.dev@gmail.com","id_usuario":104,"rol":"Administrador","estado":"Activo","auditoria_http":206}]}.
- OpenAPI TEST: {"calibrar":{"presente":true,"codigos":["201","400","401","403","404","422","500"]},"historial":{"presente":true,"codigos":["200","401","403","422"]},"auditoria":{"presente":true,"codigos":["200","206","400","403","422","500"]},"catalogo_tipos":{"presente":true,"codigos":["200","403","422"]}}.
- SQL ejecutado: ninguno. POST funcionales: 6; sin reintentos.

## Resultado por caso

### TC-M09-268 — APROBADO

- Fixture: {"sensor":6,"dispositivo":3,"area":3,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"estado":{"sensor":true,"dispositivo":true,"area":true},"asociaciones_vigentes":[{"id_dispositivo_iot":3,"id_infraestructura":3}]}.
- Ventana del intento: 2026-10-07T09:59:07.076Z → 2026-10-07T09:59:07.730Z; consulta RF-10: 2026-10-07T09:58:07.076Z → 2026-10-07T10:00:07.730Z.
- HTTP esperado/obtenido: 403 / 403; respuesta: {"error_code":"ACCESO_DENEGADO","message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.","fields":[],"timestamp":"2026-10-07T09:59:07.160672+00:00"}.
- Historial PRE/POST: {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]} / {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]}; sin cambios: true.
- GET RF-10: [{"pagina":1,"http":200,"total":3,"items":3}]; candidatos de calibración: 1; evento correlacionado: 38827.
- Evento — resultado: fallido; módulo: MODULO9; usuario: 35; motivo: Acceso denegado. Su rol no tiene permisos para realizar esta operación.; IP: 200.118.62.237.
- Candidatos y campos: [{"id_evento":38827,"resultado":"fallido","modulo":"MODULO9","id_usuario":35,"fecha_evento":"2026-10-07T09:59:07.157250Z","motivo":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}}].
- Decisión y causa observada: **APROBADO**. HTTP 403, historial intacto y evento RF-10 38827 completo/correlacionado.

### TC-M09-269 — APROBADO

- Fixture: {"sensor":29,"dispositivo":47,"area":3,"dispositivo_activo":false,"sensor_activo":true,"area_activa":true,"asociacion":29}.
- Ventana del intento: 2026-10-07T09:59:08.064Z → 2026-10-07T09:59:08.286Z; consulta RF-10: 2026-10-07T09:58:08.064Z → 2026-10-07T10:00:08.286Z.
- HTTP esperado/obtenido: 422 / 422; respuesta: {"error_code":"DISPOSITIVO_INACTIVO","message":"Solo se pueden calibrar sensores de dispositivos activos.","fields":[],"timestamp":"2026-10-07T09:59:07.727816+00:00"}.
- Historial PRE/POST: {"total":0,"ids":[]} / {"total":0,"ids":[]}; sin cambios: true.
- GET RF-10: [{"pagina":1,"http":200,"total":3,"items":3}]; candidatos de calibración: 1; evento correlacionado: 38829.
- Evento — resultado: fallido; módulo: MODULO9; usuario: 4; motivo: Solo se pueden calibrar sensores de dispositivos activos.; IP: 200.118.62.237.
- Candidatos y campos: [{"id_evento":38829,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:07.725140Z","motivo":"Solo se pueden calibrar sensores de dispositivos activos.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}}].
- Decisión y causa observada: **APROBADO**. HTTP 422, historial intacto y evento RF-10 38829 completo/correlacionado.

### TC-M09-270 — APROBADO

- Fixture: {"sensor":6,"dispositivo":3,"area":3,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"estado":{"sensor":true,"dispositivo":true,"area":true},"asociaciones_vigentes":[{"id_dispositivo_iot":3,"id_infraestructura":3}]}.
- Ventana del intento: 2026-10-07T09:59:08.630Z → 2026-10-07T09:59:08.865Z; consulta RF-10: 2026-10-07T09:58:08.630Z → 2026-10-07T10:00:08.865Z.
- HTTP esperado/obtenido: 400 / 400; respuesta: {"error_code":"VALOR_FUERA_DE_RANGO","message":"El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.","fields":[{"field":"valor_referencia","message":"El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado."}],"timestamp":"2026-10-07T09:59:08.310938+00:00"}.
- Historial PRE/POST: {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]} / {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]}; sin cambios: true.
- GET RF-10: [{"pagina":1,"http":200,"total":4,"items":4}]; candidatos de calibración: 2; evento correlacionado: 38831.
- Evento — resultado: fallido; módulo: MODULO9; usuario: 4; motivo: El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.; IP: 200.118.62.237.
- Candidatos y campos: [{"id_evento":38831,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.307796Z","motivo":"El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38829,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:07.725140Z","motivo":"Solo se pueden calibrar sensores de dispositivos activos.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":false,"detalle_ip":true}}].
- Decisión y causa observada: **APROBADO**. HTTP 400, historial intacto y evento RF-10 38831 completo/correlacionado.

### TC-M09-271 — APROBADO

- Fixture: {"sensor":6,"dispositivo":3,"area":3,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"estado":{"sensor":true,"dispositivo":true,"area":true},"asociaciones_vigentes":[{"id_dispositivo_iot":3,"id_infraestructura":3}]}.
- Ventana del intento: 2026-10-07T09:59:09.213Z → 2026-10-07T09:59:09.437Z; consulta RF-10: 2026-10-07T09:58:09.213Z → 2026-10-07T10:00:09.437Z.
- HTTP esperado/obtenido: 400 / 400; respuesta: {"error_code":"VALOR_CALIBRACION_INVALIDO","message":"El valor de referencia debe ser un número decimal válido.","fields":[{"field":"valor_referencia","message":"El valor de referencia debe ser un número decimal válido."}],"timestamp":"2026-10-07T09:59:08.867469+00:00"}.
- Historial PRE/POST: {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]} / {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]}; sin cambios: true.
- GET RF-10: [{"pagina":1,"http":200,"total":5,"items":5}]; candidatos de calibración: 3; evento correlacionado: 38833.
- Evento — resultado: fallido; módulo: MODULO9; usuario: 4; motivo: El valor de referencia debe ser un número decimal válido.; IP: 200.118.62.237.
- Candidatos y campos: [{"id_evento":38833,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.864995Z","motivo":"El valor de referencia debe ser un número decimal válido.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38831,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.307796Z","motivo":"El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38829,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:07.725140Z","motivo":"Solo se pueden calibrar sensores de dispositivos activos.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":false,"detalle_ip":true}}].
- Decisión y causa observada: **APROBADO**. HTTP 400, historial intacto y evento RF-10 38833 completo/correlacionado.

### TC-M09-272 — APROBADO

- Fixture: {"sensor":6,"dispositivo":3,"area":1,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"estado":{"sensor":true,"dispositivo":true,"area":true},"asociaciones_vigentes":[{"id_dispositivo_iot":3,"id_infraestructura":3}],"area_original":3}.
- Ventana del intento: 2026-10-07T09:59:09.784Z → 2026-10-07T09:59:10.058Z; consulta RF-10: 2026-10-07T09:58:09.784Z → 2026-10-07T10:00:10.058Z.
- HTTP esperado/obtenido: 400 / 400; respuesta: {"error_code":"SENSOR_AREA_INVALIDA","message":"El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.","fields":[{"field":"id_infraestructura","message":"El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar."}],"timestamp":"2026-10-07T09:59:09.495258+00:00"}.
- Historial PRE/POST: {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]} / {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]}; sin cambios: true.
- GET RF-10: [{"pagina":1,"http":200,"total":6,"items":6}]; candidatos de calibración: 4; evento correlacionado: 38835.
- Evento — resultado: fallido; módulo: MODULO9; usuario: 4; motivo: El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.; IP: 200.118.62.237.
- Candidatos y campos: [{"id_evento":38835,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:09.489847Z","motivo":"El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38833,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.864995Z","motivo":"El valor de referencia debe ser un número decimal válido.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38831,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.307796Z","motivo":"El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38829,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:07.725140Z","motivo":"Solo se pueden calibrar sensores de dispositivos activos.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":false,"detalle_ip":true}}].
- Decisión y causa observada: **APROBADO**. HTTP 400, historial intacto y evento RF-10 38835 completo/correlacionado.

### TC-M09-273 — APROBADO

- Fixture: {"sensor":6,"dispositivo":999999,"area":3,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"estado":{"sensor":true,"dispositivo":true,"area":true},"asociaciones_vigentes":[{"id_dispositivo_iot":3,"id_infraestructura":3}],"dispositivo_original":3}.
- Ventana del intento: 2026-10-07T09:59:10.409Z → 2026-10-07T09:59:10.696Z; consulta RF-10: 2026-10-07T09:58:10.409Z → 2026-10-07T10:00:10.696Z.
- HTTP esperado/obtenido: 404 / 404; respuesta: {"error_code":"DISPOSITIVO_NO_ENCONTRADO","message":"No existe un dispositivo IoT con ID 999999.","fields":[],"timestamp":"2026-10-07T09:59:10.138960+00:00"}.
- Historial PRE/POST: {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]} / {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21]}; sin cambios: true.
- GET RF-10: [{"pagina":1,"http":200,"total":7,"items":7}]; candidatos de calibración: 5; evento correlacionado: 38837.
- Evento — resultado: fallido; módulo: MODULO9; usuario: 4; motivo: No existe un dispositivo IoT con ID 999999.; IP: 200.118.62.237.
- Candidatos y campos: [{"id_evento":38837,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:10.136201Z","motivo":"No existe un dispositivo IoT con ID 999999.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":true,"id_sensor":true,"detalle_ip":true}},{"id_evento":38835,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:09.489847Z","motivo":"El sensor 6 no está asociado al área 1. Verifique la ubicación física y lógica del equipo antes de calibrar.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":true,"detalle_ip":true}},{"id_evento":38833,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.864995Z","motivo":"El valor de referencia debe ser un número decimal válido.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":true,"detalle_ip":true}},{"id_evento":38831,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:08.307796Z","motivo":"El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":false,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":true,"detalle_ip":true}},{"id_evento":38829,"resultado":"fallido","modulo":"MODULO9","id_usuario":4,"fecha_evento":"2026-10-07T09:59:07.725140Z","motivo":"Solo se pueden calibrar sensores de dispositivos activos.","ip":"200.118.62.237","checks":{"resultado":true,"modulo":true,"usuario":true,"fecha":true,"motivo":true,"ip":true,"operacion":true,"codigo_http":false,"id_sensor":false,"detalle_ip":true}}].
- Decisión y causa observada: **APROBADO**. HTTP 404, historial intacto y evento RF-10 38837 completo/correlacionado.

## Incidencias

**INCIDENCIA REQUERIDA: NO.**

Grupo de prueba: TC-M09-G135. Casos afectados: ninguno. Resultado: APROBADO. Grupo responsable, Type, Severity y Priority: no aplican.

Motivo: los seis POST devolvieron exactamente 403, 422, 400, 400, 400 y 404; ningún historial PRE/POST cambió; cada intento tuvo un evento RF-10 distinto, con resultado FALLIDO, módulo MODULO9, usuario, fecha, motivo e IP correlacionados. No se observó incumplimiento que justifique abrir una incidencia.

Evidencia: `evidencia.json` y `newman.html`.

Aclaración documental: se completó este apartado después del RUN, sin ejecutar nuevos POST ni modificar la evidencia JSON.

## Conclusión

Los seis rechazos exactos conservaron el historial y tuvieron un evento RF-10 completo.
