# CURLs — M03 CU01: Ingerir telemetría IoT (RF-53)

Base URL local: `http://localhost:8000`

**Auth:** Los endpoints de ingesta IoT **no usan JWT**. La identidad del dispositivo se valida mediante `access_key` en el body (debe coincidir con `modulo9.dispositivos_iot.serial`). El header `X-Gateway-Id` es opcional y se registra en la bitácora para trazabilidad.

Responsabilidad Dev: recibir desde Broker (paso 3+), validar, persistir, publicar.

---

## Flujo A — TIEMPO_REAL: Ingesta individual en línea

### FA.1 — Lectura válida (LECTURA_VALIDA)

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Id: GW-EST01-LORA-001" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 24.5,
    "unidad": "°C",
    "timestamp_captura": "2026-07-05T10:00:00Z",
    "access_key": "IOT-EST01-HLA-001",
    "origen": "TIEMPO_REAL",
    "nivel_bateria": 85.0,
    "estado_conectividad": true
  }'
```

Respuesta esperada `201`:
```json
{
  "id_telemetria": 1,
  "estado_calidad": "LECTURA_VALIDA",
  "timestamp_procesamiento": "2026-07-05T10:00:00.123Z",
  "latencia_procesamiento_ms": null
}
```

---

### FA.2 — Lectura con timestamp futuro → ERROR_TIEMPO (400)

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 24.5,
    "unidad": "°C",
    "timestamp_captura": "2030-01-01T00:00:00Z",
    "access_key": "IOT-EST01-HLA-001"
  }'
```

Respuesta esperada `400`:
```json
{
  "code": "ERROR_TIEMPO",
  "message": "El timestamp_captura es posterior a la hora del servidor.",
  "field": "timestamp_captura"
}
```

---

### FA.3 — Credenciales inválidas → ERROR_AUTENTICACION (401)

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 24.5,
    "unidad": "°C",
    "timestamp_captura": "2026-07-05T10:00:00Z",
    "access_key": "CLAVE_INCORRECTA"
  }'
```

Respuesta esperada `401`:
```json
{
  "code": "ERROR_AUTENTICACION",
  "message": "Dispositivo o sensor no encontrado, inactivo, o credenciales inválidas."
}
```

---

### FA.4 — Unidad inválida → ERROR_UNIDAD (400)

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 24.5,
    "unidad": "bar",
    "timestamp_captura": "2026-07-05T10:00:00Z",
    "access_key": "IOT-EST01-HLA-001"
  }'
```

Respuesta esperada `400`:
```json
{
  "code": "ERROR_UNIDAD",
  "message": "Unidad 'bar' inválida para TEMPERATURA_AMBIENTAL. Unidades aceptadas: °C, °F, K",
  "field": "unidad"
}
```

---

### FA.5 — Dato duplicado → ERROR_DUPLICADO (409)

Mismo payload enviado dos veces.

Respuesta esperada `409` (segunda llamada):
```json
{
  "code": "ERROR_DUPLICADO",
  "message": "Ya existe un registro con la misma clave (sensor, variable, timestamp, origen)."
}
```

---

### FA.6 — Valor físicamente imposible → ERROR_SENSOR (422)

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 500.0,
    "unidad": "°C",
    "timestamp_captura": "2026-07-05T10:00:00Z",
    "access_key": "IOT-EST01-HLA-001"
  }'
```

Respuesta esperada `422`:
```json
{
  "code": "ERROR_SENSOR",
  "message": "Valor 500.0 para TEMPERATURA_AMBIENTAL es físicamente imposible. Revise el hardware del sensor."
}
```

---

### FA.7 — Conversión de unidades (°F → °C)

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 77.0,
    "unidad": "°F",
    "timestamp_captura": "2026-07-05T11:00:00Z",
    "access_key": "IOT-EST01-HLA-001"
  }'
```

Respuesta esperada `201` (valor convertido a 25.0 °C internamente):
```json
{
  "id_telemetria": 2,
  "estado_calidad": "LECTURA_VALIDA",
  "timestamp_procesamiento": "2026-07-05T11:00:00.123Z",
  "latencia_procesamiento_ms": null
}
```

---

## Flujo B — EDGE_AGREGADO: Dato preprocesado en Edge

```bash
curl -X POST http://localhost:8000/iot/telemetria \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 23.8,
    "unidad": "°C",
    "timestamp_captura": "2026-07-05T09:00:00Z",
    "access_key": "IOT-EST01-HLA-001",
    "origen": "EDGE_AGREGADO",
    "valor_agregado": true,
    "ventana_agregacion": 15
  }'
```

Respuesta esperada `201`:
```json
{
  "id_telemetria": 3,
  "estado_calidad": "LECTURA_VALIDA",
  "timestamp_procesamiento": "2026-07-05T10:05:00.001Z",
  "latencia_procesamiento_ms": 3900001
}
```

Nota: `latencia_procesamiento_ms` refleja el desfase entre `timestamp_envio` y el momento de procesamiento.

---

## Flujo C — BUFFER_LOCAL: Sincronización en lote

### FC.1 — Batch mixto (válidos + duplicados)

```bash
curl -X POST http://localhost:8000/iot/telemetria/batch \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Id: GW-EST01-LORA-001" \
  -d '{
    "registros": [
      {
        "device_id": 1,
        "sensor_id": 1,
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 22.1,
        "unidad": "°C",
        "timestamp_captura": "2026-07-05T08:00:00Z",
        "access_key": "IOT-EST01-HLA-001",
        "origen": "BUFFER_LOCAL"
      },
      {
        "device_id": 1,
        "sensor_id": 1,
        "tipo_variable": "HUMEDAD_RELATIVA",
        "valor": 65.0,
        "unidad": "%",
        "timestamp_captura": "2026-07-05T08:01:00Z",
        "access_key": "IOT-EST01-HLA-001",
        "origen": "BUFFER_LOCAL"
      },
      {
        "device_id": 1,
        "sensor_id": 1,
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 22.1,
        "unidad": "°C",
        "timestamp_captura": "2026-07-05T08:00:00Z",
        "access_key": "IOT-EST01-HLA-001",
        "origen": "BUFFER_LOCAL"
      }
    ]
  }'
```

Respuesta esperada `200`:
```json
{
  "total": 3,
  "aceptados": 2,
  "rechazados": 0,
  "duplicados": 1,
  "detalle": [
    {
      "sensor_id": 1,
      "timestamp_captura": "2026-07-05T08:00:00Z",
      "estado": "LECTURA_VALIDA",
      "id_telemetria": 4,
      "error": null
    },
    {
      "sensor_id": 1,
      "timestamp_captura": "2026-07-05T08:01:00Z",
      "estado": "LECTURA_VALIDA",
      "id_telemetria": 5,
      "error": null
    },
    {
      "sensor_id": 1,
      "timestamp_captura": "2026-07-05T08:00:00Z",
      "estado": "ERROR_DUPLICADO",
      "id_telemetria": null,
      "error": "Dato duplicado — marcado como CONFIRMADO en buffer"
    }
  ]
}
```

---

### FC.2 — Dato BUFFER_LOCAL con más de 72 horas → ERROR_TIEMPO (400 dentro del batch)

```bash
curl -X POST http://localhost:8000/iot/telemetria/batch \
  -H "Content-Type: application/json" \
  -d '{
    "registros": [
      {
        "device_id": 1,
        "sensor_id": 1,
        "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": 22.1,
        "unidad": "°C",
        "timestamp_captura": "2026-07-01T00:00:00Z",
        "access_key": "IOT-EST01-HLA-001",
        "origen": "BUFFER_LOCAL"
      }
    ]
  }'
```

Respuesta esperada `200` (el batch no aborta — registra el rechazo en detalle):
```json
{
  "total": 1,
  "aceptados": 0,
  "rechazados": 1,
  "duplicados": 0,
  "detalle": [
    {
      "sensor_id": 1,
      "timestamp_captura": "2026-07-01T00:00:00Z",
      "estado": "RECHAZADO",
      "id_telemetria": null,
      "error": "Dato de BUFFER_LOCAL con retraso superior a 72 horas. No se puede procesar."
    }
  ]
}
```

---

## Variables disponibles en catálogo I3P-1

| tipo_variable | unidades aceptadas | unidad_estandar | id_variable M09 |
|---|---|---|---|
| TEMPERATURA_AMBIENTAL | °C, °F, K | °C | 9 |
| HUMEDAD_RELATIVA | % | % | 10 |
| NH3 | ppm | ppm | 11 |
| CO2 | ppm | ppm | 12 |
| TEMPERATURA_CORPORAL | °C, °F, K | °C | 13 |
| FRECUENCIA_CARDIACA | bpm | bpm | 14 |
| FRECUENCIA_RESPIRATORIA | rpm | rpm | 15 |
| ACTIVIDAD | m/s², g | m/s² | 16 |
| PH | pH | pH | 2 |
| OXIGENO_DISUELTO | mg/L | mg/L | 3 |
| CONDUCTIVIDAD | µS/cm, mS/cm | µS/cm | 8 |
