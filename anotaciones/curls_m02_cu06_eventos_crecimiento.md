# CURLs — M02 CU06 — Registrar Evento de Crecimiento con Validaciones Avanzadas (RF-40)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores: Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3), Ingeniero de Campo (id_rol=4)
> Permiso requerido: C(1) sobre recurso 29

Reemplazar `{TOKEN}` con JWT válido y `{ID_ACTIVO}` con el id del activo.

CU06 especializa el endpoint del CU05 añadiendo:
- FA-04: Validación de rango por especie (`valor_min` / `valor_max` en `modulo9.metricas_produccion`)
- FA-05: Tipo de medición debe estar configurado para la especie
- FA-07: `tipo_agregacion` no permitido en activos INDIVIDUAL
- Evaluación automática de avance de fase cuando `duracion_dias` se cumple (`fase_avanzada: true`)

---

## Flujo A — Happy path INDIVIDUAL (sin tipo_agregacion)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/crecimiento`

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 12.5,
    "unidad_medida": "kg",
    "fecha": "2026-06-28T08:00:00Z",
    "descripcion": "Pesaje semanal individual."
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 10,
    "id_activo_biologico": 1,
    "fecha": "2026-06-28T08:00:00+00:00",
    "descripcion": "Pesaje semanal individual.",
    "id_usuario": 2,
    "crecimiento": {
      "tipo_medicion": "PESO",
      "valor_medicion": "12.50",
      "unidad_medida": "kg",
      "tipo_agregacion": null,
      "frecuencia": null,
      "nuevo_peso_promedio": null,
      "cantidad_medida": null
    },
    "baja": null,
    "sanitario": null,
    "productivo": null
  },
  "fase_avanzada": false
}
```

---

## Flujo B — Happy path POBLACIONAL con fase avanzada

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 8.0,
    "unidad_medida": "kg",
    "tipo_agregacion": "PROMEDIO",
    "frecuencia": "Semanal",
    "nuevo_peso_promedio": 8.0,
    "cantidad_medida": 80,
    "fecha": "2026-06-28T08:00:00Z"
  }'
```

**Respuesta esperada (201) cuando la fase ha cumplido su duración:**
```json
{
  "evento": {
    "id_eventos": 11,
    "id_activo_biologico": 2,
    "fecha": "2026-06-28T08:00:00+00:00",
    "descripcion": null,
    "id_usuario": 2,
    "crecimiento": {
      "tipo_medicion": "PESO",
      "valor_medicion": "8.00",
      "unidad_medida": "kg",
      "tipo_agregacion": "PROMEDIO",
      "frecuencia": "Semanal",
      "nuevo_peso_promedio": "8.0000",
      "cantidad_medida": 80
    },
    "baja": null,
    "sanitario": null,
    "productivo": null
  },
  "fase_avanzada": true
}
```

**Nota:** `fase_avanzada: true` indica que el activo avanzó automáticamente a la siguiente fase del ciclo productivo.

---

## FA-04 — Valor fuera del rango permitido por especie

**Precondición:** La métrica PESO para la especie tiene `valor_max = 50` kg configurado en `modulo9.metricas_produccion`.

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 200.0,
    "unidad_medida": "kg"
  }'
```

**Respuesta esperada (422):**
```json
{
  "code": "VALOR_FUERA_DE_RANGO",
  "message": "El valor 200.0 supera el máximo permitido (50.0000) para esta especie.",
  "field": "valor_medicion"
}
```

---

## FA-05 — Tipo de medición no configurado para la especie

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "BIOMASA",
    "valor_medicion": 3.5,
    "unidad_medida": "kg/m2"
  }'
```

**Respuesta esperada (422):**
```json
{
  "code": "TIPO_MEDICION_NO_CONFIGURADO",
  "message": "El tipo de medición 'BIOMASA' no está configurado para esta especie.",
  "field": null
}
```

---

## FA-07 — tipo_agregacion enviado para activo INDIVIDUAL

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 15.0,
    "unidad_medida": "kg",
    "tipo_agregacion": "PROMEDIO"
  }'
```

**Respuesta esperada (400):**
```json
{
  "code": "AGREGACION_NO_PERMITIDA",
  "message": "El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL.",
  "field": "tipo_agregacion"
}
```

---

## FA-02 — Activo en estado distinto de ACTIVO

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 5.0,
    "unidad_medida": "kg"
  }'
```

**Respuesta esperada (409) si el activo está en estado CERRADO:**
```json
{
  "code": "ESTADO_NO_PERMITE_EVENTOS",
  "message": "El activo no se encuentra en estado ACTIVO. Estado actual: CERRADO. Los eventos de crecimiento solo se pueden registrar sobre activos en estado ACTIVO.",
  "field": null
}
```

---

## FA-08 — Permisos insuficientes

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN_CONTADOR}" \
  -H "Content-Type: application/json" \
  -d '{ "tipo_medicion": "PESO", "valor_medicion": 5.0, "unidad_medida": "kg" }'
```

**Respuesta esperada (403):**
```json
{
  "code": "PERMISO_DENEGADO",
  "message": "No tiene permiso para realizar esta acción.",
  "field": null
}
```
