# CU06 — Gaps BD y RBAC: RF-25, RF-26, RF-27, RF-28, RF-29

Fecha de análisis: 2026-06-21

---

## Estado de tablas en `modulo9` (todas pre-existentes)

Todas las tablas necesarias para CU06 ya existen en la BD.

### `modulo9.identidad_visuales` (RF-26)

| Columna          | Tipo          | Nullable | Nota                          |
|-----------------|---------------|----------|-------------------------------|
| id_identidad_visual | integer (PK) | NO | Secuencia auto                |
| id_finca        | integer       | NO       | FK a modulo9.fincas — **por finca, no singleton global** |
| id_usuario      | integer       | NO       | FK a modulo1.usuarios         |
| logo_path       | varchar       | YES      |                               |
| primary_color   | varchar       | YES      |                               |
| secondary_color | varchar       | YES      |                               |
| org_display_name| varchar       | YES      |                               |
| version         | integer       | YES      | Concurrencia optimista (no `fecha_actualizacion`) |
| fecha_creacion  | timestamptz   | YES      |                               |

**Decisión**: Identidad visual es **per-finca**, no singleton del sistema. El endpoint POST/PATCH recibe `id_finca` como parámetro. La concurrencia se controla con `version` (entero), no con `fecha_actualizacion`. La vista `vw_rf26_identidad_visual_activa` retorna la fila con `version DESC` por finca.

Tabla de auditoría `modulo9.auditorias_visuales`:

| Columna             | Tipo        | Nullable | Nota |
|--------------------|-------------|----------|------|
| id_auditoria_visual | integer (PK)| NO      |      |
| id_usuario         | integer     | NO       | FK   |
| fecha_creacion     | timestamptz | NO       |      |
| valor_anterior     | jsonb       | NO       |      |
| valor_nuevo        | jsonb       | NO       |      |

**Sin FK directa** a `identidad_visuales`. El id_finca se registra dentro de los campos JSON.

---

### `modulo9.temas_visuales` (RF-27)

| Columna           | Tipo        | Nullable | Nota                       |
|------------------|-------------|----------|----------------------------|
| id_tema_visual   | integer (PK)| NO       | Secuencia auto             |
| id_usuario       | integer     | NO       | FK — **NOT NULL incluso en global** |
| theme_mode       | integer     | NO       | 1=Claro, 2=Oscuro, 3=Sistema |
| es_global        | boolean     | NO       | True = tema global admin   |
| fecha_actualizacion | timestamptz | NO    |                            |

**Decisión**: Para el registro global, `id_usuario` es el admin que lo configuró y `es_global=TRUE`. Para preferencia personal: `es_global=FALSE`, `id_usuario` = usuario. Múltiples registros por usuario son posibles; la vista usa el más reciente (`fecha_actualizacion DESC`).

---

### `modulo9.preferencias_idiomas` (RF-29)

| Columna              | Tipo        | Nullable | Nota                      |
|---------------------|-------------|----------|---------------------------|
| id_preferencia_idioma| integer (PK)| NO      | Secuencia auto            |
| id_usuario          | integer     | NO       | FK — **NOT NULL incluso en global** |
| locale_code         | varchar     | NO       | 'es-CO' o 'en-US'        |
| es_por_defecto      | boolean     | NO       | True = idioma global      |
| fecha_actualizacion | timestamptz | YES      |                           |

**Decisión**: Mismo patrón que temas_visuales. Global: `es_por_defecto=TRUE`, `id_usuario` = admin. Personal: `es_por_defecto=FALSE`. La vista `vw_rf29_idioma_usuario_global` implementa la jerarquía de resolución.

---

### `modulo9.dashboard_layouts` (RF-28)

| Columna             | Tipo        | Nullable | Nota                          |
|--------------------|-------------|----------|-------------------------------|
| id_dashboard_layout | integer (PK)| NO      | Secuencia auto                |
| id_usuario         | integer     | NO       | FK                            |
| config             | jsonb       | NO       | `{"grid": [...widgets...]}` — **columna es `config`, no `layout_config`** |
| active_widget      | ARRAY       | NO       | TEXT[] — **singular, no plural** |
| fecha_actualizacion| timestamptz | YES      |                               |

**Decisión**: El JSONB tiene clave `"grid"` con array de widgets. La columna es `config` (no `layout_config`) y el array es `active_widget` (no `active_widgets`).

> **Actualización 2026-09-02 — migración `a7f3c92e4d18`.** El "múltiples registros por usuario
> posibles" que decía esta nota era un gap, no una decisión: dos `PATCH` concurrentes de un usuario
> sin fila previa insertaban dos filas y el repositorio desempataba por `fecha_actualizacion DESC`.
> Ya está resuelto con `UNIQUE(id_usuario)`, previo dedup (no-op en dev: 0 duplicados). En la misma
> migración se validó la FK `dashboard_layouts_id_usuario_fkey`, que estaba `NOT VALID` desde su
> creación: nunca se había comprobado contra las filas existentes.

---

### `modulo9.widgets` (RF-28) — creada 2026-09-02

Catálogo de widgets del dashboard. No existía; `config->grid[].id_widget` era un entero libre, sin
nada contra qué validarlo, así que los flujos alternos de "tipo de widget inexistente" y "widget no
disponible para su rol" eran inaplicables.

| Columna             | Tipo          | Nullable | Nota                                             |
|--------------------|---------------|----------|--------------------------------------------------|
| id_widget          | integer (PK)  | NO       | Ids 1-15 fijos, los mismos que el frontend usaba  |
| clave              | varchar(40)   | NO       | UNIQUE — es lo que viaja en `active_widget`       |
| nombre             | varchar(80)   | NO       |                                                   |
| grupo              | varchar(40)   | NO       | Ambiental / IoT / Alertas / Histórico / …         |
| span_predeterminado| smallint      | NO       | CHECK IN (1,2)                                    |
| id_recurso         | integer       | NO       | FK → `modulo1.recursos` — **gobierna el 403**     |
| fuente_datos       | varchar(60)   | YES      | Vista `vw_rf28_widget_*`; NULL = sin fuente aún   |
| es_activo          | boolean       | NO       | DEFAULT true                                      |

**Decisión**: la autorización por widget se resuelve por `id_recurso`, no por rol. Un widget se ve si
el rol tiene permiso `R` sobre su recurso en `modulo1.permisos`, así que cambiar una fila de permisos
cambia qué ve cada rol sin tocar código y sin escribir ningún `id_rol` en el backend. Los ids y
claves replican exactamente los que el frontend tenía quemados, para que los layouts ya guardados
sigan resolviendo sin migración de datos.

Mapeo widget → recurso: ambientales (1-5) → 33 `monitoreo_telemetria`; 6 → 35 `infraestructura_iot`;
7 y 15 → 11 `dispositivos_iot`; 8-9 → 32 `alertas_operativas`; 10-11 → 34 `historial_telemetria`;
12-13 → 19 `metricas_produccion`; 14 → 9 `fincas`.

---

### `modulo9.dashboard_layouts_default` (RF-28) — creada 2026-09-02

Layout base por rol. Antes vivía en `_DEFAULT_GRID_POR_ROL`, un diccionario **vacío** quemado en la
entidad de dominio con llaves 1-5: "Restaurar configuración predeterminada" era un no-op silencioso
y los roles 6-9 ni figuraban.

| Columna       | Tipo         | Nullable | Nota                                    |
|--------------|--------------|----------|-----------------------------------------|
| id_rol       | integer (PK) | NO       | FK → `modulo1.roles` ON DELETE CASCADE  |
| config       | jsonb        | NO       | Mismo formato que `dashboard_layouts`   |
| active_widget| ARRAY        | NO       | TEXT[]                                  |

**Decisión**: una fila por cada uno de los 9 roles existentes. Regla del seed: **un default solo
contiene widgets cuyo recurso ese rol lee de verdad**, verificado contra `modulo1.permisos`. Los
roles 6-9 (Supervisor, Gestor de Granja, Revisor Fiscal, Externo AgroFusion) no tienen `R` sobre
ningún recurso de widget, así que su grid base es vacío a propósito. Un rol creado *después* de esta
migración no tendrá fila y `POST /restaurar` responderá `500 RESTAURACION_SIN_DEFAULT` — que es
exactamente el flujo alterno que el RF define; la corrección operativa es insertarle su layout base.

---

## Relación usuario → finca activa (RF-25)

`modulo1.usuarios` **no tiene campo `id_finca`**. La relación es:
- `modulo9.fincas.id_usuario` = id del productor/admin dueño de la finca
- Vista `vw_rf25_contexto_usuario` ya existe y hace el JOIN: `fincas WHERE id_usuario = u.id_usuario AND es_activo IS TRUE`

El repositorio de RF-25 consulta esta vista directamente.

---

## RBAC — Recursos y permisos insertados

### Recursos (modulo1.recursos)

| id_recurso | nombre_recurso           | descripcion                                     |
|------------|-------------------------|-------------------------------------------------|
| 22         | contexto_interfaz       | Contexto de interfaz adaptativa del usuario     |
| 23         | identidad_visual        | Identidad visual institucional por finca        |
| 24         | tema_visual             | Preferencia de tema visual del usuario          |
| 25         | dashboard_layout        | Configuración del dashboard del usuario         |
| 26         | preferencia_idioma      | Preferencia de idioma del usuario               |
| 27         | configuracion_ui_global | Tema e idioma predeterminado del sistema (admin)|

**Nota**: `modulo1.recursos` usa columna `nombre_recurso` (no `nombre`) y no tiene columna `modulo`.

### Permisos insertados (modulo1.permisos, IDs 117–156)

| id_recurso | Rol       | Acciones |
|------------|-----------|---------|
| 22 (contexto_interfaz) | todos (1-5) | R |
| 23 (identidad_visual)  | admin (1)   | C, R, U |
| 24 (tema_visual)       | todos (1-5) | R, U |
| 25 (dashboard_layout)  | todos (1-5) | R, U |
| 26 (preferencia_idioma)| todos (1-5) | R, U |
| 27 (configuracion_ui_global) | admin (1) | R, U |

---

## SQL aplicado

```sql
-- Recursos
INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial, fecha_creacion) VALUES
  ('contexto_interfaz',        'Contexto de interfaz adaptativa del usuario',       false, NOW()),
  ('identidad_visual',         'Identidad visual institucional por finca',           false, NOW()),
  ('tema_visual',              'Preferencia de tema visual del usuario',             false, NOW()),
  ('dashboard_layout',         'Configuración del dashboard del usuario',            false, NOW()),
  ('preferencia_idioma',       'Preferencia de idioma del usuario',                 false, NOW()),
  ('configuracion_ui_global',  'Tema e idioma predeterminado del sistema (admin)',   false, NOW());

-- Permisos: ver texto completo de la sesión de implementación (2026-06-21)
-- 40 permisos insertados, IDs 117–156
```


---

## RF-28 — DDL aplicado (2026-09-02)

Todo por **migración Alembic `a7f3c92e4d18`** (`down_revision` `c4a19e7d2b63`), no por SQL suelto:
el DDL manual vía MCP es lo que dejó a `sgpmp` y `pruebas` desincronizadas en otros cambios de este
módulo, y solo lo que vive en `alembic/versions/` llega a las bases de dev y test por CI.

```sql
-- 1. Catálogo de widgets, con el recurso que gobierna cada uno
CREATE TABLE modulo9.widgets (
  id_widget            INTEGER PRIMARY KEY,
  clave                VARCHAR(40)  NOT NULL UNIQUE,
  nombre               VARCHAR(80)  NOT NULL,
  grupo                VARCHAR(40)  NOT NULL,
  span_predeterminado  SMALLINT     NOT NULL,
  id_recurso           INTEGER      NOT NULL REFERENCES modulo1.recursos(id_recurso),
  fuente_datos         VARCHAR(60),
  es_activo            BOOLEAN      NOT NULL DEFAULT true,
  CONSTRAINT widgets_span_predeterminado_check CHECK (span_predeterminado IN (1, 2))
);
-- + seed de los 15 widgets

-- 2. Layout base por rol
CREATE TABLE modulo9.dashboard_layouts_default (
  id_rol        INTEGER PRIMARY KEY REFERENCES modulo1.roles(id_rol) ON DELETE CASCADE,
  config        JSONB   NOT NULL,
  active_widget TEXT[]  NOT NULL
);
-- + seed de 9 filas (una por rol)

-- 3. Un layout por usuario (dedup previo, no-op en dev: 0 duplicados)
DELETE FROM modulo9.dashboard_layouts a USING modulo9.dashboard_layouts b
 WHERE a.id_usuario = b.id_usuario AND (... conserva la más reciente ...);
ALTER TABLE modulo9.dashboard_layouts
  ADD CONSTRAINT uq_dashboard_layouts_usuario UNIQUE (id_usuario);

-- 4. La FK nunca se había comprobado
ALTER TABLE modulo9.dashboard_layouts
  VALIDATE CONSTRAINT dashboard_layouts_id_usuario_fkey;
```

**RBAC**: no hizo falta DML. El recurso 25 `dashboard_layout` y sus permisos `R`/`U` para los roles
1-5 ya existían desde 2026-06-21. Los permisos por widget se leen de los recursos que ya gobiernan
cada módulo (9, 11, 19, 32, 33, 34, 35), sin filas nuevas.

**Verificación post-migración**: 15 filas en `widgets`, 9 en `dashboard_layouts_default`,
`UNIQUE` presente, FK con `convalidated = true`, y 0 defaults referenciando un widget que su rol no
pueda leer. `alembic downgrade -1` y `upgrade head` probados en dev.
