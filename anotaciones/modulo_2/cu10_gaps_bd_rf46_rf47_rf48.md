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
3. **C2 (compatibilidad tipo)**: Cubierta implícitamente por C1. Si la infra tiene especie configurada y coincide con el activo, el tipo es compatible por configuración del administrador. Sin tabla de mapeo adicional.
4. **C3 (capacidad)**: `capacidad_maxima IS NULL → sin límite`. Si tiene valor, se verifica que ocupación actual + cantidad del activo no supere el máximo. Ocupación calculada en tiempo real contando activos con `id_infraestructura = destino` y estado != BAJA(6) y != CERRADO(5).
5. **Historial RF-46**: Se consultan las vistas `vw_rf46_*` y `movimientos` por separado en Python, se unen y ordenan cronológicamente antes de paginar.
6. **Ficha integral RF-47**: Se consulta `vw_rf47_ficha_integral_activo` y `vw_rf47_indicadores_zootecnicos_activo` directamente.
7. **Indicadores RF-51**: Ya existe tabla `modulo2.indicadores_zootecnicos`. Sin stub.
