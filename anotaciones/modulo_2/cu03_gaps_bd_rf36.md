# CU03 — Gaps de BD y RBAC — RF-36

## Fecha de análisis
2026-06-27

## Schema: modulo2

---

## Gaps encontrados

### GAP-01: Permiso faltante para Veterinario (RBAC)

**Situación:** El veterinario (id_rol=3) solo tenía R(2) sobre el recurso 29 (`activos_biologicos`). Según RF-36, el Veterinario es actor principal y puede registrar eventos sanitarios.

**Decisión:** Agregar acción C(1) al rol vet sobre recurso 29. Se reutiliza el recurso 29 existente para los eventos de lote (son sub-recursos de `/activos-biologicos/{id}/eventos`).

**SQL aplicado:**
```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo)
VALUES (3, 29, 1, 'vet_crear_activo_biologico', true);
```

**Estado:** Aplicado el 2026-06-27.

---

## Gaps de DDL: Ninguno

Las tablas de eventos ya existían en modulo2 con la estructura correcta:
- `modulo2.eventos_activos` (tabla padre)
- `modulo2.eventos_crecimeinto` (typo intencional en la BD)
- `modulo2.eventos_bajas`
- `modulo2.eventos_sanitarios`
- `modulo2.eventos_productivos`

Los modelos ORM, puertos, repositorios, use cases y endpoints fueron creados en código durante esta iteración.

---

## Decisiones de diseño

### D-01: Validación de densidad máxima por especie omitida

**Situación:** RF-36 menciona validar `densidad` contra `densidad_maxima_por_especie` definida en M09. El puerto `ParametrosEspeciePort` actual solo expone `nombre`, `tipo_medicion`, `aplica_a_tipo_activo` — no hay `valor_max` ni `densidad_maxima`.

**Decisión:** La validación se omite en esta iteración. La densidad se calcula y persiste, pero no se valida contra un máximo. Se deja como gap para cuando M09 exponga ese dato en `ParametrosEspeciePort`.

### D-02: Typo en nombre de tabla respetado

La tabla `modulo2.eventos_crecimeinto` (le falta la 'i' en "crecimiento") tiene el typo en la BD. El ORM mapea el nombre literal en `__tablename__` para no romper la FK existente.

### D-03: Enums PG mapeados como String

Los enums de PostgreSQL (`enum_evento_bajas_tipo`, `enum_evento_sanitario_tipo`) se mapean como `String` en los modelos ORM, siguiendo el patrón del proyecto para evitar conflicto con tipos existentes en la BD.

### D-04: Arquitectura sin herencia de tabla en SQLAlchemy

Aunque `sqlacodegen` generó los sub-modelos como clases Python que heredan de `EventosActivos`, el proyecto usa relaciones FK simples (`back_populates`) sin herencia de tabla SQLAlchemy. Esto es consistente con el resto del módulo y evita complejidad de mapeo.
