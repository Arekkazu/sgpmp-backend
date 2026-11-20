# Prevalidación TC-M06-39 — solo lectura (2026-11-15)

Ambiente: `https://api.inmero.co/api-sgpmp-test`  
Caso: CAPITALIZAR / MANO_OBRA_PROPIA / activo **1573** / período **220**  
POST: **NO ejecutado** — pendiente de autorización expresa.

## Resultado de gates

Todas las precondiciones de lectura: **OK**.

| Gate | Evidencia |
|---|---|
| Activo 1573 existe y ACTIVO | `QA-M06O-COSTO-02`, finca 467, especie 423 |
| Valoración por costo activa | `es_activa=true`; costos/valor contable `4000000.0000`; VU 120 |
| Sin inversiones previas | `GET /finanzas/costos?id_activo_biologico=1573` → 0 registros |
| Sin líneas embebidas | 0 |
| Período 220 ABIERTO | NIT 900000003; 2026-11-01 → 2026-11-30 |
| Matriz CAPITALIZACION | Asignación **36** (general): D **158405** / C **250505** |
| Permisos Contador | `costos_activos` acciones 1,2,3 |
| Sin ejecución previa exitosa TC-39 | No hay costo CAPITALIZAR ni justificación TC-M06-39 |
| Auditoría baseline | 1 evento: `RECONOCIMIENTO_INICIAL` (sin `COSTO_REGISTRADO`) |

## No reutilizado

La primera ejecución bloqueada (2026-11-08) **no** aportó IDs de costo/línea reutilizables; el estado actual confirma activo limpio (0 costos, baseline 4.000.000).

## Operación pendiente de autorización

Ver `prevalidacion_tc39.json` → `payload_propuesto` y sección de autorización en el chat.
