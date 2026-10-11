# INC-M02-34-G29/G31 v2.0 — tipo_evento incorrecto al consultar un lote POBLACIONAL

**RF:** RF-36 (Gestión Poblacional de Activos Biológicos).
**Issue:** #346.

## Qué reportó QA

`modulo2.bitacora_auditoria_m02` registra consultas de lotes POBLACIONALES con
`tipo_evento='ACTIVO_INDIVIDUAL_CONSULTA'` (el de RF-35, gestión individual). El campo
`tipo_activo` sí guarda `'POBLACIONAL'` correctamente, pero `tipo_evento` no distingue.
Casos reportados: `id_bitacora=1898` (lote 344, G31) e `id_bitacora=1302` (lote 300, G29).

## Causa raíz

`GET /activos-biologicos/{id_activo}` es un único endpoint para ambos tipos de activo, resuelto
por `ConsultarActivoUseCase` (`gestion/consultar_activo_use_case.py`). Ese use case emitía siempre
`rf_origen='RF35', tipo_evento='ACTIVO_INDIVIDUAL_CONSULTA'` al registrar el evento en bitácora
(RF-52), sin mirar `activo.tipo`. Único punto de emisión — no hay otro call site con el mismo bug.

`tipo_evento` es `String(80)` en `modulo2.bitacora_auditoria_m02` (sin `CHECK` ni enum de
Postgres), así que no hizo falta ninguna migración para el nuevo valor.

## Fix

`ConsultarActivoUseCase.execute` ahora distingue por `activo.tipo` antes de emitir el evento:

- `INDIVIDUAL` → `rf_origen='RF35', tipo_evento='ACTIVO_INDIVIDUAL_CONSULTA'` (sin cambios).
- `POBLACIONAL` → `rf_origen='RF36', tipo_evento='ACTIVO_POBLACIONAL_CONSULTA'` (nuevo).

`ACTIVO_POBLACIONAL_CONSULTA` no está en el catálogo de tipos de evento que RF-52 documenta
explícitamente para RF-36 (`POBLACION_ACTUALIZADA`, `METRICA_POBLACIONAL_RECALCULADA`,
`DENSIDAD_EXCEDIDA_DETECTADA`) — ese catálogo no incluye un evento de solo-lectura para RF-36,
igual que le faltaba a RF-34/46/47 antes de implementarse. Se sigue el mismo patrón exacto que ya
usa RF-35 para su propia consulta (`ACTIVO_INDIVIDUAL_CONSULTA`, tampoco documentado ahí), en vez
de forzar un evento de escritura sobre una operación de lectura.

Se corrige también la tabla de referencia `rf_origen`/`tipo_evento` de
`curls_m02_cu13_bitacora_auditoria.md`, que no tenía fila para RF-36 (lectura).

## Pruebas

`tests/biological_assets/test_consultar_activo_use_case_bitacora_tipo_evento.py` — 2 casos:
consulta de activo POBLACIONAL emite RF36/ACTIVO_POBLACIONAL_CONSULTA; consulta de INDIVIDUAL
conserva RF35/ACTIVO_INDIVIDUAL_CONSULTA (regresión). Suite completa de `biological_assets`:
220 passed, mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, ya presentes en `fix/m02`).
