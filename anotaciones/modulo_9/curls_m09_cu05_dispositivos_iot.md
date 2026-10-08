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

Un sensor tiene una sola asociación de área activa. Asociarlo a la misma área en la que ya está activo devuelve `409 ASOCIACION_DUPLICADA`. Asociarlo a otra área es una **reasignación** (RF-22 v1.1): sin `confirmar` responde `409 REASIGNACION_REQUIERE_CONFIRMACION`; con `"confirmar": true` termina la asociación anterior y crea la nueva.

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

Respuesta esperada `201` (primera asociación):
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
  "id_usuario": 1,
  "asociaciones_activo_superadas": []
}
```

#### Reasignación confirmada a otra área

```bash
curl -X POST http://localhost:8000/configuracion/sensores/1/asociar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dispositivo_iot": 1,
    "id_infraestructura": 2,
    "punto_instalacion": "Borde sur",
    "confirmar": true
  }'
```

Respuesta esperada `201`. Las asociaciones sensor→activo `ambiental` y `poblacional` vigentes del sensor quedan `SUPERADA` en la misma transacción, con auditoría (issue #290, RF-22 v1.1 / RF-49 v1.2); las `directa` no se tocan. `asociaciones_activo_superadas` lista las que se cerraron para que el frontend avise al usuario y este las re-asocie vía RF-49 si quiere. No se recrean solas en la nueva área.
```json
{
  "id_sensores_area_asociada": 2,
  "id_sensor": 1,
  "id_dispositivo_iot": 1,
  "id_infraestructura": 2,
  "punto_instalacion": "Borde sur",
  "tiene_estado": true,
  "fecha_asociacion": "2026-10-02T15:10:00Z",
  "fecha_finalizacion": null,
  "id_usuario": 1,
  "asociaciones_activo_superadas": [
    { "id_asociacion_activo_sensor": 14, "id_activo_biologico": 279, "tipo": "ambiental" }
  ]
}
```

Errores posibles:
- `404` — sensor no existe (FA-02) — `SENSOR_NO_ENCONTRADO`
- `404` — dispositivo no existe — `DISPOSITIVO_NO_ENCONTRADO`
- `404` — área productiva no existe **o está inactiva** (FA-03) — `AREA_NO_ENCONTRADA`
- `422` — sensor no pertenece al dispositivo indicado (FA-02) — `SENSOR_DISPOSITIVO_INVALIDO`
- `422` — área de una finca distinta a la del dispositivo — `SENSOR_FINCA_DISTINTA`
- `409` — sensor ya está activo en esa área (FA-06) — `ASOCIACION_DUPLICADA`
- `409` — sensor activo en otra área y la petición no trae `"confirmar": true` — `REASIGNACION_REQUIERE_CONFIRMACION`
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

El permiso RBAC habilita la acción, pero no concede alcance territorial. El Administrador
conserva alcance global; el Ingeniero solo puede configurar dispositivos ubicados en fincas
vinculadas a su usuario mediante `modulo9.fincas.id_usuario`. Un dispositivo inexistente o
fuera de ese alcance responde igual (`404 DISPOSITIVO_NO_ENCONTRADO`) para evitar enumeración.

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
- `404` — dispositivo no existe o está fuera del alcance por finca del usuario —
  `DISPOSITIVO_NO_ENCONTRADO`
- `422` — dispositivo inactivo
- `400` — `intervalo_transmision` < `frecuencia_captura` (FA-12) — `CONFLICTO_TIEMPOS_CONFIG`
- `400` — `VAL_ENTRADA` con un campo que RF-23 no define (p. ej. `"protocolo": "LoRaWAN"`), señalado en
  `fields` con "Este campo no está permitido en esta solicitud." (INC-M09-66-G69 #492; antes se
  ignoraba y respondía `202`). LoRaWAN es la red dispositivo↔gateway; el backend solo publica MQTT
- `400` — valor fuera del rango del tipo de dispositivo (RF-23/#1632) — `PARAMETRO_FUERA_DE_RANGO`
  (mensaje: "Valor inválido: El parámetro {frecuencia_captura|intervalo_transmision} debe estar
  entre {min} y {max} minutos para este tipo de dispositivo. Valor recibido: {valor}.")
- `409` — ya existe configuración PENDIENTE para el dispositivo (FA-15) — `CONFIG_PENDIENTE_EXISTENTE`
- `504` — se envió pero no hubo ACK a tiempo — `CONFIGURACION_NO_CONFIRMADA`
- `403` — rol sin permiso U sobre dispositivos_iot (FA-01)

---

### Historial de configuraciones del dispositivo

Aplica el mismo alcance por finca que el POST. Un dispositivo inexistente o ajeno responde
`404 DISPOSITIVO_NO_ENCONTRADO` sin consultar ni exponer su historial.

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

### Reintentar o cancelar una configuración sin aplicar

Solo para configuraciones `PENDIENTE` o `NO_CONF` (permiso U del recurso 11, mismo alcance por
finca). Una `PENDIENTE` bloquea enviar otra al dispositivo y desactivarlo: cancelarla lo destraba.
Ambas acciones quedan en `modulo3.bitacora_auditoria_iot` (`CONFIGURACION_REMOTA_REINTENTADA` /
`CONFIGURACION_REMOTA_CANCELADA`) con el usuario que las hizo.

```bash
# Reintentar: vuelve a enviarla por el broker. Responde como el POST /configurar:
# 200 APLICADA, 202 PENDIENTE (sigue offline), 504 CONFIGURACION_NO_CONFIRMADA.
curl -X POST http://localhost:8000/configuracion/dispositivos-iot/1/configuraciones/2/reintentar \
  -H "Authorization: Bearer <TOKEN>"

# Cancelar: queda CANCELADA en el historial. Responde 200 con la configuración.
curl -X PATCH http://localhost:8000/configuracion/dispositivos-iot/1/configuraciones/2/cancelar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores:
- `404 CONFIGURACION_NO_ENCONTRADA`: no existe o es de otro dispositivo.
- `409 CONFIGURACION_YA_RESUELTA`: está `APLICADA` o `CANCELADA`.
- `409 CONFIGURACION_REEMPLAZADA` (solo reintentar): hay una configuración más reciente; reenviar
  la vieja la sobrescribiría en el dispositivo.
- `422 DISPOSITIVO_INACTIVO` (solo reintentar). Cancelar sí se permite sobre un dispositivo inactivo.

---

## RF-24 — Calibración de sensores (`/configuracion/sensores/{id}/calibrar`)

Recurso `id_recurso=12`, acción C(1). Admin / Ing.

### Registrar calibración (Flujo D)

El sensor debe existir, el dispositivo debe estar activo y el sensor debe tener
una asociación activa en el área indicada. `valor_referencia` (y el `offset` si se
envía) deben caer dentro del rango de seguridad del tipo de sensor (RF-24 / #1635).

`ganancia` (default `1.0`) y `offset` (default = `valor_referencia`) son opcionales:
componen el modelo lineal `valor_ajustado = ganancia * crudo + offset` que consume telemetry.

`modo_calibracion` (RF-24 v2.0, TC-M09-259 #510) es obligatorio, sin default, y `SENSOR` es el
único valor admitido aquí: la modalidad `VISION` (línea base por área y especie, sin
sensor) tiene su propio endpoint, `POST /configuracion/calibraciones-vision` (ver la
sección siguiente). Se devuelve en la respuesta y queda en el snapshot de auditoría.

```bash
curl -X POST http://localhost:8000/configuracion/sensores/1/calibrar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dispositivo_iot": 1,
    "id_infraestructura": 1,
    "valor_referencia": "25.50",
    "ganancia": "1.0",
    "offset": "0.20",
    "fecha_calibracion": "2026-06-21T10:00:00Z",
    "observaciones": "Calibración con termómetro patrón certificado",
    "modo_calibracion": "SENSOR"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_calibracion": 1,
  "id_dispositivo_iot": 1,
  "id_sensor": 1,
  "valor_referencia": "25.5000",
  "ganancia": "1.0000",
  "offset": "0.2000",
  "fecha_calibracion": "2026-06-21T10:00:00Z",
  "id_usuario": 1,
  "observaciones": "Calibración con termómetro patrón certificado",
  "modo_calibracion": "SENSOR"
}
```

Errores posibles:
- `404` — sensor no existe (FA-02)
- `404` — dispositivo no existe (FA-02) — `DISPOSITIVO_NO_ENCONTRADO`
- `404` — dispositivo de una finca fuera del alcance del usuario (#503): mismo
  `DISPOSITIVO_NO_ENCONTRADO` que el inexistente, para no confirmar que existe. Un rol
  sin U/D sobre fincas (p. ej. Ingeniero de Campo) solo calibra en las fincas de
  `modulo9.usuarios_fincas`; queda auditado como rechazo (RFC-006)
- `422` — dispositivo inactivo (FA-14) — `DISPOSITIVO_INACTIVO`
- `422` — sensor no pertenece al dispositivo (FA-02) — `SENSOR_DISPOSITIVO_INVALIDO`
- `400` — sensor no tiene asociación activa en el área indicada (FA-03) — `SENSOR_AREA_INVALIDA`
- `400` — `valor_referencia`/`offset` fuera del rango de seguridad del tipo de sensor
  (FA-11, ej. temperatura 500 °C) — `VALOR_FUERA_DE_RANGO`
- `400` — `valor_referencia` no numérico, vacío o nulo (FA "Datos no numéricos o
  incompletos") — `VALOR_CALIBRACION_INVALIDO`
- `400` — `valor_referencia` ≤ 0 cuando la `categoria` no tiene rango configurado
  (fallback) — `VALOR_CALIBRACION_INVALIDO`
- `400` — `ganancia` ≤ 0 (validación de DTO)
- `400` — `modo_calibracion` ausente, nulo o distinto de `SENSOR` (validación de DTO) — `VAL_ENTRADA`
- `403` — rol sin permiso C sobre sensores (FA-01) — solo Ing. de Campo y Admin pueden calibrar
- `500` — falla la escritura del historial de auditoría inmutable (FA RF-10): se hace
  rollback de la calibración — `AUDITORIA_CALIBRACION_FALLIDA`

Ejemplo de rechazo por rango (`400`):
```bash
curl -X POST http://localhost:8000/configuracion/sensores/1/calibrar \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"id_dispositivo_iot":1,"id_infraestructura":1,"valor_referencia":"500",
       "fecha_calibracion":"2026-06-21T10:00:00Z"}'
# {"error_code":"VALOR_FUERA_DE_RANGO","message":"El ajuste de 500 excede los rangos
#  de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000)...","field":"valor_referencia"}
```

---

### Catálogo de rangos de calibración por tipo de sensor (RF-24 / #1635)

Recurso `id_recurso=12`, acción R(2). El frontend lo consume para mostrar los límites válidos.

```bash
curl -X GET http://localhost:8000/configuracion/sensores/rangos-calibracion \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 7,
  "items": [
    {"categoria": "AMONIACO", "valor_min": "0.0000", "valor_max": "10.0000"},
    {"categoria": "TEMPERATURA", "valor_min": "0.0000", "valor_max": "45.0000"}
  ]
}
```

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
      "ganancia": "1.0000",
      "offset": "0.2000",
      "fecha_calibracion": "2026-06-21T10:00:00Z",
      "id_usuario": 1,
      "observaciones": "Calibración con termómetro patrón certificado",
      "modo_calibracion": "SENSOR"
    },
    {
      "id_calibracion": 1,
      "id_dispositivo_iot": 1,
      "id_sensor": 1,
      "valor_referencia": "25.0000",
      "ganancia": "1.0000",
      "offset": "25.0000",
      "fecha_calibracion": "2026-03-29T14:42:28Z",
      "id_usuario": 1,
      "observaciones": "Calibración inicial con termómetro patrón certificado NIST.",
      "modo_calibracion": "SENSOR"
    }
  ]
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre sensores
- `404` — sensor inexistente o de una finca fuera del alcance del usuario (#503,
  mismo criterio que el historial de asociaciones, INC-M09-22-G126-02) —
  `SENSOR_NO_ENCONTRADO`. Un rol con alcance global (Admin) ve cualquier sensor

---

## RF-24 v2.0 — Calibración por visión (`/configuracion/calibraciones-vision`)

INC-M09-78-G138 (#514). Modalidad `VISION` de RF-24 (RFC-011): calcula la **línea base
de comportamiento** de un área para su especie a partir de las cámaras activas del área,
con las tres etapas de auditoría automática (filtrado ambiental → recorte p5/p95 →
refinamiento iterativo). Mismo recurso que la calibración SENSOR: `id_recurso=12`,
acción C(1) para calcular y R(2) para consultar.

> **Estado de los datos:** M03 todavía no expone las observaciones de cámara (RF-53/56)
> ni su `apto_para_ia` (RF-62). Hasta entonces el backend usa un stub sin observaciones:
> un área que cumple todas las precondiciones termina en `422 LINEA_BASE_NO_CALCULADA`
> (Etapa 1, datos insuficientes) y el intento queda guardado como `FALLIDA`. Las
> precondiciones (área, especie, modelo POBLACIONAL, cámara activa) sí se validan de verdad.

### Calcular línea base (disparo manual)

```bash
curl -X POST http://localhost:8000/configuracion/calibraciones-vision \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "modo_calibracion": "VISION",
    "area_id": 2,
    "ventana_observacion": {"inicio": "2026-10-01T00:00:00Z", "fin": "2026-10-02T00:00:00Z"},
    "observaciones": "Recalibración tras nuevo lote"
  }'
```

- `modo_calibracion` es obligatorio y solo admite `VISION`.
- `fecha_calibracion` es opcional (por defecto, el momento del disparo).
- `origen_disparo` no se envía: este endpoint siempre es `MANUAL`. El disparo
  `AUTOMATICO` desde M02 (nuevo lote / fin de ciclo) aún no está conectado.

Respuesta esperada `201` (línea base publicada; reemplaza la vigente del par área/especie):
```json
{
  "id_calibracion_vision": 5,
  "modo_calibracion": "VISION",
  "area_id": 2,
  "especie_id": 4,
  "origen_disparo": "MANUAL",
  "id_usuario": 7,
  "ventana_observacion": {"inicio": "2026-10-01T00:00:00Z", "fin": "2026-10-02T00:00:00Z"},
  "fecha_calibracion": "2026-10-07T15:00:00Z",
  "estado": "EXITOSA",
  "etapa_fallo": null,
  "motivo": null,
  "linea_base": {
    "valores": {"densidad_actividad": 10.95, "tasa_movimiento": 3.35},
    "componentes_no_calibrables": []
  },
  "n_observaciones": 60,
  "n_observaciones_validas": 60,
  "iteraciones": 1,
  "observaciones": "Recalibración tras nuevo lote"
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso C sobre sensores (FA "Acceso no autorizado") — `ACCESO_DENEGADO`,
  con el mensaje de la ficha: *"Acceso denegado: La calibración de sensores es una función
  crítica restringida exclusivamente al Ingeniero de Campo o al Administrador."* Queda
  auditado (RFC-006)
- `404` — área inexistente o de una finca fuera del alcance del usuario — `AREA_NO_ENCONTRADA`
- `422` — `VISION_NO_DISPONIBLE` (FA "Área sin cámara apta"), en cualquiera de estos casos:
  - área sin cámara asociada (TC-M09-278, TC-M09-291)
  - todas sus cámaras inactivas (TC-M09-279)
  - `tipo_modelo_asignado` de paradigma INDIVIDUAL o META (TC-M09-280)
  - sin `tipo_modelo_asignado` (TC-M09-281) o sin especie
  - hay observaciones en la ventana, pero ninguna con `apto_para_ia = true`

  Mensaje: *"Calibración por visión no disponible: El área 2 no cuenta con observaciones
  de cámara aptas o no tiene un modelo poblacional asignado. Verifique las cámaras
  (RF-21/22) y la configuración del área (RF-20)."* No se guarda intento ni línea base.
- `422` — `LINEA_BASE_NO_CALCULADA` (FA "Observaciones válidas insuficientes o no
  convergida"): falla una de las tres etapas. El intento queda en el historial como
  `FALLIDA` o `NO_CONVERGIDA` con `etapa_fallo` y `motivo`; la línea base vigente no se
  toca. Mensaje: *"No se pudo calcular la línea base: datos insuficientes o sin
  convergencia para el área 2 y especie 4. Se conserva la línea base vigente anterior."*
- `400` — body inválido (validación de DTO): falta `modo_calibracion` o no es `VISION`,
  falta `area_id`, o `ventana_observacion.fin` ≤ `inicio` — `VAL_ENTRADA`
- `500` — falla la auditoría RF-10 del cálculo exitoso: rollback, no se publica la línea
  base — `AUDITORIA_CALIBRACION_FALLIDA`

Todo `403`/`404`/`422` queda en `modulo1.eventos` (tipo 29, `exitoso=false`,
`detalle.operacion = "CALIBRACION_VISION"`), best-effort: si esa escritura falla, el
rechazo conserva su código. El éxito se audita con el tipo 30 `CALIBRACION_EXITOSA` (`exitoso=true`,
`detalle.operacion = "CALIBRACION_VISION"`).

### Historial de cálculos del área

```bash
curl -X GET "http://localhost:8000/configuracion/calibraciones-vision?area_id=2" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta `200`: `{"total": n, "items": [ ...mismo objeto que el POST... ]}`, el más
reciente primero. Incluye los `FALLIDA` y `NO_CONVERGIDA`.

Errores: `401`, `403` (sin R sobre sensores), `404 AREA_NO_ENCONTRADA`.

### Línea base vigente del área

```bash
curl -X GET "http://localhost:8000/configuracion/calibraciones-vision/linea-base?area_id=2" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta `200`:
```json
{
  "area_id": 2,
  "especie_id": 4,
  "id_calibracion_vision": 5,
  "linea_base": {
    "valores": {"densidad_actividad": 10.95, "tasa_movimiento": 3.35},
    "componentes_no_calibrables": []
  },
  "fecha_publicacion": "2026-10-07T15:00:00Z"
}
```

Errores: `401`, `403`, `404 AREA_NO_ENCONTRADA`, `404 LINEA_BASE_NO_ENCONTRADA` (el área
nunca tuvo un cálculo exitoso para su especie actual). Sirve para comprobar que un
rechazo no publicó una línea base nueva (PRE/POST de G138).

---

## RF-21 — Gateway Edge de los dispositivos (relación N:1)

El **Gateway Edge** es la computadora de borde del sitio (hoy una Raspberry), el
"Gateway IoT" que describe M03: recibe por radio los datos de varios
dispositivos, los pasa a IP y es lo único que habla MQTT con el broker. Se
registra como un dispositivo más, con el tipo `GATEWAY_EDGE`, y cada dispositivo
que atiende apunta a él con `id_dispositivo_gateway` (autorreferencia en
`modulo9.dispositivos_iot`, migración `4254acf5798b`). Cualquier tipo de
dispositivo (un ESP32 u otro hardware) puede depender de un Edge.

Reglas (las valida el caso de uso):
- Solo se puede apuntar a un `GATEWAY_EDGE` **activo** de la **misma finca**
  (puede estar en otra área). Un Edge no depende de otro Edge.
- Desactivar un Edge **desactiva en cascada** a sus dispositivos activos, en la
  misma transacción y con una auditoría `DEACTIVATE` por cada uno
  (`valores_nuevos.motivo = "gateway_edge_desactivado"`). El vínculo se conserva.
  Si alguno tiene una configuración RF-23 pendiente, no se desactiva nada.
- Cada cambio se le avisa al broker para que recalcule los topics de la
  credencial MQTT del Edge (sin rotar la clave). Se audita en
  `modulo3.bitacora_auditoria_iot` (`DISPOSITIVO_GATEWAY_EDGE_ASIGNADO`).
- RF-23 no aplica a un Edge (`CONFIGURACION_NO_APLICA_A_GATEWAY_EDGE`): la
  configuración se hace sobre los dispositivos que atiende.

### Registrar un dispositivo vinculado a su Edge

Igual que "Registrar dispositivo IoT", con el campo opcional `id_dispositivo_gateway`:

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"serial": "IOT-EST02-HLA-002", "descripcion": "Nodo estanque 02",
       "id_infraestructura": 2, "id_tipo_dispositivo": 1, "id_dispositivo_gateway": 40}'
```

### Asignar, cambiar o quitar el Edge de un dispositivo

```bash
curl -X PATCH http://localhost:8000/configuracion/dispositivos-iot/2/gateway \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_dispositivo_gateway": 40}'   # null para quitarlo
```

Respuesta `200`: el dispositivo con su `id_dispositivo_gateway`. Permiso U (3) del recurso 11.

| Código | `error_code` | Cuándo |
|--------|--------------|--------|
| 404 | `DISPOSITIVO_NO_ENCONTRADO` / `GATEWAY_EDGE_NO_ENCONTRADO` | No existe o está fuera del alcance por finca |
| 422 | `NO_ES_GATEWAY_EDGE` | El destino no es de tipo `GATEWAY_EDGE` |
| 422 | `GATEWAY_EDGE_INACTIVO` | El Edge está inactivo |
| 422 | `GATEWAY_EDGE_OTRA_FINCA` | El Edge es de otra finca |
| 422 | `EDGE_NO_TIENE_GATEWAY` | Se intenta darle un Edge a un Edge |
| 422 | `DISPOSITIVO_INACTIVO` | El dispositivo está inactivo |

### Desactivar un Edge (cascada)

`PATCH /configuracion/dispositivos-iot/{id}/desactivar` sobre un Edge desactiva
también a sus dispositivos. Error adicional: `422 CONFIG_PENDIENTE_EN_DISPOSITIVOS_DEL_EDGE`
(lista los seriales con configuración pendiente).

---

## RF-23 — Credencial MQTT del Gateway Edge (TC-M09-250/251)

Lo que se conecta al broker es el Gateway Edge (o un dispositivo **sin** Edge, que
se conecta directo). Cada uno tiene su propia credencial: usuario = su serial,
con permiso solo sobre sus topics y los de los dispositivos que atiende, que el
broker lee de `id_dispositivo_gateway`. Un dispositivo que depende de un Edge no
tiene credencial propia. La emite `BROKER-MQTT-SGPMP`
(`/v1/devices/{serial}/credential`); este backend aplica RBAC, alcance por finca
y audita en `modulo3.bitacora_auditoria_iot` (`componente_origen=RF23`). La
contraseña **no se guarda**: se devuelve una sola vez.

| Método | Ruta | RBAC (recurso 11) |
|--------|------|-------------------|
| POST | `/configuracion/dispositivos-iot/{id}/credencial-mqtt` | U(3) — Admin, Ing |
| GET | `/configuracion/dispositivos-iot/{id}/credencial-mqtt` | R(2) — Admin, Ing, Prod |
| DELETE | `/configuracion/dispositivos-iot/{id}/credencial-mqtt` | D(4) — Admin, Ing |

### Emitir o rotar

Rotar invalida la clave anterior y desconecta al Edge hasta que se actualice su
`/etc/sgpmp/edge-agent.env`. Sin cuerpo.

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot/40/credencial-mqtt \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada (201, `Cache-Control: no-store`):**
```json
{
  "usuario": "EDGE-REMANSO-01",
  "password": "<se muestra una sola vez>",
  "seriales": ["EDGE-REMANSO-01", "IOT-EST01-HLA-001", "IOT-EST02-HLA-002"]
}
```

| Código | `error_code` | Cuándo |
|--------|--------------|--------|
| 404 | `DISPOSITIVO_NO_ENCONTRADO` | No existe o está fuera del alcance por finca |
| 409 | `CREDENCIAL_MQTT_RECHAZADA` | El broker rechazó el serial (p. ej. coincide con un usuario MQTT reservado) |
| 422 | `DISPOSITIVO_INACTIVO` | El dispositivo está inactivo |
| 422 | `DISPOSITIVO_DEPENDE_DE_GATEWAY_EDGE` | Se comunica por su Edge: la credencial es la del Edge |
| 429 | — | Más de 10 emisiones por minuto |
| 503 | `BROKER_MQTT_NO_DISPONIBLE` | El broker no responde o no está configurado |

### Consultar estado

```bash
curl http://localhost:8000/configuracion/dispositivos-iot/40/credencial-mqtt \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada (200):**
```json
{"emitida": true, "habilitada": true, "conectada": false, "usuario": "EDGE-REMANSO-01", "seriales": ["EDGE-REMANSO-01", "IOT-EST01-HLA-001"]}
```

`{"emitida": false, ...}` si no tiene credencial propia (todavía usa la
compartida o se comunica a través de su Edge).

### Revocar

Desconecta al Edge en el acto. Se permite sobre dispositivos inactivos.
Desactivar el dispositivo ya revoca su credencial; si el broker no responde en
ese momento, la desactivación se mantiene, el fallo queda en la bitácora y el
broker lo corrige al reconciliar con `modulo9`.

```bash
curl -X DELETE http://localhost:8000/configuracion/dispositivos-iot/40/credencial-mqtt \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada:** `204` sin cuerpo. Errores: `404`, `503` como arriba.

---

## Notas técnicas

- **MQTT real (RF-23)**: `MqttHttpAdapter` llama a `BROKER-MQTT-SGPMP` (`POST /v1/commands`, autenticado con un token de servicio validado contra `modulo1.credenciales_servicio`). El broker publica en Mosquitto y espera el ACK; el resultado (`APLICADA`/`PENDIENTE`/`NO_CONF`) se traduce a `200`/`202`/`504`. El broker ya **no** escribe `modulo9.configuraciones_remotas` — esa tabla es propiedad exclusiva de este backend. Fuera de esta entrega: reenvío automático cuando un dispositivo `PENDIENTE` reconecta más tarde (requiere webhook broker→backend, contrato de topics aún no cerrado con el equipo IoT).
- **Sensor fijo a infraestructura**: La DB impide mediante trigger (`trg_fn_sensor_asociacion_infraestructura_fija`) que un sensor sea asociado a más de una infraestructura en toda su vida útil. Una vez asociado al área X, nunca puede moverse al área Y.
- **Serial único**: El serial del dispositivo es globalmente único. La validación se hace con pre-check en el use case antes del INSERT para obtener un `409` limpio.
- **Auditoría de dispositivos**: Las operaciones CREATE, DEACTIVATE y GET sobre dispositivos quedan registradas en `modulo9.auditorias_dispositivos_iot`.
- **Auditoría de asociaciones**: Las operaciones CREATE sobre sensor-área quedan registradas en `modulo9.auditorias_sensores_areas`.
- **Swagger local**: `http://localhost:8000/docs` → secciones "Configuración - Dispositivos IoT" y "Configuración - Sensores".
