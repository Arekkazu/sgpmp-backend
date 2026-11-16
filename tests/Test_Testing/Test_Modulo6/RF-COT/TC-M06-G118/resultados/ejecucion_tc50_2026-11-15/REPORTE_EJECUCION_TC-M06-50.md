# Reporte de ejecucion TC-M06-50 — G118

- Fecha UTC: `2026-11-16T03:40:49.847275+00:00`
- HTTP POST: **201**
- id_cotizacion: **15** · estado **COTIZADO** · version **1**
- Dictamen TC-M06-50: **APROBADO** (14/14 CUMPLE)
- Dictamen G118: **APROBADO**
- RF-94: evento **29463** `COTIZACION_REGISTRADA`
- Activo 1571: ACTIVO · VR 3.760.000 sin cambio · sin nuevas lineas
- Periodos: 220 ABIERTO · 219 CERRADO
- AAEF vista-previa 900000003: 422 `PERIODO_NO_CERRADO`

## Criterios

| ID | Criterio | Resultado |
|---|---|---|
| 50.1 | POST HTTP 201 | CUMPLE |
| 50.2 | id_cotizacion presente | CUMPLE |
| 50.3 | Estado COTIZADO | CUMPLE |
| 50.4 | Asociación activo 1571 | CUMPLE |
| 50.5 | VR referencia 3760000 | CUMPLE |
| 50.6 | Activo 1571 permanece ACTIVO | CUMPLE |
| 50.7 | VR neto sin cambio | CUMPLE |
| 50.8 | Fecha cálculo sin cambio | CUMPLE |
| 50.9 | Sin nuevas líneas contables en 220 | CUMPLE |
| 50.10 | Líneas del activo 1571 sin incremento | CUMPLE |
| 50.11 | Auditoría COTIZACION_REGISTRADA | CUMPLE |
| 50.12 | Período 220 ABIERTO | CUMPLE |
| 50.13 | Período 219 CERRADO | CUMPLE |
| 50.14 | AAEF: sin exigir nueva exportación; vista-previa 900000003 sigue PERIODO_NO_CERRADO | CUMPLE |

Nota: 50.11/50.13/50.14 revalidados con login fresco (TOKEN_REVOCADO mid-script en la pasada inicial). Sin POST adicional. Sin commit/push.
