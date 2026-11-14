# TC-M06-G43 — reevaluación V3 oficial - APROBADO

G43 | RF-87 v1.2 (026); RF-87 (024, 025, 027) | TC-M06-024, TC-M06-025, TC-M06-026, TC-M06-027 | V3 | RUN-G43-V3-20261114-061535 | TEST | autorización AUT-G43-V3-R3-20261114 | corrección informada: e73c9c9e (origin/test 0fc55acf); despliegue no verificado por esta automatización.

## Resumen

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-024 | APROBADO | Criterios conformes |
| TC-M06-025 | APROBADO | Criterios conformes |
| TC-M06-026 | APROBADO | Criterios conformes |
| TC-M06-027 | APROBADO | Criterios conformes |

## Criterios API y UI

| Caso | Criterio | Esperado | Observado | Cumple |
|---|---|---|---|---|
| TC-M06-024 | pausa_EN_CIERRE | Pausa EN_CIERRE | 409/EN_CIERRE; 409/EN_CIERRE | APROBADO |
| TC-M06-024 | precio_congelado_ini | Precio inicial por id y fecha | 18/2026-11-07 | APROBADO |
| TC-M06-024 | cierre_autorizado | Cierre 8 CERRADO | 200/CERRADO | APROBADO |
| TC-M06-025 | aviso_api | Número, activo y especie | 1 activo: Lote 1644, Caprino Aislado Precios | APROBADO |
| TC-M06-025 | no_rollback | No deja 266 ABIERTO e intacto | 409; 200; true | APROBADO |
| TC-M06-025 | si_exclusion | Sí cierra excluyendo 1644 y procesa 1643 | 200; true | APROBADO |
| TC-M06-025 | ui_lista | Advertencia y decisión por activo en UI | APROBADO | APROBADO |
| TC-M06-026 | estimado_no_aplica | 1643 devuelve 400 ACTIVO_ESTIMADO_NO_APLICA | 400/ACTIVO_ESTIMADO_NO_APLICA | APROBADO |
| TC-M06-026 | sin_decision | Sin decisión devuelve 409 y el período no cierra | 409/EXCLUSION_REQUIERE_AUTORIZACION; EN_CIERRE | APROBADO |
| TC-M06-026 | estimacion_1644 | 1644 estimado con precio 492, sin COSTO nuevo | 200; vías {"calculo":true,"auditoria":true,"respuesta":true,"alerta":true}; sin variación false; costo nuevo false | APROBADO |
| TC-M06-026 | ui_decision | UI permite excluir o estimar por activo | APROBADO | APROBADO |
| TC-M06-027 | lista_api | Asiento 17, activo 944 y eslabón | línea 17; activo 944; faltan lecturas_nic41, auditoria_m03 | APROBADO |
| TC-M06-027 | pausa_EN_CIERRE | Pausa EN_CIERRE | 409/EN_CIERRE; 409/EN_CIERRE | APROBADO |
| TC-M06-027 | no_rollback | Cancelación deja 8 ABIERTO e intacto | 200; true | APROBADO |
| TC-M06-027 | si_exclusion_027 | Línea 17 pendiente en período siguiente | 200; true | APROBADO |
| TC-M06-027 | ui_lista | Lista completa visible en UI | APROBADO | APROBADO |

### TC-M06-024

Qué se verifica: precio congelado durante la pausa.
Preparación: período 8; preflight y línea base en resultado.json.
Qué se hizo: peticiones API y panel UI 027 registrados en las evidencias del RUN.
Esperado: Pausa EN_CIERRE; Precio inicial por id y fecha; Cierre 8 CERRADO.
Observado: 409/EN_CIERRE; 409/EN_CIERRE; 18/2026-11-07; 200/CERRADO.
Por qué se decide: APROBADO — Criterios conformes.

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
Observado: 400/ACTIVO_ESTIMADO_NO_APLICA; 409/EXCLUSION_REQUIERE_AUTORIZACION; EN_CIERRE; 200; vías {"calculo":true,"auditoria":true,"respuesta":true,"alerta":true}; sin variación false; costo nuevo false; APROBADO.
Por qué se decide: APROBADO — Criterios conformes.

### TC-M06-027

Qué se verifica: autorización de la exclusión por trazabilidad.
Preparación: período 8; preflight y línea base en resultado.json.
Qué se hizo: peticiones API y panel UI 027 registrados en las evidencias del RUN.
Esperado: Asiento 17, activo 944 y eslabón; Pausa EN_CIERRE; Cancelación deja 8 ABIERTO e intacto; Línea 17 pendiente en período siguiente; Lista completa visible en UI.
Observado: línea 17; activo 944; faltan lecturas_nic41, auditoria_m03; 409/EN_CIERRE; 409/EN_CIERRE; 200; true; 200; true; APROBADO.
Por qué se decide: APROBADO — Criterios conformes.

## Fichas de comprobaciones rechazadas


## Precios

| Especie | P_ini id/fecha | Fuente de P_ini | P_nuevo id/fecha | Congelado id/fecha |
|---|---|---|---|---|
| 39 | 18 / 2026-11-07 | valorador.precio_para: especie 39, categoria PESO_KG, fuente MERCADO_ACTIVO, vigencia mas reciente hasta 2026-11-14, desempate por id; configuracion.especies o PESO_KG por defecto | 1103 / 2026-11-14 | 18 / 2026-11-07 |

## Activos sin precio

| Período | Prevalidación | Excluidos | Procesados |
|---|---|---|---|
| 266 | 1644 | 1644 | 1 |
| 620 | 1644 |  | 2 |

## Líneas

| Línea | Activo | Eslabón faltante | Excluida | Destino |
|---|---|---|---|---|
| 17 | 944 | lecturas_nic41, auditoria_m03 | true | 619 |

## UI

| Panel | Pruebas ejecutadas | Estado | Acta |
|---|---|---|---|
| 027 | 1 | APROBADO | cypress/027/G43-UI-027.json |
| 025 | 1 | APROBADO | cypress/025/G43-UI-025.json |
| 026 | 1 | APROBADO | cypress/026/G43-UI-026.json |

- Panel 027: controles citados: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Ir al período en curso  ; Autorizo excluir del comprobante las líneas con trazabilidad incompleta (pasan al período siguiente)  ; Cerrar período  ; Cancelar cierre (No)  ; Ver comprobantes  ; Ver revelaciones  ;  Tramos: G43-UI-027-tabla-1.png, G43-UI-027-checkbox-2.png, G43-UI-027-submit-3.png, G43-UI-027-submit-4.png.
- Panel 025: controles citados: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Excluir todos  ; Estimar todos  ; Excluir de este cierre (pasa al período siguiente) · Lote 1644  ; Medir con el último precio conocido, como estimación · Lote 1644  ; Autorizo excluir del comprobante las líneas con trazabilidad incompleta (pasan al período siguiente)  ; Cerrar período  ; Cancelar cierre (No)  ;  Tramos: G43-UI-025-tabla-1.png, G43-UI-025-radio-2.png, G43-UI-025-radio-3.png, G43-UI-025-checkbox-4.png, G43-UI-025-submit-5.png, G43-UI-025-submit-6.png.
- Panel 026: controles citados: Valoración  ; Cierre  ; Reportes  ; Datos  ; Variaciones de valor  ; Pendientes  ; Cierre del período  ; Ir al período en curso  ; Excluir todos  ; Estimar todos  ; Excluir de este cierre (pasa al período siguiente) · Lote 1644  ; Medir con el último precio conocido, como estimación · Lote 1644  ; Autorizo excluir del comprobante las líneas con trazabilidad incompleta (pasan al período siguiente)  ; Cerrar período  ; Cancelar cierre (No)  ; Ver comprobantes  ; Ver revelaciones  ;  Tramos: G43-UI-026-tabla-1.png, G43-UI-026-radio-2.png, G43-UI-026-radio-3.png, G43-UI-026-checkbox-4.png, G43-UI-026-submit-5.png, G43-UI-026-submit-6.png.

## Evidencia de estimación 1644

Vías: {"calculo":true,"auditoria":true,"respuesta":true,"alerta":true}; auditoría sin variación: false; activos procesados: 2. Detalle saneado en resultado.json.

## Incidencias


## Seguimiento de incidencias previas

- INC-M06-G43-01: CORREGIDA.
- INC-M06-G43-02: CORREGIDA.
- INC-M06-G43-03: CORREGIDA.
- INC-M06-G43-05: CORREGIDA.
- INC-M06-G32-01: CORREGIDA.

## Herramientas y evidencias

Node v22.15.1; Newman código 0; Cypress código 0, pruebas 3.
- preflight.json
- cypress/025/G43-cypress-salida.log
- cypress/025/G43-cypress.json
- cypress/025/G43-UI-025.json
- cypress/025/screenshots/g43.cy.js/G43-UI-025-checkbox-4.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-radio-2.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-radio-3.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-submit-5.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-submit-6.png
- cypress/025/screenshots/g43.cy.js/G43-UI-025-tabla-1.png
- cypress/026/G43-cypress-salida.log
- cypress/026/G43-cypress.json
- cypress/026/G43-UI-026.json
- cypress/026/screenshots/g43.cy.js/G43-UI-026-checkbox-4.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-radio-2.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-radio-3.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-submit-5.png
- cypress/026/screenshots/g43.cy.js/G43-UI-026-submit-6.png
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

- OBS-G43-UI-01: en la pausa del panel 027 no se identificó un control de autorizar; revisar acta y capturas reales del RUN.
- OBS-G43-UI-02 (Desarrollo): la línea 17 muestra "Otro registro de origen" para auditoria_m03; faltan etiquetas específicas. No altera el veredicto.

## Condiciones de oficialidad

- cuatro_casos: cumple.
- rollback: cumple.
- newman: cumple.
- cypress: cumple.
- artefactos: cumple.
- presupuesto: cumple.
- sin_error_tecnico: cumple.

## Efectos persistentes

- Período 8, aviso 16229: Al cerrar el período 2026-12, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06-COSTO-01. La NIC 41 ¶30 exige pasarlos a valor razonable..
- Período 8, aviso 16222: Período 2026-12 cerrado: listo para transferir desde Agrofusión..
- Período 8, aviso 16220: El informe de revelaciones 2026-M12-V1 tiene datos insuficientes en los métodos y supuestos de valoración de QA-M06-BOV-01, QA-M06-BOV-02, QA-M06-BOV-03, QA-M06-BOV-04, QA-M06-BOV-05 y 3 más. Consulte la sección de métodos y supuestos..
- Período 266, aviso 16238: Período 2026-11 cerrado: listo para transferir desde Agrofusión..
- Período 266, aviso 16236: El informe de revelaciones 2026-M11-V1 tiene datos insuficientes en los métodos y supuestos de valoración de Lote 1643, Lote 1644. Consulte la sección de métodos y supuestos..
- Período 620, aviso 16254: El activo Lote 1644 se midió el 2026-11-14 con un precio estimado porque la especie Caprino Aislado Precios no tiene precio de mercado vigente. Revise la medición y registre el precio vigente..
- Período 620, aviso 16247: Período 2026-12 cerrado: listo para transferir desde Agrofusión..
- Período 620, aviso 16245: El informe de revelaciones 2026-M12-V1 tiene datos insuficientes en los métodos y supuestos de valoración de Lote 1643, Lote 1644. Consulte la sección de métodos y supuestos..
Los avisos de cierre y las alertas NIC 41 pueden persistir fuera del rollback del sandbox.


## Cierre, rollback y acción

Registro OFICIAL. Rollback verificado: sí. Bases intactas; precio nuevo ausente; períodos nuevos ausentes. Lecturas sin cabeceras del RUN.
Las incidencias requieren corrección y reevaluación expresamente autorizada.
