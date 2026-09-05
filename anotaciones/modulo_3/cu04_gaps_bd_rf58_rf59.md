# CU04 — Gaps de BD y RBAC — RF-58, RF-59

Fecha de análisis: 2026-07-07

---

## 1. Análisis de gaps de BD

### RF-58 — Dashboard en tiempo real

**Tabla `modulo3.estados_actuales_sensores`** ya existe con las columnas requeridas:
- `id_estado_actual_sensor`, `id_sensor`, `id_dispositivo_iot`
- `ultimo_valor`, `ultima_unidad`, `ultimo_timestamp_captura`, `ultimo_timestamp_actualizacion`
- `estado_semaforo` (VARCHAR 20)
- `estado_calidad` (PG enum `enum_telemetria_estado_calidad`)
- `estado_desviacion` (PG enum `enum_tipo_evento_edge`)
- `estado_conectividad` (PG enum `enum_estado_dispositivo`)
- `tiempo_sin_reporte_min`, `dato_desactualizado`, `id_alerta`, `tendencia`

**Decisión**: No se requiere DDL. La tabla está diseñada explícitamente para RF-58 (comentario en la tabla: "RF-58: Cache del último estado conocido de cada sensor").

**Contexto de tipo de variable**: `estados_actuales_sensores` no tiene `id_variable` ni `tipo_variable`. Se obtienen con LATERAL join a `modulo3.telemetrias` (última lectura por sensor) + `modulo9.variables_ambientales`. Igual para `id_infraestructura` vía `modulo9.sensores_areas_asociadas`.

### RF-59 — Historial

**Tabla `modulo3.telemetrias`** contiene todos los campos necesarios. La vista `vw_m03_historial_lecturas` es un subset de `vw_m03_telemetria_contextualizada`.

**Decisión**: Se consulta directamente `modulo3.telemetrias` con los mismos JOINs de `vw_m03_telemetria_contextualizada` para tener control total sobre los filtros y la paginación. No se requiere DDL.

**Semáforo histórico**: RF-59 Restricción 16 exige umbrales versionados en M09 con `fecha_inicio_vigencia` / `fecha_fin_vigencia`. M09 no expone esta funcionalidad actualmente. Se implementó `UmbralHistoricoM09Adapter` como stub que retorna `None` → semáforo `GRIS` hasta que M09 implemente umbrales versionados.

---

## 2. Gaps de RBAC aplicados

### SQL ejecutado

```sql
-- Recursos
INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial) VALUES
  ('monitoreo_telemetria', 'Dashboard de monitoreo en tiempo real de telemetría IoT (RF-58)', false),
  ('historial_telemetria', 'Historial y exportación de lecturas telemetricas (RF-59)', false);
-- → id_recurso = 33 (monitoreo_telemetria), 34 (historial_telemetria)

-- Permisos RF-58 (leer dashboard)
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_monitoreo_telemetria', 1, 33, 2),  -- id_permiso 198
  ('prod_leer_monitoreo_telemetria',  2, 33, 2),  -- 199
  ('vet_leer_monitoreo_telemetria',   3, 33, 2),  -- 200
  ('ing_leer_monitoreo_telemetria',   4, 33, 2);  -- 201

-- Permisos RF-59 (leer + ejecutar exportación)
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_historial_telemetria',    1, 34, 2),  -- 202
  ('prod_leer_historial_telemetria',     2, 34, 2),  -- 203
  ('vet_leer_historial_telemetria',      3, 34, 2),  -- 204
  ('ing_leer_historial_telemetria',      4, 34, 2),  -- 205
  ('cont_leer_historial_telemetria',     5, 34, 2),  -- 206
  ('admin_ejecutar_historial_telemetria',1, 34, 5),  -- 207
  ('prod_ejecutar_historial_telemetria', 2, 34, 5),  -- 208
  ('vet_ejecutar_historial_telemetria',  3, 34, 5),  -- 209
  ('cont_ejecutar_historial_telemetria', 5, 34, 5);  -- 210
```

---

## 3. Decisiones de diseño

| Decisión | Justificación |
|----------|---------------|
| `por_pagina` máximo 50 en dashboard | FA-07: límite de 50 sensores por vista simultánea |
| `por_pagina` máximo 500 en historial | RF-59 Restricción 9 |
| Rango máximo 90 días sin filtros | RF-59 Restricción 4 / FA-09 |
| Máximo 10.000 registros por consulta historial | RF-59 Restricción 13 / FA-10 |
| Exportación retorna 503 | M08 no implementado — stub |
| Semáforo histórico GRIS | M09 sin umbrales versionados — stub `UmbralHistoricoM09Adapter` |
| Campos técnicos nulos para Productor | CA-8 / RF-58 Proceso Fase 4 |
