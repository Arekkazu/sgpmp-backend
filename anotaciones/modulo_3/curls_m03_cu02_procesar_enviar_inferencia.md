# CURLs — M03 CU02: Procesar y enviar datos al motor de inferencia (RF-56)

## Endpoint

`POST /iot/eventos-edge`

Autenticación con el token de servicio del broker (`Authorization: Bearer $BROKER_SERVICE_TOKEN`, D3 de AIOT-DEV-03); el `serial` del body es la identidad del nodo. No requiere JWT.

**DEV-17 / P7:** los ejemplos usan el stub sin integración real. Un `201`
confirma recepción y persistencia; no confirma entrega a IA. Las desviaciones
conservan su paquete en `PENDIENTE`, con `intento_envios = 0`.

**INC-M03-118-G61 (RF-55, SLA de 500 ms):** toda respuesta `201` incluye además
`latencia_edge_ms` (`timestamp_procesamiento_edge − timestamp_captura`, en ms, reloj del
nodo) y `sla_edge_excedido` (`true` si supera 500 ms; exactamente 500 cumple). Los dos
valores quedan en `metadatos` del evento. Es evidencia de lo que reporta el Edge, no una
medición del backend. Por ejemplo, en el primer flujo de abajo
(`11:01:00Z` → `11:01:00.200Z`):

```json
{"latencia_edge_ms": 200, "sla_edge_excedido": false}
```

---

## Flujo principal — DESVIACION_SIMPLE con contexto completo → paquete PENDIENTE

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "DESVIACION_SIMPLE",
    "severidad": "MODERADO",
    "variables_involucradas": [
      {
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 38.5,
        "unidad": "C",
        "timestamp_captura": "2026-07-06T11:01:00Z"
      },
      {
        "tipo_variable": "HUMEDAD_RELATIVA",
        "valor": 90.0,
        "unidad": "%",
        "timestamp_captura": "2026-07-06T11:01:01Z"
      }
    ],
    "timestamp_captura": "2026-07-06T11:01:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T11:01:00.200Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_evento_edge_computing": 31,
  "clasificacion_rf55": "DESVIACION_SIMPLE",
  "severidad": "MODERADO",
  "estado_conectividad": true,
  "fecha_procesamiento": "2026-07-06T11:01:00.200000Z",
  "paquete_inferencia_estado": "PENDIENTE"
}
```

---

## Flujo NORMAL — evento guardado sin paquete de inferencia

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "NORMAL",
    "variables_involucradas": [
      {
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 25.0,
        "unidad": "C",
        "timestamp_captura": "2026-07-06T11:00:00Z"
      }
    ],
    "timestamp_captura": "2026-07-06T11:00:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T11:00:00.100Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_evento_edge_computing": 30,
  "clasificacion_rf55": "NORMAL",
  "severidad": null,
  "estado_conectividad": true,
  "fecha_procesamiento": "2026-07-06T11:00:00.100000Z",
  "paquete_inferencia_estado": null
}
```

---

## Flujo DESVIACION_COMPUESTA — múltiples variables, contexto completo

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "DESVIACION_COMPUESTA",
    "severidad": "CRITICO",
    "variables_involucradas": [
      {
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 42.0,
        "unidad": "C",
        "timestamp_captura": "2026-07-06T12:00:00Z"
      },
      {
        "tipo_variable": "HUMEDAD_RELATIVA",
        "valor": 98.0,
        "unidad": "%",
        "timestamp_captura": "2026-07-06T12:00:00Z"
      },
      {
        "tipo_variable": "NH3",
        "valor": 55.0,
        "unidad": "ppm",
        "timestamp_captura": "2026-07-06T12:00:01Z"
      }
    ],
    "timestamp_captura": "2026-07-06T12:00:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T12:00:00.500Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_evento_edge_computing": 34,
  "clasificacion_rf55": "DESVIACION_COMPUESTA",
  "severidad": "CRITICO",
  "estado_conectividad": true,
  "fecha_procesamiento": "2026-07-06T12:00:00.500000Z",
  "paquete_inferencia_estado": "PENDIENTE"
}
```

---

## FA-03 — Contexto incompleto (variable sin su pareja mínima)

Contexto hídrico con solo OXIGENO_DISUELTO (falta PH_AGUA).
El paquete se crea con `contexto_incomplento: true`; no es un error, el motor de inferencia decide.

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "DESVIACION_SIMPLE",
    "severidad": "LEVE",
    "variables_involucradas": [
      {
        "tipo_variable": "OXIGENO_DISUELTO",
        "valor": 4.5,
        "unidad": "mg/L",
        "timestamp_captura": "2026-07-06T11:02:00Z"
      }
    ],
    "timestamp_captura": "2026-07-06T11:02:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T11:02:00.100Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (201) — paquete creado con contexto incompleto:**
```json
{
  "id_evento_edge_computing": 32,
  "clasificacion_rf55": "DESVIACION_SIMPLE",
  "severidad": "LEVE",
  "estado_conectividad": true,
  "fecha_procesamiento": "2026-07-06T11:02:00.100000Z",
  "paquete_inferencia_estado": "PENDIENTE"
}
```

*(En BD: `paquetes_inferencia.contexto_incomplento = true`)*

---

## FA-03 — Datos fundamentalmente inconsistentes (lista vacía)

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "DESVIACION_SIMPLE",
    "variables_involucradas": [],
    "timestamp_captura": "2026-07-06T11:04:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T11:04:00.100Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (422):**
```json
{
  "error_code": "PAQUETE_INCONSISTENTE",
  "message": "El evento Edge no contiene variables para consolidar.",
  "fields": []
}
```

---

## FA-04/05 — Integración ausente y resultado de un intento de entrega

Con `MotorInferenciaStubAdapter`, el puerto señala `MotorInferenciaNoIntegradoError`:
- El paquete ya confirmado queda `PENDIENTE`, con `intento_envios = 0`.
- La respuesta sigue siendo `201`; no se revierte el paquete por falta de IA.
- El evento y su contexto permanecen almacenados y correlacionables.
- `obtener_por_evento(id_evento)` permite recuperar el paquete desde el repositorio.

Cuando un adaptador integrado devuelve `False` o lanza otra excepción:
- El paquete queda con `estado_paquete = FALLIDO`, `intento_envios = 1`
- El evento queda guardado con `enviado_backend = false`

Un retorno `True` conserva la transición a `ENVIADO`, con un intento.
Ese camino está probado con un doble del puerto; no demuestra entrega real a IA.

Reconsolidar el mismo ID de evento devuelve el paquete existente sin crear
otro ni intentar una nueva entrega. No existe aquí un worker de reintentos.
El contrato actual del POST no incluye una clave externa de idempotencia;
un nuevo POST no se identifica automáticamente como retransmisión del anterior.

---

## FA-07 — ERROR_CONFIGURACION → evento guardado, sin paquete M04

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "ERROR_CONFIGURACION",
    "variables_involucradas": [
      {
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 22.0,
        "unidad": "C",
        "timestamp_captura": "2026-07-06T11:03:00Z"
      }
    ],
    "timestamp_captura": "2026-07-06T11:03:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T11:03:00.100Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_evento_edge_computing": 33,
  "clasificacion_rf55": "ERROR_CONFIGURACION",
  "severidad": null,
  "estado_conectividad": true,
  "fecha_procesamiento": "2026-07-06T11:03:00.100000Z",
  "paquete_inferencia_estado": null
}
```

---

## Error — Credencial inválida (401)

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "SERIAL-DE-OTRO-NODO",
    "clasificacion_rf55": "NORMAL",
    "variables_involucradas": [
      {"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 25.0, "unidad": "C", "timestamp_captura": "2026-07-06T11:05:00Z"}
    ],
    "timestamp_captura": "2026-07-06T11:05:00Z",
    "timestamp_procesamiento_edge": "2026-07-06T11:05:00.100Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (401):**
```json
{
  "error_code": "DISPOSITIVO_NO_AUTORIZADO",
  "message": "El dispositivo o el sensor no corresponden al serial, o el dispositivo está inactivo.",
  "fields": []
}
```

---

## Error — Timestamp futuro (400)

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "NORMAL",
    "variables_involucradas": [
      {"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 25.0, "unidad": "C", "timestamp_captura": "2030-01-01T00:00:00Z"}
    ],
    "timestamp_captura": "2030-01-01T00:00:00Z",
    "timestamp_procesamiento_edge": "2030-01-01T00:00:00.100Z",
    "origen": "TIEMPO_REAL",
    "estado_conectividad": true
  }'
```

**Respuesta esperada (400):**
```json
{
  "error_code": "TIMESTAMP_FUTURO",
  "message": "El timestamp de captura está ... s en el futuro (máx. 30 s).",
  "fields": [{"field": "timestamp_captura", "message": "..."}]
}
```

---

## Error — Dato de buffer expirado (400)

```bash
curl -s -X POST http://localhost:8000/iot/eventos-edge \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "serial": "IOT-EST01-HLA-001",
    "clasificacion_rf55": "NORMAL",
    "variables_involucradas": [
      {"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": 25.0, "unidad": "C", "timestamp_captura": "2026-01-01T00:00:00Z"}
    ],
    "timestamp_captura": "2026-01-01T00:00:00Z",
    "timestamp_procesamiento_edge": "2026-01-01T00:00:00.100Z",
    "origen": "BUFFER_LOCAL",
    "estado_conectividad": false
  }'
```

**Respuesta esperada (400):**
```json
{
  "error_code": "TIMESTAMP_EXPIRADO",
  "message": "El dato de buffer tiene ... h de antigüedad (máx. 72 h).",
  "fields": [{"field": "timestamp_captura", "message": "..."}]
}
```
