# INC-M02-71-G48 — Alcance por finca en registro de eventos de crecimiento

**RF:** RF-40 — Registro de eventos de crecimiento (CU06)
**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/crecimiento`
**Estado QA:** hallazgo no confirmado funcionalmente (observación de revisión estática, `OBS-G48-01`), pedía confirmar y corregir si aplicaba.

## Causa raíz (confirmada)

Las rutas de consulta de este módulo resuelven el activo pasando explícitamente
`ids_fincas_permitidas=_ids_fincas_alcance(db, usuario_actual)` a
`obtener_por_id`, que en el repository real filtra: si la infraestructura del
activo no pertenece a ninguna finca permitida, retorna `None` (se trata como
inexistente, no se revela con un 403 que la fila sí existe).

`RegistrarEventoCrecimientoUseCase.execute()` llamaba `obtener_por_id(id_activo)`
sin ese parámetro — el router (`activo_biologico_router.py`) nunca lo
calculaba ni lo pasaba. Un usuario con permiso de creación (ej. Productor)
podía potencialmente registrar un evento de crecimiento sobre un activo de
una finca fuera de su alcance: autorización horizontal (BOLA).

## Fix

- `RegistrarEventoCrecimientoUseCase.execute()` gana el parámetro opcional
  `ids_fincas_permitidas: list[int] | None = None`, propagado a
  `obtener_por_id`.
- El router calcula `_ids_fincas_alcance(db, usuario_actual)` y lo pasa,
  igual que ya hacía `consultar_eventos` en el mismo archivo.

Sin cambios de esquema de BD.

## Hallazgo adicional — fuera de alcance de este fix

Al buscar el patrón `obtener_por_id(id_activo)` sin `ids_fincas_permitidas`
para confirmar que el fix seguía la convención correcta, aparece la misma
llamada (sin alcance) en casi todos los demás use cases de escritura del
módulo: `asociar_sensor_activo_use_case.py`, `cambiar_fase_use_case.py`,
`registrar_evento_sanitario_use_case.py`, `registrar_evento_productivo_use_case.py`,
`cambiar_estado_use_case.py`, `registrar_evento_baja_use_case.py`,
`cerrar_ciclo_use_case.py`, `registrar_transferencia_use_case.py`,
`actualizar_activo_individual_use_case.py`, `registrar_evento_reproductivo_use_case.py`.

Es la misma clase de gap que este issue, pero **no se corrige aquí** —
excede el alcance de INC-M02-71-G48 (que es específicamente sobre RF-40 /
crecimiento) y varios de esos archivos ya están siendo tocados por otros
issues de esta misma cadena (transferencias por INC-M02-72/73/74-G80,
eventos reproductivos por INC-M02-75/76-G53/G55). Queda documentado aquí
para que se abra un issue de auditoría general del patrón si el equipo
decide priorizarlo.

## Pruebas

`tests/biological_assets/test_registrar_evento_crecimiento_alcance_finca.py`
(nuevo, 2 casos: activo fuera de alcance → `NotFoundError`/`ACTIVO_NO_ENCONTRADO`;
alcance global no filtra). Suite completa `tests/biological_assets/`: 92 passed,
sin regresiones.
