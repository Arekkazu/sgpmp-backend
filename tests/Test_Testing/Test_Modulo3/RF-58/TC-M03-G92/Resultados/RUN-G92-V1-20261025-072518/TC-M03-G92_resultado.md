# TC-M03-G92 — resultado RUN-G92-V1-20261025-072518

## Identificación

Grupo G92; casos TC-M03-181, TC-M03-182, TC-M03-183; RF-58/CU04; V1; RUN RUN-G92-V1-20261025-072518; ambiente TEST; autorización AUT-G92-V1-20261025; commit NO_VERIFICADO; Node v22.15.1; Newman 0 ejecuciones; Cypress no exigido.

## Resumen de veredictos

| Caso | Funcional | Técnico |
|---|---|---|
| TC-M03-181 | SIN VEREDICTO | NO_CONCLUYENTE |
| TC-M03-182 | SIN VEREDICTO | NO_CONCLUYENTE |
| TC-M03-183 | SIN VEREDICTO | NO_CONCLUYENTE |

## Esperado y observado por caso

### TC-M03-181

Esperado: Resumen ROJO como peor estado entre VERDE, AMARILLO y ROJO; alertas activas y timestamp de actualización.

Observado: null

Comprobaciones: ninguna.

### TC-M03-182

Esperado: El monitoreo filtrado muestra solo sensores e información de la unidad seleccionada, sin datos de otras unidades.

Observado: null

Comprobaciones: ninguna.

### TC-M03-183

Esperado: Con 60 sensores y único ROJO en posición 55, pagina=1&por_pagina=50 mantiene estado_general=ROJO aunque el sensor ROJO no figura en la página.

Observado: null

Comprobaciones: ninguna.

## Comprobaciones API/UI

| Caso | ID | Tipo | Estado | Valor observado | Evidencia |
|---|---|---|---|---|---|


UI no exigida por la matriz.

## Observaciones documentales

- API-181-03: sin observación de TEST; pendiente del GET inicial autorizado. La discrepancia matriz–RF-58 requiere revisión documental por el responsable QA.

## Evidencias reales

- [preflight.json](preflight.json)
- [resultado.json](resultado.json)
- [TC-M03-G92_resultado.md](TC-M03-G92_resultado.md)

## Incidencias de producto

Ninguna confirmada.

## Incidencias técnicas QA

- The operation was aborted due to timeout

## Bitácora

- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- GET /usuarios/me: HTTP 200, en RUN true, eco true
- GET /iot/monitoreo/dashboard?pagina=1&por_pagina=50: HTTP ERROR, en RUN true, eco N/A
- DELETE /test-control/runs/G92-V1-20261025-072518: HTTP 200, en RUN false, eco N/A
- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- GET /iot/monitoreo/dashboard?pagina=1&por_pagina=50: HTTP ERROR, en RUN false, eco N/A

## Análisis de causas

El código local es orientación; ninguna causa raíz se atribuye sin evidencia de TEST. Los fallos de precondición, entorno o automatización no constituyen veredicto de producto.

## Cierre y rollback

DELETE: HTTP 200; rollback NO CONFIRMADO. The operation was aborted due to timeout Comprobaciones: 0; riesgos residuales: No hay GET público de sensor independiente del dispositivo ni GET directo de estado actual..

## Conclusión y acción concreta

Estado NO_CONCLUYENTE. Responsable QA debe revisar el cierre y la evidencia faltante antes de cerrar.
