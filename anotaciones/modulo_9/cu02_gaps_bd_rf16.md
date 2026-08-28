# CU02 RF-16 — Gaps entre el documento y la base de datos

Documento para revisión con el diseñador de BD antes de implementar.  
Fecha: 2026-06-14

---

## Contexto

Al analizar CU02 (Configurar Parámetros por Especie, RF-16) se encontraron tres
discrepancias entre lo que describe el documento y lo que existe en el schema
`modulo9` de la base de datos. Ninguna impide arrancar la implementación, pero
las tres requieren una decisión antes de escribir código.

---

## Gap 1 — Etapas del ciclo productivo: falta `fecha_actualizacion`

### Tabla en DB

`modulo9.ciclos_biologicos`

```
id_ciclo_biologico  integer     PK
nombre              varchar(60) NOT NULL
descripcion         varchar(255)
duracion_dias       integer     NOT NULL
id_especie          integer     FK → modulo9.especies
es_activo           boolean     NOT NULL default true
```

### Problema

El flujo alternativo FA-07 del documento dice:

> "Si otro usuario modificó el registro antes de guardar, el sistema informa el
> conflicto y solicita recargar la información." → HTTP 412

Para implementar control de concurrencia optimista (igual que en CU01 con
`fecha_actualizacion`) necesitamos una columna de timestamp en la tabla. La
tabla actual **no la tiene**.

### Opciones

**Opción A (recomendada):** Agregar la columna a la DB:
```sql
ALTER TABLE modulo9.ciclos_biologicos
ADD COLUMN fecha_actualizacion TIMESTAMPTZ;
```
El valor queda `NULL` hasta la primera edición. El código la usa igual que en
`modulo9.especies`.

**Opción B:** Implementar sin concurrencia optimista por ahora. El FA-07 queda
pendiente hasta que se agregue la columna. Se anota en código con un `# TODO`.

### Pregunta para el diseñador de BD

¿Se puede agregar `fecha_actualizacion TIMESTAMPTZ` a `modulo9.ciclos_biologicos`?

---

## Gap 2 — Patologías: catálogo global vs. catálogo por especie

> **RESUELTO (2026-08-23, issue #1633).** Se decidió cumplir la **letra del RF-16**:
> patologías **por especie**. La discrepancia se cerró **sin tocar** `modulo9.patologias`
> ni su constraint `uq_enfermedad_nombre` — esa tabla es el catálogo clínico de **M04**
> (`src/prediction`: FK `modulo4.patologias_variables_sensoricas → modulo9.patologias`).
> La entidad M09 por especie pasó a vivir en `modulo9.especies_patologias`, ahora con
> `nombre`/`descripcion`/`es_activo`/`fecha_actualizacion`/`fecha_creacion` propios y
> unicidad por especie vía índice funcional `uq_especie_patologia_nombre (id_especie,
> lower(nombre))`. El vínculo `id_patologia` al catálogo M04 quedó **opcional (nullable)**.
> Migración: `alembic/versions/192872fafd40_rf16_patologias_por_especie_y_metricas_.py`.
> Detalle en `rf16-patologias-por-especie-mod9/resumen.md`.


### Lo que dice el documento RF-16

- Las patologías son configurables **por especie**.
- El nombre de la patología debe ser **único por especie** (case-insensitive).
- Una patología se registra seleccionando primero la especie.

### Lo que hay en la DB

La tabla `modulo9.patologias` es un **catálogo global** con restricción de
unicidad global sobre `nombre`:

```
modulo9.patologias
───────────────────────────────────────────
id_patologia        serial   PK
nombre              varchar(60)   UNIQUE GLOBAL (uq_enfermedad_nombre)
descripcion         varchar(255)
es_activo           boolean
nombre_tecnico      varchar(150)  -- campos propios de M04 (Predicción IA)
etiologia           text
categoria           enum(METABOLICA, PODAL, DIARREICA, RESPIRATORIA)
codigo_cie          varchar(150)
es_base             boolean
version_catalogo    integer
descripcion_clinica text
especie_aplicable   varchar(50)   default 'TODAS'
fecha_creacion_m04  timestamptz
id_usuario_creador  integer FK
```

La relación con la especie va por una tabla pivot:

```
modulo9.especies_patologias
───────────────────────────────────────────
id_especies_patologias  serial  PK
id_patologia            integer FK → patologias
id_especie              integer FK → especies
```

### Implicaciones

1. La restricción `uq_enfermedad_nombre` hace que el nombre sea único
   **globalmente**, no por especie. Si se registra "Fiebre Aftosa" para
   Bovinos, no se puede registrar "Fiebre Aftosa" para Ovinos.

2. La tabla tiene campos de M04 (Predicción IA) que el CU02 no usa:
   `etiologia`, `nombre_tecnico`, `categoria`, `codigo_cie`, etc. Esto sugiere
   que `modulo9.patologias` fue diseñada como catálogo compartido entre M09 y M04,
   no como catálogo exclusivo de M09.

3. La vista `vw_rf16_dependencias_patologias` para verificar dependencias al
   desactivar apunta a tablas de `modulo4`:
   ```sql
   LEFT JOIN modulo4.patologias_signos ps ON (ps.id_patologia = p.id_patologia)
   LEFT JOIN modulo4.predicciones pr ON (pr.id_patologia = p.id_patologia)
   LEFT JOIN modulo4.alertas_patologicas ap ON (ap.id_patologia = p.id_patologia)
   ```
   Esas tablas de M04 no existen todavía → se cubrirá con un stub.

### Preguntas para el diseñador de BD

1. ¿La unicidad de `nombre` debe ser global o por especie?
   - **Si global:** el documento RF-16 está equivocado en ese punto. Se implementa
     respetando la restricción de la DB (nombre único en todo el sistema).
   - **Si por especie:** hay que hacer:
     ```sql
     ALTER TABLE modulo9.patologias DROP CONSTRAINT uq_enfermedad_nombre;
     -- y la unicidad por especie se maneja via la tabla pivot especies_patologias
     -- con un índice único compuesto: (id_especie, lower(nombre))
     ```

2. ¿Los campos de M04 (`etiologia`, `categoria`, `codigo_cie`, etc.) los debe
   gestionar M09 CU02, o los gestiona M04 directamente y M09 solo maneja
   `nombre`, `descripcion` y `es_activo`?

3. ¿El flujo de CU02 inserta en `patologias` y luego en `especies_patologias`,
   o solo en `especies_patologias` referenciando una patología ya existente en
   el catálogo global?

---

## Gap 3 — Métricas productivas: estructura de DB insuficiente

### Lo que dice el documento RF-16

Las métricas productivas son configurables **por especie** e incluyen:

| Campo | Descripción |
|-------|-------------|
| `nombre` | Único por especie, 3–50 caracteres |
| `unidad_medida` | Obligatorio (kg, litros, cm, unidades…) |
| `tipo_medicion` | Enum: PESO, VOLUMEN, LONGITUD, CONTEO, OTRO |
| `aplica_a_tipo_activo` | Enum: INDIVIDUAL, LOTE, AMBOS |
| `es_activo` | Estado de disponibilidad |
| `id_especie` | FK a la especie a la que pertenece |

### Lo que hay en la DB

`modulo9.metricas_produccion`

```
id_metrica_produccion  serial   PK
nombre                 varchar(60)  NOT NULL
unidad_medida          varchar(20)  NOT NULL
tipo_medicion          varchar(55)  NOT NULL  (NO es enum en DB)
tiene_estado           boolean      NOT NULL  (no es es_activo)
```

**Columnas que faltan:**

| Campo requerido por RF | Estado en DB |
|---|---|
| `id_especie` | **No existe** — las métricas son catálogo global |
| `aplica_a_tipo_activo` | **No existe** |
| `es_activo` | Se llama `tiene_estado` y no funciona como baja lógica |
| `fecha_actualizacion` | **No existe** (mismo problema que etapas) |

La relación hacia la especie existe pero indirectamente:
`metricas_ciclo_productivo` → `ciclos_productivos` → `ciclos_biologicos` → `especies`

Es decir, la métrica no está directamente ligada a una especie sino a un ciclo
productivo concreto. Eso no es lo mismo que "métrica configurable por especie".

### Implicaciones

Con la estructura actual **no es posible implementar** el comportamiento que
describe RF-16 para métricas sin modificar la DB. Las opciones son:

**Opción A — Agregar columnas a `metricas_produccion`:**
```sql
ALTER TABLE modulo9.metricas_produccion
  ADD COLUMN id_especie         INTEGER REFERENCES modulo9.especies(id_especie),
  ADD COLUMN aplica_a_tipo_activo VARCHAR(10) DEFAULT 'AMBOS',
  ADD COLUMN es_activo          BOOLEAN NOT NULL DEFAULT true,
  ADD COLUMN fecha_actualizacion TIMESTAMPTZ;

-- Renombrar o dejar tiene_estado como campo legacy
```

**Opción B — Crear tabla nueva `metricas_especie`:**
Una tabla específica para RF-16 separada del catálogo global de métricas.

**Opción C — Diferir métricas de CU02:**
Implementar solo etapas y patologías en este CU. Las métricas quedan como
tarea pendiente hasta que el diseñador de BD defina la estructura correcta.
Se documenta en código con un TODO y en anotaciones.

### Pregunta para el diseñador de BD

¿Cuál es el diseño previsto para métricas por especie?
- ¿Se agregan columnas a `metricas_produccion`?
- ¿Se crea una tabla separada?
- ¿O las métricas son siempre globales y el RF está equivocado en ese punto?

---

## Resumen de decisiones pendientes

| # | Tema | Decisión tomada |
|---|------|-------------------|
| 1 | Etapas — concurrencia | `fecha_actualizacion` agregada a `ciclos_biologicos` (Opción A). |
| 2a | Patologías — unicidad | **Por especie** (#1633): unicidad `(id_especie, lower(nombre))` en `especies_patologias`. |
| 2b | Patologías — campos M04 | Solo M04 los gestiona; `modulo9.patologias` no se toca desde M09. |
| 2c | Patologías — flujo insert | M09 inserta solo en `especies_patologias`; `id_patologia` (vínculo M04) opcional/NULL. |
| 3 | Métricas — estructura | Opción A (ALTER ya aplicado antes) + CHECKs de dominio (`tipo_medicion`/`aplica_a_tipo_activo`) en #1633. |
