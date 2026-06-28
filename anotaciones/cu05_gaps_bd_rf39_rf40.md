# CU05 — Gaps BD y RBAC (RF-39, RF-40)

## Fecha de análisis
2026-06-28

## Tablas verificadas

### modulo2.eventos_crecimeinto

Estado previo al CU05: tabla existente desde CU03/RF-36, con todos los campos NOT NULL.

Gaps detectados:

| Campo | Estado previo | Gap | Acción aplicada |
|-------|--------------|-----|-----------------|
| `tipo_agregacion` | NOT NULL | INDIVIDUAL no tiene tipo de agregación | DROP NOT NULL |
| `frecuencia` | NOT NULL | INDIVIDUAL no tiene frecuencia de lote | DROP NOT NULL |
| `nuevo_peso_promedio` | no existía | RF-40: peso promedio resultante del lote tras medición | ADD COLUMN NUMERIC(10,4) NULLABLE |
| `cantidad_medida` | no existía | RF-40: número de individuos medidos en el lote | ADD COLUMN INTEGER NULLABLE |

**Decisión de diseño**: `nuevo_peso_promedio` y `cantidad_medida` son obligatorios para activos POBLACIONAL pero opcionales en DB (nullable), dado que activos INDIVIDUAL no los tienen. La restricción de obligatoriedad para LOTE se aplica en el use case, no en la DB.

DDL aplicado:

```sql
ALTER TABLE modulo2.eventos_crecimeinto
    ADD COLUMN nuevo_peso_promedio NUMERIC(10,4),
    ADD COLUMN cantidad_medida INTEGER,
    ALTER COLUMN tipo_agregacion DROP NOT NULL,
    ALTER COLUMN frecuencia DROP NOT NULL;
```

### modulo2.eventos_activos, modulo2.eventos_bajas, modulo2.eventos_sanitarios, modulo2.eventos_productivos

Sin cambios. Estructuras existentes son compatibles con RF-39.

## RBAC — recurso 29 (`activos_biologicos`)

Sin cambios. Estado verificado:

| Rol | Acción C=1 (crear evento) |
|-----|--------------------------|
| Administrador (1) | ✓ perm 163 |
| Productor (2) | ✓ perm 165 |
| Veterinario (3) | ✓ perm 176 |
| Ingeniero de Campo (4) | ✓ perm 167 |

Todos los actores del RF-39 y RF-40 ya tienen permiso de creación sobre el recurso 29.

## Cambios de comportamiento vs CU03/RF-36

| Comportamiento | CU03 (anterior) | CU05 (nuevo) |
|----------------|-----------------|--------------|
| Validación de estado | No validaba | Bloquea CERRADO y BAJA (409) |
| Validación de fecha | No validaba | Valida futura, anterior al alta, coherencia temporal |
| Eventos sanitarios | Solo POBLACIONAL | INDIVIDUAL y POBLACIONAL |
| Eventos productivos | Solo POBLACIONAL | INDIVIDUAL y POBLACIONAL |
| Crecimiento LOTE | `valor_medicion` actualizaba `peso_promedio` | `nuevo_peso_promedio` actualiza `peso_promedio` |
| Crecimiento INDIVIDUAL | No soportado | Soportado (sin actualizar detalle_poblacional) |
| Fase activa (crecimiento) | No verificaba | Obligatoria (RF-40) |
