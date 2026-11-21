# TC-M06-G34 — APROBADO

## Identificación

TC-M06-G34 / TC-M06-006; RF-86 paso 1a, CA-15 y postcondición 6; versión 2; RUN RUN-G34-V2-20261112-052510; ambiente TEST; autorización AUT-G34-V2-R4-20261112; commit TEST no verificado; Node v22.15.1; Newman 6.2.2; Cypress 14.5.4.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-G34 / TC-M06-006 | APROBADO | Oráculo API y UI completo. |

## Detalle por caso

### B (APROBADO) — registro independiente

- **Preparación:** activo 1627, período 241, evento 1584; rebase no requerido.
- **Esperado:** variación `GANANCIA_TRANSFORMACION_BIOLOGICA` por 71289.6, PM cero, medición `COMPLETADO` y línea contable.
- **Observado y decisión:** variación 405 por 71289.60, medición 322 del evento en `COMPLETADO`, TB 71289.6000, PM 0.0000 y línea 5636. B se registró normalmente; su comprobación API queda APROBADO. En el panel se vio `Medido`.

### A (APROBADO) — suspensión del evento

- **Preparación:** activo 1831, período 241, evento 1585; costo de venta temporal de la especie al 100 % para provocar valor neto no positivo.
- **Esperado:** cero variaciones, líneas, mediciones y cálculos nuevos; auditoría `MEDICION_PENDIENTE` con motivo y referencia al evento; evento en `eventos-pendientes`; exactamente un aviso nuevo al Contador con identificador de A y fecha del evento. `RF_83_NO_COMPLETADO` es la causa interna interpretada, no un texto obligatorio de la bandeja.
- **Cumplido:** variaciones 0, líneas 0, mediciones 0, cálculos 0; auditoría 18347 `MEDICION_PENDIENTE` (`WARNING`, motivo `VALOR_NETO_NO_POSITIVO`, referencia 1585). La suspensión no dejó datos parciales y fue auditada.
- **Aviso observado:** desde la línea base de bandeja id 12532, la lectura posterior completa halló 1 avisos relacionados. Se contrastó el texto con la suspensión, identificador y fecha del evento; tipo_evento del aviso válido 40; tipo contrastado con referencia previa; la comprobación API de A queda APROBADO.

### UI (APROBADO) — visibilidad del estado

- **Preparación y esperado:** abrir `/finanzas/medicion` con el período 241; A debe verse `Medición pendiente` por su evento suspendido y B `Medido`.
- **Observado y decisión:** A mostró `Medición pendiente` y B mostró `Medido` en 1 prueba Cypress. B fue correcto; La comprobación UI queda APROBADO.

**Decisión de TC-M06-006: APROBADO**. Incidencias: ninguna.

## Comprobaciones API y UI

- G34-API-006-B (API): APROBADO; Conforme; evidencia resultado.json.
- G34-API-006-A (API): APROBADO; Conforme; evidencia resultado.json.
- G34-UI-006-01 (UI): APROBADO; Filas A y B visibles con estado esperado; evidencia cypress/G34-UI-006-01.json.

## Evidencias reales

- preflight.json
- cypress/G34-UI-006-01.json
- cypress/G34-cypress.json
- cypress/screenshots/g34.cy.js/G34-UI-006-01.png
- resultado.json
- TC-M06-G34_reevaluacion_V2.md
- newman/newman-G34.json
- newman/newman-G34.html

## Observaciones y seguimiento V1

- INC-M06-G34-01: CORREGIDA
- INC-M06-G34-02: CORREGIDA
- Efecto persistente declarado bajo la autorización de este RUN (AUT-G34-V2-R4-20261112) y su SOL de V2: El aviso ALERTA_FINANCIERA_NIC41 de suspensión a los Contadores de la finca se envía en otra sesión con commit propio; puede permanecer en la bandeja aunque DELETE cierre el RUN. Su persistencia no forma parte del rollback verificado del sandbox..

## Incidencias de producto

Ninguna incidencia de producto confirmada.

## Problemas técnicos y análisis de causas

Ninguno observado. La causa raíz de cualquier discrepancia queda NO DETERMINADA; se decidirá con evidencia del RUN.

## Cierre y rollback

Costos originales {"pct_transporte":"0.0200","pct_comisiones":"0.0300","pct_impuestos":"0.0100"}; restauración previa al DELETE true; DELETE HTTP 200; configuración poscierre true; rollback del sandbox true: Lecturas públicas poscierre sin eventos M02 ni registros financieros de A y B.. Este rollback se limita a datos del sandbox; el aviso de suspensión al Contador puede persistir fuera de él bajo la autorización AUT-G34-V2-R4-20261112 y la SOL de V2

## Conclusión y acciones

Cadena B y suspensión A acreditadas por API y UI.

Oficial: true; solicitudes API 78/90 y Cypress 14/16. 
