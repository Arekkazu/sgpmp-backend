# Reorganización de resultados — Sesión 2026-10-30

## Contexto
La sesión del 30/10/2026 tuvo dos ejecuciones:
- 12:50 → RECHAZADO (fixture sucio: seleccionaba inferencia bb6d3a2d con 1 retro preexistente, produciendo num=3 en vez de 2)
- 13:09 → APROBADO (fixture limpio: prioriza IDs sin retros preexistentes, produciendo num=2 correctamente)

## Regla aplicada
Según el estándar del equipo QA: en una misma sesión de reevaluación, las ejecuciones se sobreescriben. Solo el último resultado de la sesión queda en `resultados/` como vigente. Los intermedios se archivan en `evidencias/` para trazabilidad.

## Acciones
- RECHAZADO del 30/10 12:50 → movido a `evidencias/run-20261030/rechazado_reintento1/`
- APROBADO del 30/10 13:09 → renombrado a `resultados/resultado_TC-M04-G085_reintento1.{html,json}`
- V1 del 25/10 → intacto como `resultado_TC-M04-G085.{html,json}`

## Resultado
- `resultados/` contiene: V1 (histórico) + reintento1 (APROBADO, vigente)
- Scanner: veredicto APROBADO, archivo tomado `resultado_TC-M04-G085_reintento1.json`

