# CU-05 – Gaps de BD y RBAC (RF-21, RF-22, RF-23, RF-24)

## Gaps encontrados y decisiones tomadas

### 1. `dispositivos_iot` — sin UNIQUE en `serial`
**Gap:** La columna `serial` no tenía restricción de unicidad.
**Decisión:** `ALTER TABLE modulo9.dispositivos_iot ADD CONSTRAINT uq_dispositivo_iot_serial UNIQUE (serial);`

### 2. `dispositivos_iot` — sin FK a área productiva
**Gap:** RF-21 dice "el dispositivo debe estar asociado obligatoriamente a un área productiva válida", pero la tabla no tenía columna `id_infraestructura`.
**Decisión:** `ALTER TABLE modulo9.dispositivos_iot ADD COLUMN id_infraestructura INTEGER NOT NULL REFERENCES modulo9.infraestructuras(id_infraestructura);`
Las 9 filas existentes se actualizaron a `id_infraestructura=1` (Estanque-01, dato de prueba).

### 3. Faltaba `auditorias_dispositivos_iot`
**Decisión:** Creada la tabla con el esquema estándar del proyecto (tipo_operacion CHECK: CREATE/DEACTIVATE/GET).

### 4. Faltaba `auditorias_sensores_areas`
**Decisión:** Creada para registrar auditoría de asociaciones sensor-área (tipo_operacion CHECK: CREATE/GET).

### 5. `calibraciones` — campos nullable que deben ser NOT NULL
**Gap:** `valor_referencia` y `id_usuario` eran nullable.
**Decisión:** `ALTER COLUMN valor_referencia SET NOT NULL; ALTER COLUMN id_usuario SET NOT NULL;`

### 6. RBAC — faltaban permisos de desactivación para dispositivos IoT (recurso 11, acción 4)
**Decisión:**
```sql
INSERT INTO modulo1.permisos (nombre, id_recurso, id_accion, id_rol, es_activo, fecha_creacion)
VALUES
  ('admin_desactivar_iot', 11, 4, 1, true, NOW()),
  ('ing_desactivar_iot',   11, 4, 4, true, NOW());
```

### 7. RF-24 — rango de calibración por tipo de sensor + modelo ganancia/offset (issue #1635)
**Gap:** (a) no existía validación de rango por tipo de sensor — solo `valor_referencia > 0`,
así que un offset absurdo pero positivo (ej. temperatura 500 °C) pasaba; (b) `modulo9.calibraciones`
solo tenía `valor_referencia`, obligando al consumidor de telemetry a aproximar
`ganancia=1.0, offset=valor_referencia`.

**Decisión (migración Alembic `c3f1a9e42b7d`, down_revision `b1c4a7e9d2f3`):**

```sql
-- Catálogo de rango de seguridad (min/max) por tipo de sensor (categoria del enum
-- modulo3.enum_reglas_alertas_tipo_sensor). Solo lectura desde la app; se ajusta por SQL.
CREATE TABLE modulo9.rangos_calibracion (
    id_rango_calibracion SERIAL PRIMARY KEY,
    categoria            VARCHAR(30) NOT NULL UNIQUE,
    valor_min            NUMERIC(10,4) NOT NULL,
    valor_max            NUMERIC(10,4) NOT NULL,
    fecha_creacion       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rangos_calibracion_min_max_check CHECK (valor_max >= valor_min)
);
-- Seeds (ilustrativos, espejo de variables_ambientales acuícolas; se tunean por SQL):
INSERT INTO modulo9.rangos_calibracion (categoria, valor_min, valor_max) VALUES
  ('TEMPERATURA',0,45),('OXIGENO',0,20),('PH',0,14),('AMONIACO',0,10),
  ('SALINIDAD',0,45),('HUMEDAD',0,100),('LUMINOSIDAD',0,100000);

-- Modelo lineal real (valor_ajustado = ganancia * crudo + offset).
ALTER TABLE modulo9.calibraciones ADD COLUMN ganancia NUMERIC(10,4) NOT NULL DEFAULT 1.0;
ALTER TABLE modulo9.calibraciones ADD COLUMN offset_calibracion NUMERIC(10,4) NOT NULL DEFAULT 0;
UPDATE modulo9.calibraciones SET offset_calibracion = valor_referencia;  -- backfill, no rompe al consumidor
```

Aplicado a `sgpmp` (dev) vía `alembic upgrade head`. La base de pruebas (`pruebas`) es
solo-`modulo1`; los tests de M09 hacen `pytest.skip` cuando falta el schema, así que no
requiere esta migración. `offset_calibracion` (no `offset`) porque `OFFSET` es palabra
reservada en SQL. RBAC: sin cambios — el catálogo se lee con recurso 12 (`sensores`), acción 2.

## Simplificaciones conocidas

- **MQTT (RF-23):** No implementado. Stub `MqttStubAdapter` retorna siempre `False` (dispositivo offline). Todas las configuraciones quedan en estado `PENDIENTE`. HTTP 202.
- ~~**Rango de calibración (RF-24):** validación simplificada `valor_referencia > 0`.~~
  **Resuelto (issue #1635):** rango por tipo de sensor vía `modulo9.rangos_calibracion`
  (fuera de rango → `400 VALOR_FUERA_DE_RANGO`) y modelo ganancia/offset real.
- **Tipo de dispositivo (RF-23):** La tabla `dispositivos_iot` no tiene columna `tipo`. Los rangos de frecuencia/intervalo se validan con mínimo 1 min, sin límite por tipo.
- **Rango sin configurar:** si una `categoria` no tiene fila en `rangos_calibracion`, el use
  case cae al chequeo `valor_referencia > 0` previo (fallback seguro). Los 7 valores del enum
  actual ya están sembrados.

## Estado RBAC tras los cambios

### Recurso 11 — `dispositivos_iot`
| id_rol | Rol | Acciones |
|--------|-----|----------|
| 1 | Administrador | C R U D |
| 2 | Productor | R |
| 4 | Ingeniero | C R U D |

### Recurso 12 — `sensores`
| id_rol | Rol | Acciones |
|--------|-----|----------|
| 1 | Administrador | C R U |
| 2 | Productor | R |
| 3 | Veterinario | R |
| 4 | Ingeniero | C R U |
