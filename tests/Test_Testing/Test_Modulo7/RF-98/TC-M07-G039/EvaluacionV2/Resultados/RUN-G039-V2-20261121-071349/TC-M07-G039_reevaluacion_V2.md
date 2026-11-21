# TC-M07-G039 — Reevaluación V2 — APROBADO

## Identificación

TC-M07-G039, que agrupa TC-M07-13 a TC-M07-16: ciclo de vida del contrato AAEF (deprecación manual, transiciones inválidas, inmutabilidad de las versiones activas y no reactivación de las inactivas). RF-98 v1.2; restricciones 5.1 y 5.12; flujos FA-12 y FA-13; criterios CA-12, CA-18, CA-20, CA-26 y CA-27. Versión 2 (reevaluación del grupo completo). RUN RUN-G039-V2-20261121-071349, ambiente TEST, autorización AUT-G039-V2-20261121. Versión anterior: V1 oficial RUN-G039-V1-20261118-161622. Actor: Administrador QA. Commit desplegado en TEST no consultado; la rama origin/test del repositorio contiene las correcciones 04bddac4 y 20b5f701. Herramientas: Node v22.15.1 y Newman (código 0); sin UI. RUN oficial, en una sola fase transaccional; 58 de 70 solicitudes.

## Motivo de la reevaluación

La V1 rechazó tres casos:
- **14** (INC-M07-G039-01, MEDIA): las transiciones inválidas se rechazaban, pero no quedaban en RF-102 con severidad WARNING ni avisaban al Administrador (CA-26 y CA-27).
- **15** (INC-M07-G039-02, BAJA): modificar una versión ACTIVO respondía 404 en lugar de MODIFICACION_NO_PERMITIDA (CA-20 y FA-12).
- **16** (INC-M07-G039-03, BAJA): activar una versión INACTIVO sin anexo respondía CONTRATO_NO_VALIDO en lugar de REACTIVACION_NO_PERMITIDA (CA-12 y FA-13).

Desarrollo informó las correcciones en 04bddac4 (#1175) y 20b5f701. La V2 repite los cuatro casos.

## Resumen de veredictos

| Caso | V1 | V2 | Motivo |
|---|---|---|---|
| TC-M07-13 | APROBADO | APROBADO | La 3.0 pasó a DEPRECADO con inactivación exactamente a 90 días y evento CONTRATO_DEPRECADO. |
| TC-M07-14 | RECHAZADO | APROBADO | Las tres transiciones inválidas se rechazaron sin cambiar el estado, cada una con su evento WARNING, y el Administrador recibió el aviso. |
| TC-M07-15 | RECHAZADO | APROBADO | PATCH y PUT de la versión ACTIVO respondieron MODIFICACION_NO_PERMITIDA y la versión no cambió. |
| TC-M07-16 | RECHAZADO | APROBADO | Activar y deprecar la versión INACTIVO respondieron REACTIVACION_NO_PERMITIDA y siguió INACTIVO. |

## Preparación de los datos

Tras la preparación de TC-M07-G038 V2, la 3.0 (id 18) es en TEST la única versión vigente y no hay ninguna DEPRECADO. El ejecutor eligió en vivo, antes de escribir, la ACTIVO (3.0), la PENDIENTE de menor id (2.2, id 4) y la INACTIVO de menor id (1.0, id 1); comprobó los permisos, la gracia mínima de M09 (no mayor que 90 días), que ninguna PENDIENTE vencida fuera activable y que el último aviso del mismo tipo tuviera más de 11 minutos.

Como no había ninguna DEPRECADO real, el retroceso se probó con la 3.0 después de deprecarla dentro del RUN (caso 13). El orden fue: repetición del 14, salto del 14, 15, 13, retroceso del 14 y 16, de modo que el primer rechazo del RUN fuera una transición inválida.

Por decisión del responsable QA, el aviso de CA-27 se exige tras el primer intento inválido, porque el adaptador de alertas declara un antispam de 10 minutos; el evento WARNING se exige en cada intento.

## Detalle por caso

### TC-M07-14 — Transiciones de estado inválidas

- **Preparación:** antes y después de cada intento, el listado de contratos y la auditoría filtrada por CONTRATO_TRANSICION_RECHAZADA; después del primer intento, la bandeja del Administrador filtrada por el módulo de integración y el nivel crítico.
- **Esperado:** según 5.1, CA-26 y CA-27, cada retroceso, repetición o salto se rechaza, el estado no cambia, el intento queda en RF-102 con severidad WARNING y se notifica al Administrador.
- **Observado:**
  - Activar la 3.0, que está ACTIVO (repetición): HTTP 422 TRANSICION_NO_PERMITIDA, «No se puede activar la versión 3.0: está activo.».
  - Deprecar la 2.2, que está PENDIENTE (salto): HTTP 422 TRANSICION_NO_PERMITIDA, «No se puede deprecar la versión 2.2: está pendiente.».
  - Activar la 3.0, ya DEPRECADO en el sandbox (retroceso): HTTP 422 TRANSICION_NO_PERMITIDA, «No se puede activar la versión 3.0: está deprecado.».
  - En los tres, el listado posterior era idéntico al anterior y apareció un evento CONTRATO_TRANSICION_RECHAZADA nuevo, severidad WARNING, de la versión del intento y con ese código.
  - Tras el primer intento llegó a la bandeja del Administrador el aviso crítico nuevo 20964, a las 07:13:52 UTC, con el texto «Se rechazó un intento de activar la versión 3.0 del contrato contable: No se puede activar la versión 3.0: está activo.».
- **Decisión: APROBADO.** Las comprobaciones muestran corregida en TEST INC-M07-G039-01.

### TC-M07-15 — Intento de modificar una versión ACTIVO

- **Preparación:** sobre la 3.0 (ACTIVO), con el cuerpo `{"descripcion":"QA G039 V2"}`.
- **Esperado:** según 5.12, CA-20 y FA-12, el intento se rechaza con MODIFICACION_NO_PERMITIDA y la versión no cambia.
- **Observado:** PATCH y PUT respondieron HTTP 422 con el error estándar, `error_code` MODIFICACION_NO_PERMITIDA y el mensaje «La versión 3.0 está activo y ya no puede modificarse.». El listado posterior era idéntico al anterior. Cada intento dejó además su evento WARNING.
- **Decisión: APROBADO.** Las comprobaciones muestran corregida en TEST INC-M07-G039-02.

### TC-M07-13 — Deprecación manual de una versión ACTIVO

- **Preparación:** la 3.0 seguía ACTIVO tras los casos anteriores; línea base de la auditoría filtrada por CONTRATO_DEPRECADO.
- **Esperado:** la versión pasa de ACTIVO a DEPRECADO, con inactivación igual a la deprecación más 90 días, y, según CA-18, RF-102 registra el cambio con versión, estado resultante, usuario y fecha.
- **Observado:** `POST /integracion/contratos/18/deprecar` con `dias_gracia` 90 respondió HTTP 200. La 3.0 quedó DEPRECADO con deprecación el 2026-11-21 a las 07:13:56.416066 UTC e inactivación el 2027-02-19 a la misma hora, exactamente 90 días después. Apareció un CONTRATO_DEPRECADO nuevo de la 3.0, con el estado resultante, el usuario del Administrador QA y su fecha.
- **Decisión: APROBADO.**

### TC-M07-16 — Intento de reactivar una versión INACTIVO

- **Preparación:** sobre la 1.0 (id 1), INACTIVO y sin anexo.
- **Esperado:** según 5.1, CA-12 y FA-13, cualquier cambio de estado se rechaza con REACTIVACION_NO_PERMITIDA, la versión sigue INACTIVO y, según CA-27, el intento queda con severidad WARNING.
- **Observado:** activarla y deprecarla respondieron HTTP 422 REACTIVACION_NO_PERMITIDA, «La versión 1.0 está inactiva y no puede cambiar de estado.»; la 1.0 siguió INACTIVO y cada intento dejó su evento WARNING.
- **Decisión: APROBADO.** Las comprobaciones muestran corregida en TEST INC-M07-G039-03: el estado se comprueba antes que el anexo.

## Comprobaciones API

- TC-M07-13 / deprecacion, gracia_90, auditoria: APROBADO; resultado.json.
- TC-M07-14 / repeticion, salto, retroceso: APROBADO; 422 TRANSICION_NO_PERMITIDA, estado intacto y WARNING por intento; resultado.json.
- TC-M07-14 / aviso_administrador: APROBADO; aviso nuevo 20964; resultado.json.
- TC-M07-15 / patch, put, inmutabilidad: APROBADO; 422 MODIFICACION_NO_PERMITIDA y versión intacta; resultado.json.
- TC-M07-16 / activar, deprecar, inmutable: APROBADO; 422 REACTIVACION_NO_PERMITIDA y sigue INACTIVO; resultado.json.

## Evidencias reales

resultado.json (con las líneas base, los eventos WARNING nuevos de cada intento, la bandeja antes y después del primer intento y los avisos de los siguientes), preflight.json, contexto_operacion.json, newman/newman-G039.json y newman/newman-G039.html. Ningún archivo contiene correos, contraseñas, tokens ni el secreto del sandbox.

## Incidencias de producto

Ninguna. Las comprobaciones de la V2 muestran corregidas en TEST INC-M07-G039-01, -02 y -03; Desarrollo informó las correcciones en 04bddac4 y 20b5f701.

## Observaciones

- **El antispam de avisos no actuó.** Se esperaba que el adaptador de alertas suprimiera los avisos repetidos en 10 minutos, pero el ejecutor registró un aviso nuevo o agrupado tras casi todos los rechazos: salto, PATCH, retroceso, activar y deprecar la INACTIVO (el PUT, con el mismo texto que el PATCH, no sumó ninguno). Lo mismo se vio en TC-M07-G038 V2, donde el rechazo por cupo creó el aviso 20918 dos segundos después del 20902. Para CA-27 esto significa que cada intento sí avisa al Administrador. Hipótesis por el código, sin confirmar: la comprobación del antispam (`verificar_anti_spam`) se hace con la sesión de sistema del adaptador, que quizá no ve las notificaciones de los usuarios. Si el antispam es una regla deseada, corresponde revisarlo a Desarrollo.
- **Efectos persistentes.** Por diseño del producto, los eventos WARNING de cada rechazo y los avisos críticos se guardan con una sesión propia, fuera del sandbox, y el DELETE no los deshace. El evento WARNING del retroceso conserva el estado DEPRECADO de la 3.0 que solo existió dentro del RUN. Solo se leyó la bandeja del Administrador QA.
- En `resultado.json`, el motivo del rollback aparece con «?» en lugar de las vocales acentuadas («Comparaci?n p?blica»). Es un defecto de texto del ejecutor que no afecta a ningún veredicto.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G039-V2-20261121-071349` respondió HTTP 200. La lectura posterior, sin las cabeceras del RUN, coincidió con la base: la 3.0 de nuevo ACTIVO sin fechas de retiro y el resto de versiones con su estado original. Rollback verificado. Efectos persistentes: el inicio de sesión del Administrador QA, los eventos WARNING de los rechazos y los avisos críticos del caso 14 y siguientes.

## Conclusión y acciones

El ciclo de vida del contrato cumple RF-98: la deprecación manual aplica la gracia exacta con su registro, las transiciones inválidas se rechazan sin cambiar el estado y quedan en RF-102 con severidad WARNING y aviso al Administrador, una versión ACTIVO no se modifica y responde MODIFICACION_NO_PERMITIDA, y una INACTIVO no se reactiva y responde REACTIVACION_NO_PERMITIDA. Grupo APROBADO en la V2; INC-M07-G039-01, -02 y -03 quedan corregidas en TEST, y su cierre administrativo corresponde al responsable QA.

## Historial del informe

Informe redactado por el orquestador QA (2026-11-21) a partir de resultado.json y newman/. Veredictos y evidencias sin cambios.
