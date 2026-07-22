# CURLs — M02 CU09 — Registrar Eventos Productivos y Bajas (RF-43, RF-45)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores: Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3)
> Permiso requerido: C(1) sobre recurso 29

Reemplazar `{TOKEN}` con JWT válido, `{ID_ACTIVO}` con el id del activo.

---

## RF-43 — Registrar Evento Productivo

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/productivo`

Precondiciones: activo en estado ACTIVO, especie con métricas productivas configuradas en RF-16, fase productiva activa con esa métrica habilitada en `metricas_ciclo_productivo`.

### A1 — Happy path: registrar producción de leche

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_producto": "LECHE",
    "cantidad_producida": 25.500,
    "unidad_medida": "litros",
    "fecha_evento": "2026-06-29",
    "condiciones_produccion": "Temperatura 18°C, animal en buen estado",
    "observaciones": "Producción normal de la jornada"
  }'
```

**Respuesta esperada (HTTP 201):**
```json
{
  "id_eventos": 42,
  "id_activo_biologico": 1,
  "fecha": "2026-06-29T00:00:00Z",
  "descripcion": "Producción normal de la jornada",
  "id_usuario": 5,
  "productivo": {
    "cantidad": 25.5,
    "id_metrica_produccion": 20,
    "id_ciclo_productivo": 3,
    "condiciones": "Temperatura 18°C, animal en buen estado",
    "tipo_producto": "LECHE",
    "unidad_medida": "litros"
  }
}
```

---

### A2 — Error E-01: activo no en estado ACTIVO (FA-02)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO_CERRADO}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_producto": "LECHE", "cantidad_producida": 10.0, "unidad_medida": "litros", "fecha_evento": "2026-06-29"}'
```

**Respuesta esperada (HTTP 409):**
```json
{"code": "ESTADO_NO_ACTIVO", "message": "El activo 5 se encuentra en estado CERRADO. Solo se pueden registrar eventos productivos en activos con estado ACTIVO."}
```

---

### A3 — Error E-02: sin fase productiva activa (FA-03)

**Respuesta esperada (HTTP 422):**
```json
{"code": "SIN_FASE_PRODUCTIVA_ACTIVA", "message": "El activo no tiene una fase productiva activa que permita el registro de eventos productivos."}
```

---

### A4 — Error E-03: tipo_producto fuera de catálogo (FA-04)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_producto": "MANTEQUILLA", "cantidad_producida": 5.0, "unidad_medida": "kg", "fecha_evento": "2026-06-29"}'
```

**Respuesta esperada (HTTP 422):**
```json
{"code": "TIPO_PRODUCTO_NO_CATALOGADO", "message": "El tipo de producto \"MANTEQUILLA\" no está definido en el catálogo para la especie del activo.", "field": "tipo_producto"}
```

---

### A5 — Error E-04: tipo_producto no habilitado en la fase activa (FA-03)

**Respuesta esperada (HTTP 422):**
```json
{"code": "TIPO_PRODUCTO_NO_HABILITADO_FASE", "message": "El tipo de producto \"LECHE\" no está habilitado para el ciclo productivo activo.", "field": "tipo_producto"}
```

---

### A6 — Error E-05: fecha futura (FA-06)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_producto": "LECHE", "cantidad_producida": 20.0, "unidad_medida": "litros", "fecha_evento": "2027-01-01"}'
```

**Respuesta esperada (HTTP 422):**
```json
{"code": "FECHA_FUTURA", "message": "La fecha del evento 2027-01-01 es posterior a la fecha actual del sistema.", "field": "fecha_evento"}
```

---

### A7 — Error E-07: unidad de medida incompatible (FA-04)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_producto": "LECHE", "cantidad_producida": 20.0, "unidad_medida": "kg", "fecha_evento": "2026-06-29"}'
```

**Respuesta esperada (HTTP 422):**
```json
{"code": "UNIDAD_MEDIDA_INCOMPATIBLE", "message": "La unidad de medida \"kg\" no es válida para el tipo de producto \"LECHE\". La unidad válida es: litros.", "field": "unidad_medida"}
```

---

### A8 — Error E-08: duplicado mismo tipo/fecha (FA-07)

**Respuesta esperada (HTTP 409):**
```json
{"code": "EVENTO_PRODUCTIVO_DUPLICADO", "message": "Ya existe un evento productivo de tipo \"LECHE\" registrado para el activo 1 en la fecha 2026-06-29."}
```

---

## RF-45 — Registrar Baja de Activo Biológico

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/baja`

---

### B1 — Happy path: baja de activo INDIVIDUAL

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO_INDIVIDUAL}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_baja": "venta",
    "fecha_baja": "2026-06-29",
    "motivo_baja": "Vendido en feria ganadera regional"
  }'
```

**Respuesta esperada (HTTP 201):**
```json
{
  "id_eventos": 55,
  "id_activo_biologico": 10,
  "fecha": "2026-06-29T00:00:00Z",
  "descripcion": null,
  "id_usuario": 5,
  "baja": {
    "cantidad_afectada": 1,
    "tipo": "venta",
    "motivo_baja": "Vendido en feria ganadera regional"
  }
}
```

**Efecto colateral:** el activo queda en estado BAJA; la gestión de fase activa se cierra.

---

### B2 — Happy path: baja parcial de LOTE

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO_LOTE}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_baja": "muerte",
    "fecha_baja": "2026-06-29",
    "motivo_baja": "Mortalidad por enfermedad infecciosa",
    "cantidad_afectada": 15
  }'
```

**Respuesta esperada (HTTP 201):**
Lote permanece activo, `cantidad_actual` decrementada en 15.

---

### B3 — Happy path: baja total de LOTE (cierre automático)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO_LOTE}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_baja": "venta",
    "fecha_baja": "2026-06-29",
    "motivo_baja": "Venta total del lote a frigorífico"
  }'
```

**Respuesta esperada (HTTP 201):**
`cantidad_actual = 0`, estado del lote = BAJA, gestión de fase cerrada automáticamente.

---

### B4 — Error: activo ya en estado BAJA (FA-08)

**Respuesta esperada (HTTP 409):**
```json
{"code": "ACTIVO_YA_EN_BAJA", "message": "El activo 10 ya ha sido dado de baja previamente."}
```

---

### B5 — Error: fecha de baja futura (FA-09)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_baja": "muerte", "fecha_baja": "2027-12-31", "motivo_baja": "Prueba"}'
```

**Respuesta esperada (HTTP 422):**
```json
{"code": "FECHA_BAJA_FUTURA", "message": "La fecha de baja no puede ser posterior a la fecha actual del sistema.", "field": "fecha_baja"}
```

---

### B6 — Error: fecha anterior al último evento (FA-09)

**Respuesta esperada (HTTP 422):**
```json
{"code": "FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA", "message": "La fecha de baja no puede ser anterior al último registro de actividad registrado el 2026-06-28.", "field": "fecha_baja"}
```

---

### B7 — Error: cantidad afectada mayor a existencia (FA lote)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO_LOTE}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_baja": "muerte", "fecha_baja": "2026-06-29", "motivo_baja": "Mortalidad", "cantidad_afectada": 9999}'
```

**Respuesta esperada (HTTP 422):**
```json
{"code": "CANTIDAD_BAJA_SUPERIOR_EXISTENCIA", "message": "La cantidad a dar de baja (9999) es superior a la existencia actual del lote (50).", "field": "cantidad_afectada"}
```

---

### B8 — Error: datos obligatorios faltantes (FA-10)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"tipo_baja": "muerte", "fecha_baja": "2026-06-29"}'
```

**Respuesta esperada (HTTP 422 — Pydantic):**
```json
{"detail": [{"loc": ["body", "motivo_baja"], "msg": "Field required"}]}
```
