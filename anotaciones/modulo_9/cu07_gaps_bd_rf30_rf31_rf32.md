# CU07 — Gaps BD y RBAC — RF-30, RF-31, RF-32

Fecha análisis: 2026-06-21

---

## Tablas existentes en `modulo9`

Las tablas `plantillas` y `aplicaciones_plantillas` ya existen.

### `modulo9.plantillas`
| Columna | Tipo | Nullable |
|---------|------|----------|
| id_plantilla | integer (seq) | NO |
| id_especie | integer (FK especies) | NO |
| id_usuario | integer (FK usuarios) | NO |
| template_name | character varying | NO |
| params_snapshot | jsonb | NO |
| version | integer | NO |
| fecha_creacion | timestamptz | NO |

### `modulo9.aplicaciones_plantillas`
| Columna | Tipo | Nullable |
|---------|------|----------|
| id_aplicacion_plantilla | integer (seq) | NO |
| id_usuario | integer (FK usuarios) | NO |
| id_plantilla | integer (FK plantillas) | NO |
| target_config | jsonb | NO |
| before_snapshot | jsonb | YES |
| after_snapshot | jsonb | YES |
| fecha_aplicacion | timestamptz | YES |

---

## Gaps encontrados y solución aplicada

### GAP 1 — Falta UNIQUE constraint en `plantillas`

**Problema**: La tabla `plantillas` tenía solo PK y FKs. Sin constraint UNIQUE en `(template_name, version)`, la BD no garantizaba la inmutabilidad por versión.

**Decisión**: El par `(template_name, version)` debe ser único. Al crear con el mismo nombre, la aplicación auto-incrementa la versión.

**SQL aplicado**:
```sql
ALTER TABLE modulo9.plantillas
ADD CONSTRAINT uq_plantillas_nombre_version UNIQUE (template_name, version);
```

---

### GAP 2 — Falta tabla `auditorias_plantillas`

**Problema**: No existía tabla de auditoría para operaciones sobre plantillas. Las demás entidades del módulo tienen su tabla `auditorias_X`.

**Decisión**: Solo operación `CREATE` (plantillas son inmutables). La tabla `aplicaciones_plantillas` ya sirve de audit trail para RF-32.

**SQL aplicado**:
```sql
CREATE TABLE modulo9.auditorias_plantillas (
    id_auditoria_plantilla SERIAL PRIMARY KEY,
    id_plantilla           INTEGER NOT NULL,
    id_usuario             INTEGER,
    tipo_operacion         VARCHAR(20) NOT NULL
                           CHECK (tipo_operacion = 'CREATE'),
    valores_anteriores     JSONB,
    valores_nuevos         JSONB NOT NULL,
    fecha_gestion          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### GAP 3 — Falta recurso RBAC `plantillas`

**Problema**: `modulo1.recursos` no tenía recurso para plantillas. Sin él, `require_permission(28, X)` siempre devolvería 403.

**SQL aplicado**:
```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial, fecha_creacion)
VALUES (28, 'plantillas', 'Gestión de plantillas de configuración', false, now());
```

---

### GAP 4 — Falta permisos RBAC para plantillas

**Problema**: `modulo1.permisos` no tenía ningún registro para `id_recurso = 28`.

**Decisión**: Solo Administrador (id_rol=1) e Ingeniero de Campo (id_rol=4). Acciones: C=1 (crear), R=2 (leer), E=5 (aplicar). No hay U ni D porque las plantillas son inmutables.

**SQL aplicado**:
```sql
INSERT INTO modulo1.permisos (nombre, id_recurso, id_rol, id_accion, es_activo, fecha_creacion) VALUES
  ('admin_crear_plantilla',    28, 1, 1, true, now()),
  ('admin_leer_plantilla',     28, 1, 2, true, now()),
  ('admin_ejecutar_plantilla', 28, 1, 5, true, now()),
  ('ing_crear_plantilla',      28, 4, 1, true, now()),
  ('ing_leer_plantilla',       28, 4, 2, true, now()),
  ('ing_ejecutar_plantilla',   28, 4, 5, true, now());
```
IDs asignados: 157–162.

---

## Formato de `params_snapshot` (schema_version = 1)

```json
{
  "schema_version": 1,
  "ciclos_biologicos": [
    {
      "nombre": "string (3-50 chars)",
      "descripcion": "string o null",
      "duracion_dias": 90
    }
  ],
  "patologias": [
    {
      "id_patologia": 5,
      "nombre": "string (referencia)"
    }
  ],
  "metricas_produccion": [
    {
      "nombre": "string (3-60 chars)",
      "unidad_medida": "string",
      "tipo_medicion": "PESO|VOLUMEN|LONGITUD|CONTEO|OTRO",
      "aplica_a_tipo_activo": "INDIVIDUAL|LOTE|AMBOS"
    }
  ],
  "umbrales_ambientales": [
    {
      "id_variable_ambiental": 1,
      "unidad_medida": "string",
      "valor_min": "15.0",
      "valor_max": "30.0",
      "niveles": [
        {"nivel": "normal", "limite_inferior": "15.0", "limite_superior": "25.0"},
        {"nivel": "precaucion", "limite_inferior": "25.0", "limite_superior": "28.0"},
        {"nivel": "critico", "limite_inferior": "28.0", "limite_superior": "30.0"}
      ]
    }
  ]
}
```

Claves permitidas en el snapshot (fuera de estas → BusinessRuleError FA-09):
`schema_version`, `ciclos_biologicos`, `patologias`, `metricas_produccion`, `umbrales_ambientales`
