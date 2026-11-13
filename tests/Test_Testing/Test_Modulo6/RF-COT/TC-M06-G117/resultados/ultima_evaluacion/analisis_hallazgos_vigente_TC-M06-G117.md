# TC-M06-G117 — Analisis de hallazgos (ultima evaluacion)

- Generado: 2026-11-13T03:43:45.020490+00:00
- Dictamen: **RECHAZADO**
- Motivo: Uno o mas escenarios no cumplen la expectativa de la matriz (ver DISC-G117-01 si aplica)
- 49b ejecutado: False

## Escenarios

### 48a — Valor propuesto cero
- Estado: **RECHAZADO**
- Esperado: HTTP 422 `VALOR_COTIZACION_INVALIDO`
- Real: HTTP 400 `VAL_ENTRADA`
- Motivo: Esperado HTTP 422 VALOR_COTIZACION_INVALIDO; recibido HTTP 400 VAL_ENTRADA.

### 48b — Valor propuesto negativo
- Estado: **RECHAZADO**
- Esperado: HTTP 422 `VALOR_COTIZACION_INVALIDO`
- Real: HTTP 400 `VAL_ENTRADA`
- Motivo: Esperado HTTP 422 VALOR_COTIZACION_INVALIDO; recibido HTTP 400 VAL_ENTRADA.

### 49a — Vencimiento anterior a emision
- Estado: **APROBADO**
- Esperado: HTTP 422 `FECHA_VENCIMIENTO_INVALIDA`
- Real: HTTP 422 `FECHA_VENCIMIENTO_INVALIDA`
- Motivo: HTTP 422 FECHA_VENCIMIENTO_INVALIDA; sin persistencia.

## Discrepancias confirmadas

- **DISC-G117-01** (48a): matriz `HTTP 422 VALOR_COTIZACION_INVALIDO` vs real `HTTP 400 VAL_ENTRADA`
- **DISC-G117-01** (48b): matriz `HTTP 422 VALOR_COTIZACION_INVALIDO` vs real `HTTP 400 VAL_ENTRADA`

## Proteccion de datos

- Delta cotizaciones: 0 (7 -> 7)
- Delta eventos COTIZACION_REGISTRADA: 0 (5 -> 5)
- Reservadas 9/10 intactas: True
- Periodo 220: {"encontrado": true, "id_periodo_contable": 220, "estado": "ABIERTO", "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-30", "fecha_cierre": null, "razon_social": "QA M06 Operaciones SAS"}
