# CURLs — M04 CU-05: Validar y Versionar Modelos de IA (RF-69)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa (rol Veterinario o Administrador).
Reemplazar `<RF71_KEY>` por el valor de la variable de entorno `RF71_INTERNAL_KEY`.

---

## Flujo principal — Registro automático desde RF-71

### POST /prediccion/modelos

Endpoint interno invocado exclusivamente por el proceso de reentrenamiento RF-71.
Acepta `multipart/form-data`. El archivo ONNX de prueba puede ser cualquier binario válido.

```bash
# Generar un archivo ONNX mínimo de prueba (protobuf con byte inicial 0x08)
printf '\x08\x04' > /tmp/modelo_prueba.onnx

# Calcular su SHA-256
HASH=$(sha256sum /tmp/modelo_prueba.onnx | awk '{print $1}')
echo "Hash: $HASH"

curl -X POST "http://localhost:8000/prediccion/modelos" \
  -H "X-RF71-Internal-Key: <RF71_KEY>" \
  -F "tipo_modelo=ESPECIES_PEQUEÑAS" \
  -F "hash_artefacto_sha256=$HASH" \
  -F "dataset_entrenamiento_hash=a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4" \
  -F 'metricas_validacion={"f1_score_global":0.85,"recall_clase_riesgo_alto":0.88,"precision_global":0.82,"accuracy":0.90,"roc_auc_score":0.91,"recall_por_clase":{"0":0.95,"1":0.88},"matriz_confusion":[[90,10],[12,88]]}' \
  -F "fecha_entrenamiento=2026-07-12T08:00:00Z" \
  -F 'compatibilidad_variables=[]' \
  -F "id_proceso_rf71=550e8400-e29b-41d4-a716-446655440000" \
  -F "archivo_modelo=@/tmp/modelo_prueba.onnx"
```

Respuesta esperada `201` (métricas ≥ umbrales → APROBADO):
```json
{
  "id_version_modelo": 1,
  "nombre_version": "ESPECIES_PEQUEÑAS_20260712_550e8400",
  "tipo_modelo": "ESPECIES_PEQUEÑAS",
  "estado_version": "APROBADO",
  "formato_artefacto": "ONNX",
  "tamanio_artefacto_bytes": 2,
  "hash_artefacto_sha256": "<HASH>",
  "dataset_entrenamiento_hash": "a3b4...",
  "id_proceso_rf71": "550e8400-e29b-41d4-a716-446655440000",
  "f1_score": "0.850000",
  "recall_clase_riesgo_alto": "0.880000",
  "precision_modelo": "0.820000",
  "accuracy": "0.900000",
  "roc_auc_score": "0.910000",
  "detalle_validacion": null,
  "notas_validacion": null,
  "esta_produccion": false,
  "fecha_entrenamiento": "2026-07-12T08:00:00+00:00",
  "fecha_registro": "2026-07-12T10:30:00+00:00",
  "fecha_despliegue": null
}
```

Respuesta esperada `201` (métricas < umbrales → RECHAZADO):
```json
{
  "id_version_modelo": 2,
  "estado_version": "RECHAZADO",
  "detalle_validacion": "f1_score_global=0.75 < umbral requerido 0.80"
}
```

Errores posibles:
| HTTP | code | FA |
|------|------|----|
| 403 | REGISTRO_INTERNO_REQUERIDO | FA-02: X-RF71-Internal-Key ausente o incorrecta |
| 422 | ARTEFACTO_SUPERA_TAMANO_MAXIMO | FA-03: archivo > 500 MB |
| 422 | FORMATO_ARTEFACTO_INVALIDO | FA-01: no es ONNX ni TF SavedModel |
| 422 | HASH_SHA256_INVALIDO | FA-04: hash no tiene 64 hex chars |
| 422 | HASH_ARTEFACTO_NO_COINCIDE | FA-05: hash recalculado ≠ hash declarado |
| 422 | METRICAS_INCOMPLETAS | FA-04: faltan campos en metricas_validacion |
| 422 | METRICA_FUERA_DE_RANGO | FA-04: valor de métrica fuera de [0.0, 1.0] |
| 422 | TIPO_MODELO_INVALIDO | tipo_modelo no es uno de los valores válidos |

---

## Flujo — Consultar versiones

### GET /prediccion/modelos

```bash
# Listar todas las versiones
curl -X GET "http://localhost:8000/prediccion/modelos" \
  -H "Authorization: Bearer <TOKEN>"

# Filtrar por tipo_modelo y estado
curl -X GET "http://localhost:8000/prediccion/modelos?tipo_modelo=ESPECIES_PEQUEÑAS&estado=APROBADO" \
  -H "Authorization: Bearer <TOKEN>"

# Paginación
curl -X GET "http://localhost:8000/prediccion/modelos?limit=10&offset=0" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 3,
  "items": [
    {
      "id_version_modelo": 1,
      "nombre_version": "ESPECIES_PEQUEÑAS_20260712_550e8400",
      "tipo_modelo": "ESPECIES_PEQUEÑAS",
      "estado_version": "APROBADO",
      "f1_score": "0.850000",
      "fecha_registro": "2026-07-12T10:30:00+00:00"
    }
  ]
}
```

Errores posibles:
| HTTP | code | FA |
|------|------|----|
| 401 | - | JWT ausente o inválido |
| 403 | - | Rol sin permiso R(2) sobre recurso 43 |

---

### GET /prediccion/modelos/{id_version}

```bash
curl -X GET "http://localhost:8000/prediccion/modelos/1" \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
| HTTP | code | FA |
|------|------|----|
| 404 | VERSION_MODELO_NO_ENCONTRADA | id no existe |

---

## Flujo — Revisión clínica (Fase 4)

### PATCH /prediccion/modelos/{id_version}/notas

```bash
curl -X PATCH "http://localhost:8000/prediccion/modelos/1/notas" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"notas_validacion": "Modelo evaluado clínicamente. Las métricas de recall son adecuadas para detección temprana de leptospirosis en bovinos pequeños. Se aprueba para activación."}'
```

Respuesta esperada `200`:
```json
{
  "id_version_modelo": 1,
  "estado_version": "APROBADO",
  "notas_validacion": "Modelo evaluado clínicamente...",
  "fecha_registro": "2026-07-12T10:30:00+00:00"
}
```

Errores posibles:
| HTTP | code | FA |
|------|------|----|
| 404 | VERSION_MODELO_NO_ENCONTRADA | id no existe |
| 422 | NOTAS_VACIAS | notas_validacion vacío o solo espacios |

---

## Flujo — Activación (Fase 5)

### POST /prediccion/modelos/{id_version}/activar

Requiere que la versión esté en estado APROBADO y tenga notas_validacion registradas.
Si existe una versión ACTIVO del mismo tipo_modelo, pasa automáticamente a DEPRECADO (transacción atómica).

```bash
curl -X POST "http://localhost:8000/prediccion/modelos/1/activar" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_version_modelo": 1,
  "nombre_version": "ESPECIES_PEQUEÑAS_20260712_550e8400",
  "tipo_modelo": "ESPECIES_PEQUEÑAS",
  "estado_version": "ACTIVO",
  "esta_produccion": true,
  "fecha_despliegue": "2026-07-12T11:00:00+00:00"
}
```

Errores posibles:
| HTTP | code | FA |
|------|------|----|
| 404 | VERSION_MODELO_NO_ENCONTRADA | id no existe |
| 422 | VERSION_NO_APROBADA | estado ≠ APROBADO (FA-07) |
| 422 | TRANSICION_ESTADO_INVALIDA | intento sobre DEPRECADO o RECHAZADO (FA-08) |
| 422 | NOTAS_VALIDACION_REQUERIDAS | notas_validacion vacías (CA-13) |
| 500 | - | fallo de persistencia → rollback completo (FA-10) |
