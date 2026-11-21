# Diseño adaptado de TC-M06-G106

TC-M06-30 valida la corrección histórica de un precio. La corrección es un
`POST /finanzas/precios` que inserta un registro nuevo con `id_precio_corregido: 436`.
El precio 436 permanece en el historial con estado `CORREGIDO`.

Este diseño incorpora la aclaración funcional de Alex y el PR #1074
(`fix(rf89): la corrección de un precio ocupa su lugar…`), fusionado en `dev`
el 2026-11-11. Análisis aprobó la regla como **RF-89 v1.2** (RFC-026) en el
comentario del mismo PR. En este repositorio no hay una copia editable del RF;
no se inventó ni se modificó el requisito.

## Reglas funcionales aplicables

- La corrección hereda la fecha de vigencia del precio original. No se envía
  `fecha_vigencia` (o, si se envía, debe ser exactamente la del original).
- Si se envía otra fecha: HTTP 400 `FECHA_VIGENCIA_CORRECCION`.
- Especie, categoría, producto y fuente deben coincidir: si no,
  HTTP 400 `CORRECCION_NO_COINCIDE`.
- Un precio ya corregido no se corrige otra vez: HTTP 409 `PRECIO_YA_CORREGIDO`.
- La desviación (FA-7) se calcula contra el precio que se corrige, no contra el
  precio aplicado hoy.
- El original queda `CORREGIDO` y deja de contar para el precio aplicado.
- La corrección histórica queda `SUPERADO` cuando existe un precio más reciente
  (645) que permanece `ACTIVO` y aplicado.

## Datos del escenario positivo

| Dato | Valor |
| --- | --- |
| Especie | 424 |
| Categoría | `POR_CABEZA` |
| Fuente | `MERCADO_ACTIVO` |
| Precio corregido | 436 / $4.000.000 / vigencia 2026-11-01 |
| Precio aplicado | 645 / $7.650.000 / vigencia 2026-11-11 |
| Importe de la corrección | $4.200.000 |
| Desviación | 5 % contra 436 |
| Umbral vivo esperado | 50,00 |
| `fecha_vigencia` en el body | omitida (heredada) |
| `fecha_vencimiento` | ninguna |
| `confirmar_desviacion` | falso (5 % < 50 %) |

Resultado esperado: HTTP 201; 436 `CORREGIDO`; corrección `SUPERADO`; 645
`ACTIVO` y aplicado.

## Escenarios negativos

1. Segunda corrección del 436 → 409 `PRECIO_YA_CORREGIDO`.
2. Fecha distinta a la del 436 → 400 `FECHA_VIGENCIA_CORRECCION`.
3. Fuente distinta → 400 `CORRECCION_NO_COINCIDE`.

## Diferencia respecto a la preparación del 11-nov

La preparación anterior asumía el código previo al PR #1074: desviación contra
el 645, fecha elegida por QA y estados sin `CORREGIDO`. Esa lectura queda
obsoleta frente a RF-89 v1.2. La primera evaluación del 8-nov se conserva
intacta en `resultados/primera_evaluacion/`.

| Archivo | SHA-256 |
| --- | --- |
| `evidencia_peticiones_TC-M06-G106.json` | `DDE55154CECD2593F47E5260E66D095A183C9009974215AE60A7C06694D28B5E` |
| `resultado_ejecucion_TC-M06-G106.html` | `0F9BDA12419A475123FF719EE67FA5840452B741E0794DF4648624FDA811FD91` |
| `resumen_ejecucion_TC-M06-G106.json` | `9EA467A90E5D8E2EE90D00BE3164C42A9F9345CC72C52EED1BF8EF362C7D6DEA` |
