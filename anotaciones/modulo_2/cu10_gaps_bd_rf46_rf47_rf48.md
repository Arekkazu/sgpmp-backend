# CU10 — Gaps BD y RBAC — RF-46, RF-47, RF-48

## Fecha de análisis
2026-06-29

## Consultas ejecutadas

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo9' AND table_name = 'infraestructuras'
ORDER BY ordinal_position;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'movimientos'
ORDER BY ordinal_position;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'modulo2' ORDER BY table_name;

SELECT r.id_recurso, p.nombre AS permiso, ro.nombre_rol AS rol, a.codigo AS accion, p.es_activo
FROM modulo1.permisos p
JOIN modulo1.recursos r ON p.id_recurso = r.id_recurso
JOIN modulo1.roles ro ON p.id_rol = ro.id_rol
JOIN modulo1.acciones a ON p.id_accion = a.id_accion
WHERE r.id_recurso = 29
ORDER BY ro.id_rol, a.id_accion;
```

## Resultado

### `modulo2.movimientos`
Columnas antes del DDL: `id_movimiento`, `id_usuario`, `fecha_transferencia`, `fecha_fin`, `tipo`
(`enum_movimiento_tipo`: salida|entrada), `id_activo_biologico`, `id_infraestructura_origen`,
`id_infraestructura_destino`, `fecha_registro`.

**Gap**: Falta columna `motivo_transferencia TEXT` requerida como campo obligatorio por RF-48.

Esta tabla es la fuente de eventos TRANSFERENCIA para RF-46. No se crea tabla adicional.

### `modulo9.infraestructuras`
Columnas antes del DDL: `id_infraestructura`, `descripcion`, `nombre`, `id_finca`, `superficie`,
`es_activo`, `tipo` (enum: corral|galpon|potrero|estanque|invernadero), `fecha_actualizacion`.

**Gap 1**: Falta `capacidad_maxima INTEGER NULL` — para validación C3 (RF-48). NULL = sin límite.
**Gap 2**: Falta `id_especie INTEGER NULL FK` — para validación C1 (RF-48). NULL = acepta todas las especies.

### Tabla `indicadores_zootecnicos`
Existe en `modulo2` con: `id_indicador_zootecnico`, `id_activo_biologico`, `rango_fecha` (daterange),
`tipo` (enum: ganancia_peso|produccion_promedio|tasa_morbilidad|tasa_mortalidad|conversion_alimenticia),
`paramtros_calculo` (jsonb).
No requiere stub — se consulta directamente para la Sección 6 de RF-47.

### Vistas pre-existentes en `modulo2`
Se encontraron vistas pre-creadas que se usan directamente mediante `text()`:
- `vw_rf46_historial_completo_activo`: UNION de ESTADO, FASE_PRODUCTIVA, SANITARIO, CRECIMIENTO, PRODUCTIVO, REPRODUCTIVO, INDICADOR.
  - **Nota**: no incluye BAJA ni TRANSFERENCIA — se consultan por separado desde `vw_rf46_eventos_bajas` y `movimientos`.
- `vw_rf46_eventos_bajas`: eventos de baja con categoría BAJA.
- `vw_rf46_eventos_crecimiento`, `vw_rf46_eventos_sanitarios`, `vw_rf46_eventos_productivos`, `vw_rf46_eventos_reproductivos`: vistas individuales.
- `vw_rf47_ficha_integral_activo`: datos consolidados del activo para la ficha integral.
- `vw_rf47_indicadores_zootecnicos_activo`: indicadores zootécnicos por activo.
- `vw_rf48_infraestructura_actual_activo`: infraestructura actual del activo.
- `vw_rf52_auditoria_transferencias_internas`: auditoría de transferencias vía `movimientos`.

### RBAC — Recurso 29 (`activos_biologicos`)
| Rol | Acciones disponibles |
|-----|---------------------|
| Administrador | C, R, U, D, E |
| Productor | C, R, U, D, E |
| Veterinario | C, R, D, E |
| Ingeniero de Campo | C, R, U, E |

- RF-46 (Leer historial) usa acción R(2) → admin ✓, prod ✓, vet ✓
- RF-47 (Ficha integral) usa acción R(2) → admin ✓, prod ✓, vet ✓
- RF-48 (Transferencia) usa acción E(5) → admin ✓, prod ✓

**Sin nuevos registros RBAC requeridos.**

## DDL aplicado (2026-06-29)

```sql
ALTER TABLE modulo2.movimientos
  ADD COLUMN IF NOT EXISTS motivo_transferencia TEXT;

ALTER TABLE modulo9.infraestructuras
  ADD COLUMN IF NOT EXISTS capacidad_maxima INTEGER;

ALTER TABLE modulo9.infraestructuras
  ADD COLUMN IF NOT EXISTS id_especie INTEGER REFERENCES modulo9.especies(id_especie);
```

## Decisiones

1. **Tabla de transferencias**: Se usa `modulo2.movimientos` existente. No se crea `evento_transferencia`.
2. **C1 (compatibilidad especie)**: `infraestructuras.id_especie IS NULL → acepta todas`. Si tiene valor, el activo debe tener la misma especie.
3. **C2 (compatibilidad tipo)**: ~~Cubierta implícitamente por C1. Si la infra tiene especie configurada y coincide con el activo, el tipo es compatible por configuración del administrador. Sin tabla de mapeo adicional.~~ **Superado por `074e5c14` (INC-M02-72-G80):** esa decisión resultó insuficiente — dejaba pasar cualquier tipo de infraestructura mientras la especie coincidiera, sin importar si el tipo físico (ej. Estanque) tenía sentido para esa especie. Se creó un modelo de compatibilidad dedicado, ver iteración 2026-09-23 más abajo.
4. **C3 (capacidad)**: `capacidad_maxima IS NULL → sin límite`. Si tiene valor, se verifica que ocupación actual + cantidad del activo no supere el máximo. Ocupación calculada en tiempo real contando activos con `id_infraestructura = destino` y estado != BAJA(6) y != CERRADO(5).
5. **Historial RF-46**: Se consultan las vistas `vw_rf46_*` y `movimientos` por separado en Python, se unen y ordenan cronológicamente antes de paginar.
6. **Ficha integral RF-47**: Se consulta `vw_rf47_ficha_integral_activo` y `vw_rf47_indicadores_zootecnicos_activo` directamente.
7. **Indicadores RF-51**: Ya existe tabla `modulo2.indicadores_zootecnicos`. Sin stub.

---

## Iteración 2026-09-23 — Tarea Taiga "RF-48: Regla C2, formato de error"

Tarea recibida describiendo dos gaps: (1) "Regla C2 (compatibilidad tipo de
infraestructura) no está implementada — el campo `tipo` está disponible pero
nunca se usa"; (2) "el error de fecha futura se traduce a HTTP 400 con
formato `{error_code, fields[]}` en vez del 422 con formato `{code, message,
field}`". Ambos textos son copia literal de `estado_M02.md` (auditoría
2026-08-06) — **ambos gaps ya estaban resueltos en `dev` antes de recibir
esta tarea**, confirmado por `git log`:

- `074e5c14 fix(rf48): crear modelo de compatibilidad tipo-infraestructura/especie (C2)` — revisó la
  decisión original de este mismo documento ("C2 cubierta implícitamente por C1, sin tabla de mapeo
  adicional") y la reemplazó por un modelo dedicado real: `modulo9.tipos_area` +
  `modulo9.compatibilidades_tipo_area_especie`, consultado desde
  `InfraestructuraM09Adapter.es_tipo_compatible()` y aplicado en
  `RegistrarTransferenciaUseCase._execute` (E-07b, `code='INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA'`, 422).
  Confirmado en vivo contra `sgpmp_dev`: 6 filas sembradas, todas para el tipo `Estanque` con especies
  acuáticas (`Tilapia`, `Cachama Blanca`, `Camarón Blanco`, etc.) — un tipo de infraestructura sin
  ninguna regla configurada sigue sin restricción (comportamiento de transición documentado en el
  propio código). El ejemplo del RF ("un activo avícola a un estanque no sería rechazado") ya no
  ocurre: hoy se rechaza con `422 INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA`.
- `875732f8 fix(rf48): devolver 422 para fecha futura` — la validación de `fecha_transferencia` futura
  se sacó del `@field_validator` de Pydantic (que sí produce el formato `{error_code, fields[]}` vía
  `RequestValidationError`, HTTP 400/422 genérico) y se movió al use case como regla de negocio E-10
  (`BusinessRuleError`, `code='FECHA_TRANSFERENCIA_FUTURA'`, `field='fecha_transferencia'`, HTTP 422).

**Hallazgo real de esta iteración:** los 2 tests que llevaban toda la sesión reportándose como "fallas
pre-existentes conocidas, no relacionadas" en cada corrida de la suite completa (`tests/biological_assets/
test_registrar_transferencia_use_case.py::test_endpoint_fecha_futura_responde_422_con_campo_y_mensaje` y
`::test_fecha_actual_conserva_el_flujo_existente`) son justamente las pruebas de regresión que RF-48
escribió para el fix de fecha futura (commit `875732f8`, el único commit que tocó ese archivo de test).
Se rompieron **después**, cuando `05c5ed01 fix(rf52): registrar rechazos tempranos en auditoría` le
agregó a `RegistrarTransferenciaUseCase.execute()` el wrapper `ejecutar_con_auditoria_de_rechazo(...)`
-- nadie ajustó los fixtures de estos 2 tests a los nuevos requisitos de ese wrapper:

- `ejecutar_con_auditoria_de_rechazo` necesita llamar `db.rollback()` de verdad (para separar cualquier
  escritura pendiente del registro de auditoría del rechazo) cuando `bitacora_repo is not None`. El
  fixture `cliente_transferencia` inyectaba `db=ColaboradorNoInvocado()` (una clase que lanza
  `AssertionError` ante *cualquier* acceso de atributo) — rompía en el primer `db.rollback()` real.
- `RegistrarTransferenciaUseCase.execute()` toma una referencia a `self.activo_repo.obtener_por_id`
  (para pasarla como `obtener_activo` al wrapper) en el momento de construir la llamada, antes de que el
  wrapper decida si de verdad la va a usar. Con `activo_repo=ColaboradorNoInvocado()`, el simple *acceso*
  al atributo ya lanzaba, sin llegar siquiera a evaluar si `bitacora_repo is None` (caso en el que el
  wrapper nunca la habría invocado).

No es un bug de producción: en producción `activo_repo`/`db` son siempre instancias reales
(`SqlAlchemyActivoBiologicoRepository`/`Session`), donde tomar una referencia a un método o llamar
`rollback()` sobre una sesión sin cambios pendientes es una operación válida y sin efectos secundarios.
Es puramente un defecto de diseño de fixture: `ColaboradorNoInvocado` es demasiado estricta para cómo el
wrapper de RF-52 necesita tocar sus colaboradores incluso en el camino de rechazo. Corregido con un
`DbFake` real (con `commit()`/`rollback()` no-op) para el `db` del endpoint, y una
`ActivoRepoNoDebeConsultarse` que permite el acceso al atributo pero sigue fallando si `obtener_por_id`
se llega a *invocar* de verdad (preservando la intención original del test). Suite completa: 763 passed,
199 skipped, 0 failed (antes: 761 passed, 199 skipped, 2 failed).

**Sin cambios de código de producción, sin migración nueva, sin cambios de RBAC** — ambos gaps del RF ya
estaban resueltos; el único trabajo real de esta iteración fue reparar la cobertura de regresión rota.

## Iteración 2026-09-24 — Tarea Taiga "RF-47: Sección 8 (accesos directos), densidad real, fallo parcial por sección"

Tarea recibida con tres gaps copiados de `estado_M02.md`. Contra `dev`:

- **Fallo parcial por sección: casi resuelto.** `4f63a9dc fix(rf47): una seccion que no carga
  ya no tumba la ficha integral` ya cargaba en savepoint las 4 subconsultas de eventos y la de
  indicadores. Faltaba la vista base `vw_rf47_ficha_integral_activo` (secciones 1-4 y 7): si
  fallaba, tumbaba toda la ficha con 500. Ahora también carga en savepoint como la sección
  `Datos generales` y, si falla, la ficha usa el fallback con los datos del activo.
- **Densidad: pendiente, corregido.** La ficha ponía `densidad=None` fijo. No hacía falta
  calcularla: RF-36/RF-45/RF-48 ya la mantienen en
  `modulo2.detalles_activos_biologicos_poblacionales.densidad` y el repositorio la carga en
  `activo.detalle_poblacional`. Confirmado en `sgpmp_dev`: 5 de 6 lotes tienen densidad
  guardada (el lote 6 responde `9.74`).
- **Sección 8 (accesos directos): pendiente, implementada.** Nuevo campo
  `accesos_directos` en `FichaIntegralResponse`, calculado en el router (el filtrado por
  permisos es RBAC, que según `CLAUDE.md` vive en el router). Cada acceso exige el mismo
  `(recurso 29, acción)` que su endpoint; un test compara la tabla de accesos contra la
  dependencia RBAC real de cada ruta, para que no puedan desincronizarse.

Sin DDL ni DML: no hay columnas, vistas ni permisos nuevos.

