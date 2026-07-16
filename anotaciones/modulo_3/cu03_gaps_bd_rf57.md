# Gaps BD y RBAC — M03 CU03: RF-57 Generación y Gestión de Alertas

## Análisis realizado: 2026-07-06

---

## Gaps en `modulo3.alertas`

| Gap | Decisión | DDL aplicado |
|-----|----------|--------------|
| `conflicto_resolucion` era NOT NULL | La mayoría de alertas no tienen conflicto Edge/IA; debe ser nullable | `ALTER TABLE modulo3.alertas ALTER COLUMN conflicto_resolucion DROP NOT NULL` |
| Faltaba `valor NUMERIC(12,4)` | Guardar la medición que disparó la alerta (trazabilidad) | `ALTER TABLE modulo3.alertas ADD COLUMN valor NUMERIC(12,4)` |
| Faltaba `unidad VARCHAR(20)` | Unidad de medida del valor | `ALTER TABLE modulo3.alertas ADD COLUMN unidad VARCHAR(20)` |
| Faltaba `contexto_activo_biologico JSONB` | Contexto del activo biológico asociado (RF-61 / FA-03) | `ALTER TABLE modulo3.alertas ADD COLUMN contexto_activo_biologico JSONB` |
| Faltaba `tiene_contexto_incompleto BOOLEAN` | Flag FA-03/CA-7 — alerta sin activo biológico asociado | `ALTER TABLE modulo3.alertas ADD COLUMN tiene_contexto_incompleto BOOLEAN NOT NULL DEFAULT false` |
| Faltaba `frecuencia_evento INTEGER` | Contador de deduplicación CA-4 (cuántas veces ocurrió en la ventana) | `ALTER TABLE modulo3.alertas ADD COLUMN frecuencia_evento INTEGER NOT NULL DEFAULT 1` |
| Faltaba `ultima_ocurrencia TIMESTAMPTZ` | Timestamp de la última ocurrencia para deduplicación | `ALTER TABLE modulo3.alertas ADD COLUMN ultima_ocurrencia TIMESTAMPTZ` |
| Faltaba `referencia_alerta_original INTEGER` | FK para E16 — reevaluación IA genera nueva alerta referenciando la original | `ALTER TABLE modulo3.alertas ADD COLUMN referencia_alerta_original INTEGER REFERENCES modulo3.alertas(id_alerta)` |
| Faltaba `tiene_generada_por_reevaluacion BOOLEAN` | Flag E16 — indica que esta alerta fue generada por reevaluación IA | `ALTER TABLE modulo3.alertas ADD COLUMN tiene_generada_por_reevaluacion BOOLEAN NOT NULL DEFAULT false` |

### Nota de typo en DB
La columna `severidad_ia` fue creada como **`serveridad_ia`** (typo de origen en el DDL original). Se mantiene el nombre exacto en el modelo ORM y se mapea al campo correcto `severidad_ia` en la entidad de dominio.

---

## Gap en `modulo3.reglas_alertas`

| Gap | Decisión | DDL aplicado |
|-----|----------|--------------|
| `fecha_actualizacion` era `TIME WITH TIME ZONE` (typo en DDL original) | Debe ser `TIMESTAMPTZ` para almacenar fecha+hora completa | `ALTER TABLE modulo3.reglas_alertas ALTER COLUMN fecha_actualizacion TYPE TIMESTAMPTZ USING NOW()` |

### Nota de typo en DB
La columna `umbrales_severidad` fue creada como **`umbrales_severdiad`** (typo de origen). Se mantiene en el modelo ORM y se mapea correctamente en el repositorio.

---

## Recurso RBAC insertado

```sql
INSERT INTO modulo1.recursos (nombre_recurso, descripcion)
VALUES ('alertas_operativas', 'Gestión del ciclo de vida de alertas de monitoreo IoT');
-- id_recurso = 32
```

## Permisos RBAC insertados

```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre) VALUES
  (1, 32, 2, 'admin_leer_alerta_operativa'),
  (1, 32, 3, 'admin_actualizar_alerta_operativa'),
  (2, 32, 2, 'prod_leer_alerta_operativa'),
  (2, 32, 3, 'prod_actualizar_alerta_operativa'),
  (3, 32, 2, 'vet_leer_alerta_operativa'),
  (3, 32, 3, 'vet_actualizar_alerta_operativa'),
  (4, 32, 2, 'ing_leer_alerta_operativa');
```

**Resultado:** admin, productor y veterinario tienen R+U; ingeniero solo R.
