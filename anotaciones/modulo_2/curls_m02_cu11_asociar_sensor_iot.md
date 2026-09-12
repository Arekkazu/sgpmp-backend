# CURLs — M02 CU11: Asociar Sensor IoT al Activo Biológico (RF-49)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa.

---

## POST /activos-biologicos/{id_activo}/sensores

Asocia un sensor IoT registrado en M09 a un activo biológico de M02.

### Flujo principal — Asociación DIRECTA (happy path)

```bash
curl -X POST http://localhost:8000/activos-biologicos/1/sensores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 1,
    "sensor_id": 1,
    "id_infraestructura": 1
  }'
```

**Respuesta esperada (201 Created):**
```json
{
  "id_asociacion_activo_sensor": 1,
  "id_activo_biologico": 1,
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "directa",
  "dispositivo_iot_id": 1,
  "sensor_id": 1,
  "id_infraestructura": 1,
  "fecha_inicio": "2026-06-29T14:00:00Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": null,
  "advertencia": null
}
```

---

### Flujo — Asociación AMBIENTAL (sensor compartido por infraestructura)

```bash
curl -X POST http://localhost:8000/activos-biologicos/2/sensores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "AMBIENTAL",
    "dispositivo_iot_id": 2,
    "sensor_id": 3,
    "id_infraestructura": 1,
    "motivo": "Sensor ambiental de temperatura del galpón"
  }'
```

**Nota**: Para AMBIENTAL, el mismo sensor puede estar activo para múltiples activos en la misma infraestructura.

---

### Flujo — Asociación POBLACIONAL (lote)

```bash
curl -X POST http://localhost:8000/activos-biologicos/5/sensores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "LOTE",
    "tipo_asociacion": "POBLACIONAL",
    "dispositivo_iot_id": 1,
    "sensor_id": 2,
    "id_infraestructura": 1
  }'
```

---

### Flujo — Reasignación (mismo sensor al mismo activo, crea nueva y marca anterior SUPERADA)

```bash
# Segunda llamada con el mismo sensor_id + id_activo → cierra la anterior y crea nueva
curl -X POST http://localhost:8000/activos-biologicos/1/sensores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 1,
    "sensor_id": 1,
    "id_infraestructura": 1,
    "motivo": "Recalibración del sensor"
  }'
```

**Resultado**: La asociación anterior queda con `estado_asociacion=SUPERADA` y `fecha_fin` establecida. La nueva queda ACTIVA.

---

## Errores posibles

### FA-02 — Activo en BAJA (422)

```json
{
  "code": "ACTIVO_EN_BAJA",
  "message": "El activo 1 se encuentra en estado BAJA y no admite nuevas asociaciones de sensores."
}
```

### FA-01 — Sensor inexistente (404)

```json
{
  "code": "SENSOR_NO_ENCONTRADO",
  "message": "No existe un sensor con id 99."
}
```

### FA-01 — Sensor inactivo (422)

```json
{
  "code": "SENSOR_INACTIVO",
  "message": "El sensor 5 no está activo. Solo se permiten asociaciones con sensores activos."
}
```

### FA-01 — Dispositivo IoT inactivo (422)

```json
{
  "code": "DISPOSITIVO_INACTIVO",
  "message": "El dispositivo IoT 3 no está activo."
}
```

### FA-01 — Sensor sin área asociada (422)

```json
{
  "code": "SENSOR_SIN_AREA",
  "message": "El sensor 2 no tiene asociación activa a ninguna infraestructura. Asocie el sensor a una infraestructura (RF-22) antes de vincularlo a un activo."
}
```

### FA-03 — Infraestructura de distinta finca (409)

```json
{
  "code": "INFRAESTRUCTURA_INCOMPATIBLE",
  "message": "Error de ubicación. El activo está en la finca 1 y el sensor en la finca 2. La asociación solo es permitida dentro de la misma unidad territorial."
}
```

### FA-05 — Sensor DIRECTA ya vinculado a otro activo (409)

```json
{
  "code": "SENSOR_YA_VINCULADO",
  "message": "El sensor 1 ya está vinculado al activo 3 con una asociación DIRECTA activa. Debe desvincularlo primero."
}
```

### FA-05 — Activo LOTE ya tiene sensor POBLACIONAL (409)

```json
{
  "code": "ACTIVO_YA_TIENE_SENSOR_POBLACIONAL",
  "message": "El activo 5 ya tiene el sensor 4 con asociación POBLACIONAL activa. Desactívelo primero."
}
```

### FA-05b — Sensor POBLACIONAL ya activo en otro lote (409, INC-M02-64-G88)

Restricción 4 del RF-49: un sensor POBLACIONAL solo puede estar activo en un
único lote a la vez. Simétrico al caso anterior (ese valida por activo, este
por sensor).

```json
{
  "code": "SENSOR_YA_ASOCIADO_A_OTRO_LOTE",
  "message": "El sensor 1 ya está asociado con tipo POBLACIONAL al activo 20. Un sensor solo puede estar activo en un único lote a la vez. Desactive esa asociación primero."
}
```

### FA-06 — Sin permiso (403)

```json
{
  "code": "AUTHORIZATION_ERROR",
  "message": "No tienes permiso para realizar esta acción."
}
```

---

## PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}

**INC-M02-65-G89 (RF-49):** no existía ningún endpoint para gestionar el ciclo
de vida de una asociación una vez creada — todo intento devolvía 404 por falta
de ruta, incluida la transición inválida que debía rechazarse explícitamente.

Transiciones manuales permitidas: `ACTIVA → INACTIVA` (desactivación),
`INACTIVA → ACTIVA` (reactivación). `SUPERADA` es terminal y exclusivamente
system-managed (la asigna `AsociarSensorActivoUseCase` al reemplazar una
asociación) — no es alcanzable desde este endpoint bajo ninguna transición.

### Desactivar una asociación ACTIVA

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/1/sensores/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"estado_nuevo": "INACTIVA", "motivo": "Sensor retirado para mantenimiento"}'
```

**Respuesta esperada (200):**
```json
{
  "id_asociacion_activo_sensor": 1,
  "estado_asociacion": "INACTIVA",
  "fecha_fin": "2026-09-12T12:00:00Z",
  "motivo": "Sensor retirado para mantenimiento",
  "...": "resto de campos igual que en POST"
}
```

### Reactivar una asociación INACTIVA

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/1/sensores/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"estado_nuevo": "ACTIVA"}'
```

**Resultado**: `fecha_fin` vuelve a `null`.

### Errores

**Transición inválida — ej. intentar fijar SUPERADA manualmente (422):**
```json
{
  "error_code": "TRANSICION_INVALIDA",
  "message": "La transición INACTIVA → SUPERADA no está permitida. Transiciones válidas desde INACTIVA: ACTIVA."
}
```

**Estado redundante — ya está en el estado solicitado (409):**
```json
{
  "error_code": "ESTADO_REDUNDANTE",
  "message": "La asociación ya se encuentra en estado ACTIVA."
}
```

**Asociación inexistente, o de otro activo (404):**
```json
{
  "error_code": "ASOCIACION_NO_ENCONTRADA",
  "message": "No existe una asociación con id 999 para el activo 1."
}
```
