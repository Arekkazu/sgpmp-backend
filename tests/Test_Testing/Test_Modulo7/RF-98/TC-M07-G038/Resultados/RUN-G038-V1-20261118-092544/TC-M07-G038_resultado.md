# TC-M07-G038 — RECHAZADO

## Identificación

TC-M07-G038, que agrupa TC-M07-09, TC-M07-10, TC-M07-11 y TC-M07-12: activación de versiones del contrato AAEF. RF-98 v1.2; restricciones 5.3, 5.4 y 5.5; flujos FA-5 y FA-6; criterios CA-5, CA-6, CA-7, CA-9, CA-16, CA-21 y CA-29. La fila de la matriz se corrigió el 2026-11-18 para ajustarla al estado real de TEST. Versión 1, intento 2. RUN RUN-G038-V1-20261118-092544, ambiente TEST, autorización AUT-G038-V1-R2-20261118. Actor: Administrador QA. Commit de TEST no consultado. Herramientas: Node v22.15.1 y Newman (código 0, 0 fallos). Cypress no aplica, porque el grupo solo tiene pruebas de API. RUN oficial, ejecutado en dos fases transaccionales con el mismo identificador; 36 de 70 solicitudes.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M07-09 | APROBADO | Al activar la 4.0 MAJOR, la 2.1 pasó a DEPRECADO en el mismo instante, con inactivación exactamente a 90 días, y quedaron los dos eventos de auditoría. |
| TC-M07-10 | APROBADO | Al activar la 3.2 MINOR, la 2.1 siguió ACTIVO sin fechas de retiro y quedaron exactamente dos versiones vigentes. |
| TC-M07-11 | RECHAZADO | La activación de una versión con anexo no aprobado se bloqueó con CONTRATO_NO_VALIDO, pero el Administrador no recibió ningún aviso. |
| TC-M07-12 | APROBADO | Con dos versiones vigentes, la activación de una tercera se rechazó con LIMITE_VERSIONES_EXCEDIDO, el mensaje indicó qué versión retirar y nada cambió. |

## Preparación de los datos

La matriz se escribió suponiendo una sola versión vigente, pero en TEST había dos: la 2.1 ACTIVO y la 2.0 DEPRECADO, una semilla de 2025 sin fechas que nunca expiraba. Con el límite de 5.3 ya alcanzado, ninguna activación era posible. Con autorización del responsable QA, el 2026-11-18 se retiró la 2.0 de forma definitiva siguiendo el flujo de la aplicación: el chat de BD le puso fechas de deprecación e inactivación ya pasadas, y el proceso automático de vigencias la pasó a INACTIVO a las 08:29:22 UTC, con su evento CONTRATO_INACTIVADO. Desde entonces, la 2.1 es la única versión vigente.

Para el caso 11, la API no permite registrar una versión con un anexo inválido, porque el registro lo rechaza. Por eso se insertó con el chat de BD la versión 3.9 (id 13): PENDIENTE, MINOR, con el anexo 1 (OBSOLETO, no utilizable) y vigencia 2030-12-31. Representa un contrato cuyo anexo dejó de estar aprobado después de registrarse. Se eliminará al terminar TC-M07-G041.

Los casos 09 y 10 parten los dos de una sola versión vigente y terminan con dos, y dentro de una transacción no hay forma de volver atrás. Por eso el RUN se ejecutó en dos fases con el mismo identificador. En la fase A se hicieron el 09, el 12 (a continuación del 09) y el 11, y después un DELETE que deshizo todo. En la fase B, partiendo otra vez de la misma base, se hizo el 10 y después otro DELETE. El sandbox lo permite porque el DELETE cierra la transacción y la siguiente petición abre una nueva (`testing_sandbox.py:35-84`).

## Detalle por caso

### TC-M07-09 — Activación de una versión MAJOR

- **Preparación:** fase A. Antes de escribir nada, el ejecutor comprobó que solo había una versión vigente (la 2.1, ACTIVO), que existía el anexo 2 APROBADO y que no estaban registradas la 3.2, la 4.0 ni la 4.1. También tomó como línea base los eventos CONTRATO_ACTIVADO y CONTRATO_DEPRECADO.
- **Esperado:** según CA-6, CA-7 y la restricción 5.4, al activar una versión MAJOR la versión ACTIVO anterior pasa a DEPRECADO e inicia el período de gracia. Su deprecación coincide con la activación de la nueva y su inactivación queda en la activación más 90 días. RF-102 registra los eventos de activación y de deprecación.
- **Observado:**
  - La 4.0 MAJOR, con gracia de 90 días, se registró con HTTP 201 (id 14).
  - Su activación respondió HTTP 200: la 4.0 quedó ACTIVO el 2026-11-18 a las 09:25:47.812677 UTC.
  - En el listado posterior, la 2.1 aparece DEPRECADO con deprecación el 2026-11-18 a las 09:25:47.812677 UTC, el mismo instante de la activación, e inactivación el 2027-02-16 a las 09:25:47.812677 UTC, exactamente 90 días después.
  - En la auditoría aparecieron, respecto de la línea base, un CONTRATO_ACTIVADO nuevo para la 4.0 y un CONTRATO_DEPRECADO nuevo para la 2.1.
- **Decisión: APROBADO.** La activación MAJOR depreca la versión anterior, inicia la gracia con las fechas exactas y deja rastro en la auditoría.

### TC-M07-12 — Activación de una tercera versión con dos vigentes

- **Preparación:** fase A, a continuación del 09, con la 2.1 DEPRECADO y la 4.0 ACTIVO, es decir, el límite de 5.3 alcanzado. Se registró la 4.1 MINOR (HTTP 201, id 15).
- **Esperado:** según CA-16, CA-21 y FA-6, el sistema rechaza la activación con LIMITE_VERSIONES_EXCEDIDO sin cambiar ninguna versión. Según CA-29, el mensaje indica qué versión hay que deprecar o retirar primero.
- **Observado:** la activación de la 4.1 respondió HTTP 422 con `error_code` LIMITE_VERSIONES_EXCEDIDO y el mensaje «Ya hay 2 versiones vigentes. Retire primero la versión 2.1 antes de activar una nueva.». El listado posterior era idéntico al anterior: la 4.1 seguía PENDIENTE, la 2.1 DEPRECADO y la 4.0 ACTIVO, con sus mismas fechas.
- **Decisión: APROBADO.** El límite se aplica con el código exigido, el mensaje dice qué versión retirar y no hay cambios parciales.

### TC-M07-11 — Activación de una versión que no cumple las precondiciones

- **Preparación:** fase A. El ejecutor eligió en vivo la versión PENDIENTE cuyo anexo no es utilizable: la 3.9 (id 13), con el anexo 1 OBSOLETO. Antes del intento tomó como referencia la primera página de la bandeja del Administrador QA (862 avisos en total, ordenados del más reciente al más antiguo).
- **Esperado:** según FA-5 y CA-5, la activación se bloquea con CONTRATO_NO_VALIDO y la versión sigue en PENDIENTE. CA-5 exige además notificar al Administrador el motivo específico del bloqueo, tanto en la activación automática como en la manual.
- **Observado:** la activación respondió HTTP 422 con `error_code` CONTRATO_NO_VALIDO y el mensaje «La versión 3.9 no tiene un anexo de mapeo aprobado.». El listado posterior seguía mostrando la 3.9 en PENDIENTE y ninguna otra versión cambió. En la bandeja del Administrador no apareció ningún aviso nuevo: ningún aviso con id posterior a la línea base, y ninguno del tipo ALERTA_INTEGRACION_CONTABLE (41) en la página leída.
- **Decisión: RECHAZADO** por **INC-M07-G038-01**. El bloqueo y el código son correctos, pero el Administrador no recibe el aviso con el motivo, como exige CA-5.

### TC-M07-10 — Activación de una versión MINOR

- **Preparación:** fase B. Tras el DELETE de la fase A, el ejecutor comprobó que la base volvía a ser la inicial: 2.1 ACTIVO como única vigente, sin fechas de retiro. Tomó de nuevo la línea base de la auditoría y registró la 3.2 MINOR (HTTP 201, id 16).
- **Esperado:** según CA-9 y la restricción 5.5, una versión MINOR se activa sin deprecar las anteriores y sin iniciar período de gracia. La activación se permite porque quedan exactamente dos vigentes, que es el límite de 5.3.
- **Observado:** la activación respondió HTTP 200 y la 3.2 quedó ACTIVO el 2026-11-18 a las 09:25:50.846140 UTC. En el listado, la 2.1 seguía ACTIVO, sin fecha de deprecación ni de inactivación, y las vigentes eran exactamente dos (2.1 y 3.2). En la auditoría apareció un CONTRATO_ACTIVADO nuevo para la 3.2 y ningún CONTRATO_DEPRECADO nuevo.
- **Decisión: APROBADO.** La activación MINOR convive con la versión anterior sin retirarla.

## Comprobaciones API

- TC-M07-09 / activacion_major, deprecacion_anterior, fechas_gracia, auditoria_major: APROBADO; resultado.json.
- TC-M07-10 / activacion_minor, anterior_intacta, dos_vigentes, auditoria_minor: APROBADO; resultado.json.
- TC-M07-11 / bloqueo_precondicion: APROBADO; 422 CONTRATO_NO_VALIDO; resultado.json.
- TC-M07-11 / pendiente_intacta: APROBADO; la 3.9 sigue PENDIENTE y nada cambia; resultado.json.
- TC-M07-11 / aviso_administrador: RECHAZADO; ningún aviso nuevo en la bandeja; resultado.json y Newman.
- TC-M07-12 / limite_rechazado, mensaje_version, pendiente_y_vigentes: APROBADO; resultado.json.

## Evidencias reales

resultado.json (con las dos fases de cierre), preflight.json, contexto_operacion.json, newman/newman-G038.json y newman/newman-G038.html.

## Incidencias de producto

### INC-M07-G038-01 — La activación manual bloqueada no avisa al Administrador del motivo

**Requisito:** RF-98, CA-5: «Dado un contrato sin Mappers válidos o sin Anexo aprobado, cuando intenta activarse (automática o manualmente), entonces el sistema debe bloquear la activación, mantener el estado PENDIENTE y notificar al Administrador con el motivo específico del bloqueo».

**Pasos para reproducir:** como Administrador, tomar una versión PENDIENTE cuyo anexo no esté APROBADO (en TEST, la 3.9, id 13, con el anexo 1 OBSOLETO). Consultar la bandeja (`GET /notificaciones`) y anotar el aviso más reciente. Enviar `POST /integracion/contratos/{id}/activar`. Volver a consultar la bandeja.

**Esperado:** rechazo CONTRATO_NO_VALIDO, la versión sigue en PENDIENTE y llega a la bandeja del Administrador un aviso nuevo con el motivo («no tiene un anexo de mapeo aprobado»).

**Obtenido:** rechazo HTTP 422 CONTRATO_NO_VALIDO con el motivo en la respuesta, y la versión sigue en PENDIENTE. En la bandeja no aparece ningún aviso nuevo después del intento, ni ninguno del tipo ALERTA_INTEGRACION_CONTABLE.

**Causa probable (hipótesis a partir del código, sin confirmar en TEST):** el aviso solo existe en el camino automático.
- `GestionarContratosUseCase.activar` (`src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py:101-112`) lanza `BusinessRuleError(CONTRATO_NO_VALIDO)` cuando `motivo_bloqueo_activacion` encuentra el anexo no utilizable, sin llamar a `self.alertar`.
- El aviso solo se envía desde `procesar_vigencias` (`:152-159`), que lo invoca con `_avisar_bloqueo` (`:174-185`) cuando falla la activación automática de una versión al llegar su fecha de vigencia.
- El canal sí está preparado: el adaptador `alerta_administrador_adapter.py` escribe la alerta ALERTA_INTEGRACION_CONTABLE en la bandeja de quienes pueden leer la auditoría de la integración. El tipo 41 existe y tiene categoría asignada en el código (`evento_categoria.py:96`), así que el aviso llegaría si se invocara.
- La corrección probable es llamar al aviso también cuando la activación manual se bloquea; decidirlo y aplicarlo corresponde a Desarrollo.

**Impacto y severidad:** MEDIA. La activación inválida se impide correctamente y quien la intenta recibe el motivo en la respuesta, así que no hay riesgo para los datos. Pero el resto de administradores no se enteran del bloqueo, y el requisito pide expresamente la notificación con el motivo. Certeza de la discrepancia: CONFIRMADA en TEST. Causa raíz: hipótesis no verificada en la versión desplegada.

**Primera atención:** Desarrollo.

**Evidencias:** `resultado.json`: G038-019 (activación rechazada), G038-020 (la 3.9 sigue PENDIENTE), y la primera página de la bandeja antes del intento (línea base) y G038-021 (después), sin avisos nuevos; `newman/newman-G038.json`.

## Observaciones

- Los datos de partida se prepararon con autorización del responsable QA (ver «Preparación de los datos»). La retirada de la 2.0 es definitiva porque los triggers de la BD solo permiten avanzar de estado. La fixture 3.9 se borrará al terminar TC-M07-G041.
- El intento 1 (RUN-G038-V1-20261118-090819) fue técnico por un error de QA en el contrato de respuestas: trataba el id de los eventos de auditoría como número, cuando en el backend es texto UUID. Se detuvo antes de cualquier escritura y no afecta a estos veredictos.

## Cierre y rollback

- **Fase A:** `DELETE /test-control/runs/RUN-G038-V1-20261118-092544` respondió HTTP 200. La lectura posterior, sin las cabeceras del RUN, coincidía con la base: la 2.1 de nuevo ACTIVO sin fechas de retiro, y sin la 4.0 ni la 4.1.
- **Fase B:** el segundo DELETE respondió HTTP 200 y la lectura posterior volvió a coincidir con la base, sin la 3.2.
- Rollback verificado en las dos fases. El único efecto persistente comprobado fue el inicio de sesión del Administrador QA antes del RUN. Solo se leyó la bandeja del Administrador QA y en ella no apareció ningún aviso. Como el adaptador envía la alerta a la vez a todos los lectores de la auditoría (`alerta_administrador_adapter.py:36-46`), no hay indicios de notificaciones persistentes en otras bandejas, aunque no se consultaron.

## Conclusión y acciones

La activación de versiones cumple RF-98 en lo esencial: MAJOR depreca la anterior con la gracia exacta, MINOR convive con ella, el límite de dos vigentes se respeta con el mensaje que pide CA-29 y las activaciones inválidas se bloquean. Falla el aviso al Administrador cuando una activación manual se bloquea (INC-M07-G038-01, MEDIA). Acciones: derivar INC-M07-G038-01 a Desarrollo y reevaluar el grupo completo con una nueva autorización cuando informen la corrección. Pendiente de QA: pedir autorización para borrar el RUN técnico RUN-G038-V1-20261118-090819.

## Historial del informe

Enmienda (2026-11-18): informe redactado con formato M06; veredictos, resultado.json y evidencias sin cambios (SHA-256 de resultado.json da11a361e22852a391eb7e636594f4802bffadd5f3eb9ec21102af9652235cba).

Corrección (2026-11-18): precisada la afirmación sobre avisos fuera del sandbox; veredictos y evidencias sin cambios.
