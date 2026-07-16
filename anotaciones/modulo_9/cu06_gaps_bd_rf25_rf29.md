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

**Decisión**: El JSONB tiene clave `"grid"` con array de widgets. La columna es `config` (no `layout_config`) y el array es `active_widget` (no `active_widgets`). Múltiples registros por usuario posibles; la vista usa el más reciente.

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
