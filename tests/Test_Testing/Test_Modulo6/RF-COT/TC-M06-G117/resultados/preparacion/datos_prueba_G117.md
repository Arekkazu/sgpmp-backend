# TC-M06-G117 — Datos de prueba

Fuente: GET de solo lectura en TEST (2026-11-13), Contador.

| Campo | Valor | Verificado |
|---|---|---|
| Activo | 1569 | HTTP 200 |
| Identificador | `QA-M06O-VR-01` | Sí |
| Titular | NIT 900000003 · QA M06 Operaciones SAS | Sí |
| Finca | 467 | Sí |
| Estado activo | ACTIVO | Sí |
| Indicador valoración | VALOR_RAZONABLE (reconocimiento CONFIRMADO) | Sí |
| Último VR neto | `3760000.0000` | Sí (cálculo vigente) |
| Periodo | 220 · 2026-11-01 a 2026-11-30 · ABIERTO | Sí |
| Valor propuesto válido (49a/49b) | `1000.0000` (dato de prueba; no es VR) | Preparado |
| Baseline cotizaciones (no alterar) | ids 10, 9, 8, 7, 6, 4, 5; sobre 1569: **9, 10** | Solo lectura |

## Restricciones operativas

- No cerrar el período 220.
- No utilizar el período 219.
- No modificar el activo 1569 ni sus valoraciones.
- No utilizar datos del titular 900000001.
- No alterar cotizaciones existentes (en particular 9 y 10 sobre 1569).
- No ejecutar operaciones financieras ajenas a este caso.
- No enviar POST de cotizaciones hasta autorización expresa de ejecución G117.
