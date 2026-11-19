# TC-M07-G039 — RECHAZADO

## Identificación

TC-M07-G039, que agrupa TC-M07-13, TC-M07-14, TC-M07-15 y TC-M07-16: ciclo de vida del contrato AAEF (deprecación manual, transiciones inválidas, inmutabilidad de las versiones activas y no reactivación de las inactivas). RF-98 v1.2; restricciones 5.1 y 5.12; flujos FA-12 y FA-13; criterios CA-12, CA-18, CA-20, CA-26 y CA-27. La fila de la matriz se corrigió el 2026-11-18 para usar las versiones reales de TEST en un solo RUN. Versión 1, intento 2. RUN RUN-G039-V1-20261118-161622, ambiente TEST, autorización AUT-G039-V1-R2-20261118. Actor: Administrador QA. Commit de TEST no consultado. Herramientas: Node v22.15.1 y Newman (código 0, 0 fallos). Cypress no aplica, porque el grupo solo tiene pruebas de API. RUN oficial, en una sola fase transaccional; 47 de 70 solicitudes.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M07-13 | APROBADO | La deprecación manual de la versión ACTIVO la dejó DEPRECADO con inactivación exactamente a 90 días y registró el evento CONTRATO_DEPRECADO. |
| TC-M07-14 | RECHAZADO | Las tres transiciones inválidas se rechazaron sin cambiar ningún estado, pero ninguna quedó registrada en la auditoría con severidad WARNING ni avisó al Administrador. |
| TC-M07-15 | RECHAZADO | La versión ACTIVO no cambió, pero el intento de modificarla devolvió 404 sin el error MODIFICACION_NO_PERMITIDA. |
| TC-M07-16 | RECHAZADO | La versión INACTIVO no cambió y deprecarla dio REACTIVACION_NO_PERMITIDA, pero activarla devolvió CONTRATO_NO_VALIDO. |

## Preparación de los datos

La matriz preveía registrar versiones propias (3.0, 3.2, 4.0 y 4.1). El intento 1 (RUN-G039-V1-20261118-154957) se detuvo en el preflight, sin escribir nada, porque los datos de M07 en TEST habían cambiado ese mismo día por pruebas de otros equipos: la 3.0 MAJOR se activó a las 13:53:12 UTC, lo que dejó la 2.1 en DEPRECADO, y se crearon la 3.1, la 4.0 y la 5.0 en PENDIENTE. Con dos versiones vigentes y una 4.0 ya registrada, el plan original no era posible.

Con la aprobación del responsable QA, el intento 2 usó esas versiones tal como estaban, sin registrar ninguna, y el ejecutor las eligió en vivo por su estado: DEPRECADO la 2.1 (id 3), ACTIVO la 3.0 (id 18), la PENDIENTE de menor id, que es la 2.2 (id 4), y la INACTIVO de menor id, que es la 1.0 (id 1). Todo se hizo dentro del sandbox, y la lectura final confirmó que esas versiones quedaron exactamente como estaban.

Antes de escribir, el preflight comprobó también que el proceso automático de vigencias no podía cambiar los datos durante el RUN. La 4.0 (id 19) y la 5.0 (id 20) tienen la vigencia vencida desde el 2026-11-01, pero no pueden activarse porque ya hay dos versiones vigentes (`contrato.py:132-140`); quedaron anotadas como observación. Ninguna DEPRECADO tenía la inactivación vencida.

## Detalle por caso

### TC-M07-14 — Transiciones de estado inválidas

- **Preparación:** antes de cada intento, el ejecutor tomó como referencia el listado de contratos, la primera página de la auditoría de la integración (100 eventos de 373, del más reciente al más antiguo) y la primera página de la bandeja del Administrador QA (865 avisos). Después del intento repitió las tres lecturas.
- **Esperado:** según 5.1, CA-26 y CA-27, un retroceso, una repetición o un salto de estado se rechazan y el contrato conserva su estado. CA-27 exige además registrar el intento en RF-102 con severidad WARNING y notificar al Administrador.
- **Observado:**
  - Activar la 2.1, que está DEPRECADO (retroceso): HTTP 422, `TRANSICION_NO_PERMITIDA`, «No se puede activar la versión 2.1: está deprecado.».
  - Activar la 3.0, que está ACTIVO (repetición): HTTP 422, `TRANSICION_NO_PERMITIDA`, «No se puede activar la versión 3.0: está activo.».
  - Deprecar la 2.2, que está PENDIENTE (salto): HTTP 422, `TRANSICION_NO_PERMITIDA`, «No se puede deprecar la versión 2.2: está pendiente.».
  - En los tres casos el listado posterior era idéntico al anterior.
  - En la auditoría no apareció ningún evento nuevo: el total se mantuvo en 373 en las seis lecturas y la primera página no cambió. Tampoco llegó ningún aviso nuevo a la bandeja, que siguió con 865 avisos.
- **Decisión: RECHAZADO** por **INC-M07-G039-01**. El rechazo y la protección del estado son correctos, pero falta el registro WARNING y el aviso que exige CA-27.

### TC-M07-15 — Intento de modificar una versión ACTIVO

- **Preparación:** sobre la 3.0 (ACTIVO), con el listado de contratos como referencia.
- **Esperado:** según 5.12, CA-20 y FA-12, el intento de modificar una versión ACTIVO se rechaza con el error MODIFICACION_NO_PERMITIDA y la versión no cambia.
- **Observado:** `PATCH` y `PUT /integracion/contratos/18`, con el cuerpo `{"mapeadores":["COMPRAS","CAMBIO_QA"]}`, respondieron los dos HTTP 404 con el cuerpo `{"detail":"Not Found"}`, sin el formato de error estándar de la API ni ningún código de error. El listado posterior era idéntico al anterior: la 3.0 conservó sus Mappers, su anexo y su estado.
- **Decisión: RECHAZADO** por **INC-M07-G039-02**. La inmutabilidad se cumple, porque no hay forma de modificar la versión, pero la API no responde con el error que nombran CA-20 y FA-12.

### TC-M07-13 — Deprecación manual de una versión ACTIVO

- **Preparación:** la 3.0 seguía ACTIVO tras los casos anteriores. Se tomó como referencia la auditoría filtrada por CONTRATO_DEPRECADO (3 eventos).
- **Esperado:** la versión pasa de ACTIVO a DEPRECADO, la fecha de inactivación es la de deprecación más los días de gracia indicados (90) y, según CA-18, RF-102 registra el cambio con versión, estado resultante, usuario y fecha.
- **Observado:**
  - `POST /integracion/contratos/18/deprecar` con `dias_gracia` 90 respondió HTTP 200. La 3.0 quedó DEPRECADO con deprecación el 2026-11-18 a las 16:16:31.032754 UTC e inactivación el 2027-02-16 a las 16:16:31.032754 UTC, exactamente 90 días después.
  - En la auditoría apareció un CONTRATO_DEPRECADO nuevo (4 eventos en total): versión 3.0, usuario del Administrador QA y fecha 2026-11-18 a las 16:16:31.036619 UTC. El ejecutor comprobó sobre la respuesta completa que el detalle del evento (`json_detalle.estado`) indica el estado resultante DEPRECADO; `resultado.json` guarda la lectura resumida (G039-035), sin ese campo.
- **Decisión: APROBADO.** La deprecación manual aplica el período de gracia exacto y deja el registro completo.

### TC-M07-16 — Intento de reactivar una versión INACTIVO

- **Preparación:** sobre la 1.0 (id 1), INACTIVO y sin anexo, con el listado de contratos como referencia.
- **Esperado:** según 5.1, CA-12 y FA-13, cualquier intento de cambiar de estado una versión INACTIVO se rechaza con REACTIVACION_NO_PERMITIDA y la versión sigue INACTIVO.
- **Observado:**
  - Activarla respondió HTTP 422 con `CONTRATO_NO_VALIDO` y el mensaje «La versión 1.0 no tiene un anexo de mapeo aprobado.».
  - Deprecarla respondió HTTP 422 con `REACTIVACION_NO_PERMITIDA` y el mensaje «La versión 1.0 está inactiva y no puede cambiar de estado.».
  - Después de cada intento, el listado era idéntico al anterior y la 1.0 seguía INACTIVO.
- **Decisión: RECHAZADO** por **INC-M07-G039-03**. La versión no se reactiva y la deprecación da el código correcto, pero la activación responde con un motivo distinto del que exige CA-12.

## Comprobaciones API

- TC-M07-13 / deprecacion, gracia_90, auditoria: APROBADO; resultado.json.
- TC-M07-14 / retroceso, repeticion, salto: RECHAZADO; rechazo 422 y estados intactos, sin WARNING ni aviso; resultado.json y Newman.
- TC-M07-15 / patch, put: RECHAZADO; 404 sin MODIFICACION_NO_PERMITIDA; resultado.json.
- TC-M07-15 / inmutabilidad: APROBADO; la 3.0 idéntica antes y después; resultado.json.
- TC-M07-16 / activar: RECHAZADO; 422 CONTRATO_NO_VALIDO; resultado.json.
- TC-M07-16 / deprecar, inmutable: APROBADO; 422 REACTIVACION_NO_PERMITIDA y la 1.0 sigue INACTIVO; resultado.json.

## Evidencias reales

resultado.json, preflight.json, contexto_operacion.json, newman/newman-G039.json y newman/newman-G039.html.

## Incidencias de producto

### INC-M07-G039-01 — Las transiciones inválidas no se registran con severidad WARNING ni avisan al Administrador

**Requisito:** RF-98, CA-27: «Dado el intento de hacer una transición de estado inválida (retroceso, salto o reactivación desde INACTIVO), cuando el sistema lo detecta, entonces debe rechazar la operación, no modificar el estado actual del contrato, registrar el intento en RF-102 con severidad WARNING y notificar al Administrador». CA-26 pide también que los intentos en sentido inverso o con salto se rechacen «con registro en RF-102».

**Pasos para reproducir:** como Administrador, anotar el total de `GET /integracion/auditoria` y el aviso más reciente de `GET /notificaciones`. Enviar `POST /integracion/contratos/{id}/activar` sobre una versión DEPRECADO o ACTIVO, o `POST /integracion/contratos/{id}/deprecar` sobre una PENDIENTE. Volver a consultar la auditoría y la bandeja.

**Esperado:** rechazo, estado sin cambios, un evento nuevo en la auditoría con severidad WARNING para la versión del intento y un aviso nuevo en la bandeja del Administrador.

**Obtenido:** rechazo HTTP 422 TRANSICION_NO_PERMITIDA y estado sin cambios en los tres intentos, pero la auditoría sigue con el mismo total (373) y la bandeja no recibe ningún aviso.

**Causa probable (hipótesis a partir del código, sin confirmar en TEST):** el rechazo deshace la transacción antes de cualquier registro.
- `VersionContrato._exigir` (`src/accounting_integration/domain/entities/contrato.py:94-100`) lanza `FlowError` (TRANSICION_NO_PERMITIDA o REACTIVACION_NO_PERMITIDA) cuando el estado no permite la operación.
- `GestionarContratosUseCase.activar` (`src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py:101-129`) y `deprecar` (`:131-145`) capturan cualquier excepción, hacen `self.db.rollback()` y la relanzan, sin llamar a `_evento` (`:64-68`), que es el único punto donde se registra en RF-102, ni a la alerta al Administrador.
- Además, `_evento` siempre graba `codigo_resultado="OK"` sin severidad propia, así que hoy no hay ningún camino que registre un intento rechazado con severidad WARNING.
- Lo mismo se ve en el caso 16: el intento sobre la versión INACTIVO, que CA-27 también incluye («reactivación desde INACTIVO»), pasa por el mismo `except` y tampoco deja registro. En este RUN no se leyó la auditoría durante el 16, así que esa parte queda como hipótesis.
- La corrección probable es registrar el intento con severidad WARNING (en una transacción aparte, como hace `auditar_aparte` en el router de auditoría, `m07_router.py:274-276`) y avisar al Administrador antes de relanzar el error; decidirlo corresponde a Desarrollo.

**Impacto y severidad:** MEDIA. Las transiciones inválidas se impiden y el estado de los contratos está protegido, así que no hay riesgo para los datos. Pero no queda ningún rastro de los intentos ni se avisa al Administrador, y el requisito pide expresamente las dos cosas. Certeza de la discrepancia: CONFIRMADA en TEST. Causa raíz: hipótesis no verificada en la versión desplegada.

**Primera atención:** Desarrollo.

**Evidencias:** `resultado.json`: G039-008, G039-015 y G039-022 (los tres rechazos), las lecturas de la auditoría (G039-006, -010, -013, -017, -020 y -024, con el total en 373) y de la bandeja antes y después de cada intento; `newman/newman-G039.json`.

### INC-M07-G039-02 — Modificar una versión ACTIVO responde 404 en lugar de MODIFICACION_NO_PERMITIDA

**Requisito:** RF-98, CA-20: «Dado un contrato en estado ACTIVO o DEPRECADO, cuando se intenta modificar, entonces el sistema debe rechazar la operación con error MODIFICACION_NO_PERMITIDA». FA-12 indica el mismo error.

**Pasos para reproducir:** como Administrador, enviar `PATCH` o `PUT /integracion/contratos/{id}` sobre una versión ACTIVO con un cuerpo que cambie los Mappers.

**Esperado:** rechazo con el error estándar de la API y `error_code` MODIFICACION_NO_PERMITIDA; la versión sin cambios.

**Obtenido:** HTTP 404 con el cuerpo `{"detail":"Not Found"}`, sin `error_code`; la versión sin cambios.

**Causa probable (hipótesis a partir del código):** la API no expone ninguna operación de modificación sobre `/integracion/contratos/{id}`: el router solo define el listado, el registro, `/activar` y `/deprecar` (`src/accounting_integration/infrastructure/routers/m07_router.py:211-237`). La petición no llega a ninguna lógica de negocio y es FastAPI el que responde 404 por defecto. La inmutabilidad la protegen además la falta de ruta y el trigger de BD `tgr_m07_05`. La corrección probable es que la API responda MODIFICACION_NO_PERMITIDA a los intentos de modificación, por ejemplo con rutas que siempre rechazan, para que quien integra reciba el motivo; decidirlo corresponde a Desarrollo.

**Impacto y severidad:** BAJA. La versión ACTIVO no se puede modificar, que es lo esencial de 5.12; la diferencia es el código de error, que el requisito nombra expresamente. Certeza: CONFIRMADA en TEST.

**Primera atención:** Desarrollo.

**Evidencias:** `resultado.json`: G039-027 (PATCH) y G039-029 (PUT), con sus cuerpos de respuesta, y los listados antes y después.

### INC-M07-G039-03 — Activar una versión INACTIVO sin anexo responde CONTRATO_NO_VALIDO en lugar de REACTIVACION_NO_PERMITIDA

**Requisito:** RF-98, CA-12: «Dado un contrato en estado INACTIVO, cuando se intenta reactivarlo, entonces el sistema debe rechazar la operación con error REACTIVACION_NO_PERMITIDA». FA-13 indica el mismo error para cualquier cambio de estado desde INACTIVO.

**Pasos para reproducir:** como Administrador, enviar `POST /integracion/contratos/{id}/activar` sobre una versión INACTIVO sin anexo aprobado (en TEST, la 1.0, id 1, o la 2.0, id 2).

**Esperado:** HTTP 4xx con REACTIVACION_NO_PERMITIDA; la versión sigue INACTIVO.

**Obtenido:** HTTP 422 con CONTRATO_NO_VALIDO («La versión 1.0 no tiene un anexo de mapeo aprobado.»); la versión sigue INACTIVO. Al deprecarla, en cambio, sí responde REACTIVACION_NO_PERMITIDA.

**Causa probable (hipótesis a partir del código):** el orden de las comprobaciones de la activación. `GestionarContratosUseCase.activar` (`gestionar_contratos_use_case.py:101-129`) comprueba primero el anexo y los Mappers (`motivo_bloqueo_activacion`, `contrato.py:116-122`) y el cupo de versiones, y solo al final llama a `contrato.activar`, donde `_exigir` (`contrato.py:94-100`) rechaza el estado INACTIVO con REACTIVACION_NO_PERMITIDA. Con una versión INACTIVO sin anexo, como las semillas de TEST, salta antes el error del anexo. `deprecar` no comprueba el anexo y llega directamente a `_exigir`, por eso responde bien. La corrección probable es comprobar el estado INACTIVO antes que las precondiciones de activación; decidirlo corresponde a Desarrollo.

**Impacto y severidad:** BAJA. La versión no se reactiva y el estado está protegido; la diferencia es el motivo que recibe el Administrador, que no le dice que la versión está retirada de forma definitiva. Certeza: CONFIRMADA en TEST.

**Primera atención:** Desarrollo.

**Evidencias:** `resultado.json`: G039-037 (activar) y G039-040 (deprecar), con sus cuerpos de respuesta, y los listados antes y después.

## Observaciones

- Los datos de partida eran de otros equipos y se usaron con la aprobación del responsable QA; la lectura poscierre confirma que quedaron como estaban (ver «Cierre y rollback»).
- La auditoría de la integración contiene tres eventos SOLICITUD_RECHAZADA con fecha futura (del 2026-11-20 al 2026-11-22), ajenos a este grupo; ocupan las primeras posiciones de la página 1. No afectan a la conclusión del caso 14: un evento nuevo de este RUN habría aparecido justo después de ellos, y además el total de la auditoría no cambió.
- El intento 1 (RUN-G039-V1-20261118-154957) fue técnico: el preflight bloqueó por el cambio de datos de TEST, sin ninguna escritura. Tenía además un defecto de QA en la comprobación del rollback, corregido en ORD-G039-004. No afecta a estos veredictos.
- El login previo al RUN cerró, por la política de sesión única, otras sesiones abiertas de la cuenta del Administrador QA.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G039-V1-20261118-161622` respondió HTTP 200. La lectura posterior, sin las cabeceras del RUN (G039-043), coincidía campo por campo con la base: la 3.0 de nuevo ACTIVO sin fechas de retiro, la 2.1 DEPRECADO con su inactivación del 2027-02-16 y el resto de versiones con su estado, anexo, vigencia y fechas originales. Rollback verificado. El único efecto persistente comprobado fue el inicio de sesión del Administrador QA antes del RUN. En la bandeja del Administrador QA no apareció ningún aviso durante el RUN.

## Conclusión y acciones

El ciclo de vida del contrato protege bien el estado: la deprecación manual cumple RF-98 con la gracia exacta y su registro, ninguna transición inválida cambia el estado, una versión ACTIVO no se puede modificar y una INACTIVO no se puede reactivar. Fallan la trazabilidad y los avisos de las transiciones inválidas (INC-M07-G039-01, MEDIA) y dos códigos de error respecto de lo que nombra el requisito (INC-M07-G039-02 e INC-M07-G039-03, BAJA). Acciones: derivar las tres incidencias a Desarrollo y reevaluar el grupo completo con una nueva autorización cuando informen la corrección. Pendiente de QA: pedir autorización para borrar el RUN técnico RUN-G039-V1-20261118-154957.


## Historial del informe

Informe redactado por el orquestador QA (2026-11-18) a partir de resultado.json y newman/; la versión generada por el ejecutor se conserva en SIGAB_QA_ORQUESTACION/estado/historial_informes/M07/TC-M07-G039/. Veredictos y evidencias sin cambios.
Traslado (2026-11-19): la copia del informe del ejecutor se movió a SIGAB_QA_ORQUESTACION por decisión del responsable QA; veredictos y evidencias sin cambios.
Corrección (2026-11-18): precisado de dónde sale el estado resultante del evento CONTRATO_DEPRECADO del caso 13; veredictos y evidencias sin cambios.
