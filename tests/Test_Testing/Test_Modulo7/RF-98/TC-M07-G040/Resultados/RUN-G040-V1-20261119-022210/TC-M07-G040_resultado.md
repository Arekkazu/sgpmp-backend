# TC-M07-G040 — RECHAZADO

## Identificación

TC-M07-G040, que agrupa TC-M07-17, TC-M07-18, TC-M07-19, TC-M07-20 y TC-M07-21: resolución de la versión del contrato AAEF en las consultas de AgroFusión según la cabecera Accept-Version. RF-98 v1.2; restricciones 5.10 y 5.11; Fase 5; flujos FA-7, FA-8 y FA-11; criterios CA-8, CA-11, CA-13, CA-14, CA-15, CA-25 y CA-28; RFC-017 D-17.11. La fila de la matriz se corrigió el 2026-11-18 para usar las versiones reales de TEST, sin registrar ninguna. Versión 1, intento 2. RUN RUN-G040-V1-20261119-022210, ambiente TEST, autorización AUT-G040-V1-R2-20261118. Actores: Administrador QA (lecturas de preparación) y el cliente externo QA_M07_AAEF con un token de canal emitido a nombre de una cuenta QA con lectura de exportación contable. Commit de TEST no consultado. Herramientas: Node v22.15.1 y Newman (código 0, 0 fallos). Cypress no aplica, porque el grupo solo tiene pruebas de API. RUN oficial, en una sola fase transaccional y sin escrituras; 18 de 40 solicitudes.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M07-17 | APROBADO | Sin Accept-Version, la consulta se atendió con la versión ACTIVO (3.0) y no con la DEPRECADO. |
| TC-M07-18 | APROBADO | Pidiendo la ACTIVO o la DEPRECADO en gracia, se usó la versión pedida; con la DEPRECADO llegó la advertencia con su fecha de inactivación. |
| TC-M07-19 | RECHAZADO | La versión inexistente se rechazó con HTTP 404, pero con el código VERSION_NO_REGISTRADA en lugar de VERSION_NO_ENCONTRADA. |
| TC-M07-20 | APROBADO | La versión INACTIVO se rechazó con HTTP 410 VERSION_INACTIVA. |
| TC-M07-21 | APROBADO | Los tres valores mal formados se rechazaron con HTTP 400 VERSION_FORMATO_INVALIDO. |

## Preparación de los datos

La matriz preveía registrar y activar una 4.0 para tener una versión ACTIVO y otra DEPRECADO. No hizo falta: en TEST ya existe ese escenario por pruebas de otros equipos, con la 3.0 ACTIVO y la 2.1 DEPRECADO en período de gracia hasta el 2027-02-16. Es justo el ejemplo de CA-25. El ejecutor eligió las versiones en vivo por su estado: ACTIVO la 3.0 (id 18), DEPRECADO la 2.1 (id 3) e INACTIVO la de menor id, la 1.0 (id 1). Comprobó además que la 9.9 no existe.

La consulta de AgroFusión revisa el titular y sus fincas antes de resolver la versión (`consultar_aaef_use_case.py`). Por eso se usó una cuenta QA que tiene asignada la única finca activa de un titular (la 463), y el período contable CERRADO de ese titular, del 2026-11-01 al 2026-11-30. El ejecutor leyó en vivo el NIT, con `GET /configuracion/fincas/463/titular`, y el período, con `GET /finanzas/periodos`. El período no tiene costos, así que las respuestas correctas llevan un envelope sin documentos, que el esquema de AgroFusión admite. En las evidencias el NIT aparece enmascarado.

El token se pidió una sola vez al cliente externo QA_M07_AAEF, con su client_id y su client_secret, a nombre de esa cuenta. El cliente admite 5 consultas por minuto y el token dura 5 minutos. Por eso las 8 consultas se hicieron en serie, separadas 13 segundos, y no hubo ningún 429.

## Detalle por caso

### TC-M07-17 — Consulta sin Accept-Version

- **Preparación:** token de canal recién emitido (HTTP 200); versiones vigentes 3.0 ACTIVO y 2.1 DEPRECADO.
- **Esperado:** según CA-14, CA-25 y 5.11, sin versión pedida se usa la versión ACTIVA de mayor MAJOR, informada en X-Version-Contrato-AAEF. La versión del estándar en `metadata.StandardVersion` sigue siendo «1.0» (RFC-017 D-17.11).
- **Observado:** HTTP 200 con X-Version-Contrato-AAEF 3.0, sin cabecera Deprecation, StandardVersion «1.0» y 0 documentos (G040-008).
- **Decisión: APROBADO.** Sin versión pedida se usa la ACTIVO, no la DEPRECADO que también está vigente.

### TC-M07-18 — Consulta pidiendo una versión ACTIVO y una DEPRECADO en gracia

- **Preparación:** el mismo token. La fecha de inactivación de la 2.1 en el listado de contratos es el 2027-02-16 a las 13:53:12 UTC.
- **Esperado:** según CA-8, CA-13 y CA-25, si la versión pedida está ACTIVO o DEPRECADO se usa esa versión. Con la DEPRECADO, la respuesta incluye una advertencia con la fecha de inactivación. El requisito no fija su forma; la matriz acepta las cabeceras Deprecation y Sunset.
- **Observado:**
  - Pidiendo la 3.0: HTTP 200, X-Version-Contrato-AAEF 3.0, sin advertencia, StandardVersion «1.0» (G040-009).
  - Pidiendo la 2.1: HTTP 200, X-Version-Contrato-AAEF 2.1, `Deprecation: true` y `Sunset: Tue, 16 Feb 2027 13:53:12 GMT`, la misma fecha de inactivación al segundo, y StandardVersion «1.0» (G040-010).
- **Decisión: APROBADO.** Las dos versiones vigentes responden, cada una con su número, y la deprecada avisa de cuándo dejará de estar disponible.

### TC-M07-19 — Consulta pidiendo una versión no registrada

- **Preparación:** se comprobó en el listado de contratos que la 9.9 no existe.
- **Esperado:** según FA-7, rechazo con HTTP 404 y el error VERSION_NO_ENCONTRADA. Según CA-15, la respuesta indica que la versión no existe.
- **Observado:** HTTP 404 con `error_code` VERSION_NO_REGISTRADA y el mensaje «La versión 9.9 del contrato contable no está disponible.» (G040-011).
- **Decisión: RECHAZADO** por **INC-M07-G040-01**. El rechazo y el HTTP son correctos, pero el código de error no es el que nombra FA-7. El mensaje dice que la versión «no está disponible», no que no existe, y casi lo mismo dice el de una versión inactiva («ya no está disponible»), así que quien consulta no puede distinguir los dos casos por el mensaje.

### TC-M07-20 — Consulta pidiendo una versión INACTIVO

- **Preparación:** la 1.0 (id 1), INACTIVO.
- **Esperado:** según CA-11, CA-28, FA-8 y 5.10, una versión INACTIVO no atiende solicitudes y la consulta se rechaza con HTTP 410 VERSION_INACTIVA.
- **Observado:** HTTP 410 con `error_code` VERSION_INACTIVA y el mensaje «La versión 1.0 del contrato contable ya no está disponible.» (G040-012). No se generó envelope ni cabecera de versión.
- **Decisión: APROBADO.**

### TC-M07-21 — Consulta con Accept-Version mal formado

- **Preparación:** tres consultas con los valores «3» (sin MINOR), «3.0.0» (tres niveles) y «abc» (no numérico), en ese orden.
- **Esperado:** según FA-11, las tres se rechazan con HTTP 400 VERSION_FORMATO_INVALIDO.
- **Observado:** las tres respondieron HTTP 400 con `error_code` VERSION_FORMATO_INVALIDO y el mensaje «La versión debe tener el formato MAYOR.MENOR, por ejemplo 3.0.» (G040-013, G040-014 y G040-015).
- **Decisión: APROBADO.**

## Comprobaciones API

- TC-M07-17 / sin_version: APROBADO; 200, versión 3.0, StandardVersion 1.0; resultado.json.
- TC-M07-18 / activo: APROBADO; 200, versión 3.0; resultado.json.
- TC-M07-18 / deprecado: APROBADO; 200, versión 2.1, Deprecation y Sunset iguales a la inactivación; resultado.json.
- TC-M07-19 / inexistente: RECHAZADO; 404 VERSION_NO_REGISTRADA; resultado.json.
- TC-M07-20 / inactivo: APROBADO; 410 VERSION_INACTIVA; resultado.json.
- TC-M07-21 / solo_mayor, semver, texto: APROBADO; 400 VERSION_FORMATO_INVALIDO en las tres; resultado.json.

## Evidencias reales

resultado.json, preflight.json, contexto_operacion.json, newman/newman-G040.json y newman/newman-G040.html. De las respuestas correctas solo se guardaron las cabeceras, la versión del estándar y el número de documentos, sin datos contables. Las credenciales, el token y el NIT completo no aparecen en ninguna evidencia.

## Incidencias de producto

### INC-M07-G040-01 — Una versión no registrada se rechaza con VERSION_NO_REGISTRADA en lugar de VERSION_NO_ENCONTRADA

**Requisito:** RF-98, FA-7 («Solicitud con versión inexistente»): «Agrofusión envía Accept-Version con una versión no registrada → se rechaza la solicitud, Error: VERSION_NO_ENCONTRADA, HTTP 404 Not Found». CA-15: «Dado una solicitud con versión no registrada, cuando se procesa, entonces el sistema debe rechazar la solicitud indicando que la versión no existe».

**Pasos para reproducir:** pedir un token de canal en `POST /integraciones/agrofusion/token`. Enviar `GET /integracion/aaef/productores/{nit}?desde=…&hasta=…` con `Authorization: Bearer <token>` y `Accept-Version: 9.9` (o cualquier versión con formato válido que no esté registrada), usando un titular cuyas fincas tenga todas asignadas el usuario del token.

**Esperado:** HTTP 404 con `error_code` VERSION_NO_ENCONTRADA y un mensaje que diga que la versión no existe.

**Obtenido:** HTTP 404 con `error_code` VERSION_NO_REGISTRADA y el mensaje «La versión 9.9 del contrato contable no está disponible.».

**Causa probable (hipótesis a partir del código, sin confirmar en TEST):** `resolver_version` (`src/accounting_integration/domain/entities/contrato.py:143-163`) lanza `NotFoundError(code="VERSION_NO_REGISTRADA", …)` cuando la versión pedida no existe o está PENDIENTE (`:149-151`), con el texto «no está disponible». El nombre del código y el texto no siguen FA-7 ni CA-15. Además, el texto es casi igual al de la versión INACTIVO («ya no está disponible», `:152-154`). La corrección probable es usar VERSION_NO_ENCONTRADA y un mensaje que diga que la versión no existe; decidirlo corresponde a Desarrollo, teniendo en cuenta que AgroFusión puede depender del código que recibe.

**Impacto y severidad:** BAJA. La consulta se rechaza con el HTTP correcto y no se atiende con ninguna versión, así que no hay riesgo para los datos ni respuestas equivocadas. Pero AgroFusión recibe un código distinto del acordado en el requisito, y el mensaje no distingue «no existe» de «ya no está disponible». Certeza de la discrepancia: CONFIRMADA en TEST.

**Primera atención:** Desarrollo.

**Evidencias:** `resultado.json`: G040-011, con el cuerpo de error completo, y G040-004, el listado de contratos sin la 9.9.

## Observaciones

- El código también responde 404 VERSION_NO_REGISTRADA cuando la versión pedida existe pero está PENDIENTE (`contrato.py:149`). No se probó porque no lo pide la matriz.
- `resultado.json` no guarda el valor de Accept-Version que se envió en cada consulta. El valor sale de la lista fija del ejecutor (`g040.mjs`, SHA-256 fb5d6e4a…), en el orden de las solicitudes G040-008 a G040-015, y las respuestas lo confirman: el número de versión en las 200 y los mensajes de la 9.9 y de la 1.0. Para los tres valores mal formados, el orden es el de esa lista. En el próximo cambio del ejecutor se añadirá ese campo a la evidencia.
- Los nombres de las dos peticiones de la colección Newman todavía dicen «G039-N-01» y «G039-N-02», heredados de la plantilla. Son las lecturas de contratos y de auditoría de G040 y pasaron sus aserciones. Se corregirán en el próximo cambio.
- El intento 1 (RUN-G040-V1-20261119-020240) fue técnico por un error de QA en el cuerpo del login. Se detuvo en la primera solicitud, sin token, consultas ni escrituras. No afecta a estos veredictos.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G040-V1-20261119-022210` respondió HTTP 200. La lectura posterior de los contratos coincidía campo por campo con la base. Rollback verificado; el RUN no hizo ninguna escritura de contratos. Fuera del sandbox quedan, como estaba previsto y aceptado, el inicio de sesión del Administrador QA antes del RUN y los registros que el producto guarda siempre en la auditoría de la integración en sesión propia: la emisión del token y las 8 consultas (3 atendidas y 5 rechazadas). Estos registros los prevé el código (`gateway_aaef.py:107-123`); en este RUN no se leyeron uno por uno.

## Conclusión y acciones

La resolución de la versión del contrato cumple RF-98 en lo esencial: sin versión se usa la ACTIVO; una versión pedida, ACTIVO o DEPRECADO en gracia, se respeta, y la deprecada avisa de su fecha de retiro; las versiones inactivas se rechazan con 410 y los formatos inválidos con 400. Falla solo el código y el mensaje de una versión inexistente (INC-M07-G040-01, BAJA). Acciones: derivar INC-M07-G040-01 a Desarrollo y reevaluar el grupo completo con una nueva autorización cuando informen la corrección. Pendiente de QA: pedir autorización para borrar el RUN técnico RUN-G040-V1-20261119-020240.

## Historial del informe

Informe redactado por el orquestador QA (2026-11-18) a partir de resultado.json y newman/; la versión generada por el ejecutor se conserva en SIGAB_QA_ORQUESTACION/estado/historial_informes/M07/TC-M07-G040/. Veredictos y evidencias sin cambios.
Traslado (2026-11-19): la copia del informe del ejecutor se movió a SIGAB_QA_ORQUESTACION por decisión del responsable QA; veredictos y evidencias sin cambios.
