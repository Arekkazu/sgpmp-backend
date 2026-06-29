# CU11 — Gaps de BD y RBAC — RF-49

Fecha: 2026-06-29

---

## Estado de la tabla preexistente

La tabla `modulo2.asociaciones_activos_sensores` ya existía en la DB pero estaba incompleta respecto al RF-49.

### Columnas preexistentes
| Columna | Tipo | Estado |
|---------|------|--------|
| id_asociacion_activo_sensor | SERIAL PK | ✓ |
| id_sensor | INTEGER NOT NULL → modulo9.sensores | ✓ |
| id_usuario | INTEGER NOT NULL → modulo1.usuarios | ✓ |
| fecha_inicio | TIMESTAMPTZ NOT NULL | ✓ |
| fecha_fin | TIMESTAMPTZ **NOT NULL** | ❌ Gap: debe ser nullable |
| motivo | TEXT nullable | ✓ |
| id_activo_biologico | INTEGER nullable → modulo2.activos_biologicos | ✓ |
| tipo | enum_asociaciones_activos_sensores_tipo (directa/ambiental/poblacional) | ✓ |

### Gaps detectados y DDL aplicado (2026-06-29)

```sql
-- 1. fecha_fin debe ser nullable (asociaciones activas no tienen fecha de fin)
ALTER TABLE modulo2.asociaciones_activos_sensores ALTER COLUMN fecha_fin DROP NOT NULL;

-- 2. Columnas faltantes según RF-49
ALTER TABLE modulo2.asociaciones_activos_sensores 
  ADD COLUMN tipo_activo VARCHAR(20) CHECK (tipo_activo IN ('INDIVIDUAL','LOTE')),
  ADD COLUMN dispositivo_iot_id INTEGER REFERENCES modulo9.dispositivos_iot(id_dispositivo_iot),
  ADD COLUMN id_infraestructura INTEGER REFERENCES modulo9.infraestructuras(id_infraestructura),
  ADD COLUMN estado_asociacion VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
    CHECK (estado_asociacion IN ('ACTIVA','INACTIVA','SUPERADA'));

-- 3. Tabla de auditoría (requerida por FA-07)
CREATE TABLE modulo2.auditorias_asociaciones_sensor_activo (
    id_auditoria SERIAL PRIMARY KEY,
    id_asociacion_activo_sensor INTEGER NOT NULL
        REFERENCES modulo2.asociaciones_activos_sensores(id_asociacion_activo_sensor),
    id_usuario INTEGER NOT NULL REFERENCES modulo1.usuarios(id_usuario),
    tipo_operacion VARCHAR(20) NOT NULL CHECK (tipo_operacion IN ('CREATE','DEACTIVATE','UPDATE')),
    valores_anteriores JSONB,
    valores_nuevos JSONB NOT NULL,
    fecha_gestion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Índice parcial preexistente
`uix_asociacion_sensor_activo_vigente` sobre `(id_sensor, id_activo_biologico) WHERE fecha_fin IS NULL`
→ El DB mismo impide tener dos asociaciones activas (sin fecha_fin) para el mismo par sensor+activo.

### FK duplicada detectada
La tabla tiene dos FK constraints sobre `id_activo_biologico`:
- `fk_asociacion_activo_biologico` → modulo2.activos_biologicos (correcta)
- `fk_usuario` → modulo2.activos_biologicos (error de nomenclatura en la DB; apunta al mismo lugar)

Decisión: el modelo ORM solo declara `fk_asociacion_activo_biologico`. La constraint `fk_usuario` existe en la DB pero se ignora en el modelo para evitar ambigüedad.

---

## RBAC aplicado (2026-06-29)

```sql
-- Nuevo recurso id_recurso = 30
INSERT INTO modulo1.recursos (nombre_recurso, descripcion) 
VALUES ('asociacion_sensor_activo', 'Asociación de sensores IoT a activos biológicos');

-- Permisos
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
  (1, 30, 1, 'admin_crear_asociacion_sensor_activo', true),
  (1, 30, 2, 'admin_leer_asociacion_sensor_activo', true),
  (4, 30, 1, 'ing_crear_asociacion_sensor_activo', true),
  (4, 30, 2, 'ing_leer_asociacion_sensor_activo', true),
  (2, 30, 2, 'prod_leer_asociacion_sensor_activo', true),
  (3, 30, 2, 'vet_leer_asociacion_sensor_activo', true);
```

Roles con permiso de crear: Administrador (1), Ingeniero de campo (4).
Roles con permiso solo de leer: Productor (2), Veterinario (3).

---

## Gaps no cubiertos (pendientes de infraestructura)

### Advertencia dispositivo offline (FA-05 → HTTP 201 + warning)
El modelo `modulo9.dispositivos_iot` no tiene campo `last_heartbeat` ni timestamp de última comunicación.
**Decisión**: La asociación se registra normalmente. El campo `advertencia` en la respuesta queda `null`.
Cuando el módulo de telemetría (M03) exponga el estado de conexión, se puede reactivar este warning.

### Compatibilidad especie-sensor (FA-04 → HTTP 400)
El catálogo I3P-1 (M09) que define compatibilidad entre `sensor.categoria` y `especie` no tiene
tabla en la DB actual.
**Decisión**: La validación de compatibilidad no se implementa en este CU. Se documenta como gap.
Cuando la tabla de catálogo exista, agregar validación en el use case antes de V8.

---

## Valores del enum tipo (DB)

El campo `tipo` usa el tipo PG `enum_asociaciones_activos_sensores_tipo` con valores en **minúsculas**:
- `directa`
- `ambiental`
- `poblacional`

El DTO acepta valores en MAYÚSCULAS (`DIRECTA`, `AMBIENTAL`, `POBLACIONAL`) y el use case
normaliza a minúsculas antes de persistir.
