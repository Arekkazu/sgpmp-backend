# CU-09 M04 — Gaps BD y RBAC — RF-73

## Fecha de análisis
2026-07-12

## Consultas ejecutadas

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo4' AND table_name = 'eventos_auditoria_m04'
ORDER BY ordinal_position;

SELECT p.id_permiso, p.nombre, r.nombre_rol, a.codigo
FROM modulo1.permisos p
JOIN modulo1.roles r ON r.id_rol = p.id_rol
JOIN modulo1.acciones a ON a.id_accion = p.id_accion
WHERE p.id_recurso = 46
ORDER BY p.id_rol, a.id_accion;
```

## Resultado

### `modulo4.eventos_auditoria_m04`
21 columnas presentes. Sin gaps de DDL. Enums correctos:
- `tipo_actor`: USER-DEFINED (enum_tipo_actor_auditoria)
- `severidad_evento`: USER-DEFINED (enum_severidad_evento_auditoria)
- `resultado_operacion`: USER-DEFINED (enum_resultado_operacion_auditoria)
- `tipo_evento`: USER-DEFINED (enum_tipo_evento_auditoria_m04)

El campo `hash_evento VARCHAR(64)` existe pero no estaba siendo llenado por el repositorio. Se corrige en esta implementación.

### RBAC — Recurso 46 (`auditoria_m04`) antes del análisis
| Permiso | Rol | Acción |
|---------|-----|--------|
| admin_leer_auditoria_m04 (264) | Administrador | R |

Falta acción E=5 para exportación.

## DML aplicado

```sql
-- Admin puede exportar bitácora de auditoría M04 (id_permiso=265)
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo)
VALUES (1, 46, 5, 'admin_ejecutar_auditoria_m04', true);
```

## Decisiones

- Sin gaps de DDL: tabla completa.
- Se agrega permiso E=5 para Admin (exportar CSV/JSON). No se agrega para Veterinario ni Productor: el RF-73 restringe la bitácora a Administrador y Auditor externo. "Auditor externo" no tiene rol en el sistema; Admin cubre ese acceso.
- El campo `hash_evento` se empieza a poblar en esta implementación (SHA-256 del payload canónico). Eventos previos tendrán `hash_evento = NULL`; es esperado y no requiere migración retroactiva.
- Exportación en CSV y JSON siguiendo el patrón de RF-63 (telemetría). No se implementa PDF ni XLSX por ausencia de dependencias en el proyecto.
