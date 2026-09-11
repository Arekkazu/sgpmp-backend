# CU04 — Gaps de BD y RBAC (RF-18, RF-19, RF-20)

## Gaps encontrados y acciones aplicadas

### 1. Tabla `modulo9.infraestructuras` — columna faltante
**Gap**: No tenía `fecha_actualizacion`, requerida por FA-14 (concurrencia optimista en edición de áreas).  
**Decisión**: ALTER TABLE para agregar la columna nullable.

```sql
ALTER TABLE modulo9.infraestructuras
  ADD COLUMN fecha_actualizacion TIMESTAMPTZ;
```

### 2. Tablas de auditoría — no existían
**Gap**: No existían `auditorias_configuraciones_globales`, `auditorias_fincas`, `auditorias_infraestructuras`.  
**Decisión**: Crear siguiendo el mismo patrón de `auditorias_especies`.

```sql
CREATE TABLE modulo9.auditorias_configuraciones_globales (
  id_auditoria_config     SERIAL PRIMARY KEY,
  id_configuracion_global INTEGER NOT NULL REFERENCES modulo9.configuraciones_globales(id_configuracion_global),
  id_usuario              INTEGER NOT NULL REFERENCES modulo1.usuarios(id_usuario),
  tipo_operacion          VARCHAR(20) NOT NULL CHECK (tipo_operacion IN ('CREATE','UPDATE')),
  valores_anteriores      JSONB,
  valores_nuevos          JSONB NOT NULL,
  fecha_gestion           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE modulo9.auditorias_fincas (
  id_auditoria_finca  SERIAL PRIMARY KEY,
  id_finca            INTEGER NOT NULL REFERENCES modulo9.fincas(id_finca),
  id_usuario          INTEGER NOT NULL REFERENCES modulo1.usuarios(id_usuario),
  tipo_operacion      VARCHAR(20) NOT NULL CHECK (tipo_operacion IN ('CREATE','UPDATE','DEACTIVATE')),
  valores_anteriores  JSONB,
  valores_nuevos      JSONB NOT NULL,
  fecha_gestion       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE modulo9.auditorias_infraestructuras (
  id_auditoria_infraestructura SERIAL PRIMARY KEY,
  id_infraestructura  INTEGER NOT NULL REFERENCES modulo9.infraestructuras(id_infraestructura),
  id_usuario          INTEGER NOT NULL REFERENCES modulo1.usuarios(id_usuario),
  tipo_operacion      VARCHAR(20) NOT NULL CHECK (tipo_operacion IN ('CREATE','UPDATE','DEACTIVATE')),
  valores_anteriores  JSONB,
  valores_nuevos      JSONB NOT NULL,
  fecha_gestion       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3. Recurso RBAC faltante — `configuraciones_globales`
**Gap**: RF-18 no tenía recurso en `modulo1.recursos`.  
**Decisión**: Insertar recurso con `id_recurso = 21` (la secuencia estaba desincronizada; se corrigió con `setval`).

```sql
SELECT setval('modulo1.recursos_id_recurso_seq', 20, true);

INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial, fecha_creacion)
VALUES ('configuraciones_globales', 'Configuración de parámetros operativos del sistema', false, now());
-- Resultó id_recurso = 21
```

### 4. Permisos RBAC faltantes
**Gap**: Faltaban permisos D (desactivar) para fincas e infraestructuras, y todos los permisos para configuraciones_globales.

```sql
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion, es_activo, fecha_creacion)
VALUES
  ('admin_crear_config_global',      1, 21, 1, true, now()),  -- id_permiso = 110
  ('admin_leer_config_global',       1, 21, 2, true, now()),  -- id_permiso = 111
  ('admin_actualizar_config_global', 1, 21, 3, true, now()),  -- id_permiso = 112
  ('admin_desactivar_finca',         1,  9, 4, true, now()),  -- id_permiso = 113
  ('admin_desactivar_infraestr',     1, 10, 4, true, now());  -- id_permiso = 114
```

## Estado final de RBAC para CU04

| Recurso | id_recurso | Admin (C/R/U/D) | Productor | Vet | Ing |
|---------|-----------|-----------------|-----------|-----|-----|
| configuraciones_globales | 21 | C/R/U | — | — | — |
| fincas | 9 | C/R/U/D | R | R | R |
| infraestructuras | 10 | C/R/U/D | R | R | R |

## Notas de mapeo BD ↔ RF

- `configuraciones_globales.id_configuracion_global` (DB) ↔ `id_configuracion` (RF)
- `fincas.id_finca` (DB) ↔ `id` (RF)
- `fincas.id_usuario` (DB) ↔ `productor_id` (RF) — FK directo al usuario con rol Productor
- `fincas.ubicacion` (DB) ↔ `ubicacion_finca` (RF)
- `infraestructuras.tipo` (DB) ↔ `tipo_area` (RF) — enum `enum_tipo_infraestructura`
- `infraestructuras` no tiene `fecha_creacion` en DB
