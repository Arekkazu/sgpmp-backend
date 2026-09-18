# TC-M02-G15 (issue #326) — PATCH /activos-biologicos/{id} no aplicaba alcance de finca (BOLA, OWASP API1)

**RF:** RF-35 (edición de activos biológicos individuales).
**Endpoint:** `PATCH /activos-biologicos/{id_activo}`.
**Categoría:** OWASP API1:2023 (Broken Object Level Authorization).

## Qué reportó QA

Usuario `m2m.nuevo@ejemplo.com` (alcance finca 57) pudo modificar mediante
`PATCH /activos-biologicos/350` (activo de finca 65, fuera de su alcance) —
`HTTP 200` y el cambio quedó persistido. `GET /activos-biologicos/350` para
el mismo usuario sí devuelve `404 ACTIVO_NO_ENCONTRADO` correctamente.

## Causa raíz

El GET (`consultar_activo` → `ConsultarActivoUseCase`) ya filtra por finca
desde INC-M02-39-G27 (RF-25): el router calcula
`ids_fincas_permitidas=_ids_fincas_alcance(db, usuario_actual)` y lo pasa al
use case, que lo reenvía a
`repo.obtener_por_id(id_activo, ids_fincas_permitidas=...)` —
`SqlAlchemyActivoBiologicoRepository.obtener_por_id` ya soporta ese kwarg y
devuelve `None` cuando la infraestructura del activo no pertenece a ninguna
finca del alcance (traducido a 404 por el use case).

El PATCH (`actualizar_activo_individual` → `ActualizarActivoIndividualUseCase`)
**nunca calculaba ni pasaba ese parámetro** — ni el router lo hacía, ni el
use case lo aceptaba — así que `self.repo.obtener_por_id(id_activo)` cargaba
el activo de cualquier finca, la mutación de dominio se aplicaba y
`self.repo.actualizar_detalle_individual(activo)` la persistía sin ningún
control de alcance.

## Fix

Reutiliza exactamente el mismo mecanismo que ya usa el GET, no uno nuevo:

- Router: `actualizar_activo_individual` ahora calcula
  `ids_fincas_permitidas=_ids_fincas_alcance(db, usuario_actual)` y lo pasa a
  `use_case.execute(...)`.
- `ActualizarActivoIndividualUseCase.execute`/`_execute`: aceptan
  `ids_fincas_permitidas: list[int] | None = None` y lo reenvían a
  `self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=...)` — mismo
  método del repositorio, mismo kwarg, sin cambios en la capa de
  infraestructura.

**Código HTTP:** igual que el GET — `NotFoundError` (404), no `403`. Mismo
patrón de seguridad ya establecido en este repo (no revelar existencia de un
recurso fuera de alcance vía 403 vs 404).

## Verificación

- 3 tests nuevos en
  `test_actualizar_activo_individual_use_case_alcance_finca.py` (mismo
  patrón que `test_consultar_activo_use_case_alcance_finca.py`, el test ya
  existente para el GET): activo de otra finca → 404, sin persistir; activo
  de la propia finca → se actualiza normalmente; alcance global (`None`,
  ej. Administrador) → no filtra.
- End-to-end contra datos reales de `sgpmp` (activo 3, finca 2 — no existe
  localmente el activo 350/finca 65 exacto del reporte, pero mismo patrón):
  usuario con alcance `[1]` → `NotFoundError ACTIVO_NO_ENCONTRADO` (antes del
  fix habría sido `200` + persistencia); usuario con alcance `[1, 2]` →
  actualización exitosa. DB confirmada sin cambios tras la corrida (rollback).
