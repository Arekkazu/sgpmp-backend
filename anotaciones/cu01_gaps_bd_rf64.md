# CU-01 — Gaps BD y RBAC — RF-64 Catálogo de Patologías

## Análisis de gaps (2026-07-10)

### Tablas involucradas por Desarrollo (RF-64)

| Tabla | Estado |
|-------|--------|
| `modulo9.patologias` | ✅ Existe — ya tiene columnas M04 (`es_base`, `version_catalogo`, `descripcion_clinica`, `especie_aplicable`, `fecha_creacion_m04`, `id_usuario_creador`, `fecha_actualizacion`) |
| `modulo4.patologias_variables_sensoricas` | ✅ Existe — FK a modulo9.patologias y modulo9.variables_ambientales |
| `modulo4.historial_catalogo_patologias` | ✅ Existe — append-only con CHECK accion IN ('CREADA','MODIFICADA','INACTIVADA') |
| `modulo4.eventos_auditoria_m04` | ✅ Existe — enum_tipo_evento_auditoria_m04 ya incluye CATALOGO_PATOLOGIA_AGREGADA/MODIFICADA/INACTIVADA |

### RBAC

| Recurso | id | Roles con permisos | Estado |
|---------|----|--------------------|--------|
| `patologias` | 18 | admin (C/R/U/D), vet (C/R/U/D) | ✅ Existe |

### Observaciones

1. `modulo9.patologias.nombre` tiene UNIQUE constraint global (`uq_enfermedad_nombre`), no por especie.
   El RF-64 dice "unicidad por especie", pero la BD es más restrictiva (global).
   **Decisión**: validar unicidad global (case-insensitive) en la aplicación y dejar que la DB
   rechace duplicados globales vía IntegrityError → ConflictError.

2. `descripcion_clinica` es nullable en la BD. RF-64 la requiere con ≥50 chars.
   **Decisión**: validar en el use case; no se aplica DDL.

3. `patologias_variables_sensoricas` tiene UNIQUE constraint `uq_patologia_variable`
   sobre (id_patologia, id_variable_ambiental) — previene duplicar la misma variable en una patología.

4. No existe tabla de clases objetivo que vincule modelos con patologías (es responsabilidad IoT/IA).
   **Decisión**: stub adapter `ModeloActivoStubAdapter` devuelve False mientras IoT/IA implementa.

---

## DML aplicado — Seeding de patologías base (RF-64)

**Fecha de aplicación**: 2026-07-10  
**Variables I3P-1 usadas** (modulo9.variables_ambientales):
- 9 = Temperatura Ambiental, 10 = Humedad Relativa
- 11 = NH3, 12 = CO2
- 13 = Temperatura Corporal, 14 = Frecuencia Cardíaca, 15 = Frecuencia Respiratoria, 16 = Actividad/Movimiento

```sql
-- ============================================================
-- INSERT patologías base en modulo9.patologias (es_base = true)
-- ============================================================
INSERT INTO modulo9.patologias
  (nombre, es_activo, es_base, version_catalogo, especie_aplicable, descripcion_clinica)
VALUES
  (
    'Ninguna (estado normal)',
    true, true, 1, 'TODAS',
    'Temperatura ambiental y temperatura corporal dentro de rangos fisiológicos normales sin evidencia de patología activa detectada por telemetría.'
  ),
  (
    'Estrés térmico',
    true, true, 1, 'TODAS',
    'Temperatura ambiental elevada combinada con temperatura corporal aumentada y alta humedad relativa indican cuadro de estrés térmico en el activo biológico.'
  ),
  (
    'Deshidratación',
    true, true, 1, 'TODAS',
    'Temperatura corporal alta junto con frecuencia cardíaca elevada y reducción de actividad locomotora son indicadores de deshidratación clínica significativa.'
  ),
  (
    'Intoxicación hídrica',
    true, true, 1, 'TODAS',
    'Temperatura corporal reducida, frecuencia respiratoria aumentada y actividad anormal detectadas por telemetría sugieren cuadro de intoxicación hídrica o desequilibrio osmótico.'
  ),
  (
    'Gastroenteritis infecciosa',
    true, true, 1, 'TODAS',
    'Temperatura corporal elevada (fiebre), taquicardia y taquipnea son indicadores clásicos de proceso infeccioso gastrointestinal agudo con respuesta sistémica.'
  ),
  (
    'Hipotermia o estrés por frío',
    true, true, 1, 'TODAS',
    'Temperatura ambiental anormalmente baja con temperatura corporal disminuida por debajo del rango fisiológico indican hipotermia o estrés por exposición al frío.'
  ),
  (
    'Septicemia o infección sistémica',
    true, true, 1, 'TODAS',
    'Fiebre alta, taquicardia, taquipnea y actividad locomotora marcadamente reducida son signos clásicos de septicemia o infección sistémica de origen bacteriano o viral.'
  ),
  (
    'Síndrome respiratorio agudo',
    true, true, 1, 'TODAS',
    'Frecuencia respiratoria elevada junto con altas concentraciones de CO2 y NH3 en el ambiente son indicadores de síndrome respiratorio agudo de origen ambiental o infeccioso.'
  );

-- Capturar los ids generados para las asociaciones de variables
-- (ejecutar separado para obtener los ids reales)
SELECT id_patologia, nombre FROM modulo9.patologias WHERE es_base = true ORDER BY id_patologia;
```

```sql
-- ============================================================
-- INSERT asociaciones en modulo4.patologias_variables_sensoricas
-- Ajustar los id_patologia con los valores reales devueltos arriba
-- ============================================================

-- Ninguna (estado normal): Temp Ambiental (9), Temp Corporal (13)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[9, 13]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Ninguna (estado normal)' AND es_base = true;

-- Estrés térmico: Temp Ambiental (9), Temp Corporal (13), Humedad Relativa (10)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[9, 13, 10]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Estrés térmico' AND es_base = true;

-- Deshidratación: Temp Corporal (13), Frecuencia Cardíaca (14), Actividad (16)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[13, 14, 16]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Deshidratación' AND es_base = true;

-- Intoxicación hídrica: Temp Corporal (13), Frecuencia Respiratoria (15), Actividad (16)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[13, 15, 16]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Intoxicación hídrica' AND es_base = true;

-- Gastroenteritis infecciosa: Temp Corporal (13), Frecuencia Cardíaca (14), Frecuencia Respiratoria (15)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[13, 14, 15]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Gastroenteritis infecciosa' AND es_base = true;

-- Hipotermia o estrés por frío: Temp Ambiental (9), Temp Corporal (13)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[9, 13]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Hipotermia o estrés por frío' AND es_base = true;

-- Septicemia o infección sistémica: Temp Corporal (13), Frecuencia Cardíaca (14), Frecuencia Respiratoria (15), Actividad (16)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[13, 14, 15, 16]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Septicemia o infección sistémica' AND es_base = true;

-- Síndrome respiratorio agudo: Frecuencia Respiratoria (15), CO2 (12), NH3 (11)
INSERT INTO modulo4.patologias_variables_sensoricas (id_patologia, id_variable_ambiental, peso_evidencia, es_variable_critica)
SELECT id_patologia, unnest(ARRAY[15, 12, 11]), 1.000, false
FROM modulo9.patologias WHERE nombre = 'Síndrome respiratorio agudo' AND es_base = true;
```
