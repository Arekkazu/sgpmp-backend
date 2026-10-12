# CU09 — Gaps BD y RBAC — RF-43, RF-45

## Fecha de análisis
2026-06-29

## Consultas ejecutadas

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo9' AND table_name = 'metricas_produccion'
ORDER BY ordinal_position;

SELECT p.nombre AS permiso, r.nombre_rol AS rol, a.codigo AS accion
FROM modulo1.permisos p
JOIN modulo1.roles r ON r.id_rol = p.id_rol
JOIN modulo1.acciones a ON a.id_accion = p.id_accion
WHERE p.id_recurso = 29
ORDER BY p.id_rol, a.id_accion;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'modulo9' AND table_name = 'metricas_ciclo_productivo'
ORDER BY ordinal_position;
```

## Resultado

### `modulo9.metricas_produccion`
Columnas presentes: `id_metrica_produccion`, `nombre`, `unidad_medida`, `tipo_medicion`, `tiene_estado`, `id_especie`, `aplica_a_tipo_activo`, `es_activo`, `fecha_actualizacion`, `valor_min`, `valor_max`

- `unidad_medida` existe y es NOT NULL ✓
- El campo `tipo_medicion` es el que mapea al `tipo_producto` del RF-43 (ej: 'LECHE', 'HUEVOS', 'CARNE', 'MIEL', 'LANA')
- Los registros para tipos productivos (LECHE, HUEVOS, etc.) se crean vía RF-16 por especie cuando se configura esa especie

### `modulo9.metricas_ciclo_productivo`
Columnas: `id_metricas_ciclo_productivo`, `id_ciclo_productivo`, `id_metrica_produccion`

Esta tabla vincula qué métricas están habilitadas para cada ciclo productivo. Es la fuente para validar E-04 (tipo_producto no habilitado para la fase activa). La validación: `gestiones_fases.id_ciclo_productiva` → buscar en `metricas_ciclo_productivo WHERE id_ciclo_productivo = :id AND id_metrica_produccion = :id_metrica`.

### RBAC — Recurso 29 (activos_biologicos)

Tabla actualizada el 2026-09-24 contra `modulo1.permisos` de `sgpmp_dev`. La versión original de
este documento mostraba al Veterinario sin `U`; lo recibió después, en el PR #426 (RF-35).

| Rol | Acción |
|-----|--------|
| Administrador | C, R, U, D, E |
| Productor | C, R, U, D, E |
| Veterinario | C, R, U, D, E |
| Ingeniero de Campo | C, R, U, E |

Veterinario tiene acción C (Crear) sobre el recurso 29 ✓

## Decisiones

- Sin gaps de DDL: todas las columnas necesarias existen.
- Sin gaps de RBAC **por defecto**: todos los roles que RF-43 y RF-45 listan como actores ya tienen
  los permisos.
- **Corrección (2026-09-24):** la conclusión original ("sin gaps de RBAC") solo revisó que no faltara
  ningún permiso, no que no sobrara ninguno. Hay acceso de más:
  - **RF-45 (bajas):** los actores son Productor, Administrador y Veterinario. `POST
    /{id}/eventos/baja` exige `(29, C)` y el **Ingeniero de Campo también lo tiene**, así que puede
    registrar bajas sin ser actor del RF.
  - **RF-43 (eventos productivos):** los actores son Productor y Veterinario, y el endpoint usa el mismo
    `(29, C)`. Administrador e Ingeniero de Campo también pueden registrarlos.
  - No se puede corregir quitando `C`, porque esa acción la comparten RF-33, 36 y 40 a 43, donde el
  Ingeniero sí es actor. Es el hallazgo transversal #5 de `estado_M02.md` (recurso 29 demasiado
  agrupado), pendiente de decisión del equipo de análisis.
- Sin DML requerido.
- Los datos de metricas_produccion para tipos productivos (LECHE, HUEVOS, etc.) son responsabilidad de RF-16 (configuración por especie). El código CU09 los validará contra lo que esté configurado.

## Notas de infraestructura

- El trigger `trg_sincronizar_estado_activo` en `historicos_estados_activos` actualiza automáticamente `activos_biologicos.id_estado` al insertar. No se llama `actualizar_estado` por separado.
- Para baja con cierre automático de fase: cerrar `gestiones_fases` primero (igual que en `cerrar_ciclo_use_case.py`) y luego registrar el histórico para no bloquear el trigger de validación.
