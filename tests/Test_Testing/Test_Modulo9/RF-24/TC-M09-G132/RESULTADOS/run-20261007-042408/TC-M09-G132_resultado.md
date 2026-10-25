# TC-M09-G132 — Resultado

## Decisión general

**RECHAZADO.** El oráculo incumplido se detalla en TC-M09-261/NaN, TC-M09-261/Infinity, TC-M09-261/-Infinity.

| Caso | Variante | Resultado | Motivo |
|---|---|---|---|
| TC-M09-262 | 22.1234 | APROBADO | HTTP 201, ID 17; respuesta y GET conservan exactamente 22.1234. |
| TC-M09-261 | NaN | RECHAZADO | HTTP 500 en vez de 400; mensaje "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte." distinto del texto de formato exigido. |
| TC-M09-261 | Infinity | RECHAZADO | mensaje "El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." distinto del texto de formato exigido. |
| TC-M09-261 | -Infinity | RECHAZADO | mensaje "El ajuste de -Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." distinto del texto de formato exigido. |

## Entorno / actor / fixture

TEST: https://api.inmero.co/back-sigab-test. Prueba local: NO. RUN_ID: run-20261007-042408. Rama: qa/juan-esteban-rf24-v2. HEAD: 30ddd72144102a60af006b265a20cb18c1c72c85. Actor: {"id_usuario":4,"correo":"ingeniero@pecuaria.co","rol":"Ingeniero de Campo","estado":"Activo","permisos_calibracion":[1,2,3],"actor_auxiliar_get":"administador.dev@gmail.com","intentos_admin":[{"correo":"admin.dev@gmail.com","resultado":"La cuenta admin.dev@gmail.com no autentica (HTTP 401)."},{"correo":"administador.dev@gmail.com","login":200,"get_dispositivo_3":200}]}.

OpenAPI: {"fuente":"https://api.inmero.co/back-sigab-test/openapi.json","endpoints":{"calibrar":true,"calibraciones":true},"valor_referencia":{"anyOf":[{"type":"number"},{"type":"string","pattern":"^(?!^[-+.]*$)[+-]?0*\\d*\\.?\\d*$"},{"type":"string"},{"type":"null"}],"title":"Valor Referencia"},"modo_calibracion_declarado":false}.

Fixture validado por GET: {"preferido":{"ids":"sensor 6 / dispositivo 3 / área 3","error":null,"valido":true},"error_ingeniero":"No existe fixture verificable por GET que admita 22.1234. Preferido: GET /configuracion/dispositivos-iot/3: Ingeniero HTTP 404; requiere actor auxiliar GET..","sensor":6,"dispositivo":3,"area":3,"categoria":"TEMPERATURA","rango":{"min":"0.0000","max":"45.0000"},"asociacion":6,"activo":{"dispositivo":true,"sensor":true,"area":true},"fuente":"GET en TEST"}. La cuenta Administrador, si se utilizó, solo efectuó GET de discovery; los POST fueron del Ingeniero.

## TC-M09-262 — precisión

**Esperado:** HTTP 2xx, id_calibracion y valor decimal exacto 22.1234 tanto en respuesta como en GET de ese ID. JSON puede representar el decimal como número o string.

**Obtenido:** HTTP 201; id_calibracion 17; valor respuesta "22.1234"; valor GET "22.1234"; comparación decimal exacta: respuesta true, GET true.

**Historial:** PRE {"total":7,"ids":[10,11,12,13,14,15,16]}; POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}. Correlación por ID: sí.

**Resultado:** APROBADO. **Motivo:** HTTP 201, ID 17; respuesta y GET conservan exactamente 22.1234.

## TC-M09-261 — valores especiales

### NaN — RECHAZADO

**Esperado:** HTTP 400; mensaje exacto «Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada 'NaN'.»; respuesta sin id_calibracion; total e IDs del historial sin cambios.

**Obtenido:** HTTP 500; mensaje "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte."; id_calibracion null.

**Historial:** PRE {"total":8,"ids":[10,11,12,13,14,15,16,17]}; POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}.

**Motivo:** HTTP 500 en vez de 400; mensaje "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte." distinto del texto de formato exigido.

### Infinity — RECHAZADO

**Esperado:** HTTP 400; mensaje exacto «Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada 'Infinity'.»; respuesta sin id_calibracion; total e IDs del historial sin cambios.

**Obtenido:** HTTP 400; mensaje "El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado."; id_calibracion null.

**Historial:** PRE {"total":8,"ids":[10,11,12,13,14,15,16,17]}; POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}.

**Motivo:** mensaje "El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." distinto del texto de formato exigido.

### -Infinity — RECHAZADO

**Esperado:** HTTP 400; mensaje exacto «Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada '-Infinity'.»; respuesta sin id_calibracion; total e IDs del historial sin cambios.

**Obtenido:** HTTP 400; mensaje "El ajuste de -Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado."; id_calibracion null.

**Historial:** PRE {"total":8,"ids":[10,11,12,13,14,15,16,17]}; POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}.

**Motivo:** mensaje "El ajuste de -Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." distinto del texto de formato exigido.

## STOP_ALL

NO. POST planificados: 4. POST ejecutados: 4. No hubo reintentos automáticos ni borrado de calibraciones.

## Incidencias

### Valores especiales no rechazados como formato decimal inválido

**INCIDENCIA REQUERIDA:** SÍ  
**Grupo responsable:** Desarrollo  
**Grupo de prueba:** TC-M09-G132  
**Casos afectados:** TC-M09-261  
**Resultado:** RECHAZADO  
**Motivo:** NaN: HTTP 500 en vez de 400; mensaje "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte." distinto del texto de formato exigido. Infinity: mensaje "El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." distinto del texto de formato exigido. -Infinity: mensaje "El ajuste de -Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." distinto del texto de formato exigido.  
**Esperado:** NaN: 400, mensaje exacto y sin persistencia. Infinity: 400, mensaje exacto y sin persistencia. -Infinity: 400, mensaje exacto y sin persistencia.  
**Obtenido:** NaN: HTTP 500, mensaje "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.", PRE {"total":8,"ids":[10,11,12,13,14,15,16,17]}, POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}. Infinity: HTTP 400, mensaje "El ajuste de Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.", PRE {"total":8,"ids":[10,11,12,13,14,15,16,17]}, POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}. -Infinity: HTTP 400, mensaje "El ajuste de -Infinity excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.", PRE {"total":8,"ids":[10,11,12,13,14,15,16,17]}, POST {"total":8,"ids":[10,11,12,13,14,15,16,17]}.  
**Causa raíz:** Validación o manejo de valores no finitos en la aplicación; mecanismo exacto del despliegue por confirmar.  
**Type:** bug  
**Severity:** Important  
**Priority:** High  
**Evidencia:** evidencia.json / newman.html

## Conclusión

El oráculo incumplido se detalla en TC-M09-261/NaN, TC-M09-261/Infinity, TC-M09-261/-Infinity.
