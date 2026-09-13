# TC-M02-G42 — Resultado de ejecución

**Estado general: PASS — 10/10 tests, vía Pytest contra el backend TEST y la base de datos de TEST desplegados.**

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G42 (TC-M02-080) |
| RF / CU | RF-39 / CU-05 |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` + BD `158.69.200.27:5448/sgpmp_test` |
| Activo de prueba | `id_activo_biologico=218` (individual) |
| Evento de prueba | `id_eventos=187` (sanitario, `CONTROL_PREVENTIVO`) |
| Fecha de ejecución | 2026-09-10, ~02:00–02:04 UTC |

## Capa 1 — API: no existe endpoint de edición/eliminación

Se registró un evento real y se intentó `DELETE`/`PATCH` sobre 5 patrones de URL plausibles:

```
DELETE /activos-biologicos/218/eventos/187                  → 404
DELETE /activos-biologicos/eventos/187                      → 404
DELETE /eventos/187                                          → 404 {"detail":"Not Found"}
PATCH  /activos-biologicos/218/eventos/187                   → 404
PATCH  /activos-biologicos/218/eventos/sanitario/187         → 404
```

Los primeros intentos devolvieron `307` (redirección de FastAPI por normalización de slash) — siguiendo la
redirección (`allow_redirects=True`), el destino final es siempre `404 Not Found`: la ruta simplemente no está
definida en el router, no existe ningún control de acceso "aplicado" que rechace la operación — el endpoint nunca
se construyó, que es la forma más fuerte de "no editable" a nivel de API.

Verificación adicional: `GET /activos-biologicos/218/historial` después de los 5 intentos confirma
`total_registros >= 1` — el evento no desapareció.

## Capa 2 — Base de datos: triggers de inmutabilidad (autorizado explícitamente, todo con ROLLBACK)

Con una conexión que **sí tiene permiso de escritura** a nivel de `GRANT` de Postgres (no una cuenta de solo
lectura del motor), se intentaron las 4 combinaciones UPDATE/DELETE × tabla padre/hija sobre el mismo evento:

```
UPDATE modulo2.eventos_activos SET descripcion=... WHERE id_eventos=187;
→ RECHAZADO: IMMUTABLE_RECORD: Los eventos biológicos son inmutables una vez registrados.
             Operación UPDATE sobre tabla eventos_activos bloqueada.
             (PL/pgSQL function modulo2.trg_fn_eventos_activos_inmutable())

UPDATE modulo2.eventos_sanitarios SET observaciones=... WHERE id_evento=187;
→ RECHAZADO: IMMUTABLE_RECORD ... UPDATE sobre tabla eventos_sanitarios bloqueada.

DELETE FROM modulo2.eventos_sanitarios WHERE id_evento=187;
→ RECHAZADO: IMMUTABLE_RECORD ... DELETE sobre tabla eventos_sanitarios bloqueada.

DELETE FROM modulo2.eventos_activos WHERE id_eventos=187;
→ RECHAZADO: IMMUTABLE_RECORD ... DELETE sobre tabla eventos_activos bloqueada.
```

Las 4 intentos fueron rechazados por `trg_fn_eventos_activos_inmutable`. Todas las transacciones terminaron en
`ROLLBACK` explícito (dentro del propio test, vía fixture) — ningún dato quedó modificado ni eliminado.

## Resumen de tests (Pytest, 10/10 PASS)

| Test | Resultado |
|---|---|
| `test_delete_evento_no_existe_como_ruta` × 3 patrones de URL | PASS |
| `test_patch_evento_no_existe_como_ruta` × 2 patrones de URL | PASS |
| `test_evento_sigue_intacto_tras_los_intentos` | PASS |
| `test_update_eventos_activos_rechazado` | PASS |
| `test_update_eventos_sanitarios_rechazado` | PASS |
| `test_delete_eventos_sanitarios_rechazado` | PASS |
| `test_delete_eventos_activos_rechazado` | PASS |

## Evidencia

- [Suite Pytest](../test_tc_m02_g42_inmutabilidad_eventos.py)

## Conclusión

RF-39 cumple de forma robusta y en profundidad su exigencia de inmutabilidad: el append-only de los eventos
biológicos no depende únicamente de que la API "no tenga un botón" — está reforzado a nivel de base de datos con
triggers que rechazan incluso una escritura directa con permisos elevados. Es de los pocos controles de este
módulo verificado en dos capas independientes con evidencia real en ambas, sin ningún hallazgo que reportar.
