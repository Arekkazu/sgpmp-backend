# TC-M06-G116 — Expectativas funcionales actualizadas

Fuente: aclaraciones del desarrollador en issue #1019 y corrección en #1024.
Este documento actualiza el diseño de re-prueba. **No modifica** las evidencias históricas de la primera evaluación.

| Escenario | HTTP | Código |
|---|---:|---|
| Identificador entero de activo inexistente | 404 | `ACTIVO_NO_ENCONTRADO` |
| Activo existente en estado BAJA | 422 | `ACTIVO_NO_DISPONIBLE` |
| Activo ACTIVO sin valoración razonable vigente | 422 | `VALOR_RAZONABLE_NO_DISPONIBLE` |
| Activo ACTIVO con período contable de la emisión cerrado | 422 | `PERIODO_CONTABLE_CERRADO` |

## Notas

- Los ids de `activos_cotizados` son enteros (no UUID).
- Endpoint: `POST /finanzas/cotizaciones` con `activos_cotizados` y `valor_cotizacion_propuesto` (> 0).
- El período corresponde a la fecha de emisión (`hoy`); **no** debe trasladarse al siguiente período abierto.
- Las solicitudes negativas no deben crear cotizaciones ni eventos `COTIZACION_REGISTRADA`.

## Relación con G88 / #1019

- G88 / #1019: primera evaluación → REQUIERE ACLARACIÓN.
- G116: nueva evaluación separada bajo RF-COT, con expectativas corregidas.
