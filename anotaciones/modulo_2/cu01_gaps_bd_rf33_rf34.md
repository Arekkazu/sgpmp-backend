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

---

## Actualización — cierre de gaps de RF-34 (issue #29)

Retomando los 4 gaps documentados en `anotaciones/modulo_2/estado_M02.md` (RF-34, ~55%):
falta `fecha_referencia`, 200 en vez de 404 en el flujo E2, falta `sensores_en_infraestructura`
(RF-22) y falta `advertencia_integridad`.

### Paso 0 — verificación contra el esquema real (MCP postgres)

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'historial_infraestructura_activo';
```

`historial_infraestructura_activo` ya tenía todo lo necesario desde la creación original
de CU01: `fecha_inicio`/`fecha_fin` en `TIMESTAMPTZ`, `fecha_fin IS NULL` para la
asociación activa, índice único parcial `uq_activo_asociacion_activa`. **Ningún DDL nuevo
requerido** — el gap era puramente de aplicación (parámetro faltante en el endpoint, rama
de error faltante en el use case), no de base de datos.

Para `sensores_en_infraestructura` (enriquecimiento vía RF-22) se verificó
`modulo9.sensores_areas_asociadas` (`id_sensor`, `id_infraestructura`, `tiene_estado`,
`punto_instalacion`) y `modulo9.sensores` (`id_sensores`, `nombre`, `categoria`,
`es_activo`) — ambas tablas ya existen y están pobladas por el flujo real de RF-22
(`asociar_sensor_area_use_case.py` en `src/configuration`), así que se implementó un
adaptador real (`InfraestructuraM09Adapter.listar_sensores_activos`), **no un stub** —
el patrón de "Adaptador stub" del CLAUDE.md aplica solo cuando el módulo real todavía no
existe, y aquí RF-22 ya está implementado (~90%, ver `anotaciones/modulo_9/estado_M09.md`).

### RBAC

Sin cambios. El endpoint sigue usando `require_permission(29, 2)` (R sobre
`activos_biologicos`), y ese permiso ya está sembrado para Administrador, Productor,
Ingeniero y Veterinario desde el CU01 original — no se agregó ningún recurso ni permiso
nuevo para esta corrección.

### Decisiones de diseño

- `fecha_referencia` (query param opcional) solo es válido junto a `tipo_consulta=ACTIVA`
  (rechazado con `400 FECHA_REFERENCIA_INVALIDA` si se envía junto a `HISTORIAL`, para no
  mezclar dos semánticas de consulta en el mismo parámetro). Cuando se envía, hace una
  búsqueda puntual (`fecha_inicio <= fecha_referencia AND (fecha_fin IS NULL OR fecha_fin > fecha_referencia)`)
  en vez de la asociación vigente hoy — nuevo método de repositorio
  `obtener_asociacion_en_fecha`.
- El flujo E2 (sin asociación activa) ahora lanza `404 ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA`
  con mensaje de alerta técnica, tanto para la consulta de "hoy" como para una consulta con
  `fecha_referencia` sin cobertura en esa fecha — mismo código, mismo tipo de inconsistencia.
- `advertencia_integridad` se calcula siempre (para `ACTIVA` e `HISTORIAL` por igual)
  comparando pares de períodos del historial completo del activo por solapamiento de
  rango; es una advertencia informativa en el response, nunca bloquea la consulta.

---

## Gaps adicionales — issue #28 (auditoría de cumplimiento RF-33)

Una auditoría posterior (`anotaciones/modulo_2/estado_M02.md`, RF-33) encontró tres gaps reales sobre el código ya implementado en este CU. Se corrigen aquí siguiendo el mismo Paso 0.

**Nota sobre el Paso 0 de esta corrección:** el servidor MCP de Postgres estuvo caído (`CONNECTION_CLOSED`) durante esta tarea, así que no se pudo re-verificar en vivo el estado exacto de los datos. Se usó como evidencia la fila `BOV-003` ya confirmada por la auditoría previa (`origen_financiero='compra'`, `costo_adquisicion=8000000.0000`, `soporte_documental=NULL`). No se aplicó ningún DDL/DML contra la base compartida — solo se crearon los archivos de migración; quedan pendientes de `alembic upgrade head` por quien tenga acceso a MCP o a la base.

### Gap 1 — No existe snapshot inicial (Evento 0)

El RF-33 exige que el registro de un activo deje un snapshot en `historial_activos` con `version=1`, `tipo_evento=CREACION`. La tabla no existía y `ActivoBiologico._snapshot()` nunca se invocaba desde el registro.

Solución:
- Migración `3d0b4cbfb11c_rf33_historial_activos_snapshot.py`: crea `modulo2.historial_activos` (`id_historial_activo` PK, `id_activo_biologico` FK a `activos_biologicos` con `ON DELETE CASCADE`, `version`, `tipo_evento`, `json_snapshot` JSONB, `fecha_evento`, `id_usuario` FK a `modulo1.usuarios`), con `uq_historial_activo_activo_biologico_version (id_activo_biologico, version)` y `ck_historial_activo_version_positiva (version > 0)`.
- Nueva entidad `HistorialActivo` en `domain/entities/activo_biologico.py`, método de puerto `registrar_historial()` en `ActivoBiologicoRepository` (dominio) e implementación en `SqlAlchemyActivoBiologicoRepository`.
- `RegistrarActivoBiologicoUseCase.execute()` invoca `activo._snapshot()` e inserta el Evento 0 (`version=1`, `tipo_evento='CREACION'`) dentro de la misma transacción que `repo.guardar()`, antes del único `commit()`.
- Columna `json_snapshot` (no `snapshot`) para seguir el prefijo `json_` de `anotaciones/convencion_nomenclatura_bd.md` en columnas JSON/JSONB.

### Gap 2 — Sin CHECK a nivel de DB para soporte documental

El RF exige `soporte_documental` obligatorio si `costo_adquisicion` no es nulo; solo se validaba en el DTO. La fila `BOV-003` ya viola la regla en dev, así que un CHECK validado normalmente fallaría al aplicarse.

Solución — migración `2898e45d9813_rf33_check_soporte_documental_costo.py`:
```sql
ALTER TABLE modulo2.activos_biologicos
ADD CONSTRAINT ck_activo_biologico_soporte_documental_requerido
CHECK (costo_adquisicion IS NULL OR soporte_documental IS NOT NULL)
NOT VALID;
```
`NOT VALID` aplica la regla a todo INSERT/UPDATE nuevo de inmediato, pero no escanea las filas existentes al crearse — la migración no falla por `BOV-003`. Queda pendiente, como seguimiento separado: limpiar los datos inconsistentes (backfill de `soporte_documental` o anular `costo_adquisicion` según corresponda a cada fila) y luego correr `VALIDATE CONSTRAINT ck_activo_biologico_soporte_documental_requerido` en una migración posterior (toma `SHARE UPDATE EXCLUSIVE`, no bloquea lecturas/escrituras concurrentes).

### Gap 3 — Código HTTP incorrecto en "costo de adquisición inválido para el origen"

La regla FA-08 (coherencia `costo_adquisicion`/`soporte_documental` según `origen_financiero`) vivía en un `@model_validator` de Pydantic en `RegistrarActivoBiologicoDTO`, que al fallar produce `RequestValidationError` → 400, no el 422 que exige el RF.

Solución: se movió la validación de coherencia a `RegistrarActivoBiologicoUseCase._validar_origen_financiero()`, que lanza `BusinessRuleError` (422) con código `COSTO_ADQUISICION_INVALIDO` / `SOPORTE_DOCUMENTAL_REQUERIDO` / `SOPORTE_DOCUMENTAL_INVALIDO` según el caso. El DTO conserva solo la validación de formato (que `origen_financiero` sea uno de los 4 valores del catálogo), que sigue siendo un 400 legítimo por ser un error de forma, no de regla de negocio.

### RBAC

Sin cambios — estos tres gaps son de esquema y de código HTTP, no tocan permisos. El recurso 29 y sus permisos ya documentados arriba siguen aplicando.
