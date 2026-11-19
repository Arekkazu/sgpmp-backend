# TC-M07-G041 — APROBADO

## Identificación

TC-M07-G041, que agrupa TC-M07-22 y TC-M07-23: control de acceso a la gestión de contratos AAEF y trazabilidad de sus operaciones en RF-102. RF-98 v1.2; restricciones 5.13 y 5.14; flujo FA-4; criterios CA-17 y CA-18; RNF-98.7. La fila de la matriz se corrigió el 2026-11-19 para usar las versiones reales de TEST y verificar la activación y la inactivación sobre eventos reales. Versión 1, intento 3. RUN RUN-G041-V1-20261119-064005, ambiente TEST, autorización AUT-G041-V1-R3-20261119. Actores: Administrador QA y Contador QA. Commit de TEST no consultado. Herramientas: Node v22.15.1, Newman (código 0, 0 fallos) y Cypress 14.5.4 (1 prueba, aprobada). RUN oficial, en una sola fase transaccional; 39 de 60 solicitudes.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M07-22 | APROBADO | El Contador recibió 403 ACCESO_DENEGADO al registrar, activar y deprecar, ningún contrato cambió, y en pantalla no ve las acciones de gestión. |
| TC-M07-23 | APROBADO | El registro y la deprecación hechos en el RUN, la activación real de la 3.0 y la inactivación real de la 2.0 tienen su evento en RF-102 con tipo, versión, estado resultante, responsable (el usuario, o el actor SISTEMA en la inactivación automática) y fecha. |

## Preparación de los datos

- **Actores:** el Contador QA es una cuenta activa con rol Contador, que sobre `contratos_aaef` solo tiene lectura (R) y la acción interna sobre anexos (E), sin crear (C) ni actualizar (U). El preflight lo comprobó en vivo con su propio token. El Administrador QA tiene C, R y U sobre los contratos y lectura de la auditoría.
- **Versiones del momento**, elegidas en vivo: ACTIVO la 3.0, PENDIENTE de menor id la 2.2, INACTIVO de menor id la 1.0. Como versiones libres se tomaron la 6.0 (para el intento del Contador) y la 6.1 (para el Administrador).
- **Por qué no se activó ninguna versión en el RUN:** ya hay dos versiones vigentes (3.0 ACTIVO y 2.1 DEPRECADO), así que el límite de RF-98 5.3 impide cualquier activación. Además, la inactivación solo la hace el proceso automático al terminar la gracia. Por eso la activación y la inactivación se verificaron sobre los eventos reales ya registrados en TEST: la activación de la 3.0 (2026-11-18 13:53 UTC) y la inactivación de la 2.0 por el proceso automático (2026-11-18 08:29:22 UTC).
- **Eventos sembrados:** en la auditoría hay eventos de esos tipos sembrados por otro equipo, con fechas retroactivas y sin el campo de estado. El ejecutor solo usó eventos con estado; excluyó 7 sembrados.

## Detalle por caso

### TC-M07-22 — Usuario sin rol Administrador intenta gestionar contratos

- **Preparación:** el Contador QA inició sesión por la API antes de abrir el RUN. Dentro del RUN se leyó el listado de contratos antes y después de cada intento, con la cuenta del Administrador.
- **Esperado:** según 5.13, FA-4 y CA-17, solo el Administrador puede registrar, activar y deprecar contratos; cualquier otro rol recibe el error ACCESO_DENEGADO y ningún contrato cambia. En pantalla, el Contador no debe ver las acciones Registrar versión, Activar ni Deprecar.
- **Observado en la API:**
  - Registrar la versión 6.0: HTTP 403 con `error_code` ACCESO_DENEGADO y el mensaje «Acceso denegado. Su rol no tiene permisos para realizar esta operación.» (G041-012), que es el mensaje genérico de `shared/rbac.py:186-191`.
  - Activar la 2.2, PENDIENTE: HTTP 403 con ACCESO_DENEGADO y el mismo mensaje (G041-015).
  - Deprecar la 3.0, ACTIVO: HTTP 403 con ACCESO_DENEGADO y el mismo mensaje (G041-018).
  - Después de cada intento, el listado de contratos era idéntico al anterior. Las tres peticiones llevan el actor «contador» en la evidencia.
- **Observado en pantalla (Cypress, después del cierre del RUN, solo lectura):** con la sesión del Contador, la pestaña Integración › «Contrato y anexo» cargó con el listado de versiones. En la sección de versiones no aparecen «Registrar versión», «Activar» ni «Retirar con plazo», que es el texto del botón de deprecar en la pantalla (`integracion.json`). Tampoco aparece «Registrar anexo». La ausencia de los botones consta en el acta `cypress/G041-UI-22.json`, que inspeccionó los botones de la sección. La captura muestra la pestaña cargada con la sesión del Contador, pero solo alcanza a mostrar la parte superior (los anexos), no la sección de versiones.
- **Decisión: APROBADO.**

### TC-M07-23 — Trazabilidad de las operaciones en RF-102

- **Preparación:** antes de las operaciones se tomó como línea base la auditoría filtrada por cada tipo de evento (G041-007 a G041-010).
- **Esperado:** según 5.14, CA-18 y RNF-98.7, cada cambio de estado (registro, activación, deprecación e inactivación) deja un evento en RF-102 con la versión, el estado resultante, el usuario y la marca de tiempo, y con esos eventos se reconstruye el historial de cada versión.
- **Observado:**
  - **Registro**, dentro del RUN: el Administrador registró la 6.1 (HTTP 201, G041-020). En la auditoría apareció un CONTRATO_REGISTRADO nuevo de la 6.1 con estado resultante PENDIENTE, usuario no nulo y fecha dentro del RUN (G041-022).
  - **Deprecación**, dentro del RUN: el Administrador deprecó la 3.0 con 90 días (HTTP 200, G041-023). Apareció un CONTRATO_DEPRECADO nuevo de la 3.0 con estado resultante DEPRECADO, usuario no nulo y fecha dentro del RUN (G041-025).
  - **Activación** (evento real): según el ejecutor, el CONTRATO_ACTIVADO más reciente de la 3.0 con estado tiene estado resultante ACTIVO, usuario no nulo y una fecha a menos de 5 s de la fecha de activación del listado. La consulta de solo lectura a la BD del 2026-11-19 a las 03:36 UTC, hecha antes del RUN y que no forma parte de sus evidencias, identifica ese evento como el `db8ece27-…`, del 2026-11-18 a las 13:53:13 UTC.
  - **Inactivación** (evento real): según el ejecutor, el CONTRATO_INACTIVADO de la 2.0 tiene estado resultante INACTIVO, actor SISTEMA sin usuario (el proceso automático, responsable de la inactivación según 5.9) y una fecha a menos de 5 s de su fecha de inactivación. La misma consulta a la BD lo identifica como el `7bc7dfbc-…`, del 2026-11-18 a las 08:29:22 UTC.
  - **Historial:** el estado del último evento real de cada versión coincide con su estado en el listado.
- **Decisión: APROBADO**, con la observación **OBS-G041-01** sobre la evidencia guardada.

## Comprobaciones API y UI

- TC-M07-22 / registro_denegado, activar_denegado, deprecar_denegado: APROBADO; 403 ACCESO_DENEGADO sin cambios; resultado.json.
- TC-M07-22 / acciones_ocultas (UI): APROBADO; cypress/G041-UI-22.json y captura.
- TC-M07-23 / registro_auditado, deprecacion_auditada: APROBADO; resultado.json.
- TC-M07-23 / activacion_historica, inactivacion_historica: APROBADO; resultado.json y lectura en la BD.
- TC-M07-23 / historial: APROBADO; resultado.json.

## Evidencias reales

resultado.json, preflight.json, contexto_operacion.json, newman/newman-G041.json, newman/newman-G041.html, cypress/G041-UI-22.json (acta de la pantalla), cypress/G041-cypress.json, cypress/G041-cypress-salida.log (saneado) y cypress/screenshots/g041.cy.js/G041-UI-22.png (solo la aplicación). Sin vídeo, por privacidad. Ningún archivo contiene correos, contraseñas ni tokens.

## Incidencias de producto

Ninguna.

## Observaciones

- **OBS-G041-01 (evidencia, QA):** `resultado.json` guarda el veredicto de cada comprobación del 23 y las peticiones, pero no los campos de los eventos de auditoría que el ejecutor comparó. Newman guarda su lectura de auditoría redactada. Los dos eventos reales (activación de la 3.0 e inactivación de la 2.0) se identificaron además en una consulta de solo lectura a la BD hecha antes del RUN, que no forma parte de sus evidencias. Los del registro y la deprecación se deshicieron con el rollback. En el próximo cambio del ejecutor se guardará un resumen de cada evento comprobado (id, tipo, versión, estado y fecha, sin correos).
- **Eventos sembrados:** la auditoría de TEST contiene eventos de contrato sembrados por otro equipo, con fechas retroactivas y sin estado resultante. No son del producto, pero ensucian el historial que pide RNF-98.7; conviene que su dueño los retire.
- **Pantalla:** la captura muestra la etiqueta de estado del anexo obsoleto como «estado.OBSOLETO», una clave de traducción sin texto. No afecta a este grupo; se anota para el frontend.
- **Intentos anteriores:** los intentos 1 y 2 fueron técnicos por fallos de QA en Cypress; la parte de API fue correcta en ambos. En el 2, la captura automática del fallo mostró el token de sesión del Contador. El responsable QA invalidó esa sesión y borró los dos RUN, y la prueba se corrigió para no grabar vídeo ni el panel de Cypress.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G041-V1-20261119-064005` respondió HTTP 200. El ejecutor comparó la lectura posterior de los contratos con la base por su firma completa y coincidió, así que la 6.1 ya no existe y la 3.0 vuelve a su estado inicial. `resultado.json` guarda el resultado de esa comparación, no las dos lecturas. Rollback verificado. Fuera del sandbox quedan los inicios de sesión del Administrador QA y del Contador QA. Cypress solo leyó, con credenciales ficticias y el token del Contador, y bloqueó cualquier escritura.

## Conclusión y acciones

El control de acceso y la trazabilidad de los contratos cumplen RF-98: un usuario sin rol Administrador no puede registrar, activar ni deprecar, ni ve esas acciones en pantalla, y cada operación queda registrada en RF-102 con los datos que pide CA-18. Grupo APROBADO. Acciones: mejorar la evidencia del 23 en el ejecutor (OBS-G041-01) y avisar al dueño de los eventos sembrados. Pendiente de QA: borrar la fixture 3.9 (id 13) al cerrar M07.

## Historial del informe

Informe redactado por el orquestador QA (2026-11-19) a partir de resultado.json, newman/ y cypress/; la versión generada por el ejecutor se conserva en SIGAB_QA_ORQUESTACION/estado/historial_informes/M07/TC-M07-G041/. Veredictos y evidencias sin cambios.
Traslado (2026-11-19): la copia del informe del ejecutor se movió a SIGAB_QA_ORQUESTACION por decisión del responsable QA; veredictos y evidencias sin cambios.
Corrección (2026-11-19): ajustadas las afirmaciones sobre el mensaje de los 403, la captura, el origen de los identificadores de los eventos reales y el alcance del rollback, según la revisión de evidencias; veredictos y evidencias sin cambios.
Corrección (2026-11-19): retirada la mención a un carácter de reemplazo en el mensaje de los 403 (resultado.json lo conserva bien) y precisado el responsable de la inactivación en el resumen; veredictos y evidencias sin cambios.
