# CU05 — Gaps de BD y RBAC (RF-60, RF-61)

## Estado de tablas modulo3

Todas las tablas requeridas por CU05 ya existían en modulo3 al momento de la implementación:

| Tabla | Estado |
|---|---|
| `heartbeats` | ✅ Existe |
| `estados_dispositivos_iot` | ✅ Existe |
| `historico_transiciones_dispositivos` | ✅ Existe |
| `periodos_inactividad` | ✅ Existe |
| `vinculaciones_lecturas` | ✅ Existe |

## Typos en columnas de DB

Las siguientes columnas tienen errores tipográficos en la DB. Se mapean exactamente como están:

| Tabla | Columna real en DB | Nombre semántico |
|---|---|---|
| `estados_dispositivos_iot` | `id_ultimo_heardbeat` | id_ultimo_heartbeat |
| `historico_transiciones_dispositivos` | `causa_secundar` | causa_secundaria |
| `historico_transiciones_dispositivos` | `id_usuairo_responsable` | id_usuario_responsable |
| `vinculaciones_lecturas` | `motivo_correcion` | motivo_correccion |
| `vinculaciones_lecturas` | `id_vinculacion_remplazada` | id_vinculacion_reemplazada |

## Discrepancia RF-61 vs DB enum_estado_vinculacion

El documento RF-61 describe estados: CONFIRMADA / AMBIGUA / SIN_VINCULAR / PENDIENTE_REVISION / SUPERADA  
La DB tiene: `enum_estado_vinculacion` = VINCULADA / SIN_VINCULAR / AMBIGUA / CORREGIDA  
**Decisión:** implementar con los valores reales de la DB.

## RBAC aplicado

Fecha: 2026-07-06

```sql
-- Recursos nuevos
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial)
VALUES
  (35, 'infraestructura_iot', 'Estado y transiciones de dispositivos IoT (RF-60)', false),
  (36, 'alertas_tecnicas_iot', 'Alertas técnicas de dispositivos IoT (RF-60)', false),
  (37, 'vinculaciones_lecturas', 'Vinculación de lecturas teleméricas a activos biológicos (RF-61)', false);

-- Permisos recurso 35 (infraestructura_iot): R todos, U solo admin+ing
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_infraestructura_iot', 1, 35, 2),
  ('admin_actualizar_infraestructura_iot', 1, 35, 3),
  ('prod_leer_infraestructura_iot', 2, 35, 2),
  ('vet_leer_infraestructura_iot', 3, 35, 2),
  ('ing_leer_infraestructura_iot', 4, 35, 2),
  ('ing_actualizar_infraestructura_iot', 4, 35, 3);

-- Permisos recurso 36 (alertas_tecnicas_iot): SOLO admin + ing (RF-60 restricción)
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_alerta_tecnica_iot', 1, 36, 2),
  ('admin_actualizar_alerta_tecnica_iot', 1, 36, 3),
  ('ing_leer_alerta_tecnica_iot', 4, 36, 2),
  ('ing_actualizar_alerta_tecnica_iot', 4, 36, 3);

-- Permisos recurso 37 (vinculaciones_lecturas): R todos, U solo admin+ing
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_vinculacion_lectura', 1, 37, 2),
  ('admin_actualizar_vinculacion_lectura', 1, 37, 3),
  ('prod_leer_vinculacion_lectura', 2, 37, 2),
  ('vet_leer_vinculacion_lectura', 3, 37, 2),
  ('ing_leer_vinculacion_lectura', 4, 37, 2),
  ('ing_actualizar_vinculacion_lectura', 4, 37, 3);
```

## Gap: constraint de unicidad faltante en `estados_dispositivos_iot` (RF-60)

Fecha: 2026-07-28 · Rama: `tweak/iot` · **No gestionado por migraciones**

### Síntoma

`GET /api/iot/dispositivos/2/estado` → **500** con
`sqlalchemy.exc.MultipleResultsFound`.

### Causa

El modelo RF-60 asume **un estado actual por dispositivo** (el heartbeat hace
get-or-insert-or-update por dispositivo; Fase 2 actualiza el registro in-place). La DB **no lo
obligaba**: `modulo3.estados_dispositivos_iot` solo tenía PK sobre `id_estado_dispositivo_iot`, sin
`UNIQUE` sobre `id_dispositivo_iot`. El dispositivo 2 quedó con 2 filas (ids 1 y 3, ambas
`INACTIVO/FALLO_CONECTIVIDAD`) y `obtener_por_dispositivo` (que usaba `scalar_one_or_none()`) reventaba.

La inmutabilidad de RF-60 (Restricción 6 / RNF-06) aplica al **historial de transiciones** y a los
**periodos de inactividad**, NO al registro de estado actual → deduplicar el estado actual es correcto.
Por Restricción 11 (`timestamp_ultimo_contacto` = contacto más reciente) se conserva la fila con el
`fecha_ultimo_contacto` más nuevo (id=1); nada referencia por FK a `id_estado_dispositivo_iot`
(borrado seguro).

### Decisión y SQL aplicado (DB dev, vía MCP)

```sql
-- 1. Limpieza: eliminar la fila duplicada más antigua del dispositivo 2 (conserva id=1)
DELETE FROM modulo3.estados_dispositivos_iot WHERE id_estado_dispositivo_iot = 3;

-- 2. Invariante uno-a-uno estado↔dispositivo, para que no reaparezca
ALTER TABLE modulo3.estados_dispositivos_iot
  ADD CONSTRAINT uq_estados_dispositivos_iot_dispositivo UNIQUE (id_dispositivo_iot);
```

Además se blindó el repo `SqlAlchemyEstadoDispositivoIoTRepository.obtener_por_dispositivo`:
`scalar_one_or_none()` → `select(...).order_by(fecha_ultima_actualizacion desc,
fecha_ultimo_contacto desc nullslast, id desc).limit(1).scalars().first()`, para que la lectura no
dé 500 aunque otro entorno todavía tuviera duplicados.

> **Replicar a staging/prod**: la limpieza (borrar duplicados por `id_dispositivo_iot` conservando el
> de contacto más reciente) **debe** ejecutarse antes del `ALTER`, o el constraint falla.

## Gap: enums de alertas técnicas IoT (RF-60)

`modulo3.alertas` (compartida con alertas biológicas) no soportaba los valores que escribe/filtra la
feature de alertas técnicas. Extensión aplicada en DB dev (**no gestionado por migraciones**):

```sql
ALTER TYPE modulo3.enum_tipo_alerta          ADD VALUE IF NOT EXISTS 'TECNICA';
ALTER TYPE modulo3.enum_origen_evento_alerta ADD VALUE IF NOT EXISTS 'HEARTBEAT';
ALTER TYPE modulo3.enum_origen_evento_alerta ADD VALUE IF NOT EXISTS 'EVALUACION_PERIODICA';
```

La severidad técnica se **mapea en código** a la escala existente `LEVE / MODERADO / CRITICO` (no se
tocó `enum_buffer_nivel_severidad`). `ALTER TYPE … ADD VALUE` es prácticamente irreversible en
Postgres. Detalle completo en `fix_alertas_tecnicas_enum_rf60.md`.
