# RF-10 — Retención y archivado de auditoría · Checklist de trabajo

Rama: `feature/rf10-retencion-auditoria-12-meses`
Base: `origin/dev` (`4e5ed95`) · Commit original: `e44d41d` (Leandro)

Este archivo es el punto de retome entre sesiones. Cada casilla se marca al
quedar verificada, no al escribir el código.

---

## Fase 0 — Traer la rama y montar el entorno

- [x] `git checkout` de `feature/rf10-retencion-auditoria-12-meses` (merge limpio sobre `dev`)
- [x] `alembic upgrade head` en **`sgpmp`** → head `8fc28a787fc8`, tabla + 3 índices + 1 trigger
- [x] Migración RF-10 aplicada en **`pruebas`** (sólo esa revisión: la base es solo-`modulo1`
      y la cadena completa incluye migraciones de `modulo3`/`modulo9` que ahí no aplican)
- [x] Línea base de tests: **74 unitarias** + **41 integración** en verde

## Fase 1 — Verificación de lo que ya traía la rama

- [x] Migración `8fc28a787fc8` encadena con el head real (`down_revision='d4e2f8a15c9b'`)
- [x] `modulo1.eventos_archivados` replica 1:1 las 12 columnas de `modulo1.eventos` + `fecha_archivado`
- [x] Trigger `trg_proteger_eventos_archivados` es réplica exacta de `modulo1.trg_fn_proteger_auditoria`
      (mismo `ERRCODE P0002`, mismo prefijo `IMMUTABLE_RECORD`)
- [x] `commit()`/`rollback()` viven sólo en el use case (regla no negociable de `CLAUDE.md`)
- [x] Idempotencia real: `NOT EXISTS` + `ON CONFLICT (id_evento) DO NOTHING`
- [x] Advisory lock `pg_try_advisory_xact_lock(10101608)` evita doble ejecución entre réplicas
- [x] Decisión "copia sin borrar" confirmada como correcta contra la DB:
      `modulo1.notificaciones.id_evento` es `NOT NULL` con FK a `modulo1.eventos`, y
      `trg_proteger_auditoria_delete` bloquea `DELETE` incluso para `postgres`.
      El RF se contradice (Restricciones: "no DELETE ni para Administrador" vs. Proceso:
      "trasladar a almacenamiento histórico") y la rama resolvió a favor de la restricción dura.

## Fase 2 — Hueco 1: el histórico era data muerta

Nadie leía `modulo1.eventos_archivados`: no había endpoint, schema ni método de lectura.

- [x] `_query_con_filtros(..., modelo=Eventos)` parametrizado por modelo en el repo
- [x] `listar_eventos(..., archivados=False)` / `contar_eventos(..., archivados=False)`
- [x] `_a_entidad` y `_verificar_hash` reusados sin duplicar (columnas idénticas en ambos modelos)
- [x] Puerto `EventoRepository` actualizado con el parámetro `archivados`
- [x] `ConsultarAuditoriaUseCase` acepta `archivados` y lo refleja en el detalle del evento tipo 16
- [x] `GET /auditoria/archivado/` con el mismo `require_permission(6, 2)` y el mismo response

## Fase 3 — Hueco 2: alerta interna al administrador (FA "Error en el proceso de archivado")

La rama sólo hacía `logger.exception`. El RF pide *"dispara una alerta crítica al
administrador — Notificación Interna"*.

- [x] Migración nueva: `id_tipo_evento = 25` → `FALLO_ARCHIVADO_AUDITORIA` + `setval` de la secuencia
- [x] `25: EventoCategoria.MODIFICACION` en el value object
- [x] `NotificarFalloArchivadoUseCase`: 1 evento tipo 25 + 1 notificación interna por administrador
- [x] `main.py` dispara la alerta en el `except` del scheduler, con sesión nueva y `try/except` propio
- [x] Sin administradores → sólo log, el proceso no se rompe

## Fase 4 — Tests

- [x] Unitarios del use case de notificación (fakes, sin DB)
- [x] Integración de `GET /auditoria/archivado/`: filtra, pagina, 403 al no-admin
- [x] `tests/integration/README.md` actualizado
- [x] Suite completa en verde

## Fase 6 — Conformidad literal con el RF

Auditoría campo por campo y flujo por flujo tras cerrar la retención; encontró 8
incumplimientos. Detalle en [`auditoria_cumplimiento_rf10.md`](./auditoria_cumplimiento_rf10.md).

- [x] A · `nombre_usuario`, `direccion_ip`, `user_agent` como columnas, llenadas
      desde el contexto del request en el único punto por el que pasan todos los eventos
- [x] A · `id_sesion` derivado del JWT (antes sólo en 4 de 29 puntos de registro)
- [x] A · `RequestContextMiddleware` registrado en `main.py` (existía pero era código muerto)
- [x] A · los campos nuevos expuestos en la respuesta y copiados al histórico
- [x] B · FA hash mismatch → 500 `INTEGRIDAD_AUDITORIA_VIOLADA`
- [x] B · `modulo1.integridad_baseline` para el legado irreparable (92 registros)
- [x] B · un evento sin hash ya no se reporta como íntegro
- [x] C · FA acceso denegado → mensaje del RF y el intento queda auditado
- [x] C · eliminado el `ROL_ADMINISTRADOR = 1` del caso de uso
- [x] D · FA inmutabilidad → 405 con el mensaje del RF y el formato de error del proyecto
- [x] E · FA exceso de resultados → HTTP 206 + campo `mensaje`
- [x] F · FA filtro inválido → 400 también por `id_usuario` inexistente
- [x] G · FA blocker → 500 con el mensaje del RF desde `registrar()`
- [x] H · 3 índices sobre `modulo1.eventos` para los filtros y el orden
- [x] 14 pruebas de conformidad, una por punto
- [x] Suite completa en verde: **138 passed, 7 skipped**

## Fase 5 — Cierre

- [x] `diseno.md` ampliado con lo de Fases 2-3
- [x] `RESUMEN_FINAL.md` con SQL aplicado por base, endpoints y mapeo RF → evidencia
- [x] `estado_M01.md` apuntando al doc movido
- [x] Curls documentados
- [x] Commit y push

---

## Cambios en base de datos aplicados

| # | Cambio | `sgpmp` | `pruebas` |
|---|---|---|---|
| 1 | `CREATE TABLE modulo1.eventos_archivados` + 2 índices + trigger de inmutabilidad | ✅ | ✅ |
| 2 | `INSERT` `id_tipo_evento = 25` (`FALLO_ARCHIVADO_AUDITORIA`) en `modulo1.tipos_eventos` | ✅ | ✅ |
| 3 | `setval` de `modulo1.tipos_evento_id_tipo_evento_seq` tras el insert explícito | ✅ | ✅ |
| 4 | `nombre_usuario`, `direccion_ip`, `user_agent` en `eventos` y `eventos_archivados` | ✅ | ✅ |
| 5 | `ix_eventos_fecha`, `ix_eventos_usuario_fecha`, `ix_eventos_tipo_fecha` | ✅ | ✅ |
| 6 | `CREATE TABLE modulo1.integridad_baseline` + trigger de inmutabilidad | ✅ | ✅ |
| 7 | Siembra de la línea base (92 filas en `sgpmp`, 0 en `pruebas`: no tiene legado) | ✅ | ✅ |

Cadena Alembic: `8fc28a787fc8` → `a3b7c1d95e40` → `b5d81f27ac93` → `c8e4a5b13d72` (head).

Sin cambios de RBAC: la lectura del histórico reusa el permiso existente
`require_permission(6, 2)` (recurso 6 = auditoría, acción 2 = leer).

## Avisos operativos

- **No sembrar eventos sintéticos antiguos en `sgpmp`**: `trg_proteger_auditoria_delete`
  impide borrarlos después. Toda prueba con datos va en `pruebas`, donde el `conftest`
  revierte la transacción exterior.
- En `sgpmp` hay 936 eventos y el más antiguo es de `2026-01-27`, así que hoy hay
  **0 eventos vencidos**: el proceso corre y archiva 0 filas. Es lo esperado.
- `alembic_version` en `pruebas` sigue en el baseline `f7fe43537842`: esa base sólo tiene
  `modulo1`, así que las revisiones se le aplican de forma selectiva. No es regresión de RF-10.
