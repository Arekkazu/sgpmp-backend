# CU12 — Gaps de BD y RBAC — RF-50, RF-51

Fecha: 2026-06-29

---

## Consultas ejecutadas

```sql
SELECT definition FROM pg_views
WHERE schemaname = 'modulo2' AND viewname = 'vw_rf47_indicadores_zootecnicos_activo';

SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'indicadores_zootecnicos';

SELECT viewname FROM pg_views WHERE schemaname = 'modulo2' ORDER BY viewname;

SELECT p.id_permiso, p.nombre, p.id_rol, p.id_recurso, p.id_accion, p.es_activo
FROM modulo1.permisos p WHERE p.id_recurso = 29 AND p.id_accion = 2;
```

---

## Resultados

### Tabla `modulo2.indicadores_zootecnicos` — ya existe con datos seed

| Columna | Tipo | Nullable |
|---------|------|----------|
| id_indicador_zootecnico | integer (PK, IDENTITY) | NO |
| id_activo_biologico | integer (FK → activos_biologicos) | NO |
| rango_fecha | daterange | NO |
| tipo | enum_indicador_zootecnico_tipo | NO |
| paramtros_calculo | jsonb | NO |

Nota: La columna `paramtros_calculo` tiene typo en la BD (sin 'e'). Se usa el nombre exacto en queries.

### Enum `enum_indicador_zootecnico_tipo` existente

- `ganancia_peso`
- `produccion_promedio`
- `tasa_morbilidad`
- `tasa_mortalidad`
- `conversion_alimenticia`

### Datos seed existentes (14 registros)

- `ganancia_peso`: 3 registros
- `produccion_promedio`: 4 registros
- `tasa_morbilidad`: 3 registros
- `tasa_mortalidad`: 3 registros
- `conversion_alimenticia`: 1 registro

### Vistas ya disponibles para CU12

| Vista | Uso en CU12 |
|-------|-------------|
| `vw_rf47_indicadores_zootecnicos_activo` | Leer indicadores almacenados (RF-51 histórico) |
| `vw_rf46_eventos_crecimiento` | Calcular ganancia_peso on-demand |
| `vw_rf46_eventos_productivos` | Calcular produccion_promedio on-demand |
| `vw_rf46_eventos_sanitarios` | Calcular tasa_morbilidad on-demand |
| `vw_rf46_eventos_bajas` | Calcular tasa_mortalidad on-demand |
| `vw_rf46_historial_completo_activo` | Historial eventos para RF-50 |
| `vw_rf47_ficha_integral_activo` | Info base del activo para RF-50 |
| `vw_rf52_auditoria_acceso_modulos_analiticos` | Resumen de acceso para RF-50 |

---

## Gaps detectados

### Sin gaps

- Todas las tablas y vistas requeridas ya existen en `modulo2`.
- El `paramtros_calculo` JSONB almacena tanto variables como resultado de cada indicador.
- La conversión alimenticia requiere datos de M05 (alimento consumido) — no implementado.
  **Decisión**: El indicador `conversion_alimenticia` retorna `disponible=false` con
  advertencia `REQUIERE_M05` hasta que M05 esté disponible.

### RBAC — sin cambios

Resource 29 (`activos_biologicos`) acción 2 (READ) ya existe para todos los roles relevantes:

| id_permiso | nombre | id_rol | es_activo |
|------------|--------|--------|-----------|
| 164 | admin_leer_activo_biologico | 1 (admin) | true |
| 166 | prod_leer_activo_biologico | 2 (prod) | true |
| 168 | ing_leer_activo_biologico | 4 (ing) | true |
| 169 | vet_leer_activo_biologico | 3 (vet) | true |

**No se insertaron nuevos registros de permisos.**

---

## DDL aplicado

Ninguno. Toda la infraestructura de BD necesaria para CU12 ya estaba presente.
