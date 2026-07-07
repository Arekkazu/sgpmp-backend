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
