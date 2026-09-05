# CURLs — M04 CU-06: Distribución OTA al Edge (RF-70)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa (rol Administrador o Ingeniero).

> Nota de split: Desarrollo solo expone endpoints de consulta (lectura). La tabla
> `modulo4.despliegues_ota` es escrita exclusivamente por el equipo IoT/IA.

---

## Flujo principal — consultar estado OTA de una versión de modelo

### GET /prediccion/modelos/{id_version}/ota-status

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/3/ota-status" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_version_modelo": 3,
  "total": 2,
  "despliegues": [
    {
      "id_despliegue_ota": 5,
      "id_version_modelo": 3,
      "id_dispositivo_iot": 12,
      "tipo_modelo": "ESPECIES_PEQUEÑAS",
      "modo_distribucion": "INMEDIATO",
      "estado_despliegue": "EXITOSO",
      "hash_modelo_sha256": "a3f8e2b1c4d7e9f0123456789abcdef0a1b2c3d4e5f6789012345678abcdef01",
      "resultado_validacion_hash": true,
      "id_version_modelo_anterior": 2,
      "rollback_ejecutado": false,
      "intentos_descarga": 1,
      "max_reintentos": 3,
      "tamano_modelo_bytes": 104857600,
      "tamano_descargado_bytes": 104857600,
      "duracion_proceso_ms": 45320,
      "ventana_inicio": "2026-07-12T02:00:00+00:00",
      "ventana_fin": "2026-07-12T04:00:00+00:00",
      "nivel_bateria_al_inicio": "0.8500",
      "fecha_inicio": "2026-07-12T02:15:00+00:00",
      "fecha_fin": "2026-07-12T02:16:00+00:00",
      "motivo_fallo": null
    },
    {
      "id_despliegue_ota": 6,
      "id_version_modelo": 3,
      "id_dispositivo_iot": 17,
      "tipo_modelo": "ESPECIES_PEQUEÑAS",
      "modo_distribucion": "PROGRAMADO",
      "estado_despliegue": "PENDIENTE",
      "hash_modelo_sha256": "a3f8e2b1c4d7e9f0123456789abcdef0a1b2c3d4e5f6789012345678abcdef01",
      "resultado_validacion_hash": null,
      "id_version_modelo_anterior": null,
      "rollback_ejecutado": false,
      "intentos_descarga": 0,
      "max_reintentos": 3,
      "tamano_modelo_bytes": 104857600,
      "tamano_descargado_bytes": null,
      "duracion_proceso_ms": null,
      "ventana_inicio": "2026-07-13T02:00:00+00:00",
      "ventana_fin": "2026-07-13T04:00:00+00:00",
      "nivel_bateria_al_inicio": null,
      "fecha_inicio": "2026-07-12T10:00:00+00:00",
      "fecha_fin": null,
      "motivo_fallo": null
    }
  ]
}
```

---

## Filtros opcionales en ota-status

### Filtrar por dispositivo específico

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/3/ota-status?id_dispositivo=12" \
  -H "Authorization: Bearer <TOKEN>"
```

### Filtrar por estado

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/3/ota-status?estado=PENDIENTE" \
  -H "Authorization: Bearer <TOKEN>"
```

Estados válidos: `EXITOSO`, `FALLIDO`, `PENDIENTE`, `SIN_CAMBIOS`, `EN_PROCESO`

---

## Listado general de despliegues con filtros

### GET /prediccion/despliegues

```bash
curl -X GET "http://localhost:8000/prediccion/despliegues" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 15,
  "items": [
    {
      "id_despliegue_ota": 6,
      "id_version_modelo": 3,
      "id_dispositivo_iot": 17,
      "estado_despliegue": "PENDIENTE",
      ...
    }
  ]
}
```

### Con filtros combinados

```bash
curl -X GET "http://localhost:8000/prediccion/despliegues?id_version=3&estado=FALLIDO&limit=10&offset=0" \
  -H "Authorization: Bearer <TOKEN>"
```

### Filtrar por dispositivo (historial de un nodo)

```bash
curl -X GET "http://localhost:8000/prediccion/despliegues?id_dispositivo=12&limit=20&offset=0" \
  -H "Authorization: Bearer <TOKEN>"
```

---

## FA-01 — Versión de modelo no encontrada

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/9999/ota-status" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `404`:
```json
{
  "code": "VERSION_NO_ENCONTRADA",
  "message": "La versión de modelo especificada no existe.",
  "field": null
}
```

---

## FA-02 — Estado inválido en filtro

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/3/ota-status?estado=INVALIDO" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `400`:
```json
{
  "code": "ESTADO_INVALIDO",
  "message": "El estado 'INVALIDO' no es válido. Valores permitidos: EN_PROCESO, EXITOSO, FALLIDO, PENDIENTE, SIN_CAMBIOS.",
  "field": "estado"
}
```

---

## FA-03 — Versión sin despliegues registrados

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/1/ota-status" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200` (lista vacía — IoT/IA no ha registrado despliegues aún):
```json
{
  "id_version_modelo": 1,
  "total": 0,
  "despliegues": []
}
```

---

## FA sin token / sin permiso

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/3/ota-status"
```

Respuesta `401`:
```json
{
  "code": "TOKEN_AUSENTE",
  "message": "Se requiere autenticación."
}
```

Con token de rol sin permiso (ej. Veterinario o Productor — recurso 44 no asignado a esos roles):
```json
{
  "code": "PERMISO_DENEGADO",
  "message": "No tienes permiso para realizar esta acción."
}
```
