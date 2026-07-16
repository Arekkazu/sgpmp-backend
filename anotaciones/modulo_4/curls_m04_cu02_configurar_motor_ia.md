# CU-02 RF-65 — CURLs Configurar Motor de Inferencia IA

Base URL local: `http://localhost:8000`  
Autenticación: `Authorization: Bearer <JWT>`  
Roles autorizados para escribir: Administrador (id_rol=1), Veterinario (id_rol=3)  
Roles autorizados para leer: Administrador, Veterinario, Ingeniero (id_rol=4)

RBAC: recurso `configuracion_motor_ia` (id_recurso=41)

---

## POST /prediccion/motor-ia — Crear o actualizar configuración

**RBAC**: C sobre recurso 41  
**Respuesta exitosa**: 201 (primera vez) / 200 (actualización)  
**FA**: FA-01 a FA-08

### Flujo 1 — Crear configuración nueva (201)

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "ESPECIES_PEQUEÑAS",
    "umbral_riesgo_alto": 0.70,
    "umbral_alerta_critica": 0.85,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.500,
    "w_factor_ambiental": 0.300,
    "w_factor_densidad": 0.200
  }' | python3 -m json.tool
```

**Respuesta esperada (201)**:
```json
{
  "id_configuracion_motor": 1,
  "tipo_modelo": "ESPECIES_PEQUEÑAS",
  "umbral_riesgo_alto": "0.700",
  "umbral_alerta_critica": "0.850",
  "ventana_temporal_min": 10,
  "modo_ejecucion": "SERVIDOR",
  "id_version_modelo_activa": null,
  "config_version": 1,
  "w_factor_sanitario": "0.500",
  "w_factor_ambiental": "0.300",
  "w_factor_densidad": "0.200",
  "temp_min_config": null,
  "temp_max_config": null,
  "hr_min_config": null,
  "hr_max_config": null,
  "densidad_maxima_config": null,
  "es_activa": true,
  "id_usuario_responsable": 1,
  "fecha_creacion": "2026-07-11T00:00:00Z"
}
```

### Flujo 2 — Actualizar configuración existente (200)

Mismo endpoint y payload, config_version pasa a 2.

**Respuesta esperada (200)**:
```json
{
  "id_configuracion_motor": 1,
  "config_version": 2,
  ...
}
```

### Flujo 3 — Con rangos ambientales y versión de modelo

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "ESPECIES_MEDIANAS",
    "umbral_riesgo_alto": 0.65,
    "umbral_alerta_critica": 0.80,
    "ventana_temporal_min": 12,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.400,
    "w_factor_ambiental": 0.350,
    "w_factor_densidad": 0.250,
    "id_version_modelo_activa": 3,
    "temp_min_config": 18.0,
    "temp_max_config": 32.0,
    "hr_min_config": 40.0,
    "hr_max_config": 85.0
  }' | python3 -m json.tool
```

---

## FA-01 — Umbral fuera de rango (422)

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "ESPECIES_PEQUEÑAS",
    "umbral_riesgo_alto": 0.30,
    "umbral_alerta_critica": 0.80,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.500,
    "w_factor_ambiental": 0.300,
    "w_factor_densidad": 0.200
  }' | python3 -m json.tool
```

**Respuesta esperada (422)**:
```json
{
  "code": "UMBRAL_RIESGO_FUERA_RANGO",
  "message": "umbral_riesgo_alto debe estar entre 0.50 y 0.95.",
  "field": "umbral_riesgo_alto"
}
```

---

## FA-02 — Umbral crítica < umbral riesgo (422)

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "ESPECIES_PEQUEÑAS",
    "umbral_riesgo_alto": 0.80,
    "umbral_alerta_critica": 0.70,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.500,
    "w_factor_ambiental": 0.300,
    "w_factor_densidad": 0.200
  }' | python3 -m json.tool
```

**Respuesta esperada (422)**:
```json
{
  "code": "UMBRAL_CRITICA_MENOR_QUE_RIESGO",
  "message": "umbral_alerta_critica debe ser mayor o igual a umbral_riesgo_alto.",
  "field": "umbral_alerta_critica"
}
```

---

## FA-03 — Modelo no activo (412)

```bash
# Asumiendo que la versión 5 existe pero está en estado APROBADO (no ACTIVO)
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "ESPECIES_GRANDES",
    "umbral_riesgo_alto": 0.70,
    "umbral_alerta_critica": 0.85,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.500,
    "w_factor_ambiental": 0.300,
    "w_factor_densidad": 0.200,
    "id_version_modelo_activa": 5
  }' | python3 -m json.tool
```

**Respuesta esperada (412)**:
```json
{
  "code": "MODELO_NO_ACTIVO",
  "message": "La versión 5 está en estado 'APROBADO'. Solo se pueden vincular modelos en estado ACTIVO.",
  "field": "id_version_modelo_activa"
}
```

---

## FA-03 — Versión de modelo no existe (404)

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "CONTAGIO",
    "umbral_riesgo_alto": 0.70,
    "umbral_alerta_critica": 0.85,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.500,
    "w_factor_ambiental": 0.300,
    "w_factor_densidad": 0.200,
    "id_version_modelo_activa": 9999
  }' | python3 -m json.tool
```

**Respuesta esperada (404)**:
```json
{
  "code": "VERSION_MODELO_NO_ENCONTRADA",
  "message": "No existe la versión de modelo con id 9999.",
  "field": "id_version_modelo_activa"
}
```

---

## Pesos de contagio inválidos (422)

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "CONTAGIO",
    "umbral_riesgo_alto": 0.70,
    "umbral_alerta_critica": 0.85,
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR",
    "w_factor_sanitario": 0.500,
    "w_factor_ambiental": 0.400,
    "w_factor_densidad": 0.200
  }' | python3 -m json.tool
```

**Respuesta esperada (422)**:
```json
{
  "code": "PESOS_CONTAGIO_INVALIDOS",
  "message": "La suma de w_factor_sanitario + w_factor_ambiental + w_factor_densidad debe ser 1.0.",
  "field": "w_factor_sanitario"
}
```

---

## GET /prediccion/motor-ia — Listar configuraciones

**RBAC**: R sobre recurso 41

```bash
curl -s -X GET http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Respuesta esperada (200)**:
```json
{
  "total": 2,
  "items": [
    {
      "id_configuracion_motor": 1,
      "tipo_modelo": "ESPECIES_MEDIANAS",
      "config_version": 1,
      ...
    },
    {
      "id_configuracion_motor": 2,
      "tipo_modelo": "ESPECIES_PEQUEÑAS",
      "config_version": 3,
      ...
    }
  ]
}
```

---

## GET /prediccion/motor-ia/{tipo_modelo} — Obtener configuración por tipo

**RBAC**: R sobre recurso 41

```bash
curl -s -X GET http://localhost:8000/prediccion/motor-ia/ESPECIES_PEQUEÑAS \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Respuesta esperada (200)**:
```json
{
  "id_configuracion_motor": 1,
  "tipo_modelo": "ESPECIES_PEQUEÑAS",
  "umbral_riesgo_alto": "0.700",
  "umbral_alerta_critica": "0.850",
  "ventana_temporal_min": 10,
  "modo_ejecucion": "SERVIDOR",
  "config_version": 1,
  ...
}
```

**Error — tipo no encontrado (404)**:
```bash
curl -s -X GET http://localhost:8000/prediccion/motor-ia/TIPO_INEXISTENTE \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
```json
{
  "code": "CONFIGURACION_MOTOR_NO_ENCONTRADA",
  "message": "No existe configuración para el tipo de modelo 'TIPO_INEXISTENTE'.",
  "field": null
}
```
