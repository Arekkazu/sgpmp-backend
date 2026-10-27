# TC-M03-092

Reevaluación 2026-10-25.

## Identificador y RF

**TC-M03-092** (G55). RF-56. Fragmentar paquetes >500 registros en bloques ≤500.

## Runner

- `test_tc_m03_092_un_evento_un_paquete_sin_partir` → **PASSED**, EXIT=0 (un evento → un paquete en memoria).
- `test_tc_m03_092_fragmentacion_501` → **SKIPPED**, EXIT=0: el consolidado no parte 501 registros; `max_length=500` de `POST /iot/telemetria/batch` es RF-53.

## Estado funcional

Construcción 1:1 **comprobada en memoria**. Fragmentación 501: **BLOQUEADO** / no implementada. No se envió HTTP. INC-M03-112-G55.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m03_092_un_evento_un_paquete_sin_partir.*`  
`evidencias/reeval-2026-10-25/test_tc_m03_092_fragmentacion_501.*`
