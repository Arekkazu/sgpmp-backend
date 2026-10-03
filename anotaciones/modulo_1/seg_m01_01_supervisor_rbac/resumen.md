# SEG-M01-01 — Resumen

Issue #289 · rama `fix/seg-m01-01-supervisor-rbac-baseline`

Auditoría de la matriz RBAC completa sembrada en el baseline (9 roles, 57
recursos, 323 permisos). Un hallazgo confirmado y dos a verificar.

---

## 1. Rol Supervisor — escalada de privilegios (confirmado, corregido)

El rol Supervisor (`id_rol = 6`, descrito como *"permisos de supervisión y
reportes"*) solo tenía sembrados dos permisos de prueba:

| Antes | Acción | Recurso |
|---|---|---|
| `Supervisor_permiso_1_1` | C (Crear) | `usuarios` |
| `Supervisor_permiso_2_1` | C (Crear) | `roles` |

Ninguno de los dos tiene relación con "supervisión y reportes", ningún RF se
lo atribuye, y los nombres autogenerados (a diferencia del resto de la
matriz, que usa nombres descriptivos) confirman que eran semilla de prueba
olvidada, no una decisión de diseño.

### Fix

Migración `alembic/versions/0b9cdb05af53_seg_m01_01_retirar_escalada_de_.py`:

- Retira los dos permisos de creación.
- Siembra en su lugar `sup_leer_evento` (R sobre `eventos`, el registro de
  auditoría del sistema) y `sup_ejecutar_reporte` (E sobre
  `generacion_reportes`) — coherente con la descripción del rol y sin
  conceder ninguna capacidad de escritura.
- Ambas operaciones van en el mismo bloque `DO $$ ... $$`: se **inserta antes
  de borrar**, porque `trg_validar_permiso_minimo_rol` bloquea dejar al rol
  sin ningún permiso activo, aunque sea momentáneamente dentro de la misma
  sentencia (se verificó con un ciclo `downgrade`/`upgrade` real contra
  Postgres; el orden inverso falla con `MIN_PERMISSION`).

El `downgrade` es simétrico y completo (a diferencia de RF-12, aquí ningún
permiso es `admin_*`, así que no aplican los triggers de inmutabilidad).

### Verificado

```sql
SELECT p.nombre, r.nombre_recurso, a.codigo
FROM modulo1.permisos p
JOIN modulo1.recursos r ON r.id_recurso = p.id_recurso
JOIN modulo1.acciones a ON a.id_accion = p.id_accion
WHERE p.id_rol = 6;
-- sup_leer_evento      | eventos              | R
-- sup_ejecutar_reporte | generacion_reportes  | E
```

Ciclo `alembic downgrade -1` → `alembic upgrade head` contra `sgpmp` (dev
local) sin errores tras el ajuste de orden. Suite `tests/identity_access`:
163 pasan.

---

## 2. Revisor Fiscal — acción E sobre bitácora de auditoría (verificado, sin cambios)

Se revisó qué endpoint gatea `require_permission(57, 5)`
(`bitacora_auditoria_suministros`, E) y `require_permission(52, 5)`
(`historial_suministros`, E):

- `GET /suministros/auditoria/exportar` (`auditoria_suministros_router.py`) —
  exporta la bitácora en CSV/Excel/PDF. Solo lectura.
- `POST /suministros/historial/trabajos` (`historial_suministros_router.py`)
  — encola un trabajo async de tipo `CONSULTA_PESADA` o `EXPORTACION` sobre
  el historial. Solo lectura (no muta suministros ni la bitácora).

En esta matriz, `E` se usa consistentemente para "generar/exportar", nunca
para alterar el recurso subyacente. Ninguno de los dos endpoints escribe ni
dispara nada sobre los registros de auditoría o historial. **No se
encontró problema — sin cambios.**

---

## 3. Veterinario — "eliminar" vs "desactivar" (confirmado: nomenclatura, corregido)

Los 4 permisos `vet_eliminar_*` (ciclo biológico, patología, métrica de
producción, umbral ambiental) gatean use cases (`desactivar_*_use_case.py`)
que hacen **borrado lógico** (`entidad.desactivar()` → `es_activo = false`),
nunca `db.delete()`. Es decir: es un nombre inconsistente, no un riesgo de
borrado físico irreversible.

Ya existían en la misma matriz permisos equivalentes con el nombre correcto
para el mismo patrón de acción D (`vet_desactivar_activo_biologico`,
`vet_desactivar_consumo_alimento`, `vet_desactivar_medicamento`), lo que
confirma que `desactivar` es la convención vigente y `vet_eliminar_*` era la
excepción.

### Fix

La misma migración renombra los 4 permisos:

```
vet_eliminar_ciclo_biologico      → vet_desactivar_ciclo_biologico
vet_eliminar_patologia            → vet_desactivar_patologia
vet_eliminar_metrica_produccion   → vet_desactivar_metrica_produccion
vet_eliminar_umbral_ambiental     → vet_desactivar_umbral_ambiental
```

Solo cambia el nombre (columna `nombre`); `id_recurso`/`id_accion`/`id_rol`
no se tocan, así que ningún `require_permission` existente se ve afectado.

---

## Por qué migración Alembic y no editar `esquema_baseline.sql`

El baseline es una fotografía histórica del esquema en el momento en que se
introdujo la primera migración — solo se consulta para provisionar bases
nuevas desde cero (`pruebas`). Editarlo no cambia nada en una base ya
migrada (como `sgpmp`/dev), y una base nueva construida desde baseline +
migraciones terminaría en el mismo estado igual sin tocarlo. El patrón ya
establecido para sembrar/corregir datos de RBAC es una migración de datos
(`op.execute` con validaciones defensivas), igual que
`f2c84d91a6e7_rf12_permiso_identificacion_completa.py`.

---

## Pendiente para Análisis (fuera de alcance de este PR)

El propósito exacto del rol Supervisor ("lo que supervisa") no está definido
en ningún RF. `sup_leer_evento` + `sup_ejecutar_reporte` es la lectura mínima
coherente con su nombre y descripción actuales, elegida para cerrar la
escalada de privilegios sin inventar alcance de negocio no aprobado. Si
Análisis define un dominio de supervisión más específico, se siembra con una
migración nueva.
