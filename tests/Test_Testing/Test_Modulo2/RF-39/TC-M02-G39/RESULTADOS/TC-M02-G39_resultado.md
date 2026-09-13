# TC-M02-G39 — Resultado de ejecución

**Estado general: PASS — 3/3 sub-casos, 13/13 assertions vía Postman/Newman contra el backend TEST desplegado.**

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G39 (TC-M02-072, 073, 074) |
| RF / CU | RF-39 / CU-05 |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Activo de prueba | `id_activo_biologico=212` (POBLACIONAL, especie 3, 100 individuos iniciales) |
| Fecha de ejecución | 2026-09-10, ~01:22 UTC |

## Precondición

Se registró un activo POBLACIONAL (nace en estado ACTIVO por defecto):

```json
{"id_activo_biologico":212,"tipo":"POBLACIONAL","id_estado":1,"nombre_estado":"ACTIVO", ...}
```

## TC-M02-072 — Evento sobre activo ACTIVO

```json
// POST /activos-biologicos/212/eventos/sanitario
// {"tipo":"CONTROL_PREVENTIVO","observaciones":"TC-M02-072: evento sobre activo ACTIVO","fecha":"<hace 2s>"}
// HTTP 201
{"evento":{"id_eventos":..., "id_activo_biologico":212, "id_usuario":47, "sanitario":{"tipo":"CONTROL_PREVENTIVO", ...}}}
```

Evento asociado correctamente al activo y al usuario responsable (`id_usuario=47`).

## TC-M02-073 — Evento sobre activo EN_TRATAMIENTO

`PATCH /activos-biologicos/212/estado {"estado_nuevo":"EN_TRATAMIENTO", ...}` → 200. Luego:

```json
// POST .../eventos/sanitario → HTTP 201
```

El sistema permitió el registro sin bloquear, tal como exige el RF para este estado.

## TC-M02-074 — Evento sobre activo AISLADO

`PATCH /activos-biologicos/212/estado {"estado_nuevo":"AISLADO", ...}` → 200. Luego:

```json
// POST .../eventos/sanitario → HTTP 201
```

Igual que el anterior: permitido, sin bloqueo.

## Verificaciones finales

- `GET /activos-biologicos/212/eventos` → 200, `total: 3` — los 3 eventos (uno por cada estado) quedaron en el
  historial del lote.
- `GET /activos-biologicos/auditoria?rf_origen=RF41&id_activo_biologico=212` → 200, 3 registros
  `EVENTO_SANITARIO_REGISTRADO` con `resultado: EXITOSO`, uno por cada evento — confirma "queda registrado en
  auditoría" del resultado esperado de TC-M02-072.

## Resumen de assertions (Newman, 13/13 PASS)

| # | Assertion | Resultado |
|---|---|---|
| 1 | Login (200) | PASS |
| 2–3 | Setup: activo creado (201), nace ACTIVO | PASS |
| 4–5 | TC-M02-072: evento se registra (201), asociado a activo/usuario | PASS |
| 6 | Transición a EN_TRATAMIENTO (200) | PASS |
| 7 | TC-M02-073: evento se registra (201) | PASS |
| 8 | Transición a AISLADO (200) | PASS |
| 9 | TC-M02-074: evento se registra (201) | PASS |
| 10–11 | GET eventos (200), total=3 | PASS |
| 12–13 | GET auditoría (200), 3 registros exitosos | PASS |

## Evidencia

- [Colección Postman](../TC-M02-G39.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G39.html) · [JSON](newman-TC-M02-G39.json)

## Alcance no cubierto por este caso (ya documentado, no requiere nueva prueba)

RF-39 exige que los 3 estados permitan **todos** los tipos de evento. Esta ejecución confirma que se cumple para
eventos sanitarios (RF-41) y, por lectura de código, para reproductivos (RF-42) — ambos usan el gate compartido
`validar_estado_permite_eventos()`. Los tipos crecimiento (RF-40) y productivo (RF-43) tienen su **propio** chequeo
restrictivo (solo ACTIVO), confirmado por lectura directa de sus use cases — una violación real de esta misma
exigencia de RF-39, ya señalada en la auditoría del módulo. No se pudo reproducir en vivo aquí porque ambos exigen
además una fase productiva activa, y crear una fase está bloqueado por INC-M02-37-01. Se recomienda re-probar
crecimiento/productivo contra EN_TRATAMIENTO/AISLADO específicamente una vez corregido ese defecto — se espera que
sigan fallando (409 `ESTADO_NO_PERMITE_EVENTOS`/`ESTADO_NO_ACTIVO`), lo cual sería un FAIL real de RF-39 para esos
dos tipos.
