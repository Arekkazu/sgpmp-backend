# TC-M06-G116 — Analisis de hallazgos vigente

**Resultado:** APROBADO 2/2 (100 %)

## Escenarios

| ID | Subcaso | Esperado | HTTP | Code | Estado |
|---|---|---|---:|---|---|
| 46a | TC-M06-46 | 404 ACTIVO_NO_ENCONTRADO | 404 | ACTIVO_NO_ENCONTRADO | APROBADO |
| 46b | TC-M06-46 | 422 ACTIVO_NO_DISPONIBLE | 422 | ACTIVO_NO_DISPONIBLE | APROBADO |
| 47a | TC-M06-47 | 422 VALOR_RAZONABLE_NO_DISPONIBLE | 422 | VALOR_RAZONABLE_NO_DISPONIBLE | APROBADO |
| 47b | TC-M06-47 | 422 PERIODO_CONTABLE_CERRADO | 422 | PERIODO_CONTABLE_CERRADO | APROBADO |

## Persistencia

- Delta cotizaciones: 0 (7 -> 7)
- Delta eventos COTIZACION_REGISTRADA: 0 (5 -> 5)
- Periodo 220: ABIERTO
- Periodo 219: CERRADO
- Cotizaciones reservadas 6/7/9/10 intactas

## Dictamen

- TC-M06-46: **APROBADO**
- TC-M06-47: **APROBADO**
- G116: **APROBADO 2/2**

## Antecedente

Diagnostico de despliegue #1024 en TEST: `antecedentes/diagnostico_despliegue_1024_TEST.md` (CONFIRMADO_DESPLEGADO). No es evidencia funcional de los POST.
