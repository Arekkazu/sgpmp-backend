# CURLs — M02 CU05 — Registrar Eventos Biológicos Base (RF-39, RF-40)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores: Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3), Ingeniero de Campo (id_rol=4)
> Permiso requerido: C(1) sobre recurso 29

Reemplazar `{TOKEN}` con JWT válido y `{ID_ACTIVO}` con el id del activo.

---

## Flujo A — Registrar evento de crecimiento — activo POBLACIONAL (RF-40)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/crecimiento`
**Permiso:** C(1) sobre recurso 29
**Precondición:** activo en estado ACTIVO con fase productiva activa.

### A1 — Happy path: crecimiento en lote (POBLACIONAL)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 5.5,
    "unidad_medida": "kg",
    "tipo_agregacion": "PROMEDIO",
    "frecuencia": "Semanal",
    "nuevo_peso_promedio": 5.5,
    "cantidad_medida": 50,
    "fecha": "2026-06-28T08:00:00Z",
    "descripcion": "Medición semanal de peso del lote."
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_eventos": 1,
  "id_activo_biologico": 1,
  "fecha": "2026-06-28T08:00:00+00:00",
  "descripcion": "Medición semanal de peso del lote.",
  "id_usuario": 3,
  "crecimiento": {
    "tipo_medicion": "PESO",
    "valor_medicion": "5.50",
    "unidad_medida": "kg",
    "tipo_agregacion": "PROMEDIO",
    "frecuencia": "Semanal",
    "nuevo_peso_promedio": "5.5000",
    "cantidad_medida": 50
  },
  "baja": null,
  "sanitario": null,
  "productivo": null
}
```

**Efectos en DB:**
- `modulo2.eventos_activos` → nuevo registro
- `modulo2.eventos_crecimeinto` → nuevo registro con nuevo_peso_promedio y cantidad_medida
- `modulo2.detalles_activos_biologicos_poblacionales.peso_promedio` → 5.5000
- `modulo2.detalles_activos_biologicos_poblacionales.biomasa_total` → recalculada

### A2 — Happy path: crecimiento de activo INDIVIDUAL

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO_IND}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 12.3,
    "unidad_medida": "kg",
    "fecha": "2026-06-28T09:00:00Z",
    "descripcion": "Pesaje individual mensual."
  }'
```

**Respuesta esperada (201):** Mismo esquema que A1, `tipo_agregacion`, `frecuencia`, `nuevo_peso_promedio` y `cantidad_medida` en `null`.

### A3 — Error: activo en estado no ACTIVO

**Código:** `409`
```json
{
  "code": "ESTADO_NO_PERMITE_EVENTOS",
  "message": "El activo no se encuentra en estado ACTIVO. Estado actual: EN_TRATAMIENTO. Los eventos de crecimiento solo se pueden registrar sobre activos en estado ACTIVO."
}
```
**FA:** FA-01 (RF-40 es más estricto que RF-39 para este evento)

### A4 — Error: sin fase productiva activa

**Código:** `422`
```json
{
  "code": "SIN_FASE_ACTIVA",
  "message": "El activo no tiene una fase productiva activa. Asocie el activo a un ciclo productivo antes de registrar eventos de crecimiento."
}
```
**FA:** FA-05

### A5 — Error: fecha futura

**Código:** `422`
```json
{
  "code": "FECHA_FUTURA",
  "message": "La fecha del evento no puede ser posterior a la fecha actual."
}
```
**FA:** FA-02

### A6 — Error: fecha anterior al alta del activo

**Código:** `422`
```json
{
  "code": "FECHA_ANTERIOR_REGISTRO",
  "message": "La fecha del evento es inválida o inconsistente con el historial."
}
```
**FA:** FA-03

### A7 — Error: coherencia temporal (fecha < último evento)

**Código:** `422`
```json
{
  "code": "FECHA_INCOHERENTE",
  "message": "La fecha del evento es inválida o inconsistente con el historial."
}
```
**FA:** FA-06

### A8 — Error: unidad no corresponde al tipo de medición

**Código:** `422` (validación Pydantic)
```json
{
  "code": "VALIDATION_ERROR",
  "message": "La unidad de medida 'cm' no corresponde al tipo de medición 'PESO'. Unidades permitidas para PESO: gr, kg, lb."
}
```
**FA:** FA-05 (datos inconsistentes)

### A9 — Error: tipo_medicion inválido

**Código:** `422` (validación Pydantic)
```json
{
  "code": "VALIDATION_ERROR",
  "message": "El tipo de medición debe ser uno de: BIOMASA, PESO, TALLA."
}
```
**FA:** FA-04

### A10 — Error: campos LOTE ausentes (para activo POBLACIONAL)

**Código:** `400`
```json
{
  "code": "NUEVO_PESO_REQUERIDO",
  "message": "El campo nuevo_peso_promedio es obligatorio para activos de tipo POBLACIONAL.",
  "field": "nuevo_peso_promedio"
}
```
**FA:** FA-05

### A11 — Error: activo no encontrado

**Código:** `404`
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico con id 9999 no existe."
}
```

---

## Flujo B — Registrar evento sanitario (RF-39)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/sanitario`
**Permiso:** C(1) sobre recurso 29
**Precondición:** activo en estado ACTIVO, EN_TRATAMIENTO o AISLADO. Aplica a INDIVIDUAL y POBLACIONAL.

### B1 — Happy path: VACUNACION

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "VACUNACION",
    "medicamento": "Vacuna Newcastle",
    "dosis": 1.0,
    "unidad_dosis": "ml",
    "fecha": "2026-06-28T10:00:00Z",
    "descripcion": "Vacunación preventiva anual."
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_eventos": 2,
  "id_activo_biologico": 1,
  "fecha": "2026-06-28T10:00:00+00:00",
  "descripcion": "Vacunación preventiva anual.",
  "id_usuario": 3,
  "crecimiento": null,
  "baja": null,
  "sanitario": {
    "tipo": "VACUNACION",
    "diagnostico": null,
    "medicamento": "Vacuna Newcastle",
    "dosis": "1.00",
    "unidad_dosis": "ml",
    "frecuencia": null,
    "duracion": null,
    "observaciones": null
  },
  "productivo": null
}
```

### B2 — Happy path: TRATAMIENTO sobre activo EN_TRATAMIENTO (RF-39 permite este estado)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "TRATAMIENTO",
    "medicamento": "Amoxicilina",
    "dosis": 0.5,
    "unidad_dosis": "ml",
    "frecuencia": 2,
    "duracion": 7,
    "fecha": "2026-06-28T10:00:00Z"
  }'
```

**Respuesta esperada (201):** mismo esquema, `sanitario.tipo = "TRATAMIENTO"`.

### B3 — Error: activo en CERRADO o BAJA

**Código:** `409`
```json
{
  "code": "ESTADO_NO_PERMITE_EVENTOS",
  "message": "No es posible registrar eventos sobre este activo. El activo se encuentra en estado CERRADO, el cual no permite nuevos registros de eventos. Los estados que permiten registro de eventos son: ACTIVO, EN_TRATAMIENTO, AISLADO."
}
```
**FA:** FA-01

---

## Flujo C — Registrar evento de baja (RF-39)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/baja`
**Permiso:** C(1) sobre recurso 29
**Precondición:** activo POBLACIONAL en estado ACTIVO, EN_TRATAMIENTO o AISLADO.

### C1 — Happy path: baja por muerte en lote

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "cantidad_afectada": 10,
    "tipo": "muerte",
    "detalles": "Mortalidad por condiciones climáticas adversas.",
    "fecha": "2026-06-28T07:00:00Z"
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_eventos": 3,
  "id_activo_biologico": 1,
  "fecha": "2026-06-28T07:00:00+00:00",
  "descripcion": null,
  "id_usuario": 3,
  "crecimiento": null,
  "baja": {
    "cantidad_afectada": 10,
    "tipo": "muerte",
    "detalles": "Mortalidad por condiciones climáticas adversas."
  },
  "sanitario": null,
  "productivo": null
}
```

**Efectos en DB:**
- `modulo2.eventos_activos` + `modulo2.eventos_bajas` → nuevos registros
- `modulo2.detalles_activos_biologicos_poblacionales.cantidad_actual` → reducida en 10
- `biomasa_total` → recalculada

### C2 — Error: cantidad mayor a cantidad_actual

**Código:** `422`
```json
{
  "code": "CANTIDAD_NEGATIVA",
  "message": "La baja de 200 individuos dejaría la cantidad actual en negativo (actual: 150)."
}
```
**FA:** FA-05

---

## Flujo D — Registrar evento productivo (RF-39)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/productivo`
**Permiso:** C(1) sobre recurso 29
**Precondición:** activo en estado ACTIVO, EN_TRATAMIENTO o AISLADO. Aplica a INDIVIDUAL y POBLACIONAL.

### D1 — Happy path: producción de leche (activo INDIVIDUAL)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "cantidad": 12.5,
    "id_metrica_produccion": 1,
    "id_ciclo_productivo": 3,
    "condiciones": "Producción matutina. Temperatura 18°C.",
    "fecha": "2026-06-28T06:00:00Z"
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_eventos": 4,
  "id_activo_biologico": 1,
  "fecha": "2026-06-28T06:00:00+00:00",
  "descripcion": null,
  "id_usuario": 3,
  "crecimiento": null,
  "baja": null,
  "sanitario": null,
  "productivo": {
    "cantidad": "12.500",
    "id_metrica_produccion": 1,
    "id_ciclo_productivo": 3,
    "condiciones": "Producción matutina. Temperatura 18°C."
  }
}
```

---

## Flujo E — Consultar historial de eventos (RF-39)

**Endpoint:** `GET /activos-biologicos/{id_activo}/eventos`
**Permiso:** R(2) sobre recurso 29

### E1 — Happy path: historial con múltiples eventos

```bash
curl http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos \
  -H "Authorization: Bearer {TOKEN}"
```

**Respuesta esperada (200):**
```json
{
  "id_activo_biologico": 1,
  "total": 4,
  "eventos": [
    {
      "id_eventos": 4,
      "id_activo_biologico": 1,
      "fecha": "2026-06-28T06:00:00+00:00",
      "descripcion": null,
      "id_usuario": 3,
      "crecimiento": null,
      "baja": null,
      "sanitario": null,
      "productivo": { "cantidad": "12.500", "id_metrica_produccion": 1, "id_ciclo_productivo": 3, "condiciones": null }
    }
  ]
}
```

*Orden: DESC por fecha.*
