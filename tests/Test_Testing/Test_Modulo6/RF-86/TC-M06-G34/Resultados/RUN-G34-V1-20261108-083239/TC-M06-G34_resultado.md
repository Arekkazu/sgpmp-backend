# TC-M06-G34 — RECHAZADO

## Identificación

TC-M06-G34 / TC-M06-006; RF-86 paso 1a, CA-15 y postcondición 6; versión 1; RUN RUN-G34-V1-20261108-083239; ambiente TEST; autorización AUT-G34-V1-R3-20261108; commit TEST no verificado; Node v22.15.1; Newman 6.2.2; Cypress 14.5.4.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-G34 / TC-M06-006 | RECHAZADO | Falta aviso al Contador QA con causa, activo y evento. A Medido; B Medido |

## Detalle por caso

### B — registro independiente (API: APROBADO)

- **Preparación:** activo 945 (`QA-M06-BOV-03`), período 8, evento 965; no se requirió rebase. Se procesó antes de suspender A para comprobar que la cadena completa de otro activo del período puede registrarse.
- **Esperado:** variación `GANANCIA_TRANSFORMACION_BIOLOGICA` por 55.226,88, componente de precio de mercado en cero, medición `COMPLETADO` y línea contable.
- **Observado y decisión:** variación 241 por 55.226,88, medición 184 del evento 965 en `COMPLETADO` (TB 55.226,88; PM 0) y línea 566. Se cumplió el registro normal de B; su comprobación API queda **APROBADA**. En el panel B también apareció `Medido`, conforme a su medición completada.

### A — suspensión del evento (API: RECHAZADO)

- **Preparación:** activo 943 (`QA-M06-BOV-01`), período 8, evento 966. Se fijó temporalmente el costo de venta de la especie al 100 % para provocar un valor neto no positivo; después se restauraron los costos originales.
- **Esperado:** suspender la medición y el registro de ese evento sin variación, línea, medición ni cálculo nuevos; dejar auditoría `MEDICION_PENDIENTE` con motivo y referencia al evento; enviar al Contador un aviso nuevo con causa `RF_83_NO_COMPLETADO`, activo y evento.
- **Cumplido:** hubo cero variaciones, líneas, mediciones y cálculos nuevos. La auditoría 4739 registró `MEDICION_PENDIENTE`, severidad `WARNING`, motivo `VALOR_NETO_NO_POSITIVO`, referencia 966, activo 943 y período 8. La suspensión sin datos parciales y su trazabilidad fueron conformes.
- **Falló y por qué:** la bandeja del Contador tenía línea base id 11216; la lectura posterior completa halló cero avisos relacionados con el activo y evento. Por ello no se acreditó el aviso exigido, aunque sí la auditoría. La comprobación API de A queda **RECHAZADA** por `INC-M06-G34-01`.

### UI — visibilidad del estado (RECHAZADO)

- **Preparación y esperado:** con el período diciembre (8) seleccionado en `/finanzas/medicion`, A debía verse `MEDICION_PENDIENTE` para el evento 966 suspendido; B debía mostrar su medición completada. Se ejecutó una comprobación Cypress real.
- **Observado:** la fila `QA-M06-BOV-01` de A mostró `Medido`; la fila `QA-M06-BOV-03` de B mostró `Medido`. B fue correcto. A no mostró el pendiente exigido, por lo que el Contador no puede identificar allí la suspensión del evento 966. La comprobación UI queda **RECHAZADA** por `INC-M06-G34-02`.

**Decisión de TC-M06-006: RECHAZADO** por `INC-M06-G34-01` e `INC-M06-G34-02`. El cumplimiento de B y de la suspensión sin datos parciales de A no subsana el aviso ni la visibilidad faltantes.

## Comprobaciones API y UI

- G34-API-006-B (API): APROBADO; Conforme; evidencia resultado.json.
- G34-API-006-A (API): RECHAZADO; Falta aviso al Contador QA con causa, activo y evento.; evidencia resultado.json.
- G34-UI-006-01 (UI): RECHAZADO; A Medido; B Medido; evidencia cypress/G34-UI-006-01.json.

## Evidencias reales

- preflight.json
- cypress/G34-UI-006-01.json
- cypress/G34-cypress.json
- cypress/screenshots/g34.cy.js/G34-UI-006-01.png
- resultado.json
- TC-M06-G34_resultado.md
- newman/newman-G34.json
- newman/newman-G34.html

## Incidencias de producto

### INC-M06-G34-01 — Falta aviso de suspensión de medición al Contador

**Requisito:** RF-86 paso 1a y CA-15: al no completar RF-83, suspender sin persistir variación ni línea y notificar al Contador con causa `RF_83_NO_COMPLETADO`, activo y evento.

**Pasos para reproducir:** con A y B elegibles en el mismo período ABIERTO, completar B; fijar temporalmente costo de venta de la especie al 100 % dentro del sandbox; registrar y procesar el evento de A; consultar la bandeja del Contador, la auditoría RF-94 y las variaciones; restaurar costos y cerrar el RUN.

**Esperado:** un aviso nuevo al Contador que identifique causa `RF_83_NO_COMPLETADO`, activo 943 y evento 966; sin variación ni línea de A.

**Obtenido:** línea base de bandeja {"fecha":"2026-11-08T08:32:39.880003Z","id":11216}; lecturas posteriores completas true; avisos relacionados 0; auditoría `MEDICION_PENDIENTE` presente 1; datos nuevos de A {"variaciones":[],"lineas":[],"mediciones":[],"calculos":[]}.

**Apoyo de código leído, sin atribución causal:** `src/financial_valuation/application/services/medidor.py:147-156` audita el pendiente y retorna; en esa rama no se encontró notificación. `src/financial_valuation/infrastructure/factories/m06_factory.py:120-122,145-147` construye el medidor y el procesador. Estas lecturas no prueban la versión desplegada ni la causa raíz.

**Impacto y severidad:** ALTA. El Contador no recibe la suspensión ni su causa; debe consultar auditoría y la variación queda sin registrar. Certeza CONFIRMADA de la discrepancia observada; causa raíz NO DETERMINADA.

**Primera atención:** Desarrollo, por ausencia observada en la bandeja pública del Contador; no implica atribución de causa.

**Evidencias:** `resultado.json` (línea base, lecturas y auditoría) y reporte Newman generado en este RUN, si corresponde.

### INC-M06-G34-02 — El panel de medición muestra como Medido un activo con la medición del evento suspendida

**Requisito:** TC-M06-006, RF-86 paso 1a, CA-15 y postcondición 6: si RF-83 no completó la medición del evento, A queda `MEDICION_PENDIENTE` para ese evento y el Contador ve ese estado en el panel de gestión de M06; B, con cadena completa, se registra normalmente.

**Pasos para reproducir:** con A (943) y B (945) elegibles en el período 8 `ABIERTO`, procesar B; fijar temporalmente el costo de venta de la especie al 100 % en el sandbox y procesar el evento 966 de A; confirmar por API la suspensión sin datos parciales y la auditoría; abrir `/finanzas/medicion` como Contador, seleccionar diciembre (período 8) y observar las filas `QA-M06-BOV-01` y `QA-M06-BOV-03` mientras el RUN sigue abierto. Restaurar costos y cerrar el RUN.

**Esperado:** A visible como `MEDICION_PENDIENTE` por el evento 966 suspendido; B visible como `Medido` por el evento 965 completado.

**Obtenido:** la fila de A mostró `QA-M06-BOV-01 | Medido`, pese a la auditoría 4739 `MEDICION_PENDIENTE` y a cero datos nuevos para el evento 966. La fila de B mostró `QA-M06-BOV-03 | Medido`, correctamente. El acta Cypress registra una prueba ejecutada, lectura HTTP 200 de las mediciones del período y captura real; su comprobación UI quedó `RECHAZADO`.

**Apoyo de código leído, sin atribución causal:** `SGPMP-FRONT-END-PWA/src/financial_valuation/pages/MedicionView.tsx:32-37` deriva el estado de las filas de las mediciones del período; `src/financial_valuation/application/services/medidor.py:147-156` audita la suspensión y retorna sin crear una fila de medición. Una medición `COMPLETADO` anterior del mismo activo y período puede seguir dando `Medido` en esa vista. Esta lectura local no prueba la versión desplegada ni determina la causa raíz.

**Impacto y severidad:** MEDIA. El Contador no ve en el panel que la variación del evento 966 de A quedó suspendida; el impacto es parcial porque la auditoría conserva la trazabilidad y B se muestra correctamente. Certeza CONFIRMADA de la discrepancia observada en TEST; causa raíz NO DETERMINADA.

**Primera atención:** Desarrollo, por el estado incorrecto observado en la UI pública para A; comprende la revisión frontend/backend sin atribuir de antemano el origen técnico.

**Evidencias:** `cypress/G34-UI-006-01.json` (acta), `cypress/G34-cypress.json` (resumen), `cypress/screenshots/g34.cy.js/G34-UI-006-01.png` (captura real) y `resultado.json` (auditoría y ausencia de datos nuevos de A).

## Problemas técnicos y análisis de causas

Ninguno observado. Referencia de código local consultada: src/financial_valuation/application/services/medidor.py:147-156 audita MEDICION_PENDIENTE y retorna PENDIENTE; allí no se observó envío de notificación. Esta lectura no prueba la versión desplegada ni la causa raíz.

## Cierre y rollback

Costos originales {"pct_transporte":"0.0200","pct_comisiones":"0.0300","pct_impuestos":"0.0100"}; restauración previa al DELETE true; DELETE HTTP 200; configuración poscierre true; rollback true: Lecturas públicas poscierre sin eventos M02 ni registros financieros de A y B.

## Conclusión y acciones

La cadena completa de B cumple. A cumple la suspensión sin datos parciales y la auditoría, pero falla en el aviso al Contador (`INC-M06-G34-01`) y en la visibilidad del pendiente en el panel (`INC-M06-G34-02`). Desarrollo atiende ambas incidencias; QA reevaluará las dos comprobaciones con nueva autorización.

Oficial: true; solicitudes registradas 66/90.

Actualización del informe (2026-11-08): detalle por caso legible e INC-02 descrita; veredictos sin cambios.
