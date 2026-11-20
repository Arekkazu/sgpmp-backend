# TC-M07-G040 — Reevaluación V2 — APROBADO

## Identificación

TC-M07-G040, que agrupa TC-M07-17, TC-M07-18, TC-M07-19, TC-M07-20 y TC-M07-21: resolución de la versión del contrato AAEF en las consultas de AgroFusión según la cabecera Accept-Version. RF-98 v1.2; restricciones 5.10 y 5.11; Fase 5; flujos FA-7, FA-8 y FA-11; criterios CA-8, CA-11, CA-13, CA-14, CA-15, CA-25 y CA-28; RFC-017 D-17.11. Versión 2 (reevaluación del grupo completo); intento 4 del grupo en el registro QA, segundo de la V2. RUN RUN-G040-V2-20261119-032152, ambiente TEST, autorización AUT-G040-V2-R2-20261118. Versión anterior: V1 oficial RUN-G040-V1-20261119-022210. Actores: Administrador QA (lecturas de preparación) y el cliente externo QA_M07_AAEF con un token de canal emitido a nombre de una cuenta QA con lectura de exportación contable. Commit de TEST no consultado. Herramientas: Node v22.15.1 y Newman (código 0, 0 fallos). Cypress no aplica, porque el grupo solo tiene pruebas de API. RUN oficial, en una sola fase transaccional y sin escrituras; 18 de 40 solicitudes.

## Motivo de la reevaluación

En la V1, el caso 19 salió RECHAZADO con severidad BAJA (INC-M07-G040-01): una versión inexistente se rechaza con HTTP 404 y el código VERSION_NO_REGISTRADA, y FA-7 nombra VERSION_NO_ENCONTRADA. El líder de análisis va a cambiar en FA-7 el nombre del error. Hasta que se publique ese cambio, el responsable QA decidió el 2026-11-18 aceptar los dos códigos en el caso 19, dejando observación cuando llegue VERSION_NO_REGISTRADA. No hubo ninguna corrección de código. La fila G040 de la matriz recoge esta decisión.

La V2 guarda además en la evidencia el valor de Accept-Version enviado en cada consulta, que faltaba en la V1.

## Resumen de veredictos

| Caso | V1 | V2 | Motivo |
|---|---|---|---|
| TC-M07-17 | APROBADO | APROBADO | Sin Accept-Version, la consulta se atendió con la versión ACTIVO (3.0) y no con la DEPRECADO. |
| TC-M07-18 | APROBADO | APROBADO | Pidiendo la ACTIVO o la DEPRECADO en gracia, se usó la versión pedida; con la DEPRECADO llegó la advertencia con su fecha de inactivación. |
| TC-M07-19 | RECHAZADO | APROBADO | La versión inexistente se rechazó con HTTP 404 y VERSION_NO_REGISTRADA, código aceptado por decisión del responsable QA a la espera del cambio de FA-7 (observación OBS-G040-01). |
| TC-M07-20 | APROBADO | APROBADO | La versión INACTIVO se rechazó con HTTP 410 VERSION_INACTIVA. |
| TC-M07-21 | APROBADO | APROBADO | Los tres valores mal formados se rechazaron con HTTP 400 VERSION_FORMATO_INVALIDO. |

## Preparación de los datos

Los mismos datos de la V1, comprobados de nuevo en vivo antes de consultar. Versiones de TEST, de pruebas de otros equipos: ACTIVO la 3.0 (id 18), DEPRECADO la 2.1 (id 3) en gracia hasta el 2027-02-16 a las 13:53:12 UTC, e INACTIVO la de menor id, la 1.0 (id 1). La 9.9 no existe. No se registró ni se activó ninguna versión.

La consulta revisa el titular y sus fincas antes de resolver la versión, así que se usó una cuenta QA que tiene asignada la única finca activa de un titular (la 463) y el período CERRADO de ese titular, del 2026-11-01 al 2026-11-30, leídos en vivo con las rutas oficiales. El período no tiene costos, así que las respuestas correctas llevan un envelope sin documentos. En las evidencias el NIT aparece enmascarado.

El token se pidió una sola vez al cliente QA_M07_AAEF. Las 8 consultas se hicieron en serie, separadas 13 segundos, para respetar el límite de 5 por minuto y los 5 minutos de vida del token; no hubo ningún 429.

## Detalle por caso

### TC-M07-17 — Consulta sin Accept-Version

- **Preparación:** token de canal recién emitido (HTTP 200, G040-007); versiones vigentes 3.0 ACTIVO y 2.1 DEPRECADO.
- **Esperado:** según CA-14, CA-25 y 5.11, sin versión pedida se usa la versión ACTIVA de mayor MAJOR, informada en X-Version-Contrato-AAEF, con `metadata.StandardVersion` «1.0» (RFC-017 D-17.11).
- **Observado:** consulta sin Accept-Version (null en la evidencia). HTTP 200 con X-Version-Contrato-AAEF 3.0, sin cabecera Deprecation, StandardVersion «1.0» y 0 documentos (G040-008).
- **Decisión: APROBADO.**

### TC-M07-18 — Consulta pidiendo una versión ACTIVO y una DEPRECADO en gracia

- **Preparación:** el mismo token. La fecha de inactivación de la 2.1 en el listado de contratos es el 2027-02-16 a las 13:53:12 UTC.
- **Esperado:** según CA-8, CA-13 y CA-25, se usa la versión pedida si está ACTIVO o DEPRECADO; con la DEPRECADO, la respuesta incluye una advertencia con la fecha de inactivación (en las cabeceras Deprecation y Sunset, como acepta la matriz).
- **Observado:**
  - Accept-Version 3.0: HTTP 200, X-Version-Contrato-AAEF 3.0, sin advertencia, StandardVersion «1.0» (G040-009).
  - Accept-Version 2.1: HTTP 200, X-Version-Contrato-AAEF 2.1, `Deprecation: true` y `Sunset: Tue, 16 Feb 2027 13:53:12 GMT` (la fecha de inactivación al segundo), StandardVersion «1.0» (G040-010).
- **Decisión: APROBADO.**

### TC-M07-19 — Consulta pidiendo una versión no registrada

- **Preparación:** se comprobó en el listado de contratos que la 9.9 no existe.
- **Esperado:** rechazo con HTTP 404 y el error VERSION_NO_ENCONTRADA (FA-7) o VERSION_NO_REGISTRADA (aceptado por decisión del responsable QA a la espera del cambio de FA-7), con un mensaje que indique que la versión no existe o no está disponible (CA-15).
- **Observado:** Accept-Version 9.9. HTTP 404 con `error_code` VERSION_NO_REGISTRADA y el mensaje «La versión 9.9 del contrato contable no está disponible.» (G040-011). El ejecutor dejó la observación «Código aceptado por decisión del responsable QA a la espera del cambio de RF-98 FA-7».
- **Decisión: APROBADO**, con la observación **OBS-G040-01**. Igual que en la V1: rechazo correcto, sin datos y con el HTTP que pide FA-7; el código coincide con el que fijará el requisito actualizado.

### TC-M07-20 — Consulta pidiendo una versión INACTIVO

- **Preparación:** la 1.0 (id 1), INACTIVO.
- **Esperado:** según CA-11, CA-28, FA-8 y 5.10, rechazo con HTTP 410 VERSION_INACTIVA, sin atender la solicitud.
- **Observado:** Accept-Version 1.0. HTTP 410 con `error_code` VERSION_INACTIVA y el mensaje «La versión 1.0 del contrato contable ya no está disponible.» (G040-012), sin envelope ni cabecera de versión.
- **Decisión: APROBADO.**

### TC-M07-21 — Consulta con Accept-Version mal formado

- **Preparación:** tres consultas con valores que no cumplen MAYOR.MENOR.
- **Esperado:** según FA-11, las tres se rechazan con HTTP 400 VERSION_FORMATO_INVALIDO.
- **Observado:**
  - Accept-Version «3»: HTTP 400, VERSION_FORMATO_INVALIDO (G040-013).
  - Accept-Version «3.0.0»: HTTP 400, VERSION_FORMATO_INVALIDO (G040-014).
  - Accept-Version «abc»: HTTP 400, VERSION_FORMATO_INVALIDO (G040-015).

  Las tres con el mensaje «La versión debe tener el formato MAYOR.MENOR, por ejemplo 3.0.».
- **Decisión: APROBADO.**

## Comprobaciones API

- TC-M07-17 / sin_version: APROBADO; 200, versión 3.0, StandardVersion 1.0; resultado.json.
- TC-M07-18 / activo: APROBADO; 200, versión 3.0; resultado.json.
- TC-M07-18 / deprecado: APROBADO; 200, versión 2.1, Deprecation y Sunset iguales a la inactivación; resultado.json.
- TC-M07-19 / inexistente: APROBADO con OBS-G040-01; 404 VERSION_NO_REGISTRADA; resultado.json.
- TC-M07-20 / inactivo: APROBADO; 410 VERSION_INACTIVA; resultado.json.
- TC-M07-21 / solo_mayor, semver, texto: APROBADO; 400 VERSION_FORMATO_INVALIDO en las tres; resultado.json.

## Evidencias reales

resultado.json (con el Accept-Version enviado en cada consulta), preflight.json, contexto_operacion.json, newman/newman-G040.json y newman/newman-G040.html. De las respuestas correctas solo se guardaron las cabeceras, la versión del estándar y el número de documentos, sin datos contables. Las credenciales, el token y el NIT completo no aparecen en ninguna evidencia.

## Incidencias de producto

Ninguna. INC-M07-G040-01 (V1) queda cerrada por decisión del responsable QA y el cambio anunciado de FA-7, no por una corrección de código.

## Observaciones

- **OBS-G040-01:** el código de error de una versión inexistente es VERSION_NO_REGISTRADA (`contrato.py:149-151`) y FA-7 v1.2 todavía dice VERSION_NO_ENCONTRADA. Se acepta por decisión del responsable QA, porque el líder de análisis cambiará FA-7. Cuando se publique, conviene actualizar el documento de requisitos y citar la nueva versión en este informe. El mensaje «no está disponible» es casi igual al de una versión inactiva («ya no está disponible»); si el requisito actualizado exige distinguirlos en el mensaje, habría que revisarlo.
- El código también responde 404 VERSION_NO_REGISTRADA cuando la versión pedida existe pero está PENDIENTE (`contrato.py:149`). No se probó porque no lo pide la matriz.
- El intento 1 de la V2 (RUN-G040-V2-20261119-031311) fue técnico por un error de QA en la ruta de la carpeta del RUN. Se detuvo antes del login, sin ninguna petición a TEST. No afecta a estos veredictos.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G040-V2-20261119-032152` respondió HTTP 200. El ejecutor comparó la lectura posterior de los contratos con la base por su firma completa (ids, versiones, estados, anexos, mapeadores, vigencias y fechas) y coincidió; resultado.json guarda el resultado de esa comparación, no las dos lecturas. Rollback verificado; el RUN no hizo ninguna escritura de contratos. Fuera del sandbox quedan, como estaba previsto y aceptado, el inicio de sesión del Administrador QA antes del RUN y los registros que el producto guarda siempre en la auditoría de la integración en sesión propia: la emisión del token y las 8 consultas (3 atendidas y 5 rechazadas). Estos registros los prevé el código (`gateway_aaef.py:107-123`); en este RUN no se leyeron uno por uno.

## Conclusión y acciones

La resolución de la versión del contrato cumple RF-98: sin versión se usa la ACTIVO; una versión pedida, ACTIVO o DEPRECADO en gracia, se respeta, y la deprecada avisa de su fecha de retiro; las versiones inexistentes se rechazan con 404, las inactivas con 410 y los formatos inválidos con 400. Grupo APROBADO en la V2, con la observación OBS-G040-01 sobre el nombre del código del caso 19, pendiente del cambio de FA-7. Acciones: el responsable QA actualizará el documento de requisitos cuando se publique el cambio de FA-7. Pendiente de QA: pedir autorización para borrar el RUN técnico RUN-G040-V2-20261119-031311.

## Historial del informe

Informe redactado por el orquestador QA (2026-11-18) a partir de resultado.json y newman/; la versión generada por el ejecutor se conserva en SIGAB_QA_ORQUESTACION/estado/historial_informes/M07/TC-M07-G040/. Veredictos y evidencias sin cambios.
Traslado (2026-11-19): la copia del informe del ejecutor se movió a SIGAB_QA_ORQUESTACION por decisión del responsable QA; veredictos y evidencias sin cambios.
Corrección (2026-11-18): número de intento según el registro QA y alcance de la comprobación del rollback; veredictos y evidencias sin cambios.
