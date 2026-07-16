# CU03 RF-17 — Gaps entre el documento y la base de datos

Fecha: 2026-06-21

---

## Contexto

Al analizar CU03 (Configurar Umbrales y Alertas Ambientales, RF-17) se encontraron ocho
discrepancias entre lo que describe el documento y lo que existe en el schema `modulo9`.
Todas fueron resueltas antes de iniciar la implementación.

---

## G1 — `umbrales_ambientales` falta `fecha_actualizacion`

**Problema:** FA-09 (concurrencia optimista) requiere timestamp de última modificación.
La tabla no tenía esta columna.

**Decisión:** Agregar columna nullable (NULL hasta la primera edición).

**SQL aplicado:**
```sql
ALTER TABLE modulo9.umbrales_ambientales
  ADD COLUMN fecha_actualizacion TIMESTAMPTZ;
```

**Estado:** ✅ Aplicado

---

## G2 — `nombre` NOT NULL e UNIQUE no corresponde al RF

**Problema:** La tabla tenía `nombre VARCHAR NOT NULL` con restricción de unicidad global
`uq_umbral_ambiental_nombre`. El RF-17 no define `nombre` como campo de entrada del usuario;
el identificador real de un umbral es la combinación (id_especie, id_variable_ambiental).
El campo `nombre` es redundante y la restricción impide múltiples umbrales para distintas
especies/variables.

**Decisión:** Hacer `nombre` nullable y eliminar la restricción de unicidad global.
El campo queda disponible en la tabla pero no lo gestiona este RF.

**SQL aplicado:**
```sql
ALTER TABLE modulo9.umbrales_ambientales
  ALTER COLUMN nombre DROP NOT NULL;
ALTER TABLE modulo9.umbrales_ambientales
  DROP CONSTRAINT IF EXISTS uq_umbral_ambiental_nombre;
```

**Estado:** ✅ Aplicado

---

## G3 — `descripcion` NOT NULL no tiene sentido

**Problema:** `descripcion VARCHAR NOT NULL` obliga a enviar una descripción, pero el
documento RF-17 no la lista como campo de entrada requerido.

**Decisión:** Hacer `descripcion` nullable.

**SQL aplicado:**
```sql
ALTER TABLE modulo9.umbrales_ambientales
  ALTER COLUMN descripcion DROP NOT NULL;
```

**Estado:** ✅ Aplicado

---

## G4 — Falta restricción de unicidad (id_especie, id_variable_ambiental)

**Problema:** FA-02 del documento dice que no puede existir más de una configuración activa
para la misma combinación de especie y variable ambiental. Sin la restricción en DB,
el sistema podría insertar duplicados si falla la validación en código.

**Decisión:** Agregar constraint UNIQUE compuesto como segunda línea de defensa.

**SQL aplicado:**
```sql
ALTER TABLE modulo9.umbrales_ambientales
  ADD CONSTRAINT uq_umbral_especie_variable
  UNIQUE (id_especie, id_variable_ambiental);
```

**Estado:** ✅ Aplicado

---

## G5 — `niveles_alerta_ambientales` sin unicidad por (umbral, nivel)

**Problema:** La tabla de niveles no tenía restricción de unicidad sobre
`(id_umbral_ambiental, nivel)`. Esto permitiría insertar dos registros `critico`
para el mismo umbral.

**Decisión:** Agregar constraint UNIQUE compuesto.

**SQL aplicado:**
```sql
ALTER TABLE modulo9.niveles_alerta_ambientales
  ADD CONSTRAINT uq_nivel_por_umbral
  UNIQUE (id_umbral_ambiental, nivel);
```

**Estado:** ✅ Aplicado

---

## G6 — No existe tabla `auditorias_umbrales_ambientales`

**Problema:** El RF dice que todas las operaciones quedan registradas en historial de
auditoría. No existía tabla de auditoría para este agregado.

**Decisión:** Crear tabla append-only con el mismo patrón que `auditorias_metricas_produccion`.

**SQL aplicado:**
```sql
CREATE TABLE modulo9.auditorias_umbrales_ambientales (
  id_auditoria_umbral   SERIAL PRIMARY KEY,
  id_umbral_ambiental   INTEGER NOT NULL
                          REFERENCES modulo9.umbrales_ambientales(id_umbral_ambiental),
  id_usuario            INTEGER REFERENCES modulo1.usuarios(id_usuario),
  tipo_operacion        VARCHAR(20) NOT NULL
                          CHECK (tipo_operacion IN ('CREATE','UPDATE','DEACTIVATE')),
  valores_anteriores    JSONB,
  valores_nuevos        JSONB NOT NULL,
  fecha_gestion         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Estado:** ✅ Aplicado

---

## G7 — Falta recurso RBAC `umbrales_ambientales` en `modulo1.recursos`

**Problema:** El sistema RBAC requiere un `id_recurso` para controlar permisos.
El último `id_recurso` registrado era 19 (metricas_produccion). Faltaba el registro
para umbrales.

**Decisión:** Insertar con `id_recurso = 20`.

**SQL aplicado:**
```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso)
VALUES (20, 'umbrales_ambientales');
```

**Estado:** ✅ Aplicado

---

## G8 — Faltan permisos para el recurso 20 en `modulo1.permisos`

**Problema:** Sin registros en `modulo1.permisos`, `require_permission(20, accion)`
lanza 403 para todos los usuarios, bloqueando cualquier endpoint.

**Decisión:** Dar permisos C/R/U/D al Administrador (rol 1) y al Veterinario (rol 3),
conforme a FA-06 del documento.

**SQL aplicado:**
```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion)
VALUES
  (1, 20, 1), (1, 20, 2), (1, 20, 3), (1, 20, 4),
  (3, 20, 1), (3, 20, 2), (3, 20, 3), (3, 20, 4);
```

**Estado:** ✅ Aplicado

---

## Resumen de decisiones de diseño

| Tema | Decisión |
|------|----------|
| `nombre` en umbrales | Nullable, no gestionado por RF-17 |
| `descripcion` en umbrales | Nullable, no requerida por RF-17 |
| `unidad_medida` en umbrales | Denormalización controlada: se puebla con `variables_ambientales.unidad` al crear |
| Unicidad de umbral | Por (id_especie, id_variable_ambiental) — constraint en DB + validación en use case |
| Niveles de alerta | Exactamente 3 (uno por valor del enum), contiguos y cubriendo [valor_min, valor_max] |
| Edición de niveles | Delete-then-insert: al editar se eliminan los 3 niveles anteriores y se insertan los nuevos |
| Concurrencia | Optimistic locking vía `fecha_actualizacion` (FA-09 → HTTP 412) |
| Dependencias externas | No hay dependencia de módulos externos en este RF (sin stub necesario) |
