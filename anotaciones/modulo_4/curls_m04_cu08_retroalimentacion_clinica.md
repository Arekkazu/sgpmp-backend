# CURLs — M04 CU-08: Registrar Retroalimentación Clínica (RF-72)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN_VET>` por el JWT de sesión activa con **rol Veterinario** (id_rol=3).

---

## Flujo principal — registrar retroalimentación INCORRECTO con diagnóstico

### POST /prediccion/retroalimentacion

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "550e8400-e29b-41d4-a716-446655440000",
    "id_activo_biologico": 1,
    "estado_retroalimentacion": "INCORRECTO",
    "diagnosticos_reales": [1, 2],
    "fuente_diagnostico": "LABORATORIO",
    "observaciones_clinicas": "El animal presentó signos de fiebre aftosa, no de la patología estimada."
  }'
```

Respuesta esperada `201`:
```json
{
  "id_retroalimentacion": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "id_resultado_inferencia": "550e8400-e29b-41d4-a716-446655440000",
  "id_activo_biologico": 1,
  "estado_retroalimentacion": "INCORRECTO",
  "diagnosticos_reales": [1, 2],
  "fuente_diagnostico": "LABORATORIO",
  "es_fuente_desconocida": false,
  "es_conflicto_retroalimentacion": false,
  "observaciones_clinicas": "El animal presentó signos de fiebre aftosa, no de la patología estimada.",
  "id_usuario_veterinario": 5,
  "fecha_retroalimentacion": "2026-07-12T14:30:00+00:00",
  "estado_registro": "ACTIVO"
}
```

---

## Flujo — retroalimentación CORRECTO (sin diagnóstico)

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "660e8400-e29b-41d4-a716-446655440001",
    "id_activo_biologico": 2,
    "estado_retroalimentacion": "CORRECTO"
  }'
```

Respuesta esperada `201` con `diagnosticos_reales: null` y `es_fuente_desconocida: false`.

---

## Flujo — retroalimentación PARCIAL sin fuente (FA-12: marca fuente_desconocida)

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "770e8400-e29b-41d4-a716-446655440002",
    "id_activo_biologico": 3,
    "estado_retroalimentacion": "PARCIAL",
    "diagnosticos_reales": [3]
  }'
```

Respuesta esperada `201` con `es_fuente_desconocida: true`.

---

## FA-01 — Resultado de inferencia inexistente

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "00000000-0000-0000-0000-000000000000",
    "id_activo_biologico": 1,
    "estado_retroalimentacion": "CORRECTO"
  }'
```

Respuesta esperada `404`:
```json
{
  "code": "RESULTADO_INFERENCIA_NO_ENCONTRADO",
  "message": "El resultado de inferencia no existe o no está disponible.",
  "field": null
}
```

---

## FA-02 — Retroalimentación duplicada del mismo usuario

```bash
# Segunda llamada con el mismo id_resultado_inferencia y el mismo token (mismo usuario):
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "550e8400-e29b-41d4-a716-446655440000",
    "id_activo_biologico": 1,
    "estado_retroalimentacion": "CORRECTO"
  }'
```

Respuesta esperada `409`:
```json
{
  "code": "RETROALIMENTACION_DUPLICADA",
  "message": "Ya existe una retroalimentación registrada por este usuario para este resultado.",
  "field": null
}
```

---

## FA-03 — Estado de retroalimentación inválido

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "550e8400-e29b-41d4-a716-446655440000",
    "id_activo_biologico": 1,
    "estado_retroalimentacion": "INVALIDO"
  }'
```

Respuesta esperada `422`:
```json
{
  "code": "ESTADO_RETROALIMENTACION_INVALIDO",
  "message": "El estado de retroalimentación no es válido. Valores permitidos: CORRECTO, PARCIAL, INCORRECTO, SIN_EVENTO.",
  "field": "estado_retroalimentacion"
}
```

---

## FA-04 — Diagnóstico obligatorio faltante (estado PARCIAL/INCORRECTO sin diagnosticos_reales)

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "550e8400-e29b-41d4-a716-446655440000",
    "id_activo_biologico": 1,
    "estado_retroalimentacion": "INCORRECTO"
  }'
```

Respuesta esperada `422`:
```json
{
  "code": "DIAGNOSTICO_REQUERIDO",
  "message": "El diagnóstico clínico es obligatorio para este tipo de retroalimentación.",
  "field": "diagnosticos_reales"
}
```

---

## FA-05 — Diagnóstico no válido en catálogo (patología inactiva o inexistente)

```bash
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "550e8400-e29b-41d4-a716-446655440000",
    "id_activo_biologico": 1,
    "estado_retroalimentacion": "INCORRECTO",
    "diagnosticos_reales": [9999]
  }'
```

Respuesta esperada `422`:
```json
{
  "code": "DIAGNOSTICO_NO_VALIDO",
  "message": "La patología con id 9999 no es válida o no está activa en el sistema.",
  "field": "diagnosticos_reales"
}
```

---

## FA-09 — Fuera de ventana temporal (> 90 días desde la inferencia)

```bash
# El id_resultado_inferencia apunta a un resultado con fecha_inferencia > 90 días atrás
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "880e8400-e29b-41d4-a716-446655440003",
    "id_activo_biologico": 4,
    "estado_retroalimentacion": "CORRECTO"
  }'
```

Respuesta esperada `422`:
```json
{
  "code": "FUERA_DE_VENTANA_TEMPORAL",
  "message": "La retroalimentación no puede registrarse. Han transcurrido más de 90 días desde el resultado de inferencia 880e8400-e29b-41d4-a716-446655440003. La ventana válida para este resultado venció el 2026-04-13. Contacte al administrador si requiere registrar retroalimentación fuera de este plazo.",
  "field": null
}
```

---

## FA-11 — Detección automática de conflicto entre veterinarios

Cuando un segundo veterinario (`<TOKEN_VET2>`) registra una retroalimentación con estado opuesto sobre el mismo resultado, el sistema lo marca automáticamente.

```bash
# Veterinario 1 registró CORRECTO; veterinario 2 registra INCORRECTO:
curl -X POST "http://localhost:8000/prediccion/retroalimentacion" \
  -H "Authorization: Bearer <TOKEN_VET2>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_resultado_inferencia": "660e8400-e29b-41d4-a716-446655440001",
    "id_activo_biologico": 2,
    "estado_retroalimentacion": "INCORRECTO",
    "diagnosticos_reales": [1]
  }'
```

Respuesta esperada `201` con `es_conflicto_retroalimentacion: true`.

El sistema genera automáticamente un evento `CONFLICTO_RETROALIMENTACION` en `modulo4.eventos_auditoria_m04`.

Verificación en BD:
```sql
SELECT tipo_evento, payload_evento, fecha_evento
FROM modulo4.eventos_auditoria_m04
WHERE tipo_evento IN ('RETROALIMENTACION_REGISTRADA', 'CONFLICTO_RETROALIMENTACION')
ORDER BY fecha_evento DESC
LIMIT 5;
```
