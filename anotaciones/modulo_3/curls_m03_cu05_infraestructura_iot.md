# CURLs — M03 CU05: Gestionar infraestructura IoT y contexto productivo (RF-60, RF-61)

## Endpoints

| Método | Ruta | Auth | RF |
|--------|------|------|----|
| POST | `/iot/heartbeat` | Dispositivo IoT (`X-Device-API-Key`, `X-Device-Id`) | RF-60 |
| GET | `/iot/dispositivos/{id}/estado` | JWT + RBAC(35, R) | RF-60 |
| GET | `/iot/dispositivos/{id}/historial` | JWT + RBAC(35, R) | RF-60 |
| GET | `/iot/alertas-tecnicas` | JWT + RBAC(36, R) — solo admin + ing | RF-60 |
| PATCH | `/iot/alertas-tecnicas/{id}/estado` | JWT + RBAC(36, U) — solo admin + ing | RF-60 |
| GET | `/iot/vinculaciones` | JWT + RBAC(37, R) | RF-61 |
| GET | `/iot/vinculaciones/{id}` | JWT + RBAC(37, R) | RF-61 |
| PATCH | `/iot/vinculaciones/{id}/resolver` | JWT + RBAC(37, U) | RF-61-C |
| POST | `/iot/vinculaciones/{id}/corregir` | JWT + RBAC(37, U) | RF-61-C |

---

## POST /iot/heartbeat — Recibir heartbeat de dispositivo (RF-60)

### Flujo principal — heartbeat normal, batería OK

```bash
curl -s -X POST http://localhost:8000/iot/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Device-API-Key: IOT-EST01-HLA-001" \
  -H "X-Device-Id: 1" \
  -d '{
    "tipo_mensaje": "HEARTBEAT",
    "nivel_bateria_pct": 85.5,
    "calidad_senal_rssi": -75.0,
    "calidad_senal_snr": 8.5,
    "estado_local_buffer": "I",
    "datos_pendientes_buffer": 0,
    "version_firmware": "1.2.3",
    "coordenadas": {"lat": 4.711, "lon": -74.072},
    "fecha_registro": "2026-07-06T10:00:00Z",
    "reloj_sincronizado": true
  }'
```

**Respuesta esperada (200):**
```json
{
  "id_heartbeat": 1,
  "id_dispositivo_iot": 1,
  "tipo_mensaje": "HEARTBEAT",
  "nivel_bateria_pct": "85.50",
  "calidad_senal_rssi": "-75.00",
  "calidad_senal_snr": "8.50",
  "estado_local_buffer": "I",
  "datos_pendientes_buffer": 0,
  "version_firmware": "1.2.3",
  "coordenadas": {"lat": 4.711, "lon": -74.072},
  "fecha_registro": "2026-07-06T10:00:00Z",
  "fecha_recepcion": "2026-07-06T10:00:01.234Z",
  "reloj_sincronizado": true
}
```

**Efecto secundario:** Estado del dispositivo actualizado a ACTIVO en `estados_dispositivos_iot`. Transición registrada en `historico_transiciones_dispositivos` si cambia de estado.

### FA-01 — Batería baja (≤ 30%)

```bash
curl -s -X POST http://localhost:8000/iot/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Device-API-Key: IOT-EST01-HLA-001" \
  -H "X-Device-Id: 1" \
  -d '{
    "tipo_mensaje": "HEARTBEAT",
    "nivel_bateria_pct": 25.0,
    "fecha_registro": "2026-07-06T10:05:00Z",
    "reloj_sincronizado": true
  }'
```

**Efecto:** Genera alerta técnica `tipo_alerta=TECNICA`, `tipo_variable=BATERIA_BAJA`, `severidad=ALTA`.

### FA-02 — Buffer local activo (datos pendientes)

```bash
curl -s -X POST http://localhost:8000/iot/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Device-API-Key: IOT-EST01-HLA-001" \
  -H "X-Device-Id: 1" \
  -d '{
    "tipo_mensaje": "HEARTBEAT",
    "nivel_bateria_pct": 70.0,
    "estado_local_buffer": "A",
    "datos_pendientes_buffer": 150,
    "fecha_registro": "2026-07-06T10:10:00Z",
    "reloj_sincronizado": true
  }'
```

**Efecto:** Estado del dispositivo → `BUFFER_ACTIVO`.

### FA-03 — Credenciales inválidas

```bash
curl -s -X POST http://localhost:8000/iot/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Device-API-Key: CLAVE_INCORRECTA" \
  -H "X-Device-Id: 1" \
  -d '{"tipo_mensaje": "HEARTBEAT", "fecha_registro": "2026-07-06T10:00:00Z", "reloj_sincronizado": false}'
```

**Respuesta esperada (401):**
```json
{"code": "ERROR_AUTENTICACION_HEARTBEAT", "message": "Dispositivo no encontrado o credenciales inválidas.", "field": null}
```

---

## GET /iot/dispositivos/{id}/estado — Estado actual del dispositivo (RF-60)

```bash
JWT_TOKEN="<token_ingeniero_o_admin>"

curl -s -X GET "http://localhost:8000/iot/dispositivos/1/estado?limite_historial=20" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "estado": {
    "id_estado_dispositivo_iot": 1,
    "id_dispositivo_iot": 1,
    "estado_actual": "ACTIVO",
    "fecha_ultimo_contacto": "2026-07-06T10:00:01.234Z",
    "id_ultimo_heartbeat": 1,
    "tiempo_sin_contacto": 0,
    "causa_primaria": null,
    "causas_secundarias": null,
    "fecha_ultima_actualizacion": "2026-07-06T10:00:01.234Z"
  },
  "historial": [
    {
      "id_transaccion": 1,
      "id_dispositivo_iot": 1,
      "estado_anterior": "SIN_SEÑAL",
      "estado_nuevo": "ACTIVO",
      "causa_primaria": null,
      "notas": "Transición por recepción de heartbeat.",
      "fecha_transicion": "2026-07-06T10:00:01.234Z"
    }
  ]
}
```

### FA — Dispositivo sin estado registrado

**Respuesta esperada (404):**
```json
{"code": "ESTADO_DISPOSITIVO_NO_ENCONTRADO", "message": "No se encontró estado para el dispositivo 99.", "field": null}
```

### FA — Productor intenta ver estado sin permiso necesario

> Productores SÍ tienen permiso R sobre recurso 35 (`infraestructura_iot`). Devuelve 200.

---

## GET /iot/alertas-tecnicas — Alertas técnicas solo admin + ing (RF-60)

```bash
JWT_INGENIERO="<token_ingeniero>"

curl -s "http://localhost:8000/iot/alertas-tecnicas?estado=ACTIVA&pagina=1&por_pagina=20" \
  -H "Authorization: Bearer $JWT_INGENIERO"
```

**Respuesta esperada (200):**
```json
{
  "total": 1,
  "pagina": 1,
  "por_pagina": 20,
  "items": [
    {
      "id_alerta": 10,
      "tipo_alerta": "TECNICA",
      "severidad": "ALTA",
      "estado_alerta": "ACTIVA",
      "origen_evento": "HEARTBEAT",
      "tipo_variable": "BATERIA_BAJA",
      "fecha_evento": "2026-07-06T10:05:00Z",
      "fecha_generacion": "2026-07-06T10:05:01Z"
    }
  ]
}
```

### FA — Productor intenta acceder a alertas técnicas

```bash
JWT_PRODUCTOR="<token_productor>"

curl -s "http://localhost:8000/iot/alertas-tecnicas" \
  -H "Authorization: Bearer $JWT_PRODUCTOR"
```

**Respuesta esperada (403):**
```json
{"code": "PERMISO_INSUFICIENTE", "message": "...", "field": null}
```

---

## PATCH /iot/alertas-tecnicas/{id}/estado — Actualizar estado de alerta técnica

```bash
JWT_INGENIERO="<token_ingeniero>"

curl -s -X PATCH "http://localhost:8000/iot/alertas-tecnicas/10/estado" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_INGENIERO" \
  -d '{"nuevo_estado": "EN_ATENCION", "motivo": "Revisando batería del dispositivo 1."}'
```

**Respuesta esperada (200):** Objeto `AlertaSchema` con `estado_alerta=EN_ATENCION`.

---

## GET /iot/vinculaciones — Listar vinculaciones (RF-61)

```bash
JWT_TOKEN="<token_cualquier_rol>"

curl -s "http://localhost:8000/iot/vinculaciones?estado_vinculacion=SIN_VINCULAR&pagina=1&por_pagina=20" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "total": 3,
  "pagina": 1,
  "por_pagina": 20,
  "items": [
    {
      "id_vinculacion_lectura": 1,
      "id_telemetria": 100,
      "modelo_manejo": "INDIVIDUAL",
      "id_activo_biologico": null,
      "id_infraestructura": 5,
      "fecha_inicio_vinculacion": "2026-07-06T09:55:00Z",
      "mecanismo_vinculacion": "AUTOMATICA",
      "estado_vinculacion": "SIN_VINCULAR",
      "fecha_creacion": "2026-07-06T09:55:01Z"
    }
  ]
}
```

> Con stub M02 activo, todas las vinculaciones automáticas quedan en `SIN_VINCULAR`.

---

## PATCH /iot/vinculaciones/{id}/resolver — Resolver vinculación AMBIGUA (RF-61-C)

```bash
JWT_INGENIERO="<token_ingeniero>"

curl -s -X PATCH "http://localhost:8000/iot/vinculaciones/2/resolver" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_INGENIERO" \
  -d '{"id_activo_biologico": 15, "modelo_manejo": "INDIVIDUAL"}'
```

**Respuesta esperada (200):** Vinculación con `estado_vinculacion=VINCULADA`, `mecanismo_vinculacion=MANUAL`.

### FA — Intentar resolver vinculación que no es AMBIGUA

**Respuesta esperada (422):**
```json
{"code": "VINCULACION_NO_AMBIGUA", "message": "Solo se pueden resolver vinculaciones en estado AMBIGUA.", "field": null}
```

---

## POST /iot/vinculaciones/{id}/corregir — Corrección inmutable (RF-61-C)

```bash
JWT_INGENIERO="<token_ingeniero>"

curl -s -X POST "http://localhost:8000/iot/vinculaciones/1/corregir" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_INGENIERO" \
  -d '{
    "id_activo_biologico": 20,
    "modelo_manejo": "INDIVIDUAL",
    "motivo": "El activo fue reasignado a esta infraestructura después de la captura original."
  }'
```

**Respuesta esperada (201):** Nueva vinculación con `mecanismo_vinculacion=CORRECCION`, `estado_vinculacion=VINCULADA`, `id_vinculacion_reemplazada=1`.

**Efecto:** La vinculación original (id=1) queda con `estado_vinculacion=CORREGIDA`.

### FA — Intentar corregir vinculación ya corregida

**Respuesta esperada (422):**
```json
{"code": "VINCULACION_YA_CORREGIDA", "message": "La vinculación ya fue corregida previamente.", "field": null}
```
