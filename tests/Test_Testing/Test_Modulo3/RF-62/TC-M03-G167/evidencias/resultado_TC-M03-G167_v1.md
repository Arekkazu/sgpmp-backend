# TC-M03-G167 — Resultado

**Veredicto**: RECHAZADO POR BLOQUEO EXTERNO
**Fecha**: 2026-10-23
**Ejecutado**: PARCIAL (8/43 requests exitosos antes del bloqueo)

## Resumen

Preflight avanzó hasta `00.06-Crear-Dispositivo` (201). Falla en
`00.07-Crear-Sensor` con HTTP 500 `ERROR_INTERNO`. Efecto dominó: los 7
escenarios no pudieron ejecutarse.

## INC bloqueante

`INC-M03-G167-SENSOR-500`: `POST /configuracion/dispositivos-iot/{id}/sensores`
retorna 500. Causa raíz: `SensorModel.es_activo` es `nullable=False` sin
`default` ni `server_default`, y el DTO `RegistrarSensorDTO` no lo expone.
El `flush()` inserta NULL → IntegrityError → InfrastructureError → 500.
Fix requiere cambio en backend (default en modelo o set en entidad).

## Evidencia

- Reporte HTML: `resultados/resultado_TC-M03-G167.html`
- Consola: `evidencias/console_run.log`
- Sandbox cerrado: 200 OK

## INCs relacionados vigentes

- `INC-M03-RF57-NOT-EMITTED` (impactaría 3A.05/3B.05)
- `INC-M03-G167-SEED` (modulo9.calibraciones vacía para re-corrida post-fix)
