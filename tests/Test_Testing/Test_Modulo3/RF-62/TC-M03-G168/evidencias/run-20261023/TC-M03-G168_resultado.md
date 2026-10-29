# TC-M03-G168 — Resultado V1

**Veredicto**: RECHAZADO POR BLOQUEO EXTERNO
**Fecha**: 2026-10-23
**Ejecutado**: PARCIAL (preflight hasta crear sensor)

## Resumen

La suite se ejecutó hasta `00.06-Crear-Dispositivo` (201). Falla en
`00.07-Crear-Sensor` con HTTP 500 ERROR_INTERNO por el mismo bug
documentado en INC-M03-G167-SENSOR-500.

Los 4 subcasos (TC-312, TC-316, TC-317, TC-323) no pudieron ejecutarse.

## INCs bloqueantes (V1)

- `INC-M03-G167-SENSOR-500`: `es_activo` NOT NULL sin default en `SensorModel`
- `INC-M03-G168-GAP-NOT-IMPLEMENTED`: `gap_temporal_anomalo` comentado en Fase 5

## Hallazgos de requerimiento (documentados, no bloqueantes de V1)

- σ muestral vs poblacional (TC-312c) — oráculo ajustado al código
- frecuencia 5 min vs 10 min (TC-316) — discrepancia CSV/código
- periodo_inactividad no creable vía API (TC-316c) — bloqueado

## Evidencia

- Reporte HTML: `resultados/resultado_TC-M03-G168.html`
- Consola: `evidencias/console_run.log`
- Sandbox cerrado: sí (DELETE /test-control/runs/{run_id} devolvió 200)

## Listo para V2 (cuando se resuelvan los INCs)

- Renombrar a `resultado_TC-M03-G168_reintento1.{html,json}`
- Conservar V1 como evidencia del bloqueo original
- TC-316 seguirá fallando hasta que se implemente `gap_temporal_anomalo`
