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
Desde RF-23/#1632 el campo `id_tipo_dispositivo` es **obligatorio** (ver "Tipos de dispositivo IoT" abajo).

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "serial": "IOT-EST01-HLA-001",
    "descripcion": "Nodo IoT principal estanque 01, gateway LoRaWAN",
    "id_infraestructura": 1,
    "id_tipo_dispositivo": 1
  }'
```

Respuesta esperada `201`:
```json
{
  "id_dispositivo_iot": 1,
  "serial": "IOT-EST01-HLA-001",
  "descripcion": "Nodo IoT principal estanque 01, gateway LoRaWAN",
  "id_infraestructura": 1,
  "id_tipo_dispositivo": 1,
  "es_activo": true,
  "fecha_creacion": "2026-06-21T18:33:40Z"
}
```

Errores posibles:
- `404` — área productiva no existe (FA-03) — `AREA_NO_ENCONTRADA`
- `404` — tipo de dispositivo no existe — `TIPO_DISPOSITIVO_NO_ENCONTRADO`
- `422` — área productiva inactiva (FA-04) — `AREA_NO_DISPONIBLE`
- `409` — serial ya registrado en el sistema (FA-07) — `SERIAL_DUPLICADO`
- `403` — rol sin permiso C sobre dispositivos_iot (FA-01)

---

### Tipos de dispositivo IoT (`/configuracion/tipos-dispositivo-iot`) — RF-23/#1632

Catálogo de solo lectura con los rangos min/max permitidos por tipo. Recurso `id_recurso=11`, acción R(2).
El front lo usa para poblar el selector de `id_tipo_dispositivo` al registrar y para mostrar los rangos.

```bash
curl -X GET http://localhost:8000/configuracion/tipos-dispositivo-iot \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 3,
  "items": [
    {"id_tipo_dispositivo": 1, "nombre": "GENERICO", "frecuencia_captura_min": 1, "frecuencia_captura_max": 1440, "intervalo_transmision_min": 1, "intervalo_transmision_max": 1440},
    {"id_tipo_dispositivo": 2, "nombre": "NODO_BAJO_CONSUMO", "frecuencia_captura_min": 15, "frecuencia_captura_max": 1440, "intervalo_transmision_min": 15, "intervalo_transmision_max": 1440},
    {"id_tipo_dispositivo": 3, "nombre": "SENSOR_AMBIENTAL", "frecuencia_captura_min": 5, "frecuencia_captura_max": 120, "intervalo_transmision_min": 5, "intervalo_transmision_max": 240}
  ]
}
```

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

Integración MQTT real vía `BROKER-MQTT-SGPMP` (ya no es un stub). El endpoint
llama al broker, que publica el comando y espera hasta 30s (configurable,
`MQTT_ACK_TIMEOUT_SECONDS` en el broker) el ACK del dispositivo antes de
responder. Según el resultado, el código HTTP y el `estado` final varían:

| `estado` final | HTTP | Cuándo |
|---|---|---|
| `APLICADA` | `200` | El dispositivo confirmó el ACK dentro del timeout |
| `PENDIENTE` | `202` | Dispositivo no `ACTIVO` en `modulo3.estados_dispositivos_iot`, o broker inalcanzable |
| `NO_CONF` | `504` | Se publicó el comando pero no llegó ACK dentro del timeout |

Verificado end-to-end (2026-08-20) contra backend + broker + Mosquitto reales,
con un ACK simulado vía `mosquitto_pub` en `sgpmp/<serial>/status`.

### Enviar configuración remota (Flujo C)

`intervalo_transmision` debe ser ≥ `frecuencia_captura` (FA-12).
`frecuencia_captura`/`intervalo_transmision` deben caer dentro del rango del **tipo** del
dispositivo (RF-23/#1632, FA "parámetros fuera de rango técnico"); los rangos se consultan en
`GET /configuracion/tipos-dispositivo-iot`.
No puede existir una configuración `PENDIENTE` previa para el mismo dispositivo (FA-15,
blindado con índice único parcial en BD, ver `alembic/versions/7e2d5f3bf17a_rf23_mqtt_integracion.py`).

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot/1/configurar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "frecuencia_captura": 30,
    "intervalo_transmision": 60
  }'
```

Caso `APLICADA` (dispositivo `ACTIVO`, ACK recibido a tiempo) — `200`:
```json
{
  "id_configuracion_remota": 11,
  "id_dispositivo_iot": 10,
  "frecuencia_captura": 12,
  "intervalo_transmision": 20,
  "estado": "APLICADA",
  "id_usuario": 43,
  "fecha_creacion": "2026-08-20T14:11:41.833690Z",
  "fecha_aplicacion": "2026-08-20T14:11:49.118642Z",
  "mensaje": "El dispositivo confirmó la recepción de la configuración."
}
```

Caso `PENDIENTE` (dispositivo no `ACTIVO`, respuesta inmediata) — `202`:
```json
{
  "id_configuracion_remota": 12,
  "id_dispositivo_iot": 2,
  "frecuencia_captura": 5,
  "intervalo_transmision": 15,
  "estado": "PENDIENTE",
  "id_usuario": 43,
  "fecha_creacion": "2026-08-20T14:12:24.675930Z",
  "fecha_aplicacion": null,
  "mensaje": "Dispositivo offline. La configuración quedará pendiente hasta que reconecte."
}
```

Caso `NO_CONF` (dispositivo `ACTIVO`, sin ACK dentro de 30s) — `504`:
```json
{
  "error_code": "CONFIGURACION_NO_CONFIRMADA",
  "message": "El comando fue enviado pero el dispositivo no confirmó la recepción a tiempo.",
  "fields": [],
  "timestamp": "2026-08-20T14:13:05.862948+00:00"
}
```

Errores posibles:
- `404` — dispositivo no existe (FA-02)
- `422` — dispositivo inactivo
- `400` — `intervalo_transmision` < `frecuencia_captura` (FA-12) — `CONFLICTO_TIEMPOS_CONFIG`
- `400` — valor fuera del rango del tipo de dispositivo (RF-23/#1632) — `PARAMETRO_FUERA_DE_RANGO`
  (mensaje: "Valor inválido: El parámetro {frecuencia_captura|intervalo_transmision} debe estar
  entre {min} y {max} minutos para este tipo de dispositivo. Valor recibido: {valor}.")
- `409` — ya existe configuración PENDIENTE para el dispositivo (FA-15) — `CONFIG_PENDIENTE_EXISTENTE`
- `504` — se envió pero no hubo ACK a tiempo — `CONFIGURACION_NO_CONFIRMADA`
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

- **MQTT real (RF-23)**: `MqttHttpAdapter` llama a `BROKER-MQTT-SGPMP` (`POST /v1/commands`, autenticado con un token de servicio validado contra `modulo1.credenciales_servicio`). El broker publica en Mosquitto y espera el ACK; el resultado (`APLICADA`/`PENDIENTE`/`NO_CONF`) se traduce a `200`/`202`/`504`. El broker ya **no** escribe `modulo9.configuraciones_remotas` — esa tabla es propiedad exclusiva de este backend. Fuera de esta entrega: reenvío automático cuando un dispositivo `PENDIENTE` reconecta más tarde (requiere webhook broker→backend, contrato de topics aún no cerrado con el equipo IoT).
- **Sensor fijo a infraestructura**: La DB impide mediante trigger (`trg_fn_sensor_asociacion_infraestructura_fija`) que un sensor sea asociado a más de una infraestructura en toda su vida útil. Una vez asociado al área X, nunca puede moverse al área Y.
- **Serial único**: El serial del dispositivo es globalmente único. La validación se hace con pre-check en el use case antes del INSERT para obtener un `409` limpio.
- **Auditoría de dispositivos**: Las operaciones CREATE, DEACTIVATE y GET sobre dispositivos quedan registradas en `modulo9.auditorias_dispositivos_iot`.
- **Auditoría de asociaciones**: Las operaciones CREATE sobre sensor-área quedan registradas en `modulo9.auditorias_sensores_areas`.
- **Swagger local**: `http://localhost:8000/docs` → secciones "Configuración - Dispositivos IoT" y "Configuración - Sensores".
