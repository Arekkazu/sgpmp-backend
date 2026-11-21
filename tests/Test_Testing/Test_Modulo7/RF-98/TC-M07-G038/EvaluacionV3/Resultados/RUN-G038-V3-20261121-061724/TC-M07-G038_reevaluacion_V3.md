# TC-M07-G038 — Reevaluación V3 — APROBADO

## Identificación

TC-M07-G038, que agrupa TC-M07-09 a TC-M07-12: activación de versiones del contrato AAEF. RF-98 v1.2; restricciones 5.3, 5.4 y 5.5; flujos FA-5 y FA-6; criterios CA-5, CA-6, CA-7, CA-9, CA-16, CA-21 y CA-29. Versión 3 (reevaluación del grupo completo). RUN RUN-G038-V3-20261121-061724, ambiente TEST, autorización AUT-G038-V3-20261121. Versión anterior: V2 oficial RUN-G038-V2-20261121-060449. Actor: Administrador QA. Commit desplegado en TEST no consultado; la rama origin/test del repositorio contiene la corrección 0553cefd. Herramientas: Node v22.15.1 y Newman (código 0); sin UI. RUN oficial, en dos fases transaccionales con el mismo identificador; 39 de 70 solicitudes.

## Motivo de la reevaluación

En la V1, el caso 11 salió RECHAZADO con severidad MEDIA (INC-M07-G038-01): cuando la activación manual de una versión se bloqueaba, el Administrador no recibía ningún aviso, y CA-5 lo exige. Desarrollo informó la corrección en 0553cefd (#1168).

La V2 mostró que el aviso ya llega, pero volvió a rechazar el 11 por un error de QA: el oráculo no reconoció la redacción real del motivo. El oráculo se corrigió y, por decisión del responsable QA, la V3 repite los cuatro casos.

## Resumen de veredictos

| Caso | V1 | V2 | V3 | Motivo |
|---|---|---|---|---|
| TC-M07-09 | APROBADO | APROBADO | APROBADO | La 9.0 MAJOR se activó y la 3.0 pasó a DEPRECADO en el mismo instante, con inactivación a 90 días y los dos eventos. |
| TC-M07-10 | APROBADO | APROBADO | APROBADO | La 10.1 MINOR se activó, la 3.0 siguió ACTIVO sin fechas de retiro y quedaron dos vigentes. |
| TC-M07-11 | RECHAZADO | RECHAZADO (oráculo) | APROBADO | El bloqueo se mantuvo y el Administrador recibió el aviso crítico con la versión y el motivo. |
| TC-M07-12 | APROBADO | APROBADO | APROBADO | Con dos vigentes, la activación de la 9.1 se rechazó con LIMITE_VERSIONES_EXCEDIDO, el mensaje nombró la 3.0 y nada cambió. |

## Preparación de los datos

La matriz parte de una sola versión vigente, pero el 2026-11-21 TEST tenía dos: la 3.0 ACTIVO y la 2.1 DEPRECADO, en retiro hasta el 2027-02-16. Con autorización del responsable QA (opción A del análisis), ese día se preparó la base fuera del RUN:

- la vigencia de la 4.0 (PENDIENTE, MAJOR, anexo aprobado y vigencia vencida) se movió al 2030-12-31 con la modificación de la aplicación, auditada como CONTRATO_MODIFICADO, para que el proceso automático no la activara al liberarse un cupo;
- con el chat de BD se adelantó la fecha de inactivación de la 2.1, y el proceso automático la pasó a INACTIVO a las 05:30:44 UTC con su evento CONTRATO_INACTIVADO. Es definitivo: solo adelanta lo previsto para febrero.

Desde entonces, la 3.0 es la única vigente. La 5.0 sigue PENDIENTE con la vigencia vencida, pero su anexo está en BORRADOR y no puede activarse.

Dentro del RUN, el ejecutor comprobó en vivo, antes de escribir, la única vigente ACTIVO (3.0), la fixture 3.9 (id 13, anexo 1 OBSOLETO), los anexos aprobados (2, 6 y 7), las versiones libres 9.0, 9.1 y 10.1, los permisos del Administrador y que ninguna PENDIENTE vencida fuera activable. Leyó la gracia por defecto de M09 (90 días) y la bandeja del Administrador filtrada por el módulo de integración y el nivel crítico. El último aviso del mismo tipo tenía más de 11 minutos, así que el antispam del producto no podía suprimir el del caso 11.

La fase A hizo el 11, el 09 y el 12, y su DELETE lo deshizo todo; la fase B, desde la misma base, hizo el 10 y su DELETE.

## Detalle por caso

### TC-M07-11 — Activación de una versión que no cumple las precondiciones

- **Preparación:** fase A. Versión 3.9 (PENDIENTE, anexo 1 OBSOLETO). En la línea base de la bandeja estaba el aviso 20902 de la V2, sin atender, con 1 ocurrencia.
- **Esperado:** según FA-5 y CA-5, la activación se bloquea con CONTRATO_NO_VALIDO, la versión sigue PENDIENTE y el Administrador recibe un aviso con el motivo específico del bloqueo.
- **Observado:** la activación respondió HTTP 422 CONTRATO_NO_VALIDO con el mensaje «La versión 3.9 no tiene un anexo de mapeo aprobado.», y el listado posterior seguía mostrando la 3.9 en PENDIENTE sin otros cambios. En la bandeja del Administrador, el aviso crítico 20902, cuyo texto es «La versión 3.9 del contrato contable no pudo activarse: La versión 3.9 no tiene un anexo de mapeo aprobado.», pasó de 1 a 2 ocurrencias, con la última a las 06:17:27 UTC, justo después del intento. El producto agrupa los avisos iguales que el usuario aún no atendió (M8-05), así que el aviso de este intento quedó registrado como una ocurrencia nueva y no como una notificación aparte. La auditoría registró además el evento CONTRATO_ACTIVACION_BLOQUEADA de la 3.9 con el motivo.
- **Decisión: APROBADO.** Las comprobaciones muestran corregida en TEST INC-M07-G038-01: la activación manual bloqueada avisa al Administrador con el motivo.

### TC-M07-09 — Activación de una versión MAJOR

- **Preparación:** fase A, con la 3.0 como única vigente. Alta de la 9.0 MAJOR (id 42) con el anexo 2 y la gracia por defecto de 90 días.
- **Esperado:** según CA-6, CA-7 y 5.4, la versión ACTIVO anterior pasa a DEPRECADO en el instante de la activación, con inactivación a esa fecha más la gracia, y RF-102 registra la activación y la deprecación.
- **Observado:** la activación respondió HTTP 200 y la 9.0 quedó ACTIVO el 2026-11-21 a las 06:17:28.729370 UTC. La 3.0 pasó a DEPRECADO con deprecación en ese mismo instante e inactivación el 2027-02-19 a la misma hora, exactamente 90 días después. Respecto de la línea base, aparecieron un CONTRATO_ACTIVADO de la 9.0 y un CONTRATO_DEPRECADO de la 3.0.
- **Decisión: APROBADO.**

### TC-M07-12 — Activación de una tercera versión con dos vigentes

- **Preparación:** fase A, a continuación del 09 (9.0 ACTIVO y 3.0 DEPRECADO). Alta de la 9.1 MINOR.
- **Esperado:** según CA-16, CA-21 y FA-6, rechazo con LIMITE_VERSIONES_EXCEDIDO sin cambiar ninguna versión; según CA-29, el mensaje dice qué versión retirar o esperar.
- **Observado:** HTTP 422 LIMITE_VERSIONES_EXCEDIDO con el mensaje «Ya hay 2 versiones vigentes y la versión 3.0 ya está en retiro hasta el 19/02/2027. Podrá activar una nueva versión cuando termine ese retiro.». El listado posterior era idéntico: la 9.1 seguía PENDIENTE y las dos vigentes conservaban sus fechas.
- **Decisión: APROBADO.**

### TC-M07-10 — Activación de una versión MINOR

- **Preparación:** fase B, tras comprobar que la base volvía a ser la inicial (3.0 ACTIVO, única vigente). Alta de la 10.1 MINOR (id 44).
- **Esperado:** según CA-9 y 5.5, la MINOR se activa sin deprecar las anteriores ni iniciar gracia; quedan exactamente dos vigentes.
- **Observado:** la activación respondió HTTP 200 y la 10.1 quedó ACTIVO a las 06:17:31.208702 UTC. La 3.0 siguió ACTIVO sin fecha de deprecación ni de inactivación, y las vigentes eran exactamente dos. Apareció un CONTRATO_ACTIVADO de la 10.1 y ningún CONTRATO_DEPRECADO nuevo.
- **Decisión: APROBADO.**

## Comprobaciones API

- TC-M07-09 / activacion_major, deprecacion_anterior, fechas_gracia, auditoria_major: APROBADO; resultado.json.
- TC-M07-10 / activacion_minor, anterior_intacta, dos_vigentes, auditoria_minor: APROBADO; resultado.json.
- TC-M07-11 / bloqueo_precondicion, pendiente_intacta: APROBADO; 422 CONTRATO_NO_VALIDO; resultado.json.
- TC-M07-11 / aviso_administrador: APROBADO por la vía «agrupado» (aviso 20902, ocurrencias 1 → 2); resultado.json.
- TC-M07-12 / limite_rechazado, mensaje_version, pendiente_y_vigentes: APROBADO; resultado.json.

## Evidencias reales

resultado.json (con las dos líneas base, los avisos comparados con sus ocurrencias y fechas, y los resúmenes de los eventos de auditoría comparados), preflight.json, contexto_operacion.json, newman/newman-G038.json y newman/newman-G038.html. Ningún archivo contiene correos, contraseñas, tokens ni el secreto del sandbox.

## Incidencias de producto

Ninguna. Las comprobaciones de la V3 muestran corregida en TEST INC-M07-G038-01 (V1); Desarrollo informó la corrección en 0553cefd.

## Observaciones

- **El aviso es persistente y crítico.** Por diseño, el aviso del bloqueo se guarda con una sesión propia, fuera del sandbox, en la bandeja de cada usuario activo con lectura de la auditoría de la integración, y no se puede descartar. La V2 lo creó (notificación 20902 en la bandeja del Administrador QA) y la V3 le sumó una ocurrencia. Solo se leyó la bandeja del Administrador QA.
- **Datos de TEST modificados para esta reevaluación** (autorizados por el responsable QA): la 2.1 quedó INACTIVO de forma definitiva y la vigencia de la 4.0 está en 2030-12-31. Si se devuelve la 4.0 a su fecha original, el proceso automático la activará y la 3.0 pasará a DEPRECADO.
- La 5.0 se activaría sola si alguien aprueba su anexo 8, porque su vigencia ya venció.

## Cierre y rollback

- **Fase A:** `DELETE /test-control/runs/RUN-G038-V3-20261121-061724` respondió HTTP 200, y la lectura posterior sin las cabeceras del RUN coincidió con la base: la 3.0 de nuevo ACTIVO sin fechas de retiro, sin la 9.0 ni la 9.1.
- **Fase B:** el segundo DELETE respondió HTTP 200 y la lectura posterior volvió a coincidir con la base, sin la 10.1.
- Rollback verificado en las dos fases. Efectos persistentes: el inicio de sesión del Administrador QA antes del RUN y la ocurrencia del aviso crítico del caso 11.

## Conclusión y acciones

La activación de versiones cumple RF-98: MAJOR depreca la anterior con la gracia exacta, MINOR convive con ella, el límite de dos vigentes se respeta con el mensaje que pide CA-29 y la activación inválida se bloquea y avisa al Administrador con el motivo, como exige CA-5. Grupo APROBADO en la V3; INC-M07-G038-01 queda corregida en TEST, y su cierre administrativo corresponde al responsable QA.
## Historial del informe

Informe redactado por el orquestador QA (2026-11-21) a partir de resultado.json y newman/. Veredictos y evidencias sin cambios.
