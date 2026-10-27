# TC-M03-G92 — resultado RUN-G92-V1-20261025-075632

## Identificación

Grupo G92; casos TC-M03-181, TC-M03-182, TC-M03-183; RF-58/CU04; V1; RUN RUN-G92-V1-20261025-075632; ambiente TEST; autorización AUT-G92-V1-R2-20261025; commit NO_VERIFICADO; Node v22.15.1; Newman 0 ejecuciones; Cypress no exigido.

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

- POST_/configuracion/dispositivos-iot/522/sensores_HTTP_500

Historial técnico conservado: RUN-G92-V1-20261025-072518, intento 1; GET /iot/monitoreo/dashboard?pagina=1&por_pagina=50 agotó 30 s dentro del RUN y después del DELETE. Incidencia técnica QA pendiente: esos GET globales pudieron activar el correo RF-58 E7; envío no confirmado y sin atribución al producto.

## Bitácora

- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- GET /usuarios/me: HTTP 200, en RUN true, eco true
- GET /configuracion/fincas/184: HTTP 200, en RUN true, eco true
- GET /configuracion/infraestructuras/349: HTTP 200, en RUN true, eco true
- GET /configuracion/dispositivos-iot/357: HTTP 200, en RUN true, eco true
- GET /configuracion/dispositivos-iot/357/sensores: HTTP 200, en RUN true, eco true
- GET /configuracion/umbrales?id_especie=126: HTTP 200, en RUN true, eco true
- GET /configuracion/sensores/552/asociaciones: HTTP 200, en RUN true, eco true
- GET /configuracion/sensores/552/calibraciones: HTTP 200, en RUN true, eco true
- GET /iot/alertas?id_sensor=552&fecha_desde=2026-10-25T07%3A54%3A32.634Z&fecha_hasta=2026-10-26T07%3A56%3A32.634Z&por_pagina=200: HTTP 200, en RUN true, eco true
- GET /configuracion/sensores/737/asociaciones: HTTP 200, en RUN true, eco true
- GET /configuracion/sensores/737/calibraciones: HTTP 200, en RUN true, eco true
- GET /iot/alertas?id_sensor=737&fecha_desde=2026-10-25T07%3A54%3A32.634Z&fecha_hasta=2026-10-26T07%3A56%3A32.634Z&por_pagina=200: HTTP 200, en RUN true, eco true
- GET /iot/monitoreo/historial?fecha_inicio=2026-10-25&fecha_fin=2026-10-25&id_infraestructura=349&por_pagina=500: HTTP 200, en RUN true, eco true
- POST /configuracion/infraestructuras: HTTP 201, en RUN true, eco true
- GET /configuracion/infraestructuras/512: HTTP 200, en RUN true, eco true
- POST /configuracion/infraestructuras: HTTP 201, en RUN true, eco true
- GET /configuracion/infraestructuras/513: HTTP 200, en RUN true, eco true
- POST /configuracion/dispositivos-iot: HTTP 201, en RUN true, eco true
- POST /configuracion/dispositivos-iot: HTTP 201, en RUN true, eco true
- POST /configuracion/dispositivos-iot/522/sensores: HTTP 500, en RUN true, eco true
- DELETE /test-control/runs/G92-V1-20261025-075632: HTTP 200, en RUN false, eco N/A
- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- POST /sesiones/: HTTP 200, en RUN false, eco N/A
- GET /iot/monitoreo/historial?fecha_inicio=2026-10-25&fecha_fin=2026-10-25&id_infraestructura=512&por_pagina=500: HTTP 200, en RUN false, eco N/A
- GET /iot/monitoreo/historial?fecha_inicio=2026-10-25&fecha_fin=2026-10-25&id_infraestructura=513&por_pagina=500: HTTP 200, en RUN false, eco N/A
- GET /configuracion/dispositivos-iot/521/sensores: HTTP 200, en RUN false, eco N/A
- GET /configuracion/dispositivos-iot/521: HTTP 404, en RUN false, eco N/A
- GET /configuracion/dispositivos-iot/522/sensores: HTTP 200, en RUN false, eco N/A
- GET /configuracion/dispositivos-iot/522: HTTP 404, en RUN false, eco N/A
- GET /configuracion/infraestructuras/512: HTTP 404, en RUN false, eco N/A
- GET /iot/monitoreo/dashboard?id_infraestructura=512&pagina=1&por_pagina=50: HTTP 200, en RUN false, eco N/A
- GET /configuracion/infraestructuras/513: HTTP 404, en RUN false, eco N/A
- GET /iot/monitoreo/dashboard?id_infraestructura=513&pagina=1&por_pagina=50: HTTP 200, en RUN false, eco N/A
- GET /configuracion/fincas/184: HTTP 200, en RUN false, eco N/A
- GET /configuracion/infraestructuras/349: HTTP 200, en RUN false, eco N/A
- GET /configuracion/dispositivos-iot/357: HTTP 200, en RUN false, eco N/A
- GET /configuracion/dispositivos-iot/357/sensores: HTTP 200, en RUN false, eco N/A
- GET /configuracion/umbrales?id_especie=126: HTTP 200, en RUN false, eco N/A
- GET /configuracion/sensores/552/asociaciones: HTTP 200, en RUN false, eco N/A
- GET /configuracion/sensores/552/calibraciones: HTTP 200, en RUN false, eco N/A
- GET /iot/alertas?id_sensor=552&fecha_desde=2026-10-25T07%3A54%3A32.634Z&fecha_hasta=2026-10-26T07%3A56%3A32.634Z&por_pagina=200: HTTP 200, en RUN false, eco N/A
- GET /configuracion/sensores/737/asociaciones: HTTP 200, en RUN false, eco N/A
- GET /configuracion/sensores/737/calibraciones: HTTP 200, en RUN false, eco N/A
- GET /iot/alertas?id_sensor=737&fecha_desde=2026-10-25T07%3A54%3A32.634Z&fecha_hasta=2026-10-26T07%3A56%3A32.634Z&por_pagina=200: HTTP 200, en RUN false, eco N/A
- GET /iot/monitoreo/historial?fecha_inicio=2026-10-25&fecha_fin=2026-10-25&id_infraestructura=349&por_pagina=500: HTTP 200, en RUN false, eco N/A

## Análisis de causas

El código local es orientación; ninguna causa raíz se atribuye sin evidencia de TEST. Los fallos de precondición, entorno o automatización no constituyen veredicto de producto.

## Efectos externos potenciales

El baseline de 349 usa configuración, asociaciones, calibraciones, alertas e historial sin dashboard. Antes de cada Newman de A/B se revalida el umbral activo; LECTURA_VALIDA y un umbral no prueban el color del caché. Si algún sensor de la página está almacenado GRIS y no desactualizado, el dashboard puede auditar y enviar correo a Administradores activos; el correo no se revierte por DELETE. El historial registra auditoría incluso después de DELETE. No se da por verificada la ausencia de correos ni la reversión de esas auditorías.

## Cierre y rollback

DELETE: HTTP 200; rollback VERIFICADO. DELETE y GET posteriores acreditan reversión. Comprobaciones: 11; riesgos residuales: No hay GET público de sensor independiente del dispositivo ni GET directo de estado actual..

## Conclusión y acción concreta

Estado NO_CONCLUYENTE. Revisar incidencias funcionales y decidir cierre QA.
