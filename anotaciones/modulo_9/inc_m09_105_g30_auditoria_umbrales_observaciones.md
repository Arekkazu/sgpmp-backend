# INC-M09-105-G30 (#296) — Observaciones de auditoría de umbrales RF-17

Reevaluación V2 de TC-M09-G30 / TC-M09-64: **APROBADA**. La auditoría específica de RF-17
registra correctamente CREATE/UPDATE (umbral #44, especie Bovino, variable Temperatura Corporal,
auditoría #7 y #8 correlacionadas por `id_umbral_ambiental`, usuario y ventana temporal). QA
dejó dos observaciones explícitamente **no bloqueantes**, severidad/prioridad "pendiente de
validar".

## Observación 2 — Representación decimal inconsistente (corregida)

Los snapshots (`valores_anteriores`/`valores_nuevos`) podían mostrar el mismo valor como
`"42.0"` en un registro y `"42.00"` en otro. Causa raíz: `UmbralAmbiental._snapshot()` hacía
`str(self.valor_min)` directo sobre el `Decimal`, y ese `Decimal` no siempre tiene la misma
escala según su origen — si viene recién parseado de un DTO (`Decimal('42.0')`, tal como llegó
en el JSON de la request) conserva esa escala; si viene de una entidad releída de BD
(`modulo9.umbrales_ambientales`/`niveles_alerta_ambientales`, ambas `NUMERIC(_, 2)`) psycopg2
lo devuelve con escala fija de 2 decimales (`Decimal('42.00')`). QA confirmó que no hay pérdida
de precisión — es puramente de representación textual.

**Fix:** `_snapshot()` ahora cuantiza cada Decimal a `0.01` antes de serializarlo
(`_decimal_snapshot()` en `src/configuration/domain/entities/umbral_ambiental.py`), fijando la
misma escala que ya tienen las columnas reales en BD. No requiere migración — es solo
normalización de formato al construir el snapshot, en el dominio (no en infraestructura), para
que aplique sin importar de dónde vino el `Decimal`.

Tests: `tests/configuration/test_inc_m09_105_g30_normalizar_decimales_auditoria_umbral.py`.

## Observación 1 — Ausencia en auditoría global D09 (no implementada, requiere decisión)

Los eventos de RF-17 son consultables vía `GET /configuracion/umbrales/{id}/auditoria`, pero no
aparecen en `GET /auditoria/` (D09 global de `identity_access`, tabla `modulo1.eventos`).

**Esto no es un defecto aislado de RF-17**: se verificó que `modulo1.eventos` solo lo escribe
`identity_access` (login, cambio de contraseña, gestión de roles, perfil). Ningún otro módulo de
negocio (M02 biológicos, M03 telemetría, M04 predicción, M09 configuración/RF-17, supplies)
escribe ahí — cada uno tiene su propia tabla de auditoría append-only
(`auditorias_umbrales_ambientales`, `bitacora_auditoria_iot`, etc.), documentado ya como patrón
en `CLAUDE.md` ("Si un módulo nuevo necesita auditoría, sigue este patrón — no asumas que
`audit_sdk` está inicializado"). Es decir: D09 es el log de seguridad/acceso de
`identity_access`, no un bus de eventos transversal de todo el sistema.

**Por qué no se implementa un fix ahora**: QA mismo lo plantea como pregunta abierta ("confirmar
si D09 debe consolidar la auditoría transversal del sistema"), no como un requisito claro. Hacer
que cada módulo escriba también en `modulo1.eventos` (o introducir un bus de eventos real) es un
cambio arquitectónico transversal — afecta a todos los módulos con auditoría propia, no solo a
RF-17 — y requiere una decisión de producto/arquitectura antes de tocar código, no una
implementación unilateral en este fix.

**Acción**: queda documentado aquí para que el equipo decida. Si se confirma que D09 debe ser
transversal, el trabajo correcto sería diseñarlo una sola vez (ej. un `AuditoriaGlobalPort` que
cada módulo invoque además de su propia tabla, o una vista consolidada que una todas las tablas
de auditoría) en vez de parchear módulo por módulo.
