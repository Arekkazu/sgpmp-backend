# HALLAZGO — TC-M03-G44

| Campo | Valor |
|---|---|
| Resultado | **NO CUMPLE** |
| Tipo de reporte | ERROR |
| Categoría | FUNCIONAL |
| Criticidad | MEDIA |
| Estado del reporte | **RECHAZADO** |
| Requisito | RF-55.1 — Procesamiento Edge Básico y Detección de Desviaciones por Umbrales |
| Caso de prueba | TC-M03-G44 |
| Subcasos | TC-M03-079, TC-M03-096 |
| Fecha de inspección | 2026-10-31 |
| Firmware inspeccionado | `.worktrees/sgpmp-rf55-validation` (`qa/rf55-validation-e618a75`, HEAD `e618a75`) |

Este documento **no** sustituye los resultados SKIPPED de 2026-10-25 (`TC-M03-079_resultado.md`, `TC-M03-096_resultado.md`). No se reejecutaron pruebas ni se modificó firmware, SQL ni evidencias previas.

---

## Descripción

Durante la inspección estática del firmware Edge se identificó que el evaluador básico implementado en `raspberry/edge_agent/reglas/evaluador.py` clasifica las mediciones mediante **bandas absolutas** de RF-17 (`normal` / `precaucion` / `critico`).

RF-55.1 versión 1.0 establece que la severidad debe calcularse con el **porcentaje de desviación** respecto al umbral mínimo o máximo:

- Si `valor > umbral_max`: `(valor - umbral_max) / umbral_max * 100`
- Si `valor < umbral_min`: `(umbral_min - valor) / umbral_min * 100`
- LEVE: desviación ≤ 10 %
- MODERADO: desviación > 10 % y ≤ 25 %
- CRÍTICO: desviación > 25 %
- Si el umbral usado como divisor es cero: `ERROR_CONFIGURACION` (sin división por cero)

El firmware inspeccionado **no contiene** esa fórmula ni los cortes 10 % / 25 %. Cualquier valor fuera de `[valor_min, valor_max]` se clasifica como **CRÍTICO** (`fuera_de_rango`). RF-55.1 simple **no emite LEVE**.

## Evidencia técnica

- `raspberry/edge_agent/reglas/evaluador.py` L72–76: mapa `_GRAVEDAD` / `_SEVERIDAD` (`precaucion` → MODERADO; `critico` y `fuera_de_rango` → CRITICO).
- Mismo archivo L104–155: `evaluar_simple`.
- Mismo archivo L164–179: `clasificar` por bandas RF-17.
- `raspberry/edge_agent/reglas/evento.py` L74–94: payload; la severidad **sí** se calcula en Edge y se conserva al publicar o al buffer.

## Escenarios TC-M03-G44 (9.9 %, 10.0 %, 10.1 %, 24.9 %, 25.0 %, 25.1 %)

Con `umbral_min` / `umbral_max` como extremos de la fórmula, los seis puntos quedan fuera del intervalo. El firmware devolvería **CRITICO** en todos. RF-55.1 v1.0 espera LEVE, LEVE, MODERADO, MODERADO, MODERADO, CRÍTICO.

Solo 25.1 % coincidiría, de forma accidental (todo fuera de rango es CRÍTICO).

## Discrepancia entre fuentes

| Fuente | Comportamiento en 10.0 % y 25.0 % |
|---|---|
| RF-55.1 v1.0 | LEVE si ≤ 10 %; MODERADO si > 10 % y ≤ 25 %; CRÍTICO si > 25 % |
| SQL `modulo3.fn_clasificar_severidad` | Misma inclusividad (`<= 10` LEVE, `<= 25` MODERADO) |
| Firmware Edge | No usa porcentaje; fuera de rango = CRITICO |

SQL y el texto v1.0 coinciden en los seis cortes. El incumplimiento es del **algoritmo Edge** (y el camino HTTP de `sgpmp-backend` no recalcula la severidad).

Observación: `valor_min = 0` con rango válido se **acepta** en Edge; v1.0 exigiría `ERROR_CONFIGURACION` si 0 se usara de divisor.

## Impacto

Los escenarios de desviación leve y moderada no pueden clasificarse conforme a RF-55.1. Eso produce eventos mal etiquetados y puede afectar la priorización en RF-57.

## Conclusión y decisión pendiente

El firmware clasifica en el nodo, pero el algoritmo **no satisface** la regla porcentual de RF-55.1 v1.0. TC-M03-G44 queda **RECHAZADO / NO CUMPLE**.

**La decisión funcional de Producto sigue pendiente** antes de modificar la implementación o aprobar el caso:

1. ¿La regla vigente es la porcentual v1.0 (alineada con SQL) o las bandas RF-17 del firmware?
2. Si gana v1.0: cambiar Edge; no aprobar G44 hasta entonces.
3. Si ganan las bandas RF-17: actualizar RF-55.1 / G44 (discrepancia documental, no defecto de firmware).

No se modificó firmware, funciones SQL ni resultados de pytest.
