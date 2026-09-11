# CU-08 — Gaps de BD y RBAC para RF-72 (Retroalimentación Clínica)

## Resultado del análisis

### Tabla principal: `modulo4.retroalimentaciones_clinicas`

Sin gaps. La tabla existe con todas las columnas requeridas:

| Columna | Tipo | Estado |
|---------|------|--------|
| `id_retroalimentacion` | uuid, PK, gen_random_uuid() | ✓ |
| `id_resultado_inferencia` | uuid, NOT NULL | ✓ |
| `id_activo_biologico` | integer, NOT NULL | ✓ |
| `estado_retroalimentacion` | USER-DEFINED (enum PG), NOT NULL | ✓ |
| `diagnosticos_reales` | ARRAY(integer), nullable | ✓ |
| `fuente_diagnostico` | USER-DEFINED (enum PG), nullable | ✓ |
| `es_fuente_desconocida` | boolean, default false | ✓ |
| `es_conflicto_retroalimentacion` | boolean, default false | ✓ |
| `observaciones_clinicas` | text, nullable | ✓ |
| `id_usuario_veterinario` | integer, NOT NULL | ✓ |
| `fecha_retroalimentacion` | timestamptz, default now() | ✓ |
| `estado_registro` | varchar(20), default 'ACTIVO' | ✓ |

Constraint de unicidad existente: `uq_retro_usuario_resultado` sobre `(id_resultado_inferencia, id_usuario_veterinario)` ✓

### RBAC — recurso `id=45` (`retroalimentacion_clinica`)

Permisos ya registrados:

| id_permiso | nombre | id_rol | id_accion | es_activo |
|-----------|--------|--------|-----------|-----------|
| 261 | vet_crear_retroalimentacion_clinica | 3 (Veterinario) | 1 (C) | true |
| 262 | vet_leer_retroalimentacion_clinica | 3 (Veterinario) | 2 (R) | true |
| 263 | admin_leer_retroalimentacion_clinica | 1 (Administrador) | 2 (R) | true |

Sin acción requerida en RBAC.

---

## Gap detectado: ventana temporal configurable (M09)

**RF-72 dice:** "Ventana predeterminada: 90 días, configurable desde M09."

**Realidad en BD:** `modulo9.configuraciones_globales` solo tiene columnas `frecuencia_muestreo`, `heartbeat`, `fecha_actualizacion`, `id_usuario`, `es_activo`. No existe campo para configurar la ventana de retroalimentación.

**Decisión:** Usar constante `VENTANA_RETROALIMENTACION_DIAS = 90` en el use case. La integración con M09 quedará pendiente hasta que el equipo de M09 agregue el parámetro a su tabla. No se bloquea la implementación.

---

## SQL aplicado

Ninguno. Sin cambios de DDL ni DML necesarios.
