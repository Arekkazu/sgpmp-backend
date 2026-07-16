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

## Simplificaciones conocidas

- **MQTT (RF-23):** No implementado. Stub `MqttStubAdapter` retorna siempre `False` (dispositivo offline). Todas las configuraciones quedan en estado `PENDIENTE`. HTTP 202.
- **Rango de calibración (RF-24):** No existe tabla de rangos por tipo de sensor en la BD. Validación simplificada: `valor_referencia > 0`.
- **Tipo de dispositivo (RF-23):** La tabla `dispositivos_iot` no tiene columna `tipo`. Los rangos de frecuencia/intervalo se validan con mínimo 1 min, sin límite por tipo.

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
