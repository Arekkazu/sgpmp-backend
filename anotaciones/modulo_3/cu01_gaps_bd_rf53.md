# Gaps BD — M03 CU01: Recibir y validar telemetría IoT (RF-53)

## Contexto

CU01 es el primer caso de uso del Módulo 3 (Telemetría IoT). Cubre la ingesta de lecturas de sensores en tres flujos:
- **Flujo A** — TIEMPO_REAL: lectura directa en línea
- **Flujo B** — EDGE_AGREGADO: dato preprocesado en Edge
- **Flujo C** — BUFFER_LOCAL: sincronización de buffer offline (lote ≤500)

Responsabilidad del equipo Dev: pasos 3 en adelante (recibir desde Broker, validar, persistir, publicar). AIOT gestiona captura LoRaWAN y buffer de hardware.

---

## Gaps encontrados y DDL aplicado

### Gap 1 — `modulo3.telemetrias.valor_ajustado` NOT NULL

**Problema:** La columna era NOT NULL, pero RF-53 dice que si no hay parámetros de calibración el valor ajustado es nulo.

**Fix aplicado:**
```sql
ALTER TABLE modulo3.telemetrias ALTER COLUMN valor_ajustado DROP NOT NULL;
```

---

### Gap 2 — `modulo3.telemetrias.latitud` / `longitud` NOT NULL

**Problema:** Ambas columnas eran NOT NULL, pero RF-53 indica que la geolocalización es opcional (no todos los dispositivos tienen GPS).

**Fix aplicado:**
```sql
ALTER TABLE modulo3.telemetrias ALTER COLUMN latitud DROP NOT NULL;
ALTER TABLE modulo3.telemetrias ALTER COLUMN longitud DROP NOT NULL;
```

---

### Gap 3 — `modulo3.bitacora_ingest.id_telemetria` NOT NULL

**Problema:** La FK era NOT NULL, pero los registros rechazados (ERROR_AUTENTICACION, ERROR_ESTRUCTURA, etc.) no tienen `id_telemetria` porque no se persisten en `telemetrias`.

**Fix aplicado:**
```sql
ALTER TABLE modulo3.bitacora_ingest ALTER COLUMN id_telemetria DROP NOT NULL;
```

---

### Gap 4 — Índice único para EDGE_AGREGADO no incluye `ventana_agregacion_min`

**Problema:** El constraint existente `uq_telemetria_sensor_variable_captura_origen` no discrimina por `ventana_agregacion_min`. El RF establece que para EDGE_AGREGADO la clave de deduplicación incluye la ventana de agregación.

**Fix aplicado:**
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_telemetria_edge_agregado
  ON modulo3.telemetrias (id_sensor, id_variable, timestamp_captura, origen, ventana_agregacion_min)
  WHERE origen = 'EDGE_AGREGADO';
```

---

### Gap 5 — Catálogo I3P-1 incompleto en `modulo9.variables_ambientales`

**Problema:** La tabla solo tenía 8 entradas (variables acuícolas). El catálogo I3P-1 del RF-53 define 11 tipos de variable adicionales (ambientales, animales, hídricas) necesarios para el módulo de telemetría.

**Fix aplicado:**
```sql
INSERT INTO modulo9.variables_ambientales (nombre, unidad, valor_fisico_min, valor_fisico_max, es_activo) VALUES
  ('Temperatura Ambiental',      '°C',    -50,    100, true),   -- id=9
  ('Humedad Relativa',           '%',       0,    100, true),   -- id=10
  ('Amoniaco (NH3)',             'ppm',     0,    500, true),   -- id=11
  ('Dióxido de Carbono (CO2)',  'ppm',     0, 100000, true),   -- id=12
  ('Temperatura Corporal',       '°C',     30,     50, true),   -- id=13
  ('Frecuencia Cardiaca',        'bpm',     0,    500, true),   -- id=14
  ('Frecuencia Respiratoria',    'rpm',     0,    200, true),   -- id=15
  ('Actividad/Movimiento',       'm/s²',    0,    200, true);   -- id=16
```

**Nota:** Las variables acuícolas existentes (pH id=2, O2 disuelto id=3, conductividad id=8, etc.) ya cubrían el catálogo I3P-1 hídrico parcialmente.

---

## Typos en columnas de DB (no corregidos — se mantienen en ORM)

| Tabla | Columna real (typo) | Nombre correcto | Decisión |
|-------|---------------------|-----------------|----------|
| `modulo3.telemetrias` | `dato_agredado_edge` | `dato_agregado_edge` | ORM usa el nombre real de DB; la entidad de dominio usa el nombre correcto. El mapeo ocurre en `_a_entidad()`. |
| `modulo3.bitacora_ingest` | `gatway_id` | `gateway_id` | Ídem — columna ORM usa `gatway_id`, parámetros de métodos usan `gateway_id`. |

---

## RBAC

Los endpoints de ingesta IoT (`POST /iot/telemetria`, `POST /iot/telemetria/batch`) **no usan JWT Bearer**. La autenticación de dispositivos se hace mediante `access_key` en el body del request, que se valida contra `modulo9.dispositivos_iot.serial` en el use case.

No se insertan filas en `modulo1.permisos` para estos endpoints.

---

## Notas de calibración

`modulo9.calibraciones` solo tiene `valor_referencia`, no `ganancia` ni `offset`. La implementación del `CalibracionM09Adapter` usa la aproximación:
- `ganancia = 1.0`
- `offset = valor_referencia` (ajuste de cero)

Esto es una simplificación válida hasta que M09 extienda el modelo de calibración.
