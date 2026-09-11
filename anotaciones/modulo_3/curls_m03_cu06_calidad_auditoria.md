# CURLs — M03 CU06: Calidad de telemetría y auditoría IoT (RF-62, RF-63)

## Endpoints

| Método | Ruta | Auth | RF |
|--------|------|------|----|
| GET | `/iot/calidad` | JWT + RBAC(38, R) — todos los roles | RF-62 |
| GET | `/iot/calidad/{id_telemetria}` | JWT + RBAC(38, R) | RF-62 |
| POST | `/iot/calidad/{id_telemetria}/evaluar` | JWT + RBAC(38, E) — admin + ing | RF-62 |
| POST | `/iot/calidad/reevaluar` | JWT + RBAC(38, E) — admin + ing | RF-62 FA-08 |
| GET | `/iot/auditoria` | JWT + RBAC(39, R) — admin + ing + cont | RF-63 |
| GET | `/iot/auditoria/{id_evento}` | JWT + RBAC(39, R) | RF-63 |
| GET | `/iot/auditoria/exportar` | JWT + RBAC(39, E) — admin + cont | RF-63 |
| POST | `/iot/auditoria/verificar-integridad` | JWT + RBAC(39, E) — admin + cont | RF-63 FA-11 |

---

## GET /iot/calidad — Listar evaluaciones de calidad (RF-62)

### Flujo principal — listar todas las evaluaciones

```bash
curl -s -X GET "http://localhost:8000/iot/calidad?pagina=1&por_pagina=20" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "total": 5,
  "pagina": 1,
  "por_pagina": 20,
  "items": [
    {
      "id_evaluacion": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "id_telemetria": 42,
      "id_sensor": 3,
      "timestamp_evaluacion": "2026-07-07T10:00:00Z",
      "indice_calidad": 85,
      "clasificacion_calidad": "APTO",
      "apto_para_ia": true,
      "apto_para_nic41": true,
      "flags_detectados": {},
      "version_limites_fisicos_aplicada": "1.0",
      "parametros_aplicados": {"k": 3.0, "M": 5, "N": 20},
      "parametros_calibracion_aplicados": null,
      "estado_evaluacion": "VIGENTE",
      "motivo_reevaluacion": null,
      "id_evaluacion_superada": null,
      "version_evaluacion": "1.0",
      "fecha_creacion": "2026-07-07T10:00:00Z"
    }
  ]
}
```

### Con filtros — solo lecturas no aptas de un sensor

```bash
curl -s -X GET "http://localhost:8000/iot/calidad?id_sensor=3&clasificacion=NO_APTO&pagina=1&por_pagina=50" \
  -H "Authorization: Bearer $TOKEN"
```

### Error — sin autenticación

```bash
curl -s -X GET "http://localhost:8000/iot/calidad" 
```

**Respuesta (401):**
```json
{"code": "TOKEN_AUSENTE", "message": "No se proporcionó token de autenticación.", "field": null}
```

---

## GET /iot/calidad/{id_telemetria} — Obtener calidad de una lectura (RF-62)

### Flujo principal — lectura existente con evaluación

```bash
curl -s -X GET "http://localhost:8000/iot/calidad/42" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "id_evaluacion": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "id_telemetria": 42,
  "id_sensor": 3,
  "timestamp_evaluacion": "2026-07-07T10:00:00Z",
  "indice_calidad": 65,
  "clasificacion_calidad": "APTO_CON_RESERVA",
  "apto_para_ia": false,
  "apto_para_nic41": true,
  "flags_detectados": {"outlier_estadistico": true},
  "version_limites_fisicos_aplicada": "1.0",
  "parametros_aplicados": {"k": 3.0, "M": 5, "N": 20},
  "parametros_calibracion_aplicados": null,
  "estado_evaluacion": "VIGENTE",
  "motivo_reevaluacion": null,
  "id_evaluacion_superada": null,
  "version_evaluacion": "1.0",
  "fecha_creacion": "2026-07-07T10:00:00Z"
}
```

### Error — lectura sin evaluación registrada (FA-06)

```bash
curl -s -X GET "http://localhost:8000/iot/calidad/9999" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (404):**
```json
{"code": "CALIDAD_NO_ENCONTRADA", "message": "Evaluación de calidad no encontrada.", "field": null}
```

---

## POST /iot/calidad/{id_telemetria}/evaluar — Disparar evaluación puntual (RF-62)

### Flujo principal — forzar re-evaluación de una lectura existente

```bash
curl -s -X POST "http://localhost:8000/iot/calidad/42/evaluar" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (201):**
```json
{
  "id_evaluacion": "4ba85f64-5717-4562-b3fc-2c963f66afa7",
  "id_telemetria": 42,
  "id_sensor": 3,
  "timestamp_evaluacion": "2026-07-07T10:05:00Z",
  "indice_calidad": 100,
  "clasificacion_calidad": "APTO",
  "apto_para_ia": true,
  "apto_para_nic41": true,
  "flags_detectados": {},
  "version_limites_fisicos_aplicada": "1.0",
  "parametros_aplicados": {"k": 3.0, "M": 5, "N": 20},
  "parametros_calibracion_aplicados": null,
  "estado_evaluacion": "VIGENTE",
  "motivo_reevaluacion": null,
  "id_evaluacion_superada": null,
  "version_evaluacion": "1.0",
  "fecha_creacion": "2026-07-07T10:05:00Z"
}
```

### Error — telemetría no encontrada (FA-01 / 404)

```bash
curl -s -X POST "http://localhost:8000/iot/calidad/9999/evaluar" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (404):**
```json
{"code": "TELEMETRIA_NO_ENCONTRADA", "message": "Lectura telemétrica no encontrada.", "field": null}
```

### Error — sin permiso de ejecución (403)

Solo admin (rol 1) e ing (rol 4) tienen acción E sobre recurso 38.

---

## POST /iot/calidad/reevaluar — Re-evaluación explícita ante error de configuración (RF-62 FA-08)

### Flujo principal — corrección de parámetros con causa documentada

```bash
curl -s -X POST "http://localhost:8000/iot/calidad/reevaluar" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id_sensor": 3,
    "fecha_desde": "2026-07-06T00:00:00Z",
    "fecha_hasta": "2026-07-07T00:00:00Z",
    "causa_documentada": "Parámetros de calibración incorrectos por error de configuración inicial del sensor 3",
    "parametros_correctos": {"k": 2.5, "M": 5, "N": 20}
  }'
```

**Respuesta esperada (200):**
```json
{
  "evaluaciones_superadas": 12,
  "evaluaciones_creadas": 12
}
```

### Error — sin causa documentada (CA-17 → 422)

```bash
curl -s -X POST "http://localhost:8000/iot/calidad/reevaluar" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id_sensor": 3,
    "fecha_desde": "2026-07-06T00:00:00Z",
    "fecha_hasta": "2026-07-07T00:00:00Z",
    "causa_documentada": ""
  }'
```

**Respuesta (422):**
```json
{"code": "CAUSA_REEVALUACION_REQUERIDA", "message": "La causa documentada es obligatoria para re-evaluar.", "field": null}
```

### Error — sin causa en DTO (validación Pydantic → 422)

```bash
curl -s -X POST "http://localhost:8000/iot/calidad/reevaluar" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id_sensor": 3,
    "fecha_desde": "2026-07-06T00:00:00Z",
    "fecha_hasta": "2026-07-07T00:00:00Z"
  }'
```

**Respuesta (422):** error de validación Pydantic por campo requerido `causa_documentada`.

---

## GET /iot/auditoria — Listar bitácora de auditoría IoT (RF-63)

### Flujo principal — listar todos los eventos

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria?pagina=1&por_pagina=50" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "total": 23,
  "pagina": 1,
  "por_pagina": 50,
  "items": [
    {
      "id_evento": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
      "id_usuario": null,
      "nombre_usuario": null,
      "tipo_evento": "TELEMETRIA_RECIBIDA",
      "modulo": "M03",
      "descripcion": "Lectura id=42 sensor=3 variable=1",
      "resultado": "EXITOSO",
      "direccion_ip": null,
      "user_agent": null,
      "id_sesion": null,
      "fecha_hora": "2026-07-07T10:00:00Z",
      "accion_detallada": {"id_telemetria": 42, "valor_crudo": "25.3"},
      "entidad_afectada_tipo": "TELEMETRIA",
      "entidad_afectada_id": "42",
      "severidad_log": "INFO",
      "hash_integridad": "a3f5c...",
      "clasificacion_registro": "NIC41",
      "retencion_aplicable": 5,
      "registro_incompleto": false,
      "timestamp_registro": "2026-07-07T10:00:00.123Z"
    }
  ]
}
```

### Con filtros — solo eventos críticos en rango de fechas

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria?severidad_log=CRITICO&fecha_desde=2026-07-07T00:00:00Z&fecha_hasta=2026-07-07T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

### Con filtros — eventos de una entidad específica

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria?entidad_afectada_id=42&tipo_evento=EVALUACION_CALIDAD_COMPLETADA" \
  -H "Authorization: Bearer $TOKEN"
```

---

## GET /iot/auditoria/{id_evento} — Detalle de evento de auditoría (RF-63)

### Flujo principal

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria/5fa85f64-5717-4562-b3fc-2c963f66afa8" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):** mismo schema que un ítem en la lista.

### Error — evento no encontrado (404)

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria/00000000-0000-0000-0000-000000000000" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (404):**
```json
{"code": "EVENTO_AUDITORIA_NO_ENCONTRADO", "message": "Evento de auditoría no encontrado.", "field": null}
```

---

## GET /iot/auditoria/exportar — Exportar bitácora (RF-63)

### Exportar en JSON

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria/exportar?formato=json" \
  -H "Authorization: Bearer $TOKEN" \
  -o auditoria_iot.json
```

### Exportar en CSV con filtro de fechas

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria/exportar?formato=csv&fecha_desde=2026-07-01T00:00:00Z&fecha_hasta=2026-07-07T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN" \
  -o auditoria_iot.csv
```

**Respuesta:** archivo `auditoria_iot.json` o `auditoria_iot.csv` descargado. Cabecera `Content-Disposition: attachment`.

### Error — formato inválido (422)

```bash
curl -s -X GET "http://localhost:8000/iot/auditoria/exportar?formato=xml" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (422):** error de validación Pydantic (patrón `^(json|csv)$` no coincide).

---

## POST /iot/auditoria/verificar-integridad — Verificar hashes SHA-256 (RF-63 FA-11)

### Flujo principal — todos los registros íntegros

```bash
curl -s -X POST "http://localhost:8000/iot/auditoria/verificar-integridad" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta esperada (200):**
```json
{
  "total_verificados": 23,
  "comprometidos": 0,
  "ids_comprometidos": []
}
```

### Con rango de fechas

```bash
curl -s -X POST "http://localhost:8000/iot/auditoria/verificar-integridad?fecha_desde=2026-07-01T00:00:00Z&fecha_hasta=2026-07-07T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

### Registros comprometidos detectados (FA-11)

Si algún hash no coincide, el endpoint devuelve la lista de IDs y registra automáticamente un evento de auditoría CRITICO de tipo `INTEGRIDAD_COMPROMETIDA` (append-only):

```json
{
  "total_verificados": 23,
  "comprometidos": 2,
  "ids_comprometidos": [
    "5fa85f64-5717-4562-b3fc-2c963f66afa8",
    "6ab12c34-5717-4562-b3fc-2c963f66afa9"
  ]
}
```
