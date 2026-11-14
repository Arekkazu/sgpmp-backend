# TC-M06-G43 — reevaluación V2 oficial - RECHAZADO

G43 | RF-87 v1.2 (026); RF-87 (024, 025, 027) | TC-M06-024 a TC-M06-027 | V2 | RUN-G43-V2-20261113-074459 | TEST | autorización AUT-G43-V2-R8-20261113. Commit desplegado informado: 453277e4, sin verificación en este RUN. Esta enmienda es solo documental.

## Resumen

| Caso | Veredicto del informe | Fundamento |
| --- | --- | --- |
| TC-M06-024 | RECHAZADO | INC-M06-G43-05: precio nuevo congelado durante el cierre. |
| TC-M06-025 | APROBADO | Advertencia, cancelación y exclusión conformes. |
| TC-M06-026 | RECHAZADO | INC-M06-G43-03: no se acreditó la estimación de 1644. |
| TC-M06-027 | APROBADO | Lista y autorización visibles; ERROR_QA del comparador. |

[resultado.json](resultado.json) conserva el estado automatizado RECHAZADO de 027; la decisión enmendada usa la evidencia del mismo RUN. El único veredicto que cambia en el informe es 027.

## Detalle por caso

### TC-M06-024

**Qué se verifica.** La matriz exige que la revaluación use el precio capturado al inicio del cierre, con el mismo identificador y fecha de vigencia, aunque se registre otro precio durante la pausa EN_CIERRE.

**Preparación.** Período 8 y especie 39, categoría PESO_KG, fuente MERCADO_ACTIVO. [resultado.json](resultado.json) identifica el precio inicial 18, vigente desde 2026-11-07; [preflight.json](preflight.json) registra la autorización y la ausencia de barreras.

**Qué se hizo.** G43-032 y G43-041 comprobaron la pausa mediante HTTP 409. Durante ella, G43-044 registró por POST /finanzas/precios el precio nuevo 900, vigente desde 2026-11-13 (HTTP 201). G43-046 autorizó POST /finanzas/periodos/8/cierre (HTTP 200).

**Qué se esperaba.** Cierre CERRADO con el precio inicial 18 y su fecha 2026-11-07 congelados.

**Qué se observó.** El cierre quedó CERRADO, pero el precio congelado fue 900, fecha 2026-11-13; coincide con el registrado durante la pausa. Lo acredita resultado.json.precios.

**Por qué se decide así.** La pausa y el cierre autorizado cumplieron; el identificador y la fecha del precio congelado incumplen el criterio de la matriz. La causa raíz técnica no está demostrada.

**Decisión.** RECHAZADO; INC-M06-G43-05, Desarrollo, ALTA.

### TC-M06-025

**Qué se verifica.** La matriz exige advertir el número, los activos y las especies sin precio vigente; cancelar sin cambios ante la negativa y cerrar excluyéndolos cuando se autorice.

**Preparación.** Período 266 ABIERTO, con el activo 1644 sin precio vigente y el 1643 procesable; constan en [resultado.json](resultado.json).

**Qué se hizo.** G43-054 intentó cerrar sin decisión (HTTP 409); G43-057 canceló (HTTP 200); G43-063 volvió a comprobar la falta de autorización (HTTP 409), y G43-066 cerró con exclusión (HTTP 200). El panel tuvo una prueba UI: [acta 025](cypress/025/G43-UI-025.json) y [captura de tabla](cypress/025/screenshots/g43.cy.js/G43-UI-025-tabla-1.png).

**Qué se esperaba.** Advertencia por un activo con identificación y especie; cancelación que dejara el período ABIERTO e intacto; autorización que excluyera al 1644, procesara al 1643 y completara el cierre. La UI debía permitir la decisión por activo.

**Qué se observó.** La advertencia identificó a Lote 1644, Caprino Aislado Precios. La cancelación dejó el período ABIERTO e intacto. El cierre autorizado excluyó al 1644 y procesó un activo. La UI mostró las alternativas de excluir y estimar para Lote 1644; su acta fue APROBADA.

**Por qué se decide así.** Las respuestas API y la comprobación UI ejecutada satisfacen las decisiones exigidas.

**Decisión.** APROBADO.

### TC-M06-026

**Qué se verifica.** La matriz exige decisión por activo sin precio vigente. RF-87 v1.2 CA-5 permite estimarlo con el último precio conocido; RF-83 v1.2 CA-5 y CA-7 exigen marcar la medición como estimada y alertar al Contador. RF-86 CA-14 exime el registro de variación y la alerta de error cuando el monto es cero, sin exceptuar la estimación ni su alerta.

**Preparación.** En el período 523, el activo 1644 carecía de precio vigente y tenía como último precio conocido el registro 492. El 1643 permitía comprobar la estimación no aplicable.

**Qué se hizo.** G43-078 intentó estimar al 1643 (HTTP 400 ACTIVO_ESTIMADO_NO_APLICA). G43-081 intentó cerrar sin decisión (HTTP 409 EXCLUSION_REQUIERE_AUTORIZACION; período EN_CIERRE). G43-085 cerró el período 523 con activos_estimados = [1644] en la solicitud (HTTP 200). Se consultaron cálculos, auditoría, respuesta y alertas. El panel tuvo una prueba UI: [acta 026](cypress/026/G43-UI-026.json) y [captura propia](cypress/026/screenshots/g43.cy.js/G43-UI-026-tabla-1.png).

**Qué se esperaba.** Rechazo de la estimación del 1643; cierre detenido sin decisión; medición del 1644 con el precio 492, tiene_valor_estimado = true y alerta al Contador. Una variación nueva de monto cero no era exigible. La UI debía permitir excluir o estimar por activo.

**Qué se observó.** Los HTTP 400 y 409 cumplieron. G43-085 devolvió HTTP 200 y procesó dos activos, pero la respuesta registró activos_estimados = null. Para el 1644 no hubo cálculo estimado ni marca acreditada; la única auditoría fue MEDICION_SIN_VARIACION, id_referencia 121, precio_usado null. No hubo alerta de estimación ni nuevo registro de COSTO. La prueba UI fue APROBADA.

**Por qué se decide así.** La variación cero explica la ausencia de variación nueva y de alerta de error; no elimina la obligación de identificar la estimación y avisar al Contador. La falta de ambas se comprobó en las vías públicas del RUN; la causa raíz sigue sin determinarse.

**Decisión.** RECHAZADO; INC-M06-G43-03, Desarrollo, MEDIA.

### TC-M06-027

**Qué se verifica.** La matriz exige presentar, antes de continuar, la lista de asientos y activos con el eslabón incompleto y pedir autorización; la negativa cancela sin cambios y la autorización deja las líneas pendientes para el período siguiente.

**Preparación.** Período 8 ABIERTO para la UI. [resultado.json](resultado.json) identifica la línea 17, activo interno 944 (QA-M06-BOV-02) y eslabón faltante lecturas_nic41.

**Qué se hizo.** Se consultaron prevalidación y línea base, se comprobó la pausa EN_CIERRE con dos HTTP 409, se canceló con HTTP 200 y se autorizó el cierre con HTTP 200. Se ejecutó la prueba UI documentada en [acta 027](cypress/027/G43-UI-027.json) y [captura de tabla](cypress/027/screenshots/g43.cy.js/G43-UI-027-tabla-1.png).

**Qué se esperaba.** Lista visible con asiento, activo y eslabón; autorización; cancelación que dejara el período 8 ABIERTO e intacto; exclusión que trasladara la línea 17 al período siguiente.

**Qué se observó.** La API informó línea 17, activo 944 y lecturas_nic41. La cancelación dejó el período ABIERTO e intacto; la exclusión trasladó la línea 17 al período 522. El panel mostró la fila «Línea 17 · Variación por transformación biológica» | «QA-M06-BOV-02» | «Lecturas IoT aptas» y el título «1 línea con la cadena de trazabilidad incompleta».

**Por qué se decide así.** La vista muestra el identificador del activo y el nombre legible del eslabón; ambos cumplen la matriz. El comparador buscó los valores internos 944 y lecturas_nic41 en el texto visible, lo que produjo un ERROR_QA. Las comprobaciones API ya eran conformes.

**Decisión.** APROBADO en este informe enmendado.

## Fichas de rechazos confirmados

### INC-M06-G43-05 · TC-M06-024

**Criterio de la matriz.** «Tras autorizar, la revaluación usa el precio capturado al inicio (mismo id_precio_referencia y fecha_vigencia del congelado), no el precio nuevo».

**Esperado.** Precio inicial id 18, fecha 2026-11-07, PESO_KG, MERCADO_ACTIVO, congelado y usado en el cierre.

**Observado y evidencia.** G43-044: POST /finanzas/precios, HTTP 201, precio nuevo id 900 con vigencia 2026-11-13, registrado durante la pausa. G43-046: POST /finanzas/periodos/8/cierre, HTTP 200 con autorización; congelado id 900, fecha 2026-11-13. Véanse [solicitudes y precios](resultado.json). Las capturas del panel 027 no son evidencia del precio.

**Equipo y severidad.** Desarrollo es el primer contacto por la discrepancia en la respuesta pública de cierre, sin atribución de causa raíz. ALTA, certeza CONFIRMADA: el cierre puede valorar con un precio registrado después del inicio, contrario a la base exigida.

### INC-M06-G43-03 · TC-M06-026

**Criterio de la matriz.** Decisión por activo sin precio vigente. RF-87 v1.2 CA-5 y RF-83 v1.2 CA-5/CA-7 exigen estimación con último precio conocido, marca de estimación y alerta; RF-86 CA-14 solo exime variación y alerta de error por monto cero.

**Esperado.** Activo 1644 medido con último precio id 492, tiene_valor_estimado = true y alerta al Contador; sin nuevo registro de COSTO.

**Observado y evidencia.** G43-078: HTTP 400; G43-081: HTTP 409; G43-085: HTTP 200 con el 1644 seleccionado para estimación. La respuesta registró activos_estimados = null. Para 1644 hubo cálculos vacíos, solo auditoría MEDICION_SIN_VARIACION (id_referencia 121, precio_usado null) y alertas vacías. Véanse [solicitudes y diagnóstico](resultado.json), [acta UI](cypress/026/G43-UI-026.json) y [captura del panel 026](cypress/026/screenshots/g43.cy.js/G43-UI-026-tabla-1.png).

**Equipo y severidad.** Desarrollo es el primer contacto por la falta de marca y alerta en las consultas públicas, sin atribución de causa raíz. MEDIA, certeza CONFIRMADA: afecta la revelación de la estimación, sin evidencia de alteración de los montos en este RUN.

## Corrección del veredicto UI de 027

El [acta UI](cypress/027/G43-UI-027.json) y la [captura de la tabla](cypress/027/screenshots/g43.cy.js/G43-UI-027-tabla-1.png) acreditan «1 línea con la cadena de trazabilidad incompleta» y la fila «Línea 17 · Variación por transformación biológica» | «QA-M06-BOV-02» | «Lecturas IoT aptas». El selector mostró el período 8 «Diciembre de 2026 · Abierto». El acta registra casilla_autorizacion = true y boton_deshabilitado = true; entre los controles están «Autorizo excluir del comprobante las líneas con trazabilidad incompleta (pasan al período siguiente)», «Cerrar período» y «Cancelar cierre (No)». También constan [captura de casilla](cypress/027/screenshots/g43.cy.js/G43-UI-027-checkbox-2.png) y [captura del control](cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-3.png).

El identificador interno 944 corresponde a QA-M06-BOV-02, y lecturas_nic41 se muestra como «Lecturas IoT aptas». resultado.json conserva ui_lista RECHAZADO por el error del comparador; el informe enmendado decide con la evidencia visual y textual del mismo RUN. INC-M06-G43-02 queda CORREGIDA y sale de la lista de incidencias de producto activas.

## Comprobaciones, herramientas y evidencias

[resultado.json](resultado.json) registra las comprobaciones API de pausa, congelación, advertencia, cancelación, exclusión, estimación y traslado. Hubo una ejecución UI por cada panel obligatorio: 025 APROBADO, 026 APROBADO y 027 registrado RECHAZADO por el comparador, con su criterio visual resuelto arriba. Newman terminó con código 0, 10 solicitudes y cero fallos: [JSON](newman/newman-G43.json) y [HTML](newman/newman-G43.html). Cypress terminó con código 0 y tres pruebas, documentadas en [cypress](cypress). Node verificado: v22.15.1. Se registraron 109 solicitudes API y 53 Cypress. Los códigos 0 no sustituyen los oráculos ni prueban por sí solos el rollback.

[preflight.json](preflight.json) indica autorización válida y ninguna barrera; [contexto_operacion.json](contexto_operacion.json) identifica este RUN como reintento V2. No se registraron problemas técnicos de ejecución en el RUN oficial. El comparador de 027 es un problema interno de automatización y no una incidencia de producto.

## Intentos técnicos previos de V2

Antes del RUN 074459 constan 025305, 030640, 031156, 033923, 041055, 065303 y 070927. El 025305 conserva preflight y contexto, sin resultado.json; 030640 registró datos de precondición; 031156 y 033923 tuvieron problemas de ejecución Cypress; 041055 y 065303 registraron discrepancias de producto en sus propias corridas. El 070927 quedó no oficial por presupuesto y rollback no verificado, según el contexto de la operación actual. Cada intento tiene alcance y estado propios; ninguno constituye evidencia del veredicto del RUN 074459.

## Seguimiento, incidencias y análisis de causas

INC-M06-G43-01, INC-M06-G43-02 e INC-M06-G32-01 quedan CORREGIDAS. INC-M06-G43-03 queda REPRODUCIDA. INC-M06-G43-05 ya figuraba en el informe original y se mantiene confirmada en este RUN. Las incidencias activas de producto son solo INC-M06-G43-05 e INC-M06-G43-03; sus fichas separan primera derivación y causa raíz. La causa raíz no está determinada. Desarrollo debe revisar las dos discrepancias de API y aportar evidencia para una reevaluación autorizada.

## Observaciones

- OBS-G43-UI-01 (usabilidad, Desarrollo): durante la pausa EN_CIERRE la alerta indica «hasta que autorices las exclusiones», mientras el control disponible es «Cancelar el cierre» y no se muestra la lista de trazabilidad. Es una [observación histórica del intento 070927](../RUN-G43-V2-20261113-070927/cypress/027/screenshots/g43.cy.js/G43-UI-027-tramo-1.png), no evidencia del veredicto de este RUN.
- precios_congelados.id_especie tuvo la forma anómala [id_especie, estima]. No modifica el oráculo de identificador y fecha del precio congelado.
- En 026, la variación cero produjo MEDICION_SIN_VARIACION. RF-83 v1.2 CA-5 y CA-7 mantienen la exigencia de marca de estimación y alerta; su ausencia sostiene el rechazo firme.

## Cierre, rollback y efectos persistentes

El RUN permanece OFICIAL. [resultado.json](resultado.json) registra cumplidas las condiciones de cuatro casos, rollback, Newman, Cypress, artefactos, presupuesto y ausencia de error técnico. El rollback figura verificado por las lecturas del RUN: bases intactas, precio nuevo ausente y períodos nuevos ausentes. Esta enmienda no volvió a comprobarlo.

El RUN registró avisos 15185 y 15179 para el período 8, 15191 para el 266 y 15203 para el 523. El 15185 trata el paso a valor razonable de un activo al costo; los otros informan los cierres. El preflight advierte que avisos de cierre y alertas NIC 41 pueden persistir fuera del rollback del sandbox.

## Conclusión y acción

La reevaluación V2 oficial queda RECHAZADA por TC-M06-024 y TC-M06-026. TC-M06-025 y TC-M06-027 quedan APROBADOS en este informe. Desarrollo debe atender primero las discrepancias confirmadas de precio congelado y revelación de estimación. El responsable QA podrá ordenar una reevaluación posterior. Esta enmienda no cambia pruebas, datos, oficialidad ni registro.

## Enmienda documental (2026-11-13)

ORD-G43-034 ordenó esta enmienda del Markdown oficial. La [copia previa byte a byte](../../../historial_informes/TC-M06-G43_reevaluacion_V2.RUN-G43-V2-20261113-074459.antes-enmienda.md) tiene SHA-256 221349358BE8E25C55592FAE0C79661E7893F80BA5C06B62D55EBB2375C6915F. [resultado.json](resultado.json) conserva SHA-256 C871C2971435BEC592F9C92F08ADAF3CDD08F49391CFDA2442C5B4199C081FFD.

Se corrigieron las fichas de 024 con G43-044/G43-046 y de 026 con G43-078/G43-081/G43-085; se retiraron citas ajenas y la incidencia de producto 02; se fundamentó 026 con RF-83 v1.2, RF-86 CA-14 y RF-87 CA-5; se reescribieron los casos en prosa y se documentaron los intentos previos. El único veredicto que cambia en el informe es el de 027 (RECHAZADO → APROBADO, por ERROR_QA del comparador). No cambian la oficialidad, el rollback ni la evidencia del RUN.