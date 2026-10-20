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
    "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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
  "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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
    "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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
    "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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
    "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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
    "tipo_modelo": "MODELO_ESPECIES_GRANDES",
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
    "tipo_modelo": "MODELO_RIESGO_CONTAGIO",
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
    "tipo_modelo": "MODELO_RIESGO_CONTAGIO",
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
      "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
      "config_version": 1,
      ...
    },
    {
      "id_configuracion_motor": 2,
      "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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
curl -s -X GET http://localhost:8000/prediccion/motor-ia/MODELO_ESPECIES_MEDIANAS \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Respuesta esperada (200)**:
```json
{
  "id_configuracion_motor": 1,
  "tipo_modelo": "MODELO_ESPECIES_MEDIANAS",
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

---

## DEV-09 — Sincronización con los nodos Edge (RF-65 E7/E8/E10)

Al guardar, la configuración se envía a los nodos Edge de su `tipo_modelo` por el
broker con `origen: "config_motor"` (BRK-05 de `BROKER-MQTT-SGPMP`:
`tipo_comando = CONFIG_MOTOR_IA`, confirmación `ACK_CONFIG_MOTOR` con el
`config_version` que quedó activo en el nodo). El resultado de cada nodo queda en
`modulo4.sincronizacion_nodos_edge` (una fila por nodo y `tipo_modelo`).

**Nodos de un `tipo_modelo`:** los Gateway Edge activos instalados en un área activa
con ese `tipo_modelo_asignado` (M09·RF-20), o que atienden un dispositivo activo de
esa área. `MODELO_RIESGO_CONTAGIO` no se asigna a áreas, así que no tiene nodos. La
búsqueda corre como el usuario de servicio, porque `modulo9` tiene RLS forzada y un
Veterinario no ve `dispositivos_iot`. Reemplaza a `NodoEdgeStubAdapter`, que siempre
respondía que había nodos: ahora **FA-08 `MODO_EDGE_SIN_NODOS`** (EDGE/HIBRIDO sin
nodos, 422) se decide con datos. En modo SERVIDOR la configuración también se envía a
los nodos que haya, para que sepan que la inferencia pasó al servidor.

Comando enviado a cada nodo:

```json
{
  "origen": "config_motor",
  "serial": "DISPOSITIVOCAMARONERA41",
  "tipo_modelo": "MODELO_ACUICULTURA",
  "config_version": 2,
  "configuracion": {"modo_ejecucion": "EDGE", "umbral_score_anomalia": "0.6", "...": "snapshot completo"}
}
```

| Respuesta del broker | `estado_sincronizacion` | HTTP del POST |
|---|---|---|
| APLICADA con el mismo `config_version` | `APLICADA` | 201 / 200 |
| APLICADA con otro `config_version` | `DESINCRONIZADO` | **409** (E10) |
| PENDIENTE (nodo desconectado) | `PENDIENTE` | **202** (E7) |
| NO_CONF (sin ACK, broker caído o error HTTP) | `FALLIDA` | **202** (E8) |
| Sin broker configurado en el ambiente | `PENDIENTE` | 202 |

Con varios nodos: si alguno quedó `DESINCRONIZADO` responde 409; si no, si alguno quedó
`PENDIENTE` o `FALLIDA` responde 202. **En todos los casos la configuración ya quedó
guardada**: el código solo informa si llegó a los nodos. Sin nodos responde 201/200.

### Nodo apagado (202) — criterio de aceptación

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{"tipo_modelo": "MODELO_ACUICULTURA", "modo_ejecucion": "EDGE", "ventana_temporal_min": 10, "umbral_score_anomalia": "0.6"}'
```

Respuesta `202`: la configuración guardada más el bloque `sincronizacion`:

```json
{
  "tipo_modelo": "MODELO_ACUICULTURA",
  "config_version": 1,
  "...": "resto de la configuración",
  "sincronizacion": {
    "estado": "PENDIENTE",
    "mensaje": "DISPOSITIVOCAMARONERA41: El dispositivo está desconectado; el comando no se publicó.",
    "nodos": [
      {
        "id_dispositivo_iot": 38,
        "serial": "DISPOSITIVOCAMARONERA41",
        "config_version_servidor": 1,
        "config_version_nodo": null,
        "estado_sincronizacion": "PENDIENTE",
        "intentos_sincronizacion": 1,
        "fecha_ultimo_intento": "2026-10-19T06:00:00Z",
        "fecha_aplicacion": null,
        "motivo_fallo": "El dispositivo está desconectado; el comando no se publicó."
      }
    ]
  }
}
```

### Nodo con otra versión (409, E10)

Mismo cuerpo, con `"estado_sincronizacion": "DESINCRONIZADO"`, `config_version_nodo`
distinto de `config_version_servidor` y
`motivo_fallo: "El nodo confirmó con config_version 1 y el servidor está en 3."`.

---

## GET /prediccion/motor-ia/{tipo_modelo}/sincronizacion — Estado por nodo

Mismo permiso que la consulta (R sobre el recurso 41).

```bash
curl -s http://localhost:8000/prediccion/motor-ia/MODELO_ACUICULTURA/sincronizacion \
  -H "Authorization: Bearer <TOKEN_VET>"
```

Respuesta `200`: el bloque `sincronizacion` de arriba con el último veredicto de cada
nodo. Si un nodo confirmó una versión anterior a la vigente, el `estado` consolidado
es `PENDIENTE`.

Errores: 401, 403, 404 `CONFIGURACION_MOTOR_NO_ENCONTRADA`.
