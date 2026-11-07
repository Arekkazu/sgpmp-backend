# TC-M09-G134 — Resultado

## Decisión general

**APROBADO.** Las tres verificaciones cumplieron: historial oficial, calibraciones previas intactas y telemetría histórica SQL/API inalterada.

| Caso | Resultado | Motivo |
|---|---|---|
| TC-M09-265 | APROBADO | HTTP 200; calibraciones 12, 13, 14 presentes con todos los campos iguales y sin mezcla de sensores. Orden no evaluado. |
| TC-M09-266 | APROBADO | HTTP 201; ID 21 nuevo atribuible a G134 y 10 calibraciones PRE intactas campo por campo. |
| TC-M09-267 | APROBADO | POST HTTP 201; 1 lectura(s) SQL y 1 lectura(s) API idénticas PRE/POST; pytest pasó. |

## Entorno y actores

TEST: https://api.inmero.co/back-sigab-test. Prueba local: NO. RUN_ID: run-20261007-044846. Rama: qa/juan-esteban-rf24-v2; HEAD y origin/test: 30ddd72144102a60af006b265a20cb18c1c72c85 / 30ddd72144102a60af006b265a20cb18c1c72c85; divergencia 0	0.

Ingeniero funcional: {"id_usuario":4,"correo":"ingeniero@pecuaria.co","rol":"Ingeniero de Campo","estado":"Activo","permisos_calibracion":[1,2,3]}. Administrador de GET: {"correo":"administador.dev@gmail.com","id_usuario":104,"rol":"Administrador","estado":"Activo","intentos":[{"correo":"admin.dev@gmail.com","resultado":"admin.dev@gmail.com no autentica (HTTP 423)."},{"correo":"administador.dev@gmail.com","id_usuario":104,"rol":"Administrador","estado":"Activo"}]}. OpenAPI: {"GET historial calibraciones":{"presente":true,"codigos_declarados":["200","401","403","422"]},"POST calibrar":{"presente":true,"codigos_declarados":["201","400","401","403","404","422","500"]},"GET telemetría histórica":{"presente":true,"codigos_declarados":["200","400","401","403","422"]}}. BD TEST usada exclusivamente con SELECT read-only; SQL de escritura: NO.

## TC-M09-265 — historial oficial

**Esperado:** tres calibraciones oficiales por ID, con dispositivo, sensor, usuario, fecha, valor y observaciones idénticos; ningún item de otro sensor. Orden no evaluado.

Referencias oficiales y fuentes: [{"caso":"TC-M09-141-v2.0","fuente":"tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G74-v2.0/RESULTADOS/run-20261007-064935/evidencia/response_calibracion.json","id_calibracion":12,"id_dispositivo_iot":3,"id_sensor":6,"id_usuario":4,"fecha_calibracion":"2026-10-07T06:49:37.209000Z","valor_referencia":"22.5000","observaciones":"QA TC-M09-141-v2.0"},{"caso":"TC-M09-142-v2.0","fuente":"tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0/RESULTADOS/run-20261007-072226/142_calibracion_creada.json","id_calibracion":13,"id_dispositivo_iot":3,"id_sensor":6,"id_usuario":4,"fecha_calibracion":"2026-10-07T07:22:35.282000Z","valor_referencia":"0.0000","observaciones":"QA TC-M09-142-v2.0"},{"caso":"TC-M09-143-v2.0","fuente":"tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75-v2.0/RESULTADOS/run-20261007-072226/143_calibracion_creada.json","id_calibracion":14,"id_dispositivo_iot":3,"id_sensor":6,"id_usuario":4,"fecha_calibracion":"2026-10-07T07:22:35.877000Z","valor_referencia":"45.0000","observaciones":"QA TC-M09-143-v2.0"}].

GET HTTP 200; total 10; IDs [10,11,12,13,14,15,16,17,18,19]. Comparaciones: [{"caso":"TC-M09-141-v2.0","id_calibracion":12,"presente":true,"iguales":{"id_dispositivo_iot":true,"id_sensor":true,"id_usuario":true,"fecha_calibracion":true,"valor_referencia":true,"observaciones":true},"obtenido":{"id_dispositivo_iot":3,"id_sensor":6,"id_usuario":4,"fecha_calibracion":"2026-10-07T06:49:37.209000Z","valor_referencia":"22.5000","observaciones":"QA TC-M09-141-v2.0"}},{"caso":"TC-M09-142-v2.0","id_calibracion":13,"presente":true,"iguales":{"id_dispositivo_iot":true,"id_sensor":true,"id_usuario":true,"fecha_calibracion":true,"valor_referencia":true,"observaciones":true},"obtenido":{"id_dispositivo_iot":3,"id_sensor":6,"id_usuario":4,"fecha_calibracion":"2026-10-07T07:22:35.282000Z","valor_referencia":"0.0000","observaciones":"QA TC-M09-142-v2.0"}},{"caso":"TC-M09-143-v2.0","id_calibracion":14,"presente":true,"iguales":{"id_dispositivo_iot":true,"id_sensor":true,"id_usuario":true,"fecha_calibracion":true,"valor_referencia":true,"observaciones":true},"obtenido":{"id_dispositivo_iot":3,"id_sensor":6,"id_usuario":4,"fecha_calibracion":"2026-10-07T07:22:35.877000Z","valor_referencia":"45.0000","observaciones":"QA TC-M09-143-v2.0"}}]. Items de otro sensor: [].

**Resultado:** APROBADO. **Motivo:** HTTP 200; calibraciones 12, 13, 14 presentes con todos los campos iguales y sin mezcla de sensores. Orden no evaluado.

## TC-M09-266 — calibraciones previas inmutables

Fixture: {"sensor":6,"dispositivo":3,"area":3,"categoria":"TEMPERATURA","asociacion":6,"rango":{"min":"0.0000","max":"45.0000"},"activo":{"sensor":true,"dispositivo":true,"area":true},"fuente":"GET con Administrador TEST"}. POST del Ingeniero: {"ruta":"/configuracion/sensores/6/calibrar","body":{"modo_calibracion":"SENSOR","id_dispositivo_iot":3,"id_infraestructura":3,"valor_referencia":30,"observaciones":"QA TC-M09-266","fecha_calibracion":"2026-10-07T09:48:51.339Z"},"valor_referencia_literal":"30.0000"}; respuesta {"http":201,"id_calibracion":21,"id_usuario":4,"id_sensor":6,"valor_referencia":"30.0000","observaciones":"QA TC-M09-266","error_code":null,"mensaje":""}.

Snapshot PRE: {"total":10,"ids":[10,11,12,13,14,15,16,17,18,19],"filas":[{"id_calibracion":19,"valor_referencia":"30.0000","fecha_calibracion":"2026-10-07T09:46:12.463000Z","id_usuario":4,"observaciones":"QA TC-M09-266"},{"id_calibracion":18,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T09:33:26.952000Z","id_usuario":104,"observaciones":"QA TC-M09-264"},{"id_calibracion":17,"valor_referencia":"22.1234","fecha_calibracion":"2026-10-07T09:24:13.117000Z","id_usuario":4,"observaciones":"QA TC-M09-262"},{"id_calibracion":16,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T09:07:27.257000Z","id_usuario":4,"observaciones":"QA TC-M09-259"},{"id_calibracion":15,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T08:50:54.866000Z","id_usuario":4,"observaciones":"QA TC-M09-151-v2.0"},{"id_calibracion":14,"valor_referencia":"45.0000","fecha_calibracion":"2026-10-07T07:22:35.877000Z","id_usuario":4,"observaciones":"QA TC-M09-143-v2.0"},{"id_calibracion":13,"valor_referencia":"0.0000","fecha_calibracion":"2026-10-07T07:22:35.282000Z","id_usuario":4,"observaciones":"QA TC-M09-142-v2.0"},{"id_calibracion":12,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T06:49:37.209000Z","id_usuario":4,"observaciones":"QA TC-M09-141-v2.0"},{"id_calibracion":11,"valor_referencia":"45.0000","fecha_calibracion":"2026-09-06T04:23:01.536000Z","id_usuario":4,"observaciones":"QA TC-M09-143 G75 run-20260906"},{"id_calibracion":10,"valor_referencia":"0.0000","fecha_calibracion":"2026-09-06T04:22:49.008000Z","id_usuario":4,"observaciones":"QA TC-M09-142 G75 run-20260906"}]}. Snapshot POST: {"total":11,"ids":[10,11,12,13,14,15,16,17,18,19,21],"filas":[{"id_calibracion":21,"valor_referencia":"30.0000","fecha_calibracion":"2026-10-07T09:48:51.339000Z","id_usuario":4,"observaciones":"QA TC-M09-266"},{"id_calibracion":19,"valor_referencia":"30.0000","fecha_calibracion":"2026-10-07T09:46:12.463000Z","id_usuario":4,"observaciones":"QA TC-M09-266"},{"id_calibracion":18,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T09:33:26.952000Z","id_usuario":104,"observaciones":"QA TC-M09-264"},{"id_calibracion":17,"valor_referencia":"22.1234","fecha_calibracion":"2026-10-07T09:24:13.117000Z","id_usuario":4,"observaciones":"QA TC-M09-262"},{"id_calibracion":16,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T09:07:27.257000Z","id_usuario":4,"observaciones":"QA TC-M09-259"},{"id_calibracion":15,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T08:50:54.866000Z","id_usuario":4,"observaciones":"QA TC-M09-151-v2.0"},{"id_calibracion":14,"valor_referencia":"45.0000","fecha_calibracion":"2026-10-07T07:22:35.877000Z","id_usuario":4,"observaciones":"QA TC-M09-143-v2.0"},{"id_calibracion":13,"valor_referencia":"0.0000","fecha_calibracion":"2026-10-07T07:22:35.282000Z","id_usuario":4,"observaciones":"QA TC-M09-142-v2.0"},{"id_calibracion":12,"valor_referencia":"22.5000","fecha_calibracion":"2026-10-07T06:49:37.209000Z","id_usuario":4,"observaciones":"QA TC-M09-141-v2.0"},{"id_calibracion":11,"valor_referencia":"45.0000","fecha_calibracion":"2026-09-06T04:23:01.536000Z","id_usuario":4,"observaciones":"QA TC-M09-143 G75 run-20260906"},{"id_calibracion":10,"valor_referencia":"0.0000","fecha_calibracion":"2026-09-06T04:22:49.008000Z","id_usuario":4,"observaciones":"QA TC-M09-142 G75 run-20260906"}]}.

Previas ausentes: []; modificadas: []; IDs nuevos: [21]; nueva atribuible: true.

**Resultado:** APROBADO. **Motivo:** HTTP 201; ID 21 nuevo atribuible a G134 y 10 calibraciones PRE intactas campo por campo.

## TC-M09-267 — telemetría histórica

Fixture: {"sensor":1,"dispositivo":1,"area":1,"categoria":"TEMPERATURA","asociacion":1,"rango":{"min":"0.0000","max":"45.0000"},"activo":{"sensor":true,"dispositivo":true,"area":true},"fuente":"GET con Administrador TEST","dia_historico":"2026-10-05","api_actor":"Administrador"}. Período cerrado: {"dia":"2026-10-05","inicio_utc":"2026-10-05T00:00:00Z","fin_exclusivo_utc":"2026-10-06T00:00:00Z"}. t_post_before: 2026-10-07T09:48:59.107Z; t_post_after: 2026-10-07T09:49:00.634Z.

SQL PRE: {"cantidad":1,"sha256":"d4e63e5d365d73ef5eaf5b8d376c8243c27ce063f3fc03e77aa0bc5fb9f7203c","filas":[{"id_telemetria":56,"valor_crudo":"-10.5000","valor_ajustado":"15.0000","calibrado":true}],"read_only":true}. SQL POST: {"cantidad":1,"sha256":"d4e63e5d365d73ef5eaf5b8d376c8243c27ce063f3fc03e77aa0bc5fb9f7203c","filas":[{"id_telemetria":56,"valor_crudo":"-10.5000","valor_ajustado":"15.0000","calibrado":true}],"read_only":true}. Digest SQL igual: true.

API PRE: {"http":200,"actor":"Administrador","paginas":1,"cantidad":1,"sha256":"53e5d55abc5dcdb9a378c14705a7418b8cc3a5f1461055483dbd11c30ea23de9","filas":[{"id_telemetria":56,"valor":"15.0000","valor_ajustado":"15.0000","timestamp_captura":"2026-10-05T07:11:57Z"}]}. API POST: {"http":200,"actor":"Administrador","paginas":1,"cantidad":1,"sha256":"53e5d55abc5dcdb9a378c14705a7418b8cc3a5f1461055483dbd11c30ea23de9","filas":[{"id_telemetria":56,"valor":"15.0000","valor_ajustado":"15.0000","timestamp_captura":"2026-10-05T07:11:57Z"}]}. Digest API igual: true.

POST del Ingeniero: {"ruta":"/configuracion/sensores/1/calibrar","body":{"modo_calibracion":"SENSOR","id_dispositivo_iot":1,"id_infraestructura":1,"valor_referencia":30,"observaciones":"QA TC-M09-267","fecha_calibracion":"2026-10-07T09:49:00.357Z"},"valor_referencia_literal":"30.0000"}; respuesta {"http":201,"id_calibracion":22,"id_usuario":4,"id_sensor":1,"valor_referencia":"30.0000","observaciones":"QA TC-M09-267","error_code":null,"mensaje":""}. Diferencias SQL: {"ausentes":[],"nuevas":[],"modificadas":[]}. Diferencias API: {"ausentes":[],"nuevas":[],"modificadas":[]}. Pytest read-only: {"exit_code":0,"detalle":".                                                                        [100%]\r\n1 passed in 1.10s\r\n"}.

**Resultado:** APROBADO. **Motivo:** POST HTTP 201; 1 lectura(s) SQL y 1 lectura(s) API idénticas PRE/POST; pytest pasó.

## Incidencias

INCIDENCIA REQUERIDA: NO.

## Conclusión

Las tres verificaciones cumplieron: historial oficial, calibraciones previas intactas y telemetría histórica SQL/API inalterada. POST planificados: 2; ejecutados: 2; sin reintentos ni SQL de escritura.
