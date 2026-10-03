# Gaps BD y RBAC — RF-35 (tarea Taiga): RBAC Veterinario, eventos pendientes, concurrencia optimista

Sigue a `cu02_gaps_bd_rf35_rf37.md` (implementación original de CU02). Este
documento cubre los tres gaps reportados en la tarea Taiga "RF-35: RBAC
Veterinario, validar eventos pendientes, concurrencia optimista" sobre el
`PATCH /activos-biologicos/{id}`.

**Nota de origen:** esta tarea ya se había resuelto una vez, en una sesión
anterior (commit local `a7fe56c8`, issue histórico #30), pero ese trabajo
nunca se pusheó ni se mergeó a `origin/dev` — quedó solo en una rama local
(`feature/rf35-rbac-vet-eventos-pendientes-concurrencia`) que terminó
reutilizada para otro trabajo (RF-49) sin retomar esto. Se confirmó en vivo
(vía MCP Postgres) que los tres gaps seguían exactamente igual en
`sgpmp_dev` antes de retomar: Veterinario sin permiso `U`, sin columna
`fecha_actualizacion`, y el use case sin las validaciones. Este documento
reemplaza y actualiza el análisis original (adaptado al código actual, que
cambió desde entonces: BOLA de alcance de finca en TC-M02-G15 y el wrapper
`ejecutar_con_auditoria_de_rechazo`).

## 1. RBAC — Veterinario sin permiso de Actualizar (U) sobre recurso 29

Verificado en vivo contra `modulo1.permisos` (MCP Postgres, solo lectura)
antes de escribir código:

```sql
SELECT id_permiso, nombre, id_rol, id_accion, es_activo
FROM modulo1.permisos
WHERE id_recurso = 29 AND id_rol = 3
ORDER BY id_accion;
```

Resultado: Veterinario (`id_rol=3`) tenía `C, R, D, E` — **faltaba `U`
(id_accion=3)**. Administrador, Productor e Ingeniero de Campo sí lo tenían
desde CU02. Confirmado además: `modulo1.roles` `id_rol=3` → `'Veterinario'`;
`modulo1.acciones` `id_accion=3` → `codigo='U'`; `modulo1.recursos`
`id_recurso=29` → `'activos_biologicos'`.

**Decisión:** insertar `vet_actualizar_activo_biologico` vía migración de
Alembic (DML), estilo `f2c84d91a6e7` (bloque `DO $$` con validación de
catálogos + `ON CONFLICT DO NOTHING` + verificación final). Ver
`alembic/versions/e5ce9d42b2ec_v5_5_0_rf35_permiso_actualizar_vet_.py`.

## 2. Eventos pendientes sin cerrar / inconsistencias en el historial

El resumen de `estado_M02.md` (RF-35) no detalla más allá de "el RF lo exige
explícitamente en su Proceso" — el documento RF-35 completo no está en este
repositorio (a diferencia de RF-50, cuyo texto completo sí se compartió en
otra tarea). Se documenta aquí la interpretación aplicada, apoyada en
mecanismos ya existentes en el dominio (sin inventar columnas ni conceptos
nuevos):

### "Eventos pendientes sin cerrar"

El modelo de `eventos_sanitarios` no tiene un flag propio de abierto/cerrado.
La única señal persistente de un evento sanitario sin cerrar es el propio
`id_estado` del activo: `RegistrarEventoSanitarioUseCase` (RF-41) transiciona
el activo a `EN_TRATAMIENTO` (3) o `AISLADO` (4) cuando el evento lo
solicita, y la única forma de "cerrarlo" es un cambio de estado explícito de
vuelta a `ACTIVO`/`INACTIVO`/`CERRADO` vía `CambiarEstadoUseCase` (RF-44).
Nueva función `validar_sin_eventos_pendientes` en `_event_validations.py`:
rechaza el `PATCH` con `422 EVENTO_PENDIENTE_SIN_CERRAR` si `activo.id_estado`
está en `{EN_TRATAMIENTO, AISLADO}`. **No** bloquea `CERRADO`/`BAJA` — esos
son estados terminales, no "pendientes".

### "Inconsistencias en el historial"

`historicos_estados_activos` registra cada cambio de estado y
`CambiarEstadoUseCase` es, por convención del código, el único punto que muta
`id_estado` — siempre inserta el histórico en la misma transacción. Nueva
función `validar_historial_consistente`: obtiene el último registro de
histórico del activo (reutiliza `HistoricoEstadoRepository.obtener_ultimo_cambio`,
**ya existente** en el código actual — no fue necesario agregar un método
nuevo) y rechaza el `PATCH` con `422 HISTORIAL_INCONSISTENTE` si
`id_estado_nuevo` de ese registro no coincide con el `id_estado` actual del
activo — señal de que algo mutó el estado fuera del flujo centralizado.

**Pendiente de confirmación del grupo de análisis:** esta interpretación de
"evento pendiente" e "inconsistencia" no está verificada contra el texto
original del RF-35 (no disponible en el repo). Ambas funciones viven en un
único lugar (`_event_validations.py`) y son triviales de ajustar sin tocar el
resto del use case si el grupo de análisis tiene una definición distinta.

## 3. Concurrencia optimista (412)

Verificado en vivo vía MCP Postgres antes de escribir código:

```sql
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'activos_biologicos'
  AND column_name = 'fecha_actualizacion';
-- 0 filas
```

`modulo2.activos_biologicos` no tenía ninguna columna `fecha_actualizacion`.
Se agrega vía migración Alembic (DDL):
`alembic/versions/ccc0b8df02a6_v5_5_0_rf35_fecha_actualizacion_activo_.py`,
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS fecha_actualizacion timestamptz`
(nullable, sin default — mismo patrón usado para `modulo9.especies`, RF-15).
Sin backfill: los activos existentes y los recién creados quedan con
`fecha_actualizacion = NULL` hasta su primera edición vía este `PATCH`.
`ActualizarActivoIndividualDTO.fecha_actualizacion` es `Optional[datetime]`
por lo mismo, permitiendo la doble rama `None`/`None` documentada en
`CLAUDE.md`. Se siguió el patrón exacto de esa sección: comparación
normalizada a UTC, `PreconditionFailedError` con `code='CONFLICTO_CONCURRENCIA'`.

### Bug encontrado al verificar en vivo (no relacionado con RBAC/validaciones)

Al probar el flujo completo contra `sgpmp_dev` (credenciales `dba`, dentro
de una transacción revertida), tocar `fecha_actualizacion` —columna del
**padre** `activos_biologicos`— hace que SQLAlchemy emita por primera vez un
`UPDATE` directo sobre esa tabla desde `actualizar_detalle_individual`
(antes, ese método solo mutaba la tabla **hija**
`detalles_activos_individuales`, así que el padre nunca se tocaba). Eso
dispara `trg_auditar_activo_biologico` (`AFTER UPDATE ON activos_biologicos`),
que exige la variable de sesión `app.usuario_id` — y ese método nunca la
establecía (a diferencia de `guardar()`, que sí lo hace para el `INSERT`).
Sin este fix, **todo** `PATCH /activos-biologicos/{id}` exitoso habría
fallado con una excepción cruda de Postgres (`RaiseException`) en cuanto se
desplegara esta migración — no un bug preexistente en producción hasta
ahora (antes de esta migración el padre nunca se actualizaba), pero sí una
consecuencia directa e ineludible de agregar `fecha_actualizacion` al padre.
Corregido agregando `SET LOCAL app.usuario_id` en
`actualizar_detalle_individual` (mismo patrón que `guardar()`), más
`try/except` + `raise_from_db_error` que ese método tampoco tenía (regla no
negociable de `CLAUDE.md`, no aplicada hasta ahora en este método
específico). Verificado end-to-end contra `sgpmp_dev` real: migraciones +
`SqlAlchemyActivoBiologicoRepository.actualizar_detalle_individual()` real
(no un fake) ejecutados dentro de una transacción revertida — funcionó
limpio.

## Migraciones creadas (no aplicadas contra la BD compartida)

| Archivo | Tipo | down_revision |
|---|---|---|
| `e5ce9d42b2ec_v5_5_0_rf35_permiso_actualizar_vet_.py` | DML (seed permiso) | `c8d4f1a9b7e2` (head real de `origin/dev` al momento de escribir esta migración) |
| `ccc0b8df02a6_v5_5_0_rf35_fecha_actualizacion_activo_.py` | DDL (columna) | `e5ce9d42b2ec` |

**Nota sobre el número de versión (`v5.5.0`):** en este momento hay varias
ramas hermanas sin mergear que también usan `v5.5.0` para trabajo
independiente sobre `origin/dev` (ver PRs de INC-M02-93-G93/#391). El número
exacto debe reconfirmarse contra la versión real de la BD al momento del
merge — es un problema conocido de coordinación entre ramas paralelas, no
específico de este ticket.

## Verificación en vivo (credenciales `dba`, transacción revertida con `ROLLBACK`)

| Comprobación | Resultado |
|---|---|
| `e5ce9d42b2ec` (permiso) corre sin error | ✅ |
| `ccc0b8df02a6` (columna) corre sin error | ✅ |
| Permiso `vet_actualizar_activo_biologico` creado (rol 3, recurso 29, acción 3) | ✅ |
| Columna `fecha_actualizacion` creada (`timestamptz`, nullable) | ✅ |
| `SqlAlchemyActivoBiologicoRepository.actualizar_detalle_individual()` real (con el fix de `app.usuario_id`) ejecutado contra un activo real | ✅ — `raza` y `fecha_actualizacion` actualizados correctamente |
| Downgrade de ambas migraciones corre sin error y limpia todo | ✅ |
| Estado de `sgpmp_dev` tras el `ROLLBACK` final | ✅ Sin cambios |

No se corrió el `alembic upgrade head` real vía CLI (se prefirió la
transacción revertida, igual que en los PRs de INC-M02-92/93-G93).

## Fuera de alcance

- **Otros métodos de este mismo repositorio con el mismo patrón de gap**
  (`actualizar_detalle_poblacional`, línea 404) tampoco establecen
  `app.usuario_id` — pero, a diferencia de `actualizar_detalle_individual`,
  ese método no fue tocado por este ticket y su comportamiento actual (solo
  toca la tabla hija poblacional, nunca el padre) no cambió, así que no
  dispara el trigger hoy. Se deja anotado como riesgo latente si alguna vez
  se le agrega una columna del padre, pero no se corrige aquí por no ser
  parte del alcance de RF-35.
- Errores de trigger PL/pgSQL que no traduce `raise_from_db_error` (ej. el
  `RaiseException` genérico de `app.usuario_id` ausente, si volviera a
  faltar) siguen cayendo en `InfrastructureError` (500) en vez de un código
  específico — mismo hallazgo transversal #4 ya documentado en
  `estado_M02.md`, no específico de este ticket.
- `trg_estado_activo_no_baja_modify` (bloquea cualquier `UPDATE` sobre un
  activo en `BAJA`) y `ck_activo_biologico_soporte_documental_requerido`
  (CHECK constraint sobre datos preexistentes) son protecciones/datos
  preexistentes descubiertos al verificar, no relacionados con RF-35 — el
  primero es consistente con que `validar_sin_eventos_pendientes` no
  necesita bloquear `BAJA` explícitamente (la DB ya lo bloquea); el segundo
  es un dato de prueba inconsistente preexistente en `sgpmp_dev`, no algo
  que este ticket deba limpiar.
