# TC-M06-G33 — APROBADO

## Identificación

TC-M06-G33 / TC-M06-005; RF-86 v2.0; RUN RUN-G33-V1-20261108-072219; versión 1; intento 1; ambiente TEST; autorización AUT-G33-V1-20261108; commit de TEST no verificado; Node v22.15.1; Newman 6.2.2; API únicamente.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-G33 / TC-M06-005 | APROBADO | Ausencias y auditoría RF-94 conformes. |

## Diagnóstico de candidatos

medido: true; total_recibido: 9; bovino: 6; individual: 6; estado: 5; sin_costo: 5; valor_positivo: 5; precio_vigente: 5; periodo_destino: 5; peso_kg: 5; calculo_previo: 5; primera_condicion_fallida: no observado

## Detalle por caso

### TC-M06-G33 / TC-M06-005

- **Preparación:** activo 945, período destino 8, precio vigente 18, peso constante 306 kg; rebase no requerido. El rebase, si ocurrió, queda fuera del oráculo.
- **Esperado:** no se crea variación ni línea de asiento; no se emite alerta de error; RF-94 registra exactamente una medición sin variación del activo. Valores razonables anterior y nuevo iguales y positivos.
- **Observado:** Variaciones nuevas 0; líneas nuevas 0; mediciones nuevas 0; cálculos nuevos 0; último cálculo 28 → 28; valor razonable 2761344.0000 → 2761344.0000; auditorías conformes 1; alertas de auditoría 0; avisos de error del caso 0; avisos ajenos observados 0; avisos relacionados sin error 0. Evento M02 942.
- **Cumplido:** Lecturas de variaciones, líneas, mediciones, historial, RF-94 y bandeja contrastadas.
- **Falló y por qué:** Ningún incumplimiento observado.
- **Decisión:** APROBADO.

## Comprobaciones API y evidencias

- G33-API-005-01: APROBADO. Ausencias y auditoría RF-94 conformes. Evidencia: resultado.json.
- G33-API-005-02: APROBADO. Ausencias y auditoría RF-94 conformes. Evidencia: resultado.json.

## Incidencias de producto

No se confirmaron incidencias de producto.

## Problemas técnicos y análisis de causas

Ninguno observado. Las respuestas HTTP por sí solas no prueban causa raíz.

## Cierre y rollback

DELETE HTTP 200; rollback verificado: DELETE 200; eventos M02, auditoría RF-94 y registros financieros del RUN ausentes en lecturas públicas.. Lecturas poscierre de eventos M02 y auditoría RF-94 incluidas solo si DELETE fue 200.

## Conclusión y acciones

Oráculo completo demostrado por API pública.

## Herramientas y cierre

Newman: 2 lecturas, 0 aserciones fallidas. Cypress: 0, sin UI requerida.
