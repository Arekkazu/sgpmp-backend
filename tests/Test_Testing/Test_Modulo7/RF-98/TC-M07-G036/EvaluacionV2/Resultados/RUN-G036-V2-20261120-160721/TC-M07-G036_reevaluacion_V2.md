# TC-M07-G036 — Reevaluación V2 — APROBADO

## Identificación

TC-M07-G036, que agrupa TC-M07-01 a TC-M07-05: registro de versiones del contrato AAEF. RF-98 v1.2 (incluye RFC-030), CU04; criterios CA-1, CA-2, CA-3 y CA-19; flujos alternos FA-1, FA-2 y FA-3. Versión 2 (reevaluación del grupo completo). RUN RUN-G036-V2-20261120-160721, ambiente TEST, autorización AUT-G036-V2-20261120. Versión anterior: V1 oficial RUN-G036-V1-20261118-040435. Actor: Administrador QA. Commit desplegado en TEST no consultado; la rama origin/test del repositorio contiene la corrección 5baa6e1f. Herramientas: Node v22.15.1, Newman (código 0, 0 fallos) y Cypress 14.5.4 (1 prueba, aprobada). RUN oficial, en una sola fase transaccional; 40 de 80 solicitudes.

## Motivo de la reevaluación

En la V1, el caso 04 salió RECHAZADO con severidad BAJA (INC-M07-G036-01): las listas de Mappers vacías o con un valor fuera del catálogo se rechazaban con 400 VAL_ENTRADA, y FA-3 exige MAPPERS_INVALIDOS. Desarrollo lo corrigió en 5baa6e1f (#1166): la validación de los Mappers pasó del DTO al caso de uso. La V2 repite los cinco casos con el código actual de origin/test.

## Resumen de veredictos

| Caso | V1 | V2 | Motivo |
|---|---|---|---|
| TC-M07-01 | APROBADO | APROBADO | La versión libre 6.0 se registró en PENDIENTE con todos sus datos y quedó auditada. |
| TC-M07-02 | APROBADO | APROBADO | Registrar otra vez la 3.0 (ACTIVO) se rechazó con VERSION_DUPLICADA. |
| TC-M07-03 | APROBADO | APROBADO | El anexo inexistente y el anexo en BORRADOR se rechazaron con ANEXO_MAPEO_INVALIDO; con el anexo EN_REVISION se registró la 6.1, como permite RFC-030 en TEST. |
| TC-M07-04 | RECHAZADO | APROBADO | Las dos listas de Mappers inválidas se rechazaron con MAPPERS_INVALIDOS. |
| TC-M07-05 | APROBADO | APROBADO | Desde la pantalla se registró la 6.2, que apareció en PENDIENTE, y cada versión mostró las acciones de su estado. |

## Preparación de los datos

Los datos de M07 en TEST cambiaron desde la V1 por pruebas de otros equipos: la 3.0 está ACTIVO, la 2.1 DEPRECADO y la 4.0 ya existe en PENDIENTE. Por eso la V2 no usa números fijos. El ejecutor eligió en vivo, antes de escribir:

- tres versiones libres, la 6.0, la 6.1 y la 6.2;
- la versión ACTIVO del momento, la 3.0, como duplicada;
- el anexo APROBADO de mayor id (7), el EN_REVISION (3) y el BORRADOR existente (8);
- como anexo inexistente, el id 9, comprobado en el listado.

Con dos versiones vigentes, el cupo de RF-98 5.3 está lleno; el ejecutor lo registró solo como dato. La fecha de vigencia de las altas fue el 2027-12-25, para que el proceso automático no las activara.

Todo se hizo dentro del RUN, también el registro desde la pantalla. La prueba de Cypress está construida para enviar todas sus peticiones a la API con las cabeceras del sandbox y en serie; el ensayo previo con Cypress real lo comprobó (verificar.mjs, paso 2), pero el acta del RUN no guarda las cabeceras de cada petición.

## Detalle por caso

### TC-M07-01 — Registro de una versión válida

- **Preparación:** cuerpo con la versión 6.0, MAJOR, gracia de 90 días, anexo 7 (APROBADO) y Mappers COMPRAS.
- **Esperado:** según CA-1 y CA-19, la versión queda en PENDIENTE (nunca ACTIVO), con versión, fecha de vigencia, endpoint, anexo y Mappers, y RF-102 registra el evento CONTRATO_REGISTRADO.
- **Observado:** HTTP 201 y la versión 6.0 creada con id 26, estado PENDIENTE, sin fecha de activación, endpoint `/integracion/aaef/productores/{nit}`, anexo 7, Mappers COMPRAS, tipo MAJOR y gracia 90 (G036-016). En la auditoría apareció el evento nuevo `1e09bb8c-…`: CONTRATO_REGISTRADO de la 6.0, estado PENDIENTE, actor el Administrador y fecha 2026-11-20 a las 16:07:28 UTC (G036-018; resumen guardado en `resultado.json`).
- **Decisión: APROBADO.**

### TC-M07-02 — Registro de una versión ya existente

- **Preparación:** cuerpo válido con la versión 3.0, que está ACTIVO.
- **Esperado:** según FA-1 y CA-2, rechazo VERSION_DUPLICADA sin crear contrato ni cambiar estados.
- **Observado:** HTTP 409 con `error_code` VERSION_DUPLICADA, `field` contrato_version y el mensaje «La versión 3.0 ya está registrada.» (G036-006). El listado posterior no cambió (G036-007).
- **Decisión: APROBADO.**

### TC-M07-03 — Registro sin anexo de mapeo aprobado

- **Preparación:** la versión 6.0 (aún sin registrar) con el anexo inexistente (id 9) y con el anexo en BORRADOR (id 8); y la versión 6.1 con el anexo EN_REVISION (id 3).
- **Esperado:** según FA-2 y CA-3, ANEXO_MAPEO_INVALIDO con el anexo inexistente o en borrador, sin crear la versión. Con el anexo EN_REVISION, RFC-030 permite el registro en TEST.
- **Observado:**
  - anexo inexistente: HTTP 422 con ANEXO_MAPEO_INVALIDO en `id_mapeo_anexo_aaef` y el mensaje «El contrato necesita un anexo de mapeo aprobado.» (G036-008);
  - anexo en BORRADOR: la misma respuesta (G036-010);
  - en los dos, la 6.0 no apareció en el listado;
  - anexo EN_REVISION: HTTP 201 y la 6.1 creada con id 27 en PENDIENTE (G036-019).
- **Decisión: APROBADO.**

### TC-M07-04 — Registro con Mappers no válidos

- **Preparación:** cuerpo válido de la 6.0 con el anexo 7, cambiando solo los Mappers: (a) lista vacía `[]` y (b) `["MAPPER_X"]`.
- **Esperado:** según FA-3, rechazo con MAPPERS_INVALIDOS y sin crear la versión.
- **Observado:** las dos peticiones respondieron HTTP 400 con `error_code` MAPPERS_INVALIDOS, `field` mapeadores y el mensaje «Indique transformadores válidos: compras y, si aplica, comprobante NIC 41.» (G036-012 y G036-014). En ningún caso se creó la 6.0.
- **Decisión: APROBADO.** La corrección 5baa6e1f resuelve INC-M07-G036-01: el código de error es el que exige FA-3 y el mensaje ya no es técnico ni está en inglés.

### TC-M07-05 — Registro desde la pantalla y acciones por estado

- **Preparación:** Cypress abrió Integración › Contrato y anexo con la sesión del Administrador. El login y la recuperación de la sesión se interceptaron con el token obtenido por la API y credenciales ficticias, sin un login real adicional.
- **Esperado:**
  - registrar la versión desde el formulario y verla en la tabla en PENDIENTE;
  - en la PENDIENTE, «Activar», que con el cupo lleno debe estar deshabilitado y mostrar el motivo del servidor (5.3, CA-16 y CA-29);
  - en la ACTIVO, la acción de retiro con plazo;
  - ninguna acción en la DEPRECADO ni en la INACTIVO.
- **Observado** (acta `cypress/G036-UI-05.json`):
  - el formulario registró la 6.2 con HTTP 201 y la versión apareció en la tabla;
  - «Activar» visible y deshabilitado, con el motivo del servidor;
  - «Retirar con plazo» en la 3.0 (ACTIVO);
  - ninguna acción en la 2.1 (DEPRECADO) ni en las INACTIVO.

  La captura de la aplicación muestra la tabla con «Activar» deshabilitado en las PENDIENTE y el motivo «Ya hay 2 versiones vigentes. Retire primero la versión 2.1 antes de activar una nueva.», y «Retirar con plazo» en la 3.0. La captura no alcanza la fila de la 6.2; su presencia consta en el acta.
- **Decisión: APROBADO.**

## Comprobaciones API y UI

- TC-M07-01 / registro_version_libre, auditoria: APROBADO; resultado.json.
- TC-M07-02 / duplicado: APROBADO; 409 VERSION_DUPLICADA; resultado.json.
- TC-M07-03 / anexo_inexistente, anexo_borrador: APROBADO; 422 ANEXO_MAPEO_INVALIDO; resultado.json.
- TC-M07-03 / anexo_revision: APROBADO; 201 PENDIENTE; resultado.json.
- TC-M07-04 / mappers_vacios, mapper_invalido: APROBADO; 400 MAPPERS_INVALIDOS; resultado.json.
- TC-M07-05 / registro_ui_version_libre, tabla_acciones: APROBADO; acta y captura de Cypress.

## Evidencias reales

resultado.json (con el resumen del evento de auditoría comparado), preflight.json, contexto_operacion.json, newman/newman-G036.json, newman/newman-G036.html, cypress/G036-UI-05.json, cypress/G036-cypress.json, cypress/G036-cypress-salida.log (saneado) y cypress/screenshots/g036.cy.js/G036-UI-05.png (solo la aplicación). Sin vídeo. Ningún archivo contiene correos, contraseñas, tokens ni el secreto del sandbox.

## Incidencias de producto

Ninguna. INC-M07-G036-01 (V1) queda corregida por 5baa6e1f.

## Observaciones

- En el acta de Cypress, el hito `refresh_interceptado` aparece como «[RESERVADO]», porque el saneamiento oculta cualquier clave que contenga «refresh». No afecta al veredicto: la petición de refresh interceptada consta en el acta con su respuesta local.
- La V2 cubre la RFC-030 en TEST como la V1: el anexo EN_REVISION se acepta en TEST, y su rechazo en producción no se puede comprobar desde TEST.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G036-V2-20261120-160721` respondió HTTP 200, después de terminar Cypress. El ejecutor comparó las lecturas posteriores, sin las cabeceras del RUN, con la base y coincidieron: las versiones 6.0, 6.1 y 6.2 ya no existen. Rollback verificado. El único efecto persistente es el inicio de sesión del Administrador QA antes del RUN.

## Conclusión y acciones

El registro de versiones del contrato cumple RF-98 en sus cinco casos, y el caso 04 ya responde MAPPERS_INVALIDOS como pide FA-3. Grupo APROBADO en la V2; INC-M07-G036-01 queda cerrada.
## Historial del informe

Informe redactado por el orquestador QA (2026-11-20) a partir de resultado.json, newman/ y cypress/. Veredictos y evidencias sin cambios.
Corrección (2026-11-20): precisadas la referencia al commit (rama origin/test, no el despliegue) y la evidencia de las cabeceras del sandbox en Cypress (comprobadas en el ensayo, no guardadas en el acta); veredictos y evidencias sin cambios.
