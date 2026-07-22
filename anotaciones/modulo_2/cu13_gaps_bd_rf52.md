# Gaps BD y RBAC — M02 CU13: RF-52

## Estado al iniciar implementación

La infraestructura de base de datos para CU13 estaba **completamente pre-existente** antes de escribir código. No fue necesario aplicar ningún DDL ni DML.

## Verificación realizada

### Tabla `modulo2.bitacora_auditoria_m02`

Existente con los siguientes campos:

| Columna | Tipo | Notas |
|---------|------|-------|
| `id_bitacora` | SERIAL PK | |
| `id_evento` | UUID | `DEFAULT gen_random_uuid()` |
| `rf_origen` | VARCHAR(10) | |
| `tipo_evento` | VARCHAR(80) | |
| `clasificacion_biologica` | VARCHAR(30) | |
| `id_activo_biologico` | INTEGER | nullable, sin FK en ORM |
| `tipo_activo` | VARCHAR(15) | nullable |
| `timestamp_evento` | TIMESTAMPTZ | |
| `timestamp_registro` | TIMESTAMPTZ | `DEFAULT now()` |
| `resultado` | VARCHAR(15) | `DEFAULT 'EXITOSO'` |
| `severidad_log` | VARCHAR(10) | `DEFAULT 'INFO'` |
| `hash_integridad` | VARCHAR(64) | calculado en Python (SHA-256) |
| `registro_incompleto` | BOOLEAN | `DEFAULT false` |
| `descripcion` | VARCHAR(500) | nullable |
| `detalle_tecnico` | JSONB | nullable |
| `id_usuario_responsable` | INTEGER | nullable, sin FK en ORM |
| `modulo_consumidor` | VARCHAR(30) | nullable |
| `id_evento_correlacionado` | UUID | nullable |

Índices existentes: `idx_bitacora_m02_activo`, `idx_bitacora_m02_clasificacion`, `idx_bitacora_m02_resultado`, `idx_bitacora_m02_rf_origen`, `idx_bitacora_m02_timestamp_evento`, `idx_bitacora_m02_usuario`.

### RBAC

| Elemento | Valor | Estado |
|----------|-------|--------|
| Recurso | `id_recurso = 31`, `nombre = 'bitacora_auditoria_m02'` | Pre-existente |
| Permiso READ (acción 2) | Roles: admin(1), cont(5), vet(3), prod(2) | Pre-existente |

### Vistas auxiliares (read-only)

Existentes y no modificadas:
- `modulo2.vw_rf52_bitacora_m02_completa`
- `modulo2.vw_rf52_eventos_fallidos`
- `modulo2.vw_rf52_actividad_por_activo`
- `modulo2.vw_rf52_actividad_por_rf`
- `modulo2.vw_rf52_actividad_por_usuario`
- `modulo2.vw_rf52_resumen_diario`

## Decisiones de diseño

- `hash_integridad` se calcula en Python (SHA-256) antes del INSERT, no en trigger de DB.
- FK de `id_activo_biologico` e `id_usuario_responsable` existen en DB pero **no se declaran en el ORM**, para evitar errores de carga lazy y simplificar el INSERT de auditoría.
- Los errores en `registrar()` se propagan crudos (sin `raise_from_db_error()`), para que el caller los absorba con `except Exception: pass` y no bloqueen la operación principal.
