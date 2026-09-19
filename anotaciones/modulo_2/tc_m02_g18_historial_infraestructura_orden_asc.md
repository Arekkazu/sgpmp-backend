# TC-M02-G18 (issue #329) — historial de infraestructura en DESC, debía ser ASC

**RF:** RF-34 — Asociación a infraestructura productiva (historial).
**Endpoint:** `GET /activos-biologicos/{id}/infraestructura?tipo_consulta=HISTORIAL`.

## Causa raíz

`activo_biologico_repository.py::obtener_historial_infraestructura` (único
call-site, usado por `ConsultarAsociacionUseCase`) ordenaba por
`fecha_inicio.desc()` — más reciente primero. El caso de prueba (y RF-34)
esperan orden cronológico ascendente: de la asociación más antigua a la
vigente.

## Fix

Una línea: `.order_by(HistorialInfraestructuraActivoModel.fecha_inicio.desc())`
→ `.asc()`.

## Verificación

Contra datos reales de `sgpmp` (activo id 5, único activo local con ≥2
registros de historial): antes del fix devolvía
`[2026-06-29T20:09:33 → None, 2026-06-29T20:07:23 → 2026-06-29T20:09:33]`
(DESC); después, `[2026-06-29T20:07:23 → 2026-06-29T20:09:33, 2026-06-29T20:09:33 → None]`
(ASC), mismos 2 registros, sin pérdida de datos.

Sin test nuevo: es un cambio de una línea en la construcción de la query SQL,
ya verificado contra datos reales; los tests existentes de
`ConsultarAsociacionUseCase` usan un repositorio fake que no ejercita el
`order_by` real (reciben el historial ya en el orden que el test les pasa),
así que no habría cobertura adicional real que agregar sin introducir
infraestructura de pruebas de integración nueva para este módulo.
