# Gaps BD y RBAC — M02 CU01: RF-33 + RF-34

## Gaps identificados y resolución

### Tabla `modulo2.activos_biologicos`

| Gap | Tipo | Solución |
|-----|------|---------|
| `fecha_inicio_ciclo` era `integer` (año) | Tipo incorrecto | `ALTER COLUMN fecha_inicio_ciclo TYPE DATE USING NULL` — se eliminaron las 26 vistas dependientes y se recrearon |
| Faltaba `soporte_documental` | Columna ausente | `ADD COLUMN soporte_documental VARCHAR(150)` |
| Faltaba `detalles_procedencia` | Columna ausente | `ADD COLUMN detalles_procedencia VARCHAR(100)` |
| `id_especie` sin FK a `modulo9.especies` | Integridad | `ADD CONSTRAINT fk_activo_especie FOREIGN KEY (id_especie) REFERENCES modulo9.especies(id_especie)` |
| CHECK constraints `chk_activos_fecha_inicio_ciclo_*` comparaban como integer | Tipo | Eliminadas y recreadas con lógica DATE |
| Trigger `trg_fn_activo_fecha_inicio_valida` comparaba `< 0` y con epoch/días | Lógica rota | Actualizado a comparar con `DATE '1970-01-01'` y `CURRENT_DATE` |
| Trigger `trg_fn_activo_biologico_origen_financiero` buscaba `soporte_documental` en `atributos_dinamicos->>'soporte_documental'` | Diseño antiguo | Actualizado para usar la columna `soporte_documental` directamente |
| Trigger `trg_fn_activo_biologico_coherencia_tipo` buscaba `cantidad_inicial` en `atributos_dinamicos` | Diseño antiguo | Actualizado: `cantidad_inicial` ahora vive en `detalles_activos_biologicos_poblacionales`; el trigger valida solo `identificador` según tipo |

### Tabla `modulo2.detalles_activos_biologicos_poblacionales`

| Gap | Solución |
|-----|---------|
| Faltaba `peso_promedio_inicial` | `ADD COLUMN peso_promedio_inicial NUMERIC(10,4)` |
| `peso_promedio`, `biomasa_total`, `densidad` eran NOT NULL (se calculan en CU06) | Hechas nullable |

### Tablas con tipo incorrecto (TIME → TIMESTAMPTZ)

| Tabla | Columna | Solución |
|-------|---------|---------|
| `detalles_activos_individuales` | `fecha_creacion` | `ALTER TYPE timestamptz` |
| `auditoria_activos_biologicos` | `fecha_cambio` | `ALTER TYPE timestamptz` |
| `movimientos` | `fecha_fin` | `ALTER TYPE timestamptz` |
| `gestiones_fases` | `fecha_inicio` | `ALTER TYPE timestamptz` |

Vista `vw_rf46_historial_completo_activo` tenía cast `(gf.fecha_inicio)::time without time zone` que quedó inválido tras el ALTER. Corregida con `COALESCE(gf.fecha_finalizacion, gf.fecha_inicio)`.

### Tabla nueva — RF-34

```sql
CREATE TABLE modulo2.historial_infraestructura_activo (
    id_historial            SERIAL PRIMARY KEY,
    id_activo_biologico     INTEGER NOT NULL REFERENCES modulo2.activos_biologicos(id_activo_biologico),
    id_infraestructura      INTEGER NOT NULL REFERENCES modulo9.infraestructuras(id_infraestructura),
    fecha_inicio            TIMESTAMPTZ NOT NULL,
    fecha_fin               TIMESTAMPTZ,
    id_usuario_registro     INTEGER NOT NULL REFERENCES modulo1.usuarios(id_usuario),
    CONSTRAINT chk_historial_fechas CHECK (fecha_fin IS NULL OR fecha_fin > fecha_inicio)
);
CREATE UNIQUE INDEX uq_activo_asociacion_activa
    ON modulo2.historial_infraestructura_activo (id_activo_biologico)
    WHERE fecha_fin IS NULL;
```

`fecha_fin = NULL` indica la asociación activa. El índice parcial único garantiza exactamente una asociación activa por activo.

## RBAC

Recurso insertado en `modulo1.recursos`:
- `id_recurso = 29`, `nombre_recurso = 'activos_biologicos'`

Permisos en `modulo1.permisos`:

| Rol | id_rol | Acción | Nombre permiso |
|-----|--------|--------|---------------|
| Administrador | 1 | C (1) | `admin_crear_activo_biologico` |
| Administrador | 1 | R (2) | `admin_leer_activo_biologico` |
| Productor | 2 | C (1) | `prod_crear_activo_biologico` |
| Productor | 2 | R (2) | `prod_leer_activo_biologico` |
| Ingeniero | 4 | C (1) | `ing_crear_activo_biologico` |
| Ingeniero | 4 | R (2) | `ing_leer_activo_biologico` |
| Veterinario | 3 | R (2) | `vet_leer_activo_biologico` |

## Nota sobre `app.usuario_id`

El trigger `trg_auditar_activo_biologico` exige `SET LOCAL app.usuario_id = ?` antes de cualquier INSERT/UPDATE. El repositorio SQLAlchemy ejecuta esta sentencia al inicio del bloque `guardar()`.
