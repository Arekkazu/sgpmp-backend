# CURLs — M03 CU03: Generar y gestionar alertas de monitoreo (RF-57)

## Endpoints

| Método | Ruta | Auth | RF |
|--------|------|------|----|
| POST | `/iot/alertas` | Dispositivo IoT (`access_key`) | FA-01–FA-08 |
| GET | `/iot/alertas` | JWT + RBAC(32, R) | FA-09 |
| GET | `/iot/alertas/{id}` | JWT + RBAC(32, R) | FA-09 |
| PATCH | `/iot/alertas/{id}/estado` | JWT + RBAC(32, U) | FA-10 |

---

## POST /iot/alertas — Generar alerta nueva (FA-01–FA-08)

### Flujo principal — LECTURA_VALIDA con severidad CRITICO → alerta ACTIVA

```bash
curl -s -X POST http://localhost:8000/iot/alertas \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "access_key": "IOT-EST01-HLA-001",
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 42.5,
    "unidad": "C",
    "timestamp_evento": "2026-07-06T10:00:00Z",
    "estado_dato": "LECTURA_VALIDA",
    "severidad_edge": "CRITICO",
    "origen_evento": "EDGE",
    "reglas_activadas": ["UMBRAL_TEMP_MAX"],
    "id_evento_edge_computing": 31
  }'
```

**Respuesta esperada (201):**
```json
{
  "es_duplicado": false,
  "id_alerta": 1,
  "tipo_alerta": "ESTRES_TERMICO",
  "severidad": "CRITICO",
  "alerta_existente_id": null,
  "motivo_descarte": null
}
```

`fecha_vencimiento ≈ NOW() + 5 minutos` (SLA CRITICO — FA-05).

---

### FA-02/CA-4 — Segunda llamada con misma (sensor_id, tipo_variable) dentro de 30 min → duplicado

```bash
curl -s -X POST http://localhost:8000/iot/alertas \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "access_key": "IOT-EST01-HLA-001",
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 43.1,
    "unidad": "C",
    "timestamp_evento": "2026-07-06T10:05:00Z",
    "estado_dato": "LECTURA_VALIDA",
    "severidad_edge": "CRITICO",
    "origen_evento": "EDGE",
    "id_evento_edge_computing": 32
  }'
```

**Respuesta esperada (201):**
```json
{
  "es_duplicado": true,
  "id_alerta": 1,
  "tipo_alerta": "ESTRES_TERMICO",
  "severidad": "CRITICO",
  "alerta_existente_id": 1,
  "motivo_descarte": null
}
```

---

### FA-01/E1 — estado_dato inválido → descarte sin alerta (CA-3)

```bash
curl -s -X POST http://localhost:8000/iot/alertas \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "access_key": "IOT-EST01-HLA-001",
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 99.9,
    "unidad": "C",
    "timestamp_evento": "2026-07-06T10:00:00Z",
    "estado_dato": "ERROR_CALIBRACION",
    "severidad_edge": "CRITICO",
    "origen_evento": "EDGE"
  }'
```

**Respuesta esperada (201):**
```json
{
  "es_duplicado": false,
  "id_alerta": null,
  "tipo_alerta": null,
  "severidad": null,
  "alerta_existente_id": null,
  "motivo_descarte": "estado_dato=ERROR_CALIBRACION no genera alerta operativa"
}
```

---

### E12 — Conflicto severidad Edge vs IA: compromiso (prob_ia < 0.85, CRITICO vs LEVE → MODERADO)

```bash
curl -s -X POST http://localhost:8000/iot/alertas \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 2,
    "access_key": "IOT-EST01-HLA-001",
    "tipo_variable": "NH3",
    "valor": 28.0,
    "unidad": "ppm",
    "timestamp_evento": "2026-07-06T11:00:00Z",
    "estado_dato": "LECTURA_VALIDA",
    "severidad_edge": "LEVE",
    "severidad_ia": "CRITICO",
    "probabilidad_ia": "0.72",
    "origen_evento": "IA",
    "id_paquete_inferencia": 5
  }'
```

**Respuesta esperada (201):**
```json
{
  "es_duplicado": false,
  "id_alerta": 2,
  "tipo_alerta": "SINDROME_RESPIRATORIO",
  "severidad": "MODERADO",
  "alerta_existente_id": null,
  "motivo_descarte": null
}
```

`conflicto_resolucion = "SEVERIDAD_COMPROMISO"` en la tabla `modulo3.alertas`.

---

### E13 — Conflicto de tipo Edge vs IA: IA prevalece (prob_ia >= 0.85)

```bash
curl -s -X POST http://localhost:8000/iot/alertas \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 2,
    "access_key": "IOT-EST01-HLA-001",
    "tipo_variable": "TEMPERATURA_CORPORAL",
    "valor": 41.2,
    "unidad": "C",
    "timestamp_evento": "2026-07-06T11:30:00Z",
    "estado_dato": "LECTURA_VALIDA",
    "severidad_edge": "MODERADO",
    "tipo_alerta_ia": "PREDICCION_PATOLOGIA",
    "severidad_ia": "CRITICO",
    "probabilidad_ia": "0.91",
    "origen_evento": "IA",
    "id_paquete_inferencia": 6
  }'
```

**Respuesta esperada (201):**
```json
{
  "es_duplicado": false,
  "id_alerta": 3,
  "tipo_alerta": "PREDICCION_PATOLOGIA",
  "severidad": "CRITICO",
  "alerta_existente_id": null,
  "motivo_descarte": null
}
```

---

### E3 — Credencial inválida → 401

```bash
curl -s -X POST http://localhost:8000/iot/alertas \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "sensor_id": 1,
    "access_key": "CLAVE-INVALIDA",
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 42.5,
    "unidad": "C",
    "timestamp_evento": "2026-07-06T10:00:00Z",
    "estado_dato": "LECTURA_VALIDA",
    "severidad_edge": "CRITICO",
    "origen_evento": "EDGE"
  }'
```

**Respuesta esperada (401):**
```json
{
  "code": "DISPOSITIVO_NO_AUTORIZADO",
  "message": "Credenciales de dispositivo inválidas o dispositivo inactivo."
}
```

---

## GET /iot/alertas — Listar alertas con filtros (FA-09)

### Listar alertas CRITICO activas

```bash
TOKEN="eyJ..."  # JWT del usuario con permiso R sobre recurso 32

curl -s "http://localhost:8000/iot/alertas?severidad=CRITICO&estado=ACTIVA&pagina=1&por_pagina=20" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "total": 2,
  "pagina": 1,
  "por_pagina": 20,
  "items": [
    {
      "id_alerta": 1,
      "tipo_alerta": "ESTRES_TERMICO",
      "severidad": "CRITICO",
      "estado_alerta": "ACTIVA",
      "origen_evento": "EDGE",
      "tipo_variable": "TEMPERATURA_AMBIENTAL",
      "valor": "42.5000",
      "unidad": "C",
      "fecha_evento": "2026-07-06T10:00:00Z",
      "fecha_generacion": "2026-07-06T10:00:01Z",
      "fecha_vencimiento": "2026-07-06T10:05:01Z",
      "frecuencia_evento": 2
    }
  ]
}
```

---

### Filtro por activo biológico y rango de fechas

```bash
curl -s "http://localhost:8000/iot/alertas?id_activo_biologico=12&fecha_desde=2026-07-06T00:00:00Z&fecha_hasta=2026-07-06T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Sin permiso → 403

```bash
curl -s "http://localhost:8000/iot/alertas" \
  -H "Authorization: Bearer $TOKEN_SIN_PERMISO"
```

**Respuesta esperada (403):**
```json
{
  "code": "PERMISO_DENEGADO",
  "message": "No tienes permiso para realizar esta acción."
}
```

---

## GET /iot/alertas/{id_alerta} — Detalle con historial (FA-09)

```bash
curl -s "http://localhost:8000/iot/alertas/1" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "id_alerta": 1,
  "tipo_alerta": "ESTRES_TERMICO",
  "severidad": "CRITICO",
  "estado_alerta": "ACTIVA",
  "historico_estados": [
    {
      "id_historico_estado_alerta": 1,
      "id_alerta": 1,
      "estado_anterior": "ACTIVA",
      "estado_nuevo": "ACTIVA",
      "fecha_cambio": "2026-07-06T10:00:01Z",
      "id_usuario": null,
      "motivo": null
    }
  ]
}
```

---

### Alerta inexistente → 404

```bash
curl -s "http://localhost:8000/iot/alertas/9999" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (404):**
```json
{
  "code": "ALERTA_NO_ENCONTRADA",
  "message": "Alerta 9999 no encontrada."
}
```

---

## PATCH /iot/alertas/{id_alerta}/estado — Actualizar estado (FA-10)

### ACTIVA → EN_ATENCION

```bash
curl -s -X PATCH "http://localhost:8000/iot/alertas/1/estado" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "nuevo_estado": "EN_ATENCION",
    "motivo": "Técnico asignado para revisión de temperatura en establo 1"
  }'
```

**Respuesta esperada (200):** alerta con `estado_alerta = "EN_ATENCION"` y `fecha_atencion` poblada.

---

### EN_ATENCION → RESUELTA

```bash
curl -s -X PATCH "http://localhost:8000/iot/alertas/1/estado" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "nuevo_estado": "RESUELTA",
    "motivo": "Ventilación activada, temperatura normalizada a 27°C"
  }'
```

**Respuesta esperada (200):** alerta con `estado_alerta = "RESUELTA"` y `fecha_resolucion` poblada.

---

### ACTIVA → DESCARTADA (falsa alarma)

```bash
curl -s -X PATCH "http://localhost:8000/iot/alertas/2/estado" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "nuevo_estado": "DESCARTADA",
    "motivo": "Falsa alarma, sensor recalibrado"
  }'
```

**Respuesta esperada (200):** alerta con `estado_alerta = "DESCARTADA"`.

---

### Transición inválida → 422 (E11)

```bash
curl -s -X PATCH "http://localhost:8000/iot/alertas/1/estado" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"nuevo_estado": "ACTIVA"}'
```

**Respuesta esperada (422):**
```json
{
  "code": "TRANSICION_INVALIDA",
  "message": "No se puede pasar de RESUELTA a ACTIVA."
}
```

---

## Notas

- `POST /iot/alertas` no usa JWT — la autenticación es por `access_key` (serial del dispositivo).
- Los endpoints GET y PATCH requieren JWT Bearer con permisos RBAC sobre `recurso=32` (alertas_operativas).
- La deduplicación opera en ventana de 30 minutos sobre `(id_sensor, tipo_variable)` con `estado IN (ACTIVA, EN_ATENCION)`.
- SLA: CRITICO→5 min, MODERADO→30 min, LEVE→2 h hasta `fecha_vencimiento`.
- CU02 llama automáticamente a `GenararAlertaUseCase` (internamente) cuando recibe una DESVIACION_SIMPLE o DESVIACION_COMPUESTA con severidad definida.
