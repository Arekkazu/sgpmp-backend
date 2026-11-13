# TC-M06-G43 — reevaluación V2 oficial - RECHAZADO

G43 | RF-87 v1.2 (026); RF-87 (024, 025, 027) | TC-M06-024, TC-M06-025, TC-M06-026, TC-M06-027 | V2 | RUN-G43-V2-20261113-074459 | TEST | autorización AUT-G43-V2-R8-20261113 | commit desplegado informado: 453277e4, no verificado en este RUN.

## Resumen

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-024 | RECHAZADO | precio_congelado_ini |
| TC-M06-025 | APROBADO | Criterios conformes |
| TC-M06-026 | RECHAZADO | estimacion_1644 |
| TC-M06-027 | RECHAZADO | ui_lista |

## Criterios API y UI

| Caso | Criterio | Esperado | Observado | Cumple |
|---|---|---|---|---|
| TC-M06-024 | pausa_EN_CIERRE | Pausa EN_CIERRE | 409/EN_CIERRE; 409/EN_CIERRE | APROBADO |
| TC-M06-024 | precio_congelado_ini | Precio inicial por id y fecha | 900/2026-11-13 | RECHAZADO |
| TC-M06-024 | cierre_autorizado | Cierre 8 CERRADO | 200/CERRADO | APROBADO |
| TC-M06-025 | aviso_api | Número, activo y especie | 1 activo: Lote 1644, Caprino Aislado Precios | APROBADO |
| TC-M06-025 | no_rollback | No deja 266 ABIERTO e intacto | 409; 200; true | APROBADO |
| TC-M06-025 | si_exclusion | Sí cierra excluyendo 1644 y procesa 1643 | 200; true | APROBADO |
| TC-M06-025 | ui_lista | Advertencia y decisión por activo en UI | APROBADO | APROBADO |
| TC-M06-026 | estimado_no_aplica | 1643 devuelve 400 ACTIVO_ESTIMADO_NO_APLICA | 400/ACTIVO_ESTIMADO_NO_APLICA | APROBADO |
| TC-M06-026 | sin_decision | Sin decisión devuelve 409 y el período no cierra | 409/EXCLUSION_REQUIERE_AUTORIZACION; EN_CIERRE | APROBADO |
| TC-M06-026 | estimacion_1644 | 1644 estimado con precio 492, sin COSTO nuevo | 200; vías {"calculo":false,"auditoria":false,"respuesta":false,"alerta":false}; sin variación true; costo nuevo false | RECHAZADO |
| TC-M06-026 | ui_decision | UI permite excluir o estimar por activo | APROBADO | APROBADO |
| TC-M06-027 | lista_api | Asiento 17, activo 944 y eslabón | línea 17; activo 944; faltan lecturas_nic41 | APROBADO |
| TC-M06-027 | pausa_EN_CIERRE | Pausa EN_CIERRE | 409/EN_CIERRE; 409/EN_CIERRE | APROBADO |
| TC-M06-027 | no_rollback | Cancelación deja 8 ABIERTO e intacto | 200; true | APROBADO |
| TC-M06-027 | si_exclusion_027 | Línea 17 pendiente en período siguiente | 200; true | APROBADO |
| TC-M06-027 | ui_lista | Lista completa visible en UI | RECHAZADO | RECHAZADO |

### TC-M06-024

Qué se verifica: precio congelado durante la pausa.
Preparación: período 8; preflight y línea base en resultado.json.
Qué se hizo: peticiones API y panel UI 027 registrados en las evidencias del RUN.
Esperado: Pausa EN_CIERRE; Precio inicial por id y fecha; Cierre 8 CERRADO.
Observado: 409/EN_CIERRE; 409/EN_CIERRE; 900/2026-11-13; 200/CERRADO.
Por qué se decide: RECHAZADO — precio_congelado_ini.

### TC-M06-025

Qué se verifica: advertencia y exclusión de activos sin precio.
Preparación: período 266; preflight y línea base en resultado.json.
Qué se hizo: peticiones API y panel UI 025 registrados en las evidencias del RUN.
Esperado: Número, activo y especie; No deja 266 ABIERTO e intacto; Sí cierra excluyendo 1644 y procesa 1643; Advertencia y decisión por activo en UI.
Observado: 1 activo: Lote 1644, Caprino Aislado Precios; 409; 200; true; 200; true; APROBADO.
Por qué se decide: APROBADO — Criterios conformes.

### TC-M06-026

Qué se verifica: RF-87 v1.2, estimación o exclusión por activo.
Preparación: período siguiente de 266; preflight y línea base en resultado.json.
Qué se hizo: peticiones API y panel UI 026 registrados en las evidencias del RUN.
Esperado: 1643 devuelve 400 ACTIVO_ESTIMADO_NO_APLICA; Sin decisión devuelve 409 y el período no cierra; 1644 estimado con precio 492, sin COSTO nuevo; UI permite excluir o estimar por activo.
Observado: 400/ACTIVO_ESTIMADO_NO_APLICA; 409/EXCLUSION_REQUIERE_AUTORIZACION; EN_CIERRE; 200; vías {"calculo":false,"auditoria":false,"respuesta":false,"alerta":false}; sin variación true; costo nuevo false; APROBADO.
Por qué se decide: RECHAZADO — estimacion_1644.

### TC-M06-027

Qué se verifica: autorización de la exclusión por trazabilidad.
Preparación: período 8; preflight y línea base en resultado.json.
Qué se hizo: peticiones API y panel UI 027 registrados en las evidencias del RUN.
Esperado: Asiento 17, activo 944 y eslabón; Pausa EN_CIERRE; Cancelación deja 8 ABIERTO e intacto; Línea 17 pendiente en período siguiente; Lista completa visible en UI.
Observado: línea 17; activo 944; faltan lecturas_nic41; 409/EN_CIERRE; 409/EN_CIERRE; 200; true; 200; true; RECHAZADO.
Por qué se decide: RECHAZADO — ui_lista.

## Fichas de comprobaciones rechazadas

### TC-M06-024 · precio_congelado_ini

Criterio de matriz: Precio inicial congelado durante el cierre.
Esperado: Precio inicial por id y fecha.
Observado: 900/2026-11-13; HTTP 200.
Precio inicial 18/2026-11-07; precio nuevo 900/2026-11-13; congelado 900/2026-11-13.
Evidencia: G43-006; cypress/027/screenshots/g43.cy.js/G43-UI-027-tabla-1.png, cypress/027/screenshots/g43.cy.js/G43-UI-027-checkbox-2.png, cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-3.png, cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-4.png; resultado.json.
Equipo inicial: Desarrollo. Severidad: ALTA; La valoración del cierre puede usar un precio posterior..
### TC-M06-026 · estimacion_1644

Criterio de matriz: RF-87 v1.2: decisión por activo.
Esperado: 1644 estimado con precio 492, sin COSTO nuevo.
Observado: 200; vías {"calculo":false,"auditoria":false,"respuesta":false,"alerta":false}; sin variación true; costo nuevo false; HTTP 200.
Vías de estimación consultadas: {"calculo":false,"auditoria":false,"respuesta":false,"alerta":false}; variación cero: true; cálculos: []; auditoría: [{"tipo_evento":"MEDICION_SIN_VARIACION","id_referencia":121,"id_activo_biologico":1644,"precio_usado":null}]; alertas: [].
Evidencia: G43-006; cypress/026/screenshots/g43.cy.js/G43-UI-026-tabla-1.png, cypress/026/screenshots/g43.cy.js/G43-UI-026-radio-2.png, cypress/026/screenshots/g43.cy.js/G43-UI-026-radio-3.png, cypress/026/screenshots/g43.cy.js/G43-UI-026-submit-4.png, cypress/026/screenshots/g43.cy.js/G43-UI-026-submit-5.png; resultado.json.
Equipo inicial: Desarrollo. Severidad: ALTA; La valoración por activo puede ser incorrecta..
### TC-M06-027 · ui_lista

Criterio de matriz: Antes de continuar, lista de asientos y activos con eslabón incompleto y solicitud de autorización.
Esperado: Lista completa visible en UI.
Observado: RECHAZADO; HTTP 200.
Evidencia: G43-006; cypress/027/screenshots/g43.cy.js/G43-UI-027-tabla-1.png, cypress/027/screenshots/g43.cy.js/G43-UI-027-checkbox-2.png, cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-3.png, cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-4.png; resultado.json.
Equipo inicial: Desarrollo. Severidad: MEDIA; La lista limita la decisión informada..

## Precios

| Especie | P_ini id/fecha | Fuente de P_ini | P_nuevo id/fecha | Congelado id/fecha |
|---|---|---|---|---|
| 39 | 18 / 2026-11-07 | valorador.precio_para: especie 39, categoria PESO_KG, fuente MERCADO_ACTIVO, vigencia mas reciente hasta 2026-11-13, desempate por id; configuracion.especies o PESO_KG por defecto | 900 / 2026-11-13 | 900 / 2026-11-13 |

## Activos sin precio

| Período | Prevalidación | Excluidos | Procesados |
|---|---|---|---|
| 266 | 1644 | 1644 | 1 |
| 523 | 1644 |  | 2 |

## Líneas

| Línea | Activo | Eslabón faltante | Excluida | Destino |
|---|---|---|---|---|
| 17 | 944 | lecturas_nic41 | true | 522 |

## UI

| Panel | Pruebas ejecutadas | Estado | Acta |
|---|---|---|---|
| 027 | 1 | RECHAZADO | cypress/027/G43-UI-027.json |
| 025 | 1 | APROBADO | cypress/025/G43-UI-025.json |
| 026 | 1 | APROBADO | cypress/026/G43-UI-026.json |

- Panel 027: controles citados: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Ir al período en curso  ; Autorizo excluir del comprobante las líneas con trazabilidad incompleta (pasan al período siguiente)  ; Cerrar período  ; Cancelar cierre (No)  ; Ver comprobantes  ; Ver revelaciones  ; Falta: Línea 17, activo 944 y eslabón faltante; eslabón lecturas_nic41. Encontrado: {"titulo":"1 línea con la cadena de trazabilidad incompleta","encabezados":["Asiento","Activo","Qué falta"],"filas":["Línea 17 · Variación por transformació Tramos: G43-UI-027-tabla-1.png, G43-UI-027-checkbox-2.png, G43-UI-027-submit-3.png, G43-UI-027-submit-4.png.
- Panel 025: controles citados: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Excluir todos  ; Estimar todos  ; Excluir de este cierre (pasa al período siguiente) · Lote 1644  ; Medir con el último precio conocido, como estimación · Lote 1644  ; Cerrar período  ; Cancelar cierre (No)  ;  Tramos: G43-UI-025-tabla-1.png, G43-UI-025-radio-2.png, G43-UI-025-radio-3.png, G43-UI-025-submit-4.png, G43-UI-025-submit-5.png.
- Panel 026: controles citados: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Ir al período en curso  ; Excluir todos  ; Estimar todos  ; Excluir de este cierre (pasa al período siguiente) · Lote 1644  ; Medir con el último precio conocido, como estimación · Lote 1644  ; Cerrar período  ; Cancelar cierre (No)  ; Ver comprobantes  ; Ver revelaciones  ;  Tramos: G43-UI-026-tabla-1.png, G43-UI-026-radio-2.png, G43-UI-026-radio-3.png, G43-UI-026-submit-4.png, G43-UI-026-submit-5.png.

## Evidencia de estimación 1644

Vías: {"calculo":false,"auditoria":false,"respuesta":false,"alerta":false}; auditoría sin variación: true; activos procesados: 2. Detalle saneado en resultado.json.

## Incidencias

- INC-M06-G43-02 (casos TC-M06-027): esperado Lista UI con asiento, activo y eslabón; obtenido Falta: Línea 17, activo 944 y eslabón faltante; eslabón lecturas_nic41. Encontrado: {"titulo":"1 línea con la cadena de trazabilidad incompleta","encabezados":["Asiento","Activo","Qué falta"],"filas":["Línea 17 · Variación por transformació. Evidencia: resultado.json. Impacto: La lista limita la decisión informada.. Severidad MEDIA: La lista limita la decisión informada.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en API o UI pública de cierre. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar. Acción: Desarrollo revisa la discrepancia; QA repite con autorización.
- INC-M06-G43-05 (casos TC-M06-024): esperado Precio 39 congelado al inicio y usado en la medición; obtenido congelado 900; inicial 18; nuevo 900. Evidencia: resultado.json. Impacto: La valoración del cierre puede usar un precio posterior.. Severidad ALTA: La valoración del cierre puede usar un precio posterior.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en API o UI pública de cierre. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar. Acción: Desarrollo revisa la discrepancia; QA repite con autorización.
- INC-M06-G43-03 (casos TC-M06-026): esperado RF-87 v1.2: decisión y estimación por activo; obtenido estimacion_1644; UI: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Ir al período en curso  ; Excluir todos  ; Estimar todos  ; Excluir de este cierre (pasa al período siguiente) · L. Evidencia: resultado.json. Impacto: La valoración por activo puede ser incorrecta.. Severidad ALTA: La valoración por activo puede ser incorrecta.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en API o UI pública de cierre. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar. Acción: Desarrollo revisa la discrepancia; QA repite con autorización.

## Seguimiento de incidencias previas

- INC-M06-G43-01: CORREGIDA.
- INC-M06-G43-02: REPRODUCIDA.
- INC-M06-G43-03: REPRODUCIDA.
- INC-M06-G32-01: CORREGIDA.

## Herramientas y evidencias

Node v22.15.1; Newman código 0; Cypress código 0, pruebas 3.
- preflight.json
- cypress/025/G43-cypress-salida.log
- cypress/025/G43-cypress.json
- cypress/025/G43-UI-025.json
- cypress/025/screenshots/g43.cy.js/G43-UI-025-radio-2.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-radio-3.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-submit-4.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-submit-5.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-tabla-1.png
- cypress/026/G43-cypress-salida.log
- cypress/026/G43-cypress.json
- cypress/026/G43-UI-026.json
- cypress/026/screenshots/g43.cy.js/G43-UI-026-radio-2.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-radio-3.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-submit-4.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-submit-5.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-tabla-1.png
- cypress/027/G43-cypress-salida.log
- cypress/027/G43-cypress.json
- cypress/027/G43-UI-027.json
- cypress/027/screenshots/g43.cy.js/G43-UI-027-checkbox-2.png
- cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-3.png
- cypress/027/screenshots/g43.cy.js/G43-UI-027-submit-4.png
- cypress/027/screenshots/g43.cy.js/G43-UI-027-tabla-1.png
- newman/newman-G43.html
- newman/newman-G43.json

## Problemas técnicos


## Observaciones

- precios_congelados.id_especie se recibió como [id_especie, estima]; forma anómala del dato, sin alterar el oráculo del precio congelado.
- 026: variación cero del 1644: MEDICION_SIN_VARIACION sin marca de estimación acreditada; consultar a la líder de requisito, como en G41.
- OBS-G43-UI-01 (usabilidad, Desarrollo): en la pausa EN_CIERRE, la alerta indica “hasta que autorices las exclusiones”, mientras el único control es “Cancelar el cierre” y no se muestra la lista de trazabilidad. Evidencia histórica: ../RUN-G43-V2-20261113-070927/cypress/027/screenshots/g43.cy.js/G43-UI-027-tramo-1.png y ../RUN-G43-V2-20261113-070927/cypress/026/screenshots/g43.cy.js/G43-UI-026-tramo-1.png. No altera los veredictos de los casos.

## Condiciones de oficialidad

- cuatro_casos: cumple.
- rollback: cumple.
- newman: cumple.
- cypress: cumple.
- artefactos: cumple.
- presupuesto: cumple.
- sin_error_tecnico: cumple.

## Efectos persistentes

- Período 8, aviso 15185: Al cerrar el período 2026-12, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06-COSTO-01. La NIC 41 ¶30 exige pasarlos a valor razonable..
- Período 8, aviso 15179: Período 2026-12 cerrado: listo para transferir desde Agrofusión..
- Período 266, aviso 15191: Período 2026-11 cerrado: listo para transferir desde Agrofusión..
- Período 523, aviso 15203: Período 2026-12 cerrado: listo para transferir desde Agrofusión..
Los avisos de cierre y las alertas NIC 41 pueden persistir fuera del rollback del sandbox.


## Cierre, rollback y acción

Registro OFICIAL. Rollback verificado: sí. Bases intactas; precio nuevo ausente; períodos nuevos ausentes. Lecturas sin cabeceras del RUN.
Las incidencias requieren corrección y reevaluación expresamente autorizada.
