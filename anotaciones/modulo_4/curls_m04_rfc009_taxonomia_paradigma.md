# CURLs — M04: RFC-009 (taxonomía por tipo de manejo y paradigma)

Base URL local: `http://localhost:8000`
Autenticación: `Authorization: Bearer <JWT>`
Resumen de la implementación y de lo que quedó fuera de alcance: `anotaciones/implementacion_rfc006_rfc009_rfc011.md`.

`tipo_modelo` pasa de 4 valores por tamaño a 6 por tipo de manejo. El paradigma no se envía: el
backend lo deriva y lo devuelve en `paradigma`.

| tipo_modelo | paradigma | Antes (renombrado por la migración) |
|---|---|---|
| `MODELO_AVES` | POBLACIONAL | `ESPECIES_PEQUEÑAS` |
| `MODELO_PORCINOS` | POBLACIONAL | (nuevo) |
| `MODELO_ACUICULTURA` | POBLACIONAL | (nuevo) |
| `MODELO_ESPECIES_MEDIANAS` | INDIVIDUAL | `ESPECIES_MEDIANAS` |
| `MODELO_ESPECIES_GRANDES` | INDIVIDUAL | `ESPECIES_GRANDES` |
| `MODELO_RIESGO_CONTAGIO` | META | `CONTAGIO` |

Componentes de un modelo POBLACIONAL: `DETECTOR`, `SEGUIMIENTO`, `METRICAS`, `ANOMALIAS`.

---

## RF-65 v2.0 — POST /prediccion/motor-ia

### POBLACIONAL: umbral de anomalía y versión activa por componente

`umbral_score_anomalia` (0–1, sin restricción de orden) es obligatorio. `umbral_riesgo_alto`,
`umbral_alerta_critica` e `id_version_modelo_activa` no aplican: si llegan, se descartan.

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "MODELO_AVES",
    "umbral_score_anomalia": 0.65,
    "versiones_activas_por_componente": {"DETECTOR": 31, "ANOMALIAS": 32},
    "ventana_temporal_min": 10,
    "modo_ejecucion": "SERVIDOR"
  }'
```

Respuesta `201`/`200` con `"paradigma": "POBLACIONAL"`, `"umbral_riesgo_alto": null`,
`"umbral_alerta_critica": null`, `"umbral_score_anomalia": "0.650"` y el mapa de versiones.

### INDIVIDUAL / META: igual que antes

`umbral_riesgo_alto` y `umbral_alerta_critica` son obligatorios (0.50–0.95, crítica ≥ riesgo).
`umbral_score_anomalia` y `versiones_activas_por_componente` se descartan.

```bash
curl -s -X POST http://localhost:8000/prediccion/motor-ia \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_modelo": "MODELO_ESPECIES_GRANDES",
    "umbral_riesgo_alto": 0.70,
    "umbral_alerta_critica": 0.85,
    "ventana_temporal_min": 10,
    "id_version_modelo_activa": 20
  }'
```

Errores posibles (nuevos o cambiados):
- `422` `TIPO_MODELO_INVALIDO` — incluye los 4 valores viejos (`ESPECIES_PEQUEÑAS`…)
- `422` `UMBRAL_SCORE_ANOMALIA_FUERA_RANGO` — POBLACIONAL sin `umbral_score_anomalia` o fuera de 0–1
- `422` `UMBRALES_REQUERIDOS` — INDIVIDUAL/META sin `umbral_riesgo_alto` o `umbral_alerta_critica`
- `422` `VERSION_MODELO_INCOMPATIBLE` — la versión vinculada es de otra llave (`tipo_modelo`, `componente`) (RF-65 4.e)
- `412` `MODELO_NO_ACTIVO` / `404` `VERSION_MODELO_NO_ENCONTRADA` — sin cambios, ahora también por componente
- `400` `VAL_ENTRADA` — clave de `versiones_activas_por_componente` que no es un componente

---

## RF-69 v2.0 — POST /prediccion/modelos (interno, RF-71)

### Registrar una versión de un componente POBLACIONAL

`componente` es obligatorio. Las métricas son las poblacionales (sin F1/recall):
`calibracion_completada` (bool), `tasa_falsos_positivos_rutina` y `tasa_deteccion_eventos_clinicos` (0–1).
Se aprueba si `calibracion_completada` es `true` (las tasas se registran sin umbral; ver supuestos).

```bash
curl -X POST "http://localhost:8000/prediccion/modelos" \
  -H "X-RF71-Internal-Key: <RF71_KEY>" \
  -F "tipo_modelo=MODELO_PORCINOS" \
  -F "componente=DETECTOR" \
  -F "hash_artefacto_sha256=$HASH" \
  -F "dataset_entrenamiento_hash=a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4" \
  -F 'metricas_validacion={"calibracion_completada":true,"tasa_falsos_positivos_rutina":0.04,"tasa_deteccion_eventos_clinicos":0.91}' \
  -F "fecha_entrenamiento=2026-10-01T08:00:00Z" \
  -F 'compatibilidad_variables=[]' \
  -F "id_proceso_rf71=550e8400-e29b-41d4-a716-446655440000" \
  -F "archivo_modelo=@/tmp/modelo_prueba.onnx"
```

Respuesta `201` con `"paradigma": "POBLACIONAL"`, `"componente": "DETECTOR"`, `"metricas_poblacionales"`
y `nombre_version` con el formato `PORCINOS_DETECTOR_aammdd_<proceso>`. El nombre ya no lleva el prefijo
`MODELO_` y la fecha va en `aammdd` porque `nombre_version` es `varchar(40)`.

Errores posibles (nuevos):
- `422` `COMPONENTE_INVALIDO` — POBLACIONAL sin `componente` o con uno fuera del catálogo
- `422` `METRICAS_INCOMPLETAS` / `METRICA_INVALIDA` / `METRICA_FUERA_DE_RANGO` — sobre las métricas poblacionales

Para INDIVIDUAL/META el flujo y las métricas (F1/recall) no cambian; `componente` se ignora.

---

## RF-69 R5 v2.0 — POST /prediccion/modelos/{id}/activar

La unicidad de la versión ACTIVO pasa a ser por (`tipo_modelo`, `componente`): activar el DETECTOR de
`MODELO_PORCINOS` solo deprecia el DETECTOR activo anterior, no el SEGUIMIENTO. La BD lo garantiza
con el índice único parcial `uq_version_modelo_activa_tipo_componente`.

```bash
curl -X POST http://localhost:8000/prediccion/modelos/31/activar \
  -H "Authorization: Bearer $TOKEN"
```

---

## RF-70 v2.0 — GET /prediccion/despliegues y GET /prediccion/modelos/{id}/ota-status

Cada despliegue trae `paradigma` y `componente` (null para INDIVIDUAL/META).

---

## RF-73 v2.0 — campos mínimos de auditoría por paradigma

`VERSION_APROBADA` y `VERSION_RECHAZADA` exigen `tipo_modelo`, `id_version` y:
- INDIVIDUAL/META: `f1_score_global`, `recall_clase_riesgo_alto`
- POBLACIONAL: `calibracion_completada`, `tasa_falsos_positivos_rutina`, `tasa_deteccion_eventos_clinicos`

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria?tipo_evento=VERSION_APROBADA" \
  -H "Authorization: Bearer $TOKEN"
```
