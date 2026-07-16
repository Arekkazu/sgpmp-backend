# CURLs — M09 CU05: Gestionar Dispositivos IoT

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `POST /sesiones/`.

Actores con acceso: Administrador (`id_rol=1`), Ingeniero de Campo (`id_rol=4`).

---

## RF-21 — Dispositivos IoT (`/configuracion/dispositivos-iot`)

Recurso `id_recurso=11`.
- Admin / Ing: C(1) R(2) U(3) D(4)
- Productor: R(2)

### Registrar dispositivo IoT (Flujo A)

El área (`id_infraestructura`) debe existir y estar activa. El serial debe ser único en el sistema.

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "serial": "IOT-EST01-HLA-001",
    "descripcion": "Nodo IoT principal estanque 01, gateway LoRaWAN",
    "id_infraestructura": 1
  }'
```

Respuesta esperada `201`:
```json
{
  "id_dispositivo_iot": 1,
  "serial": "IOT-EST01-HLA-001",
  "descripcion": "Nodo IoT principal estanque 01, gateway LoRaWAN",
  "id_infraestructura": 1,
  "es_activo": true,
  "fecha_creacion": "2026-06-21T18:33:40Z"
}
```

Errores posibles:
- `404` — área productiva no existe (FA-03) — `AREA_NO_ENCONTRADA`
- `422` — área productiva inactiva (FA-04) — `AREA_NO_DISPONIBLE`
- `409` — serial ya registrado en el sistema (FA-07) — `SERIAL_DUPLICADO`
- `403` — rol sin permiso C sobre dispositivos_iot (FA-01)

---

### Listar dispositivos IoT (Flujo E)

```bash
# Todos los dispositivos
curl -X GET http://localhost:8000/configuracion/dispositivos-iot \
  -H "Authorization: Bearer <TOKEN>"

# Solo activos
curl -X GET "http://localhost:8000/configuracion/dispositivos-iot?solo_activos=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 11,
  "items": [
    {
      "id_dispositivo_iot": 1,
      "serial": "IOT-EST01-HLA-001",
      "descripcion": "Nodo IoT principal estanque 01, gateway LoRaWAN con batería solar",
      "id_infraestructura": 1,
      "es_activo": true,
      "fecha_creacion": "2026-04-28T14:42:28.213141Z"
    }
  ]
}
```

---

### Detalle de dispositivo IoT

```bash
curl -X GET http://localhost:8000/configuracion/dispositivos-iot/1 \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — dispositivo no existe

---

### Desactivar dispositivo IoT (Flujo E)

Solo si no tiene configuraciones PENDIENTE activas (FA-15).

```bash
curl -X PATCH http://localhost:8000/configuracion/dispositivos-iot/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_dispositivo_iot": 1,
  "serial": "IOT-EST01-HLA-001",
  "es_activo": false,
  "fecha_creacion": "..."
}
```

Errores posibles:
- `404` — dispositivo no existe
- `422` — dispositivo ya inactivo (FA-04)
- `422` — dispositivo tiene configuración PENDIENTE — `CONFIG_PENDIENTE_EXISTENTE`
- `403` — rol sin permiso D sobre dispositivos_iot (FA-01)

---

## RF-22 — Sensores (`/configuracion/dispositivos-iot/{id}/sensores` y `/configuracion/sensores`)

Recurso `id_recurso=11` (sensores bajo dispositivo) y `id_recurso=12` (operaciones sobre sensor).

### Registrar sensor en un dispositivo

Los sensores se registran bajo un dispositivo IoT. Valores válidos para `categoria`:
`HUMEDAD`, `TEMPERATURA`, `OXIGENO`, `PH`, `AMONIACO`, `SALINIDAD`, `LUMINOSIDAD`.

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot/1/sensores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Sensor temperatura estanque-01",
    "categoria": "TEMPERATURA"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_sensores": 1,
  "nombre": "Sensor temperatura estanque-01",
  "id_dispositivo_iot": 1,
  "es_activo": true,
  "categoria": "TEMPERATURA"
}
```

Errores posibles:
- `404` — dispositivo no existe

---

### Listar sensores de un dispositivo

```bash
curl -X GET http://localhost:8000/configuracion/dispositivos-iot/1/sensores \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 3,
  "items": [
    { "id_sensores": 1, "nombre": "Sensor temperatura estanque-01", "id_dispositivo_iot": 1, "es_activo": true, "categoria": "TEMPERATURA" }
  ]
}
```

---

### Asociar sensor a área productiva (Flujo B)

El sensor queda vinculado de por vida a la infraestructura de la primera asociación.
Si ya tiene una asociación activa en esa área, devuelve `409`.
Si se intenta asociar a una infraestructura diferente a su historial, devuelve `422`.

```bash
curl -X POST http://localhost:8000/configuracion/sensores/1/asociar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dispositivo_iot": 1,
    "id_infraestructura": 1,
    "punto_instalacion": "Esquina noroeste, a 1.5m de profundidad"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_sensores_area_asociada": 1,
  "id_sensor": 1,
  "id_dispositivo_iot": 1,
  "id_infraestructura": 1,
  "punto_instalacion": "Esquina noroeste, a 1.5m de profundidad",
  "tiene_estado": true,
  "fecha_asociacion": "2026-06-21T18:34:11Z",
  "fecha_finalizacion": null,
  "id_usuario": 1
}
```

Errores posibles:
- `404` — sensor no existe (FA-02)
- `404` — área productiva no existe (FA-03)
- `422` — sensor no pertenece al dispositivo indicado (FA-02) — `SENSOR_DISPOSITIVO_INVALIDO`
- `422` — área productiva inactiva (FA-04) — `AREA_NO_DISPONIBLE`
- `422` — intento de reasignar a infraestructura diferente — `SENSOR_INFRAESTRUCTURA_FIJA`
- `409` — sensor ya está activo en esa área (FA-06) — `ASOCIACION_DUPLICADA`
- `403` — rol sin permiso C sobre sensores (FA-01)

---

### Historial de asociaciones del sensor

```bash
curl -X GET http://localhost:8000/configuracion/sensores/1/asociaciones \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 1,
  "items": [
    {
      "id_sensores_area_asociada": 1,
      "id_sensor": 1,
      "id_dispositivo_iot": 1,
      "id_infraestructura": 1,
      "punto_instalacion": "Esquina noroeste, a 1.5m de profundidad",
      "tiene_estado": true,
      "fecha_asociacion": "2026-06-21T18:34:11Z",
      "fecha_finalizacion": null,
      "id_usuario": 1
    }
  ]
}
```

---

## RF-23 — Configuración remota (`/configuracion/dispositivos-iot/{id}/configurar`)

Recurso `id_recurso=11`, acción U(3). Admin / Ing.

El endpoint siempre responde `202` porque el stub MQTT simula el dispositivo offline.
La configuración queda en estado `PENDIENTE` hasta que el dispositivo se conecte.

### Enviar configuración remota (Flujo C)

`intervalo_transmision` debe ser ≥ `frecuencia_captura` (FA-12).
No puede existir una configuración `PENDIENTE` previa para el mismo dispositivo (FA-15).

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot/1/configurar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "frecuencia_captura": 30,
    "intervalo_transmision": 60
  }'
```

Respuesta esperada `202`:
```json
{
  "id_configuracion_remota": 1,
  "id_dispositivo_iot": 1,
  "frecuencia_captura": 30,
  "intervalo_transmision": 60,
  "estado": "PENDIENTE",
  "id_usuario": 1,
  "fecha_creacion": "2026-06-21T18:36:02Z",
  "fecha_aplicacion": null,
  "mensaje": "Dispositivo offline. La configuración ha sido almacenada y se enviará automáticamente en la próxima ventana de conexión del dispositivo."
}
```

Errores posibles:
- `404` — dispositivo no existe (FA-02)
- `422` — dispositivo inactivo
- `400` — `intervalo_transmision` < `frecuencia_captura` (FA-12) — `CONFLICTO_TIEMPOS_CONFIG`
- `409` — ya existe configuración PENDIENTE para el dispositivo (FA-15) — `CONFIG_PENDIENTE_EXISTENTE`
- `403` — rol sin permiso U sobre dispositivos_iot (FA-01)

---

### Historial de configuraciones del dispositivo

```bash
curl -X GET http://localhost:8000/configuracion/dispositivos-iot/1/configuraciones \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 2,
  "items": [
    {
      "id_configuracion_remota": 2,
      "id_dispositivo_iot": 1,
      "frecuencia_captura": 30,
      "intervalo_transmision": 60,
      "estado": "PENDIENTE",
      "id_usuario": 1,
      "fecha_creacion": "2026-06-21T18:36:02Z",
      "fecha_aplicacion": null,
      "mensaje": null
    },
    {
      "id_configuracion_remota": 1,
      "id_dispositivo_iot": 1,
      "frecuencia_captura": 30,
      "intervalo_transmision": 300,
      "estado": "APLICADA",
      "id_usuario": 1,
      "fecha_creacion": "2026-03-29T14:42:28Z",
      "fecha_aplicacion": "2026-03-30T14:42:28Z",
      "mensaje": null
    }
  ]
}
```

---

## RF-24 — Calibración de sensores (`/configuracion/sensores/{id}/calibrar`)

Recurso `id_recurso=12`, acción C(1). Admin / Ing.

### Registrar calibración (Flujo D)

El sensor debe existir, el dispositivo debe estar activo y el sensor debe tener
una asociación activa en el área indicada.

```bash
curl -X POST http://localhost:8000/configuracion/sensores/1/calibrar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dispositivo_iot": 1,
    "id_infraestructura": 1,
    "valor_referencia": "25.50",
    "fecha_calibracion": "2026-06-21T10:00:00Z",
    "observaciones": "Calibración con termómetro patrón certificado"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_calibracion": 1,
  "id_dispositivo_iot": 1,
  "id_sensor": 1,
  "valor_referencia": "25.5000",
  "fecha_calibracion": "2026-06-21T10:00:00Z",
  "id_usuario": 1,
  "observaciones": "Calibración con termómetro patrón certificado"
}
```

Errores posibles:
- `404` — sensor no existe (FA-02)
- `404` — dispositivo no existe (FA-02)
- `422` — dispositivo inactivo (FA-14) — `DISPOSITIVO_INACTIVO`
- `422` — sensor no pertenece al dispositivo (FA-02) — `SENSOR_DISPOSITIVO_INVALIDO`
- `400` — sensor no tiene asociación activa en el área indicada (FA-03) — `SENSOR_AREA_INVALIDA`
- `400` — `valor_referencia` ≤ 0 (FA-11) — `VALOR_CALIBRACION_INVALIDO`
- `403` — rol sin permiso C sobre sensores (FA-01)

---

### Historial de calibraciones del sensor

```bash
curl -X GET http://localhost:8000/configuracion/sensores/1/calibraciones \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 2,
  "items": [
    {
      "id_calibracion": 2,
      "id_dispositivo_iot": 1,
      "id_sensor": 1,
      "valor_referencia": "25.5000",
      "fecha_calibracion": "2026-06-21T10:00:00Z",
      "id_usuario": 1,
      "observaciones": "Calibración con termómetro patrón certificado"
    },
    {
      "id_calibracion": 1,
      "id_dispositivo_iot": 1,
      "id_sensor": 1,
      "valor_referencia": "25.0000",
      "fecha_calibracion": "2026-03-29T14:42:28Z",
      "id_usuario": 1,
      "observaciones": "Calibración inicial con termómetro patrón certificado NIST."
    }
  ]
}
```

---

## Notas técnicas

- **MQTT stub**: La comunicación MQTT con dispositivos LoRaWAN está simulada con un adaptador stub (`MqttStubAdapter`) que siempre retorna `False` (dispositivo offline). Todas las configuraciones remotas quedan en estado `PENDIENTE`. El endpoint responde `202 Accepted` en todos los casos.
- **Sensor fijo a infraestructura**: La DB impide mediante trigger (`trg_fn_sensor_asociacion_infraestructura_fija`) que un sensor sea asociado a más de una infraestructura en toda su vida útil. Una vez asociado al área X, nunca puede moverse al área Y.
- **Serial único**: El serial del dispositivo es globalmente único. La validación se hace con pre-check en el use case antes del INSERT para obtener un `409` limpio.
- **Auditoría de dispositivos**: Las operaciones CREATE, DEACTIVATE y GET sobre dispositivos quedan registradas en `modulo9.auditorias_dispositivos_iot`.
- **Auditoría de asociaciones**: Las operaciones CREATE sobre sensor-área quedan registradas en `modulo9.auditorias_sensores_areas`.
- **Swagger local**: `http://localhost:8000/docs` → secciones "Configuración - Dispositivos IoT" y "Configuración - Sensores".
