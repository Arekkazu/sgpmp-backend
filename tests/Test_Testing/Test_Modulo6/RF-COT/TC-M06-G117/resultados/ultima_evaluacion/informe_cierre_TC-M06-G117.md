# TC-M06-G117 — Informe de cierre (ejecucion autorizada)

**Dictamen: RECHAZADO**

Uno o mas escenarios no cumplen la expectativa de la matriz (ver DISC-G117-01 si aplica)

- Conteos: {"aprobados": 1, "rechazados": 2, "bloqueados": 0, "ejecutados": 3, "autorizados": 3}
- 49b ejecutado: **No**
- Escritura positiva: **No**

## Resultados

| Escenario | Esperado | Real | Estado |
|---|---|---|---|
| 48a | 422 `VALOR_COTIZACION_INVALIDO` | 400 `VAL_ENTRADA` | RECHAZADO |
| 48b | 422 `VALOR_COTIZACION_INVALIDO` | 400 `VAL_ENTRADA` | RECHAZADO |
| 49a | 422 `FECHA_VENCIMIENTO_INVALIDA` | 422 `FECHA_VENCIMIENTO_INVALIDA` | APROBADO |

## Proteccion

- Cotizaciones: 7 -> 7 (delta 0)
- Eventos COTIZACION_REGISTRADA: 5 -> 5 (delta 0)
- Cotizaciones 9 y 10 intactas: True
- Periodo 220 final: `ABIERTO`

## Evidencias

`tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G117/resultados/ultima_evaluacion/`

No se ejecuto commit ni push.
