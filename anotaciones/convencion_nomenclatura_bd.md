# Convención de nomenclatura de base de datos — SGPMP

Convención acordada con el equipo para todo objeto nuevo o modificado en la base de
datos (tablas, columnas, índices, constraints, ENUMs, stored procedures, funciones y
triggers). Aplica a partir de este documento para toda migración Alembic nueva; no
implica renombrar retroactivamente objetos existentes que no la sigan.

| Categoría | Tipo | Elemento | Convención / Regla | Comentarios |
|---|---|---|---|---|
| Tablas | Tabla | Nombres de tablas | Idioma español. Sustantivos en plural, minúsculas, snake_case. Nombre único, descriptivo y representativo del dominio. Evitar prefijos innecesarios como `tbl_`. | Evitar colisiones semánticas entre módulos (ej. `usuarios` vs `usuarios_app`). No reutilizar nombres con distinto significado. Validar unicidad en el esquema completo. Evitar nombres genéricos (`datos`, `info`). |
| Columnas | Campo | Columnas de tablas | Idioma español. Sustantivos en singular, minúsculas, snake_case. Deben describir claramente el dato que almacenan. Cumplir 1FN: no repetir columnas ni almacenar datos multivaluados. | No duplicar lógica en columnas (`telefono1`, `telefono2`) — normalizar. Evitar columnas derivadas que puedan calcularse. Mantener coherencia exacta en nombres de FK/PK. |
| Índices | Índice | Índices regulares | Prefijo `idx_` + nombre de la(s) columna(s). Español, singular, minúsculas, snake_case. Claros, concisos, descriptivos. Sin abreviaciones ambiguas ni caracteres especiales. | Crear solo cuando exista un caso de uso real (consultas frecuentes). Índices innecesarios degradan INSERT/UPDATE. Alineación exacta con columnas indexadas. |
| Índices | Constraint | Llaves únicas (UNIQUE) | Prefijo `uq_` + nombre de la(s) columna(s). Español, singular, minúsculas, snake_case. No depender de nombres autogenerados por el motor — deben ser explícitos. | Validar reglas de negocio antes de definir unicidad. No confiar solo en validación de aplicación. Garantizar integridad desde la BD. |
| Índices | PK | Claves primarias (PK) | Formato `id_<tabla_en_singular>` (ej. `id_usuario`). Minúsculas, snake_case. Obligatoriamente `NOT NULL UNIQUE`. Evitar palabras reservadas de SQL. | No usar claves naturales que puedan cambiar. Preferir surrogate keys. Una sola PK por tabla. No reutilizar PK en otras tablas. |
| Índices | FK | Claves foráneas (FK) | Prefijo `<tabla>_<columna>_fkey`. La columna FK debe tener el mismo nombre que la PK referenciada (`id_usuario`). Con múltiples referencias a la misma tabla, diferenciar con contexto (`id_usuario_creador`, `id_usuario_modificador`). | Definir siempre `ON DELETE`/`ON UPDATE` explícitos. Evitar FKs huérfanas. Validar consistencia en migraciones. |
| Objeto de catálogo | ENUM | Tipos ENUM | Prefijo `enum_<tabla_singular>_<columna>`. Singular. Evitar valores genéricos (`otro`, `varios`) sin contexto. **Valores en MAYÚSCULA.** | Evitar ENUM cuando los valores puedan crecer dinámicamente — en ese caso usar tabla relacional. El ENUM debe ser estable y controlado. |
| Índices | Campo | Booleanos | Prefijo `es_` o `tiene_` (ej. `es_activo`, `tiene_permiso`). Evitar el anglicismo `is_`. Singular, claro, afirmativo. | Evitar dobles negaciones (`es_no_valido`). Mantener consistencia lógica (`true` = estado afirmativo). No usar enteros 0/1 sin tipado booleano. |
| Índices | Campo | Fechas (DATE/TIMESTAMP) | Prefijo obligatorio `fecha_` + descriptor semántico (ej. `fecha_creacion`, `fecha_actualizacion`, `fecha_evento`). | Uso exclusivo de `fecha_` para consistencia. No se permiten sufijos alternativos. |
| Índices | Campo | JSON (JSON/JSONB) | Prefijo `json_<columna>`. Español, minúsculas, snake_case. Preferir JSONB en PostgreSQL. Para indexación, usar GIN (`USING gin`). | No usar JSON como sustituto de normalización — solo para datos semi-estructurados o dinámicos. Indexar solo las claves necesarias (`->`, `->>`). Validar estructura con `CHECK` o en capa de aplicación. |
| Procedimientos | Stored Proc. | Procedimientos almacenados | Prefijo `sp_` (ej. `sp_crear_usuario`). Verbos en infinitivo, español, snake_case. | Evitar lógica de negocio excesivamente compleja en BD si afecta mantenibilidad. Documentar efectos secundarios (transacciones, múltiples tablas). |
| Funciones | Function | Funciones | Prefijo `fn_` (ej. `fn_calcular_total`). Deben describir claramente el valor que retornan. | Determinísticas cuando sea posible. Evitar efectos secundarios (modificar datos). Usar para cálculos y reutilización lógica. |
| Triggers | Trigger | Triggers | Prefijo obligatorio `trg_` + momento_evento + acción + tabla (ej. `trg_antes_insertar_usuario`, `trg_despues_actualizar_rol`). | Usar con moderación — pueden ocultar lógica y dificultar debugging. Documentar claramente su propósito y evitar dependencias encadenadas. |
| General | Regla general | Consistencia semántica | Mantener coherencia en todo el modelo. Evitar abreviaciones ambiguas (`usr`, `tmp`). Nombres descriptivos y uniformes. Una misma regla no debe romperse entre módulos. | Revisar en auditorías y validaciones del equipo de pruebas en cada entrega. Definir checklist de validación. Cualquier desviación debe justificarse técnicamente. |

## Nota sobre CHECK constraints

La tabla anterior no cubre explícitamente los `CHECK constraints`. Por consistencia
con el resto de constraints (`uq_`, `idx_`), se usa el prefijo `ck_` + nombre
descriptivo en singular, español, snake_case (ej. `ck_auditoria_plantilla_tipo_operacion`),
en vez de dejar el nombre autogenerado por Postgres.
