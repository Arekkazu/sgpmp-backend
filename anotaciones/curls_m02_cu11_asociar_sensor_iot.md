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

### FA-06 — Sin permiso (403)

```json
{
  "code": "AUTHORIZATION_ERROR",
  "message": "No tienes permiso para realizar esta acción."
}
```
