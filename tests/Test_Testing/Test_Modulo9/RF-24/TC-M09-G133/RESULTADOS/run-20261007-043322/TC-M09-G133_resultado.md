# TC-M09-G133 — Resultado

## Decisión general

**APROBADO.** El Administrador registró una calibración atribuida a su id_usuario y ambas peticiones sin sesión válida recibieron 4xx sin persistencia.

| Caso | Variante | Resultado | Motivo |
|---|---|---|---|
| TC-M09-264 | Administrador | APROBADO | HTTP 201, calibración 18 recuperada por GET con id_usuario 104 del Administrador y datos coincidentes. |
| TC-M09-263 | Sin Authorization | APROBADO | HTTP 401; total e IDs del historial sin cambios. |
| TC-M09-263 | Token de sesión cerrada | APROBADO | HTTP 401; total e IDs del historial sin cambios. |

## Entorno / fixture

TEST: https://api.inmero.co/back-sigab-test. Prueba local: NO. RUN_ID: run-20261007-043322. Rama: qa/juan-esteban-rf24-v2. HEAD: 30ddd72144102a60af006b265a20cb18c1c72c85; origin/test: 30ddd72144102a60af006b265a20cb18c1c72c85; divergencia: 0	0.

OpenAPI: {"POST /sesiones/":{"presente":true,"codigos_declarados":["200","400","401","403","422","423","503"]},"DELETE /sesiones/":{"presente":true,"codigos_declarados":["200","401","422"]},"POST /configuracion/sensores/{id_sensor}/calibrar":{"presente":true,"codigos_declarados":["201","400","401","403","404","422","500"]},"GET /configuracion/sensores/{id_sensor}/calibraciones":{"presente":true,"codigos_declarados":["200","401","403","422"]}}.

Fixture validado por GET: {"sensor":6,"dispositivo":3,"area":3,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"activo":{"sensor":true,"dispositivo":true,"area":true},"fuente":"GET con Administrador en TEST"}. El oráculo no exige códigos HTTP exactos para rechazo 4xx ni éxito 2xx.

## TC-M09-264 — Administrador autorizado

Admin efectivo: {"correo":"administador.dev@gmail.com","login_status":200,"id_usuario":104,"rol":"Administrador","estado":"Activo","permiso_registrar":true,"permiso_historial":true,"intentos":[{"correo":"admin.dev@gmail.com","resultado":"admin.dev@gmail.com no autentica (HTTP 401)."},{"correo":"administador.dev@gmail.com","login_status":200,"id_usuario":104,"rol":"Administrador","estado":"Activo","permiso_registrar":true,"permiso_historial":true}]}.

**Esperado:** 2xx, id_calibracion, registro recuperado por ese ID con sensor, dispositivo, valor 22.5000, observaciones e id_usuario del Administrador.

**Obtenido:** {"http":201,"id_calibracion":18,"id_usuario":104,"id_sensor":6,"id_dispositivo_iot":3,"valor_referencia":"22.5000","observaciones":"QA TC-M09-264","error_code":null,"mensaje":""}. Registro por ID: {"id_calibracion":18,"id_sensor":6,"id_dispositivo_iot":3,"id_usuario":104,"valor_referencia":"22.5000","observaciones":"QA TC-M09-264"}.

Historial PRE: {"total":8,"ids":[10,11,12,13,14,15,16,17]}. POST: {"total":9,"ids":[10,11,12,13,14,15,16,17,18]}.

**Resultado:** APROBADO. **Motivo:** HTTP 201, calibración 18 recuperada por GET con id_usuario 104 del Administrador y datos coincidentes.

## TC-M09-263/A — sin Authorization

El item Postman carece de cabecera Authorization; no se envió valor vacío ni token ficticio. El historial fue consultado con el Administrador.

**Esperado:** cualquier 4xx y mismo total/IDs. **Obtenido:** {"http":401,"id_calibracion":null,"id_usuario":null,"id_sensor":null,"id_dispositivo_iot":null,"valor_referencia":null,"observaciones":null,"error_code":"TOKEN_REQUERIDO","mensaje":"Se requiere autenticación. Proporciona un token Bearer [REDACTED]álido."}.

Historial PRE: {"total":9,"ids":[10,11,12,13,14,15,16,17,18]}. POST: {"total":9,"ids":[10,11,12,13,14,15,16,17,18]}.

**Resultado:** APROBADO. **Motivo:** HTTP 401; total e IDs del historial sin cambios.

## TC-M09-263/B — token de sesión cerrada

Cadena: login nuevo del Ingeniero → mismo token T en DELETE /sesiones/ → cierre 2xx → mismo T en POST de calibración. No se hizo un login intermedio ni se guardó T.

Ingeniero: {"id_usuario":4,"correo":"ingeniero@pecuaria.co","rol":"Ingeniero de Campo","estado":"Activo","permisos_calibracion":[1,2,3]}. Setup de cierre: login_status 200, logout_status 200, mensaje "Sesión cerrada exitosamente.", timestamp "2026-10-07T09:33:30.406Z", mismo_token_reutilizado true.

**Esperado:** cualquier 4xx y mismo total/IDs. **Obtenido:** {"http":401,"id_calibracion":null,"id_usuario":null,"id_sensor":null,"id_dispositivo_iot":null,"valor_referencia":null,"observaciones":null,"error_code":"TOKEN_REVOCADO","mensaje":"El token de sesión ha sido revocado o es inválido."}.

Historial PRE: {"total":9,"ids":[10,11,12,13,14,15,16,17,18]}. POST: {"total":9,"ids":[10,11,12,13,14,15,16,17,18]}.

**Resultado:** APROBADO. **Motivo:** HTTP 401; total e IDs del historial sin cambios.

## STOP_ALL

NO. POST de calibración planificados: 3; ejecutados: 3. DELETE /sesiones/ ejecutados: 1. Sin reintentos ni borrado de calibraciones.

## Incidencias

INCIDENCIA REQUERIDA: NO.

## Conclusión

El Administrador registró una calibración atribuida a su id_usuario y ambas peticiones sin sesión válida recibieron 4xx sin persistencia.
