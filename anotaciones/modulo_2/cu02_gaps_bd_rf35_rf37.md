# Gaps BD y RBAC — M02 CU02: RF-35 + RF-37

## Gaps identificados y resolución

### Tabla `modulo2.gestiones_fases`

| Gap | Tipo | Solución |
|-----|------|---------|
| Faltaba `motivo_cambio` | Columna ausente | `ALTER TABLE modulo2.gestiones_fases ADD COLUMN motivo_cambio TEXT` |

Todas las demás columnas ya eran correctas (TIMESTAMPTZ, es_activa boolean, FKs a activos_biologicos, ciclos_productivos, usuarios).

### Triggers relevantes en `gestiones_fases`

| Trigger | Efecto en la implementación |
|---------|-----------------------------|
| `trg_fn_fase_unica_activa` | El use case cierra la fase activa existente ANTES de insertar la nueva, en la misma transacción |
| `trg_fn_fase_activo_estado_valido` | Rechaza si el activo está en estado CERRADO o BAJA — no se duplica validación en código |
| `trg_fn_fase_solapamiento` | Valida orden temporal — `fecha_inicio` de la nueva fase ≥ `fecha_finalizacion` de la anterior |

### Modelo de secuencia de fases (RF-37)

La "fase actual" de un activo en un ciclo productivo es implícita:
- `COUNT(gestiones_fases WHERE id_activo_biologico = X AND id_ciclo_productiva = Y)` = número de fases completadas (incluyendo activa actual)
- La fase correspondiente = índice (count - 1) en `ciclos_productivos_biologicos` ordenado por `id_ciclos_productivo_biologico ASC`
- `total_pasos` = COUNT de fases en `ciclos_productivos_biologicos` para ese ciclo

## RBAC — permisos agregados en `modulo1.permisos` para `id_recurso=29`

| Rol | id_rol | Acción | id_accion | Nombre permiso |
|-----|--------|--------|-----------|---------------|
| Administrador | 1 | U (Actualizar) | 3 | `admin_actualizar_activo_biologico` |
| Productor | 2 | U (Actualizar) | 3 | `prod_actualizar_activo_biologico` |
| Ingeniero | 4 | U (Actualizar) | 3 | `ing_actualizar_activo_biologico` |
| Administrador | 1 | E (Ejecutar) | 5 | `admin_ejecutar_cambio_fase` |
| Productor | 2 | E (Ejecutar) | 5 | `prod_ejecutar_cambio_fase` |
| Ingeniero | 4 | E (Ejecutar) | 5 | `ing_ejecutar_cambio_fase` |

Los permisos C(1) y R(2) para Admin, Productor, Ingeniero y R(2) para Veterinario ya existían desde CU01.
Contador (id_rol=5) no tiene permisos sobre `activos_biologicos`.
