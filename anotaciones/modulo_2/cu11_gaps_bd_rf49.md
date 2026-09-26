# CU11 — Gaps de BD y RBAC — RF-49

Fecha: 2026-06-29

---

## Estado de la tabla preexistente

La tabla `modulo2.asociaciones_activos_sensores` ya existía en la DB pero estaba incompleta respecto al RF-49.

### Columnas preexistentes
| Columna | Tipo | Estado |
|---------|------|--------|
| id_asociacion_activo_sensor | SERIAL PK | ✓ |
| id_sensor | INTEGER NOT NULL → modulo9.sensores | ✓ |
| id_usuario | INTEGER NOT NULL → modulo1.usuarios | ✓ |
| fecha_inicio | TIMESTAMPTZ NOT NULL | ✓ |
| fecha_fin | TIMESTAMPTZ **NOT NULL** | ❌ Gap: debe ser nullable |
| motivo | TEXT nullable | ✓ |
| id_activo_biologico | INTEGER nullable → modulo2.activos_biologicos | ✓ |
| tipo | enum_asociaciones_activos_sensores_tipo (directa/ambiental/poblacional) | ✓ |

### Gaps detectados y DDL aplicado (2026-06-29)

```sql
-- 1. fecha_fin debe ser nullable (asociaciones activas no tienen fecha de fin)
ALTER TABLE modulo2.asociaciones_activos_sensores ALTER COLUMN fecha_fin DROP NOT NULL;

-- 2. Columnas faltantes según RF-49
ALTER TABLE modulo2.asociaciones_activos_sensores 
  ADD COLUMN tipo_activo VARCHAR(20) CHECK (tipo_activo IN ('INDIVIDUAL','LOTE')),
  ADD COLUMN dispositivo_iot_id INTEGER REFERENCES modulo9.dispositivos_iot(id_dispositivo_iot),
  ADD COLUMN id_infraestructura INTEGER REFERENCES modulo9.infraestructuras(id_infraestructura),
  ADD COLUMN estado_asociacion VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
    CHECK (estado_asociacion IN ('ACTIVA','INACTIVA','SUPERADA'));

-- 3. Tabla de auditoría (requerida por FA-07)
CREATE TABLE modulo2.auditorias_asociaciones_sensor_activo (
    id_auditoria SERIAL PRIMARY KEY,
    id_asociacion_activo_sensor INTEGER NOT NULL
        REFERENCES modulo2.asociaciones_activos_sensores(id_asociacion_activo_sensor),
    id_usuario INTEGER NOT NULL REFERENCES modulo1.usuarios(id_usuario),
    tipo_operacion VARCHAR(20) NOT NULL CHECK (tipo_operacion IN ('CREATE','DEACTIVATE','UPDATE')),
    valores_anteriores JSONB,
    valores_nuevos JSONB NOT NULL,
    fecha_gestion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Índice parcial preexistente
`uix_asociacion_sensor_activo_vigente` sobre `(id_sensor, id_activo_biologico) WHERE fecha_fin IS NULL`
→ El DB mismo impide tener dos asociaciones activas (sin fecha_fin) para el mismo par sensor+activo.

### FK duplicada detectada
La tabla tiene dos FK constraints sobre `id_activo_biologico`:
- `fk_asociacion_activo_biologico` → modulo2.activos_biologicos (correcta)
- `fk_usuario` → modulo2.activos_biologicos (error de nomenclatura en la DB; apunta al mismo lugar)

Decisión: el modelo ORM solo declara `fk_asociacion_activo_biologico`. La constraint `fk_usuario` existe en la DB pero se ignora en el modelo para evitar ambigüedad.

---

## RBAC aplicado (2026-06-29)

```sql
-- Nuevo recurso id_recurso = 30
INSERT INTO modulo1.recursos (nombre_recurso, descripcion) 
VALUES ('asociacion_sensor_activo', 'Asociación de sensores IoT a activos biológicos');

-- Permisos
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
  (1, 30, 1, 'admin_crear_asociacion_sensor_activo', true),
  (1, 30, 2, 'admin_leer_asociacion_sensor_activo', true),
  (4, 30, 1, 'ing_crear_asociacion_sensor_activo', true),
  (4, 30, 2, 'ing_leer_asociacion_sensor_activo', true),
  (2, 30, 1, 'prod_crear_asociacion_sensor_activo', true),
  (2, 30, 2, 'prod_leer_asociacion_sensor_activo', true),
  (3, 30, 2, 'vet_leer_asociacion_sensor_activo', true);
```

Roles con permiso de crear: Administrador (1), Productor (2) e Ingeniero de campo (4).
Rol con permiso solo de leer: Veterinario (3).

> Actualización INC-M02-37-G87 v2.0 (#349, 2026-09-16): el CREATE del
> Productor se formalizó mediante la migración Alembic v5.3.0
> `1d7d6069da52_v5_3_0_rf49_permiso_productor_`. Los POST de RF-49 limitan
> al Productor a activos e infraestructuras de sus propias fincas.

---

## Gaps no cubiertos (pendientes de infraestructura)

### Advertencia dispositivo offline (FA-05 → HTTP 201 + warning)
El modelo `modulo9.dispositivos_iot` no tiene campo `last_heartbeat` ni timestamp de última comunicación.
**Decisión**: La asociación se registra normalmente. El campo `advertencia` en la respuesta queda `null`.
Cuando el módulo de telemetría (M03) exponga el estado de conexión, se puede reactivar este warning.

### Compatibilidad especie-sensor (FA-04 → HTTP 400) — resuelto 2026-09-16

La revisión Alembic `281e99d58ecb` (`v5.3.0_rf49_compatibilidad_sensor_especie`)
crea `modulo9.compatibilidad_sensores_especies` como lista blanca por sensor.
La migración inicializa los pares que puede determinar sin inventar taxonomía:

- especie explícita de la infraestructura donde el sensor está instalado;
- especies compatibles con el tipo de esa infraestructura según el catálogo de RF-48.

`AsociarSensorActivoUseCase` consulta el catálogo mediante `SensorConsultaPort`
después de validar la coherencia territorial y antes de las cardinalidades V8.
Un par no listado responde `400 INCOMPATIBILIDAD_ESPECIE_SENSOR` con el mensaje
de FA-04. Un sensor sin ninguna regla también falla cerrado con
`400 COMPATIBILIDAD_SENSOR_NO_CONFIGURADA`; la ausencia de configuración ya no
equivale a compatibilidad universal.

El I3P-1 de variables fisicoquímicas conserva su función existente. La nueva
tabla separa explícitamente la compatibilidad biológica por sensor para evitar
sobrecargar ese catálogo con una semántica distinta.

---

## Valores del enum tipo (DB)

El campo `tipo` usa el tipo PG `enum_asociaciones_activos_sensores_tipo` con valores en **minúsculas**:
- `directa`
- `ambiental`
- `poblacional`

El DTO acepta valores en MAYÚSCULAS (`DIRECTA`, `AMBIENTAL`, `POBLACIONAL`) y el use case
normaliza a minúsculas antes de persistir.

---

## Iteración 2026-09-23 — Tarea Taiga "RF-49: Compatibilidad de especie sensor-activo y ciclo de vida completo"

Tarea recibida describiendo dos gaps, ambos copiados literalmente de `estado_M02.md`
(auditoría 2026-08-06): (1) "no existe validación de compatibilidad de especie... un
sensor de aves podría asociarse hoy a un bovino sin rechazo"; (2) "solo existe `POST
/{id}/sensores`... no hay endpoint para desactivar, reactivar ni listar". **Ambos ya
estaban resueltos en `dev`** antes de recibir esta tarea:

- Compatibilidad de especie: ya documentada arriba como "resuelto 2026-09-16"
  (sección "Compatibilidad especie-sensor"), bloque **V7** de
  `AsociarSensorActivoUseCase`, confirmado en vivo con 156 filas reales en
  `modulo9.compatibilidad_sensores_especies`.
- Ciclo de vida completo: `GET /{id}/sensores` (listar, con `tipo_consulta=ACTIVA|HISTORIAL`,
  commit `2b3e3772`) y `PATCH /{id}/sensores/{id_asociacion}` (activar/desactivar,
  commit `c1eaf765`, documentado en `inc_m02_65_g89_patch_ciclo_vida_asociacion_sensor.md`)
  ya existen como endpoints reales, con tests dedicados pasando.

### Gap real encontrado: el PATCH nunca funcionó en `dev` por RBAC faltante

`inc_m02_65_g89_patch_ciclo_vida_asociacion_sensor.md` documenta que el PATCH exige
`(recurso 30, accion U=3)`, y que ese permiso se insertó para Administrador (`id_rol=1`)
e Ingeniero de Campo (`id_rol=4`) — pero el propio documento aclara que el INSERT se
aplicó **directamente por SQL contra `sgpmp` y `pruebas`**, nunca se formalizó como
migración Alembic. Confirmado en vivo contra `sgpmp_dev`:

```sql
SELECT * FROM modulo1.permisos WHERE id_recurso = 30 AND id_accion = 3;
-- 0 filas
```

Es decir: el endpoint `PATCH /{id_activo}/sensores/{id_asociacion}` responde `403`
silencioso para **los 4 roles, incluido Administrador**, en `dev` — el escenario
exacto que el Paso 0 de `CLAUDE.md` pide verificar antes de dar por resuelta una
tarea de RBAC.

**Fix aplicado:** `alembic/versions/1ee808f9ee6b_v5_4_0_rf49_permiso_patch_asociacion_sensor.py`
formaliza el mismo INSERT que ya está vigente en `sgpmp`/`pruebas` (mismos roles,
mismo `nombre` de permiso), para que se aplique también en `dev` y en cualquier
entorno futuro vía `alembic upgrade head`. Verificado en vivo (transacción revertida):
`upgrade()` idempotente (correrlo dos veces no duplica filas, `ON CONFLICT DO NOTHING`
para `admin_*`/`DO UPDATE` para `ing_*`), `downgrade()` elimina solo la fila `ing_*`
— la fila `admin_*` es intencionalmente inmutable: `trg_fn_proteger_permisos_admin_delete`
bloquea cualquier `DELETE` sobre permisos `admin_%` con `ADMIN_PERM_NO_DELETE`,
confirmado al intentar revertirla en la misma verificación.

No se decide aquí si Productor también debería tener `U` sobre este recurso —
`inc_m02_65_g89...md` dejó esa pregunta explícitamente abierta para no invadir el
alcance de otro issue (#212), y el RF no lo exige de forma inequívoca. Queda fuera
de esta iteración.

**Sin cambios de código de producción** — ambos gaps del RF ya estaban resueltos en
código; el único trabajo real fue formalizar en Alembic un permiso RBAC que existía
en otros entornos pero nunca llegó a `dev`.
