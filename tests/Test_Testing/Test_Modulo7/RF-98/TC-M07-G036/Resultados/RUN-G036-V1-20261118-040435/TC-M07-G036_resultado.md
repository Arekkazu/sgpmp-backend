# TC-M07-G036 — RECHAZADO

## Identificación

TC-M07-G036, que agrupa TC-M07-01 a TC-M07-05: registro de versiones del contrato AAEF. RF-98 v1.2 (incluye RFC-030), CU04; criterios CA-1, CA-2, CA-3 y CA-19; flujos alternos FA-1, FA-2 y FA-3. Versión 1, intento 2. RUN RUN-G036-V1-20261118-040435, ambiente TEST, autorización AUT-G036-V1-R2-20261117. Actor: Administrador QA. Commit de TEST no consultado. Herramientas: Node v22.15.1, Newman (código 0, 0 fallos) y Cypress 14.5.4 (código 0, 1 prueba). RUN oficial; 27 de 80 solicitudes.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M07-01 | APROBADO | La versión 4.0 se registró en PENDIENTE con todos sus datos y quedó auditada. |
| TC-M07-02 | APROBADO | Registrar otra vez la 2.1 se rechazó con VERSION_DUPLICADA y nada cambió. |
| TC-M07-03 | APROBADO | El anexo inexistente y el anexo en borrador se rechazaron; el anexo en revisión se aceptó, como permite RFC-030 en TEST. |
| TC-M07-04 | RECHAZADO | Las listas de Mappers inválidas se rechazan, pero con un error genérico de validación y no con MAPPERS_INVALIDOS. |
| TC-M07-05 | APROBADO | Desde la pantalla se registró la 4.2 y cada versión mostró las acciones que le corresponden según su estado. |

## Detalle por caso

### TC-M07-01 — Registro de una versión válida

- **Preparación:** antes de escribir nada, el ejecutor leyó en TEST los anexos y las versiones del contrato. Eligió el anexo 2 (ANEXO-AAEF-V2.0), que está APROBADO, y comprobó que la versión 4.0 no existía. La fecha de vigencia se calculó a 400 días de hoy (2027-12-22) para que el proceso automático no la activara durante la prueba.
- **Esperado:** según CA-1 y CA-19, la versión debe quedar en PENDIENTE (nunca ACTIVO) y contener versión, fecha de vigencia, endpoint, anexo y Mappers. El listado debe mostrarla y RF-102 debe registrar el evento CONTRATO_REGISTRADO.
- **Observado:** el registro de la 4.0 (tipo MAJOR, Mappers COMPRAS, período de gracia 90 días) respondió HTTP 201 y creó la versión con id 7. La respuesta trae estado PENDIENTE, sin fecha de activación, y todos los campos exigidos: versión 4.0, vigencia 2027-12-22, endpoint `/integracion/aaef/productores/{nit}`, anexo 2, Mappers COMPRAS, tipo MAJOR y gracia 90. Al consultar el listado, la 4.0 aparece en PENDIENTE con el mismo id. En la auditoría apareció un evento CONTRATO_REGISTRADO nuevo para la versión 4.0, con estado PENDIENTE en el detalle, el usuario del Administrador QA y su fecha. El RUN guardó la comprobación, no el contenido del evento; por eso este informe no cita su id.
- **Decisión: APROBADO.** La versión se creó como exige el requisito: en PENDIENTE, completa y auditada.

### TC-M07-02 — Registro de una versión ya existente

- **Preparación:** como versión duplicada se usó la que estaba ACTIVO en TEST, la 2.1. La matriz mencionaba la 3.0, pero esa versión no existe en TEST. El resto del cuerpo era válido (anexo 2, COMPRAS, MAJOR y gracia 90), para que el único motivo de rechazo posible fuera el duplicado.
- **Esperado:** según FA-1 y CA-2, el rechazo debe ser VERSION_DUPLICADA, sin crear contrato y sin cambiar el estado de las versiones existentes.
- **Observado:** HTTP 409 con `error_code` VERSION_DUPLICADA en el campo `contrato_version` y el mensaje «La versión 2.1 ya está registrada.». El listado posterior tenía los mismos ids y estados que antes del intento.
- **Decisión: APROBADO.** El sistema detectó el duplicado con el código correcto y no alteró nada.

### TC-M07-03 — Registro sin anexo de mapeo aprobado

- **Preparación:** se probaron tres variantes, cada una con la versión 4.0 (aún sin registrar) y el resto del cuerpo válido:
  - (a) el id de anexo 999999, que el ejecutor comprobó que no existe;
  - (b) un anexo en BORRADOR, que no había en TEST: el ejecutor lo creó dentro del RUN (QA-G036-BORRADOR, id 5) y el rollback lo eliminó al final;
  - (c) el anexo 3 (QA-M07-ANEXO-2.2), que está EN_REVISION, esta vez con la versión 4.1.
- **Esperado:** según FA-2 y CA-3, en (a) y (b) el rechazo debe ser ANEXO_MAPEO_INVALIDO sin crear la versión. Para (c), RF-98 v1.2 (RFC-030) admite en TEST un anexo EN_REVISION, así que se espera el registro aceptado en PENDIENTE.
- **Observado:** (a) y (b) respondieron HTTP 422 con ANEXO_MAPEO_INVALIDO en el campo `id_mapeo_anexo_aaef` y el mensaje «El contrato necesita un anexo de mapeo aprobado.»; tras cada uno, el listado seguía sin la 4.0. (c) respondió HTTP 201 y creó la 4.1 (id 8) en PENDIENTE.
- **Decisión: APROBADO.** El sistema rechaza los anexos que no sirven y acepta el anexo en revisión, como permite RFC-030 en TEST. En producción ese mismo registro debería rechazarse, pero desde TEST no se puede comprobar (ver Observaciones).

### TC-M07-04 — Registro con Mappers no válidos

- **Preparación:** cuerpo válido para la versión 4.0 con el anexo APROBADO 2, cambiando solo la lista de Mappers: (a) una lista vacía `[]` y (b) un Mapper que no existe, `[MAPPER_X]`.
- **Esperado:** según FA-3, ambas deben rechazarse con el error de negocio MAPPERS_INVALIDOS y sin crear la versión.
- **Observado:** las dos peticiones se rechazaron y en ningún caso se creó la 4.0, pero no con el error esperado:
  - (a) devolvió HTTP 400 con `error_code` VAL_ENTRADA («Errores de validacion en la solicitud») y, en el campo `mapeadores`, el mensaje técnico en inglés «List should have at least 1 item after validation, not 0»;
  - (b) devolvió el mismo HTTP 400 VAL_ENTRADA, en el campo `mapeadores.0`, con «El valor ingresado no es una de las opciones permitidas.».
- **Decisión: RECHAZADO** por INC-M07-G036-01. El sistema impide el registro inválido, pero no responde con el código que exige FA-3. Un cliente que espere MAPPERS_INVALIDOS no reconoce el motivo, y en (a) recibe además un mensaje en inglés.

### TC-M07-05 — Registro desde la pantalla Integración › Contrato y anexo

- **Preparación:** Cypress abrió el frontal de TEST como Administrador QA. El login se resolvió dentro de Cypress con el token que el ejecutor ya había obtenido, sin un segundo inicio de sesión. Luego fue a `/integracion/contrato`. Las versiones que se iban a revisar se eligieron en vivo según su estado: 2.1 ACTIVO, 2.0 DEPRECADO y 1.0 INACTIVO.
- **Esperado:** registrar la 4.2 desde el formulario «Registrar versión» (MAJOR, vigencia futura, anexo APROBADO y plazo de retiro de 90 días) y verla en la tabla en PENDIENTE con su tipo de cambio, sus Mappers y su anexo. Además, en una versión PENDIENTE debe ofrecerse «Activar»; en una ACTIVO, «Retirar con plazo»; y en DEPRECADO e INACTIVO, ninguna acción.
- **Observado:** el frontal cargó y la pantalla del contrato mostró la tabla de versiones. Se abrió el formulario, se rellenó y se guardó; la petición de registro respondió HTTP 201. La 4.2 apareció en la tabla como «Pendiente», con «Cambio mayor (retira la anterior con plazo)», «Facturas de compra» y el anexo ANEXO-AAEF-V2.0, y con el botón «Activar». La fila de la 2.1 («Activa») ofrecía «Retirar con plazo»; las de la 2.0 («En retiro») y la 1.0 («Retirada») no mostraban ningún botón. Una lectura posterior por API confirmó la 4.2 en PENDIENTE. Hay captura de pantalla y vídeo. El acta marca `video=false` porque se escribió antes de que Cypress terminara de guardar el vídeo, pero el archivo está en el RUN.
- **Decisión: APROBADO.** El registro desde la pantalla funciona y las acciones de cada fila corresponden a su estado.

## Comprobaciones API y UI

- TC-M07-01 / API / registro_v4_0: APROBADO; 201, PENDIENTE y campos completos; resultado.json.
- TC-M07-01 / API / auditoria: APROBADO; CONTRATO_REGISTRADO nuevo para la 4.0; resultado.json.
- TC-M07-02 / API / duplicado: APROBADO; 409 VERSION_DUPLICADA sin cambios; resultado.json.
- TC-M07-03 / API / anexo_inexistente: APROBADO; 422 ANEXO_MAPEO_INVALIDO; resultado.json.
- TC-M07-03 / API / anexo_borrador: APROBADO; 422 ANEXO_MAPEO_INVALIDO; resultado.json.
- TC-M07-03 / API / anexo_revision: APROBADO; 201 PENDIENTE (RFC-030); resultado.json.
- TC-M07-04 / API / mappers_vacios: RECHAZADO; 400 VAL_ENTRADA en lugar de MAPPERS_INVALIDOS; resultado.json.
- TC-M07-04 / API / mapper_invalido: RECHAZADO; 400 VAL_ENTRADA en lugar de MAPPERS_INVALIDOS; resultado.json.
- TC-M07-05 / API / registro_v4_2: APROBADO; 4.2 en PENDIENTE por API; resultado.json.
- TC-M07-05 / UI / tabla_acciones: APROBADO; registro y acciones por estado; cypress/G036-UI-05.json.

## Evidencias reales

resultado.json, preflight.json, contexto_operacion.json, newman/newman-G036.json, newman/newman-G036.html, cypress/G036-UI-05.json, cypress/G036-cypress.json, cypress/G036-cypress-salida.log, cypress/screenshots/g036.cy.js/G036-UI-05.png y cypress/videos/g036.cy.js.mp4.

## Incidencias de producto

### INC-M07-G036-01 — El registro de una versión con Mappers vacíos o inexistentes devuelve VAL_ENTRADA en lugar de MAPPERS_INVALIDOS

**Requisito:** RF-98, FA-3 «Mappers no disponibles o inconsistentes»: si los Mappers asociados no existen, no están operativos o no corresponden al estándar AAEF, el registro se rechaza con el error MAPPERS_INVALIDOS. La matriz (TC-M07-04) aplica esa regla a dos variantes: lista vacía y Mapper inexistente.

**Pasos para reproducir:** como Administrador, enviar `POST /integracion/contratos` con un cuerpo válido (versión no registrada, tipo MAJOR, vigencia futura, anexo APROBADO y gracia 90) y `mapeadores: []`. Repetir con `mapeadores: ["MAPPER_X"]`. Después de cada intento, consultar `GET /integracion/contratos`.

**Esperado:** rechazo con `error_code` MAPPERS_INVALIDOS en el campo `mapeadores` y ninguna versión creada.

**Obtenido:** en los dos casos, HTTP 400 con `error_code` VAL_ENTRADA y el mensaje «Errores de validacion en la solicitud». Con la lista vacía, el detalle en `mapeadores` es «List should have at least 1 item after validation, not 0», en inglés. Con MAPPER_X, el detalle en `mapeadores.0` es «El valor ingresado no es una de las opciones permitidas.». En ninguno se creó la versión.

**Causa probable (hipótesis a partir del código, sin confirmar en TEST):** la regla de FA-3 existe en el caso de uso, pero estas peticiones no llegan a ejecutarla porque la validación del cuerpo las rechaza antes.
- El DTO de entrada define `mapeadores: list[Mapper] = Field(min_length=1)` con `Mapper = Literal["COMPRAS", "COMPROBANTE_NIC41"]` (`src/accounting_integration/infrastructure/dto/m07_dto.py:16` y `:100`).
- FastAPI valida el cuerpo contra ese DTO antes de llamar al router (`m07_router.py:219-223`). Una lista vacía incumple `min_length=1` y un valor fuera del `Literal` no es una opción válida, así que Pydantic lanza `RequestValidationError`.
- El manejador global convierte esa excepción en HTTP 400 VAL_ENTRADA (`src/shared/error_handlers.py:306-332`; el 400 sale de `_codigo_validacion`, `:194-201`).
- La comprobación que devuelve MAPPERS_INVALIDOS está en `GestionarContratosUseCase.registrar` (`src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py:79-81`) y nunca se alcanza con estas entradas.
- El mensaje en inglés de la lista vacía apunta en la misma dirección: el manejador no tiene traducción para el error de Pydantic `too_short` y devuelve el texto original. `_mensaje_legible` usa el texto de Pydantic cuando el tipo de error no está en `_MENSAJES_PYDANTIC_POR_TIPO` (`error_handlers.py:303`), y ese diccionario sí traduce `literal_error` (`:273`) pero no `too_short`. Por eso el caso (b) llega en español y el (a) en inglés.
- Una posible corrección, que decide Desarrollo, sería que el DTO acepte la lista sin esas restricciones y deje la validación al caso de uso, o que el manejador traduzca los errores del campo `mapeadores` de esta ruta a MAPPERS_INVALIDOS.

**Impacto y severidad:** BAJA. No se pueden registrar contratos con Mappers inválidos, así que la integridad del dato está protegida. Lo que falla es el contrato de error: un consumidor o la propia pantalla no reciben el código de negocio que define el requisito, y en la lista vacía el mensaje llega en inglés. Certeza de la discrepancia: CONFIRMADA en TEST. Causa raíz: hipótesis no verificada en la versión desplegada.

**Primera atención:** Desarrollo, porque la discrepancia está en la respuesta de la API pública de M07.

**Evidencias:** `resultado.json`, solicitudes G036-013 (lista vacía) y G036-015 (MAPPER_X) con sus cuerpos de error, y G036-014 y G036-016 (listados sin la 4.0); `newman/newman-G036.json`.

## Observaciones

- **TC-M07-03 (c):** en TEST el registro con un anexo EN_REVISION se acepta porque RF-98 v1.2 (RFC-030) lo permite fuera de producción. El código lo implementa en `AnexoMapeo.usable()` (`src/accounting_integration/domain/entities/contrato.py:37-40`), que exige APROBADO solo cuando el entorno es PROD. No se pudo comprobar que en producción se rechace. No es una incidencia.
- La matriz citaba la 3.0 como versión ya registrada, pero en TEST las versiones son 1.0 INACTIVO, 2.0 DEPRECADO, 2.1 ACTIVO y 2.2 PENDIENTE. Para el duplicado se usó la 2.1, y el resultado esperado no cambia.

## Problemas técnicos y análisis de causas

Ninguno en este RUN. Antes hubo un intento técnico, RUN-G036-V1-20261118-034446, que ya fue eliminado con autorización. En él Cypress no pudo abrir la pantalla porque el ejecutor usaba la dirección del frontal con `www`, que da 404. Se corrigió en ORD-G036-011 y no afecta a ningún veredicto de este informe.

## Cierre y rollback

Al terminar se envió `DELETE /test-control/runs/RUN-G036-V1-20261118-040435`, que respondió HTTP 200. Las lecturas posteriores, hechas sin las cabeceras del RUN, mostraron los mismos ids y estados de versiones y anexos que antes de empezar, sin las versiones 4.0, 4.1 y 4.2 ni el anexo QA-G036-BORRADOR. Rollback verificado. El único efecto persistente fue el inicio de sesión del Administrador QA anterior al RUN.

## Conclusión y acciones

El registro de versiones del contrato AAEF cumple lo esencial: crea las versiones en PENDIENTE con todos sus datos y las audita; rechaza duplicados y anexos no válidos; y la pantalla permite registrar y muestra las acciones correctas por estado. Lo único que falla es el código de error cuando los Mappers no son válidos (INC-M07-G036-01, BAJA). Acciones: derivar INC-M07-G036-01 a Desarrollo y, cuando informen la corrección, reevaluar el grupo completo con una nueva autorización.

## Historial del informe

- **Enmienda de saneado (2026-11-17):** por una fuga de credencial (ORD-G036-013), se enmascaró `solicitudes[*].cuerpo_solicitud.contrasena` del `POST /sesiones/` en `resultado.json` como `[RESERVADO]`. No cambia ningún veredicto ni dato funcional. SHA-256 de `resultado.json`: antes `546c6bc60ffec10173088eae2a06cf0af90f32216b807207a7b52d779dea0f39`; después `9c2b369bd070e72d9b595127876d0fe9743924f6bbe9ff533a12288bea7d634d`.
- **Actualización del informe (2026-11-18):** se reescribió con el formato de M06: detalle explicativo por caso e incidencia con causa probable. Los veredictos y `resultado.json` no cambian (SHA-256 `9c2b369bd070e72d9b595127876d0fe9743924f6bbe9ff533a12288bea7d634d`).
