# CURLs — M02 CU03 — Gestionar Activo Poblacional (RF-36)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores: Productor (id_rol=2), Veterinario (id_rol=3), Ingeniero (id_rol=4)

Reemplazar `{TOKEN}` con JWT válido y `{ID_LOTE}` con el id de un activo tipo POBLACIONAL.

---

## Flujo A — Consultar activo poblacional

**Endpoint:** `GET /activos-biologicos/{id_activo}`  
**Permiso:** R(2) sobre recurso 29

```bash
curl -X GET http://localhost:8000/activos-biologicos/{ID_LOTE} \
  -H "Authorization: Bearer {TOKEN}"
```

**Respuesta esperada (200):**
```json
{
  "id_activo_biologico": 1,
  "id_especie": 2,
  "tipo": "POBLACIONAL",
  "origen_financiero": "compra",
  "id_infraestructura": 3,
  "id_estado": 1,
  "nombre_estado": "ACTIVO",
  "detalle_poblacional": {
    "cantidad_inicial": 500,
    "cantidad_actual": 500,
    "peso_promedio_inicial": "0.1500",
    "peso_promedio": null,
    "biomasa_total": null,
    "densidad": null
  }
}
```

---

## Flujo A — Consultar historial de eventos del lote

**Endpoint:** `GET /activos-biologicos/{id_activo}/eventos`  
**Permiso:** R(2) sobre recurso 29

```bash
curl -X GET http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos \
  -H "Authorization: Bearer {TOKEN}"
```

**Respuesta esperada (200):**
```json
{
  "id_activo_biologico": 1,
  "total": 2,
  "eventos": [
    {
      "id_eventos": 2,
      "id_activo_biologico": 1,
      "fecha": "2026-06-27T10:30:00Z",
      "descripcion": "Baja por mortalidad",
      "id_usuario": 5,
      "baja": {
        "cantidad_afectada": 10,
        "tipo": "muerte",
        "detalles": "Mortalidad por estrés térmico"
      }
    },
    {
      "id_eventos": 1,
      "id_activo_biologico": 1,
      "fecha": "2026-06-27T09:00:00Z",
      "descripcion": null,
      "id_usuario": 5,
      "crecimiento": {
        "tipo_medicion": "PESO",
        "valor_medicion": "0.2500",
        "unidad_medida": "kg",
        "tipo_agregacion": "PROMEDIO",
        "frecuencia": "SEMANAL"
      }
    }
  ]
}
```

**Errores posibles:**
| Código | code | Descripción |
|--------|------|-------------|
| 404 | ACTIVO_NO_ENCONTRADO | El lote no existe |
| 422 | TIPO_INVALIDO | El activo no es POBLACIONAL |
| 403 | — | Sin permiso R sobre recurso 29 |

---

## Flujo C — Registrar evento de crecimiento

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/crecimiento`  
**Permiso:** C(1) sobre recurso 29  
**Efecto:** Actualiza `peso_promedio`, `biomasa_total` y `densidad` del lote.

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos/crecimiento \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_medicion": "PESO",
    "valor_medicion": 0.25,
    "unidad_medida": "kg",
    "tipo_agregacion": "PROMEDIO",
    "frecuencia": "SEMANAL",
    "descripcion": "Muestreo semanal de peso"
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_eventos": 1,
  "id_activo_biologico": 1,
  "fecha": "2026-06-27T09:00:00Z",
  "descripcion": "Muestreo semanal de peso",
  "id_usuario": 5,
  "crecimiento": {
    "tipo_medicion": "PESO",
    "valor_medicion": "0.25",
    "unidad_medida": "kg",
    "tipo_agregacion": "PROMEDIO",
    "frecuencia": "SEMANAL"
  }
}
```

**Errores posibles:**
| Código | code | Descripción |
|--------|------|-------------|
| 404 | ACTIVO_NO_ENCONTRADO | El lote no existe |
| 422 | TIPO_INVALIDO | El activo no es POBLACIONAL |
| 400 | — | `unidad_medida` inválida o `valor_medicion <= 0` |

---

## Flujo C/D — Registrar evento de baja

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/baja`  
**Permiso:** C(1) sobre recurso 29  
**Efecto:** Reduce `cantidad_actual`, recalcula `biomasa_total` y `densidad`.

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos/baja \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "cantidad_afectada": 10,
    "tipo": "muerte",
    "detalles": "Mortalidad por estrés térmico"
  }'
```

**Tipos de baja válidos:** `muerte`, `venta`, `sacrificio`, `perdida`, `descarte_sanitario`

**Respuesta esperada (201):**
```json
{
  "id_eventos": 2,
  "id_activo_biologico": 1,
  "fecha": "2026-06-27T10:30:00Z",
  "descripcion": null,
  "id_usuario": 5,
  "baja": {
    "cantidad_afectada": 10,
    "tipo": "muerte",
    "detalles": "Mortalidad por estrés térmico"
  }
}
```

**Errores posibles:**
| Código | code | Descripción |
|--------|------|-------------|
| 404 | ACTIVO_NO_ENCONTRADO | El lote no existe |
| 422 | TIPO_INVALIDO | El activo no es POBLACIONAL |
| 422 | CANTIDAD_NEGATIVA | La baja deja `cantidad_actual` en negativo (FA-04/FA-06) |
| 400 | — | `tipo` inválido o `cantidad_afectada <= 0` |

---

## Flujo C — Registrar evento sanitario

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/sanitario`  
**Permiso:** C(1) sobre recurso 29 (incluye Veterinario desde este CU)  
**Efecto:** Registro informativo, NO modifica métricas del lote.

```bash
# VACUNACION
curl -X POST http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "VACUNACION",
    "medicamento": "Vacuna ND",
    "dosis": 0.5,
    "unidad_dosis": "ml",
    "descripcion": "Vacunación preventiva Newcastle"
  }'
```

```bash
# TRATAMIENTO
curl -X POST http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "TRATAMIENTO",
    "medicamento": "Oxitetraciclina",
    "dosis": 1.0,
    "unidad_dosis": "ml",
    "frecuencia": 2,
    "duracion": 5,
    "diagnostico": "Infección bacteriana"
  }'
```

**Tipos válidos:** `VACUNACION`, `TRATAMIENTO`, `DIAGNOSTICO`, `CONTROL_PREVENTIVO`

**Campos requeridos por tipo:**
- VACUNACION: `medicamento`, `dosis`
- TRATAMIENTO: `medicamento`, `dosis`, `frecuencia`, `duracion`
- DIAGNOSTICO: `diagnostico`
- CONTROL_PREVENTIVO: `observaciones`

**Respuesta esperada (201):**
```json
{
  "id_eventos": 3,
  "id_activo_biologico": 1,
  "fecha": "2026-06-27T11:00:00Z",
  "descripcion": "Vacunación preventiva Newcastle",
  "id_usuario": 7,
  "sanitario": {
    "tipo": "VACUNACION",
    "medicamento": "Vacuna ND",
    "dosis": "0.5",
    "unidad_dosis": "ml",
    "diagnostico": null,
    "frecuencia": null,
    "duracion": null,
    "observaciones": null
  }
}
```

---

## Flujo C — Registrar evento productivo

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/productivo`  
**Permiso:** C(1) sobre recurso 29  
**Efecto:** Registro informativo de producción, NO modifica métricas del lote.

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos/productivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "cantidad": 125.5,
    "id_metrica_produccion": 1,
    "id_ciclo_productivo": 2,
    "condiciones": "Temperatura óptima 22°C"
  }'
```

**Respuesta esperada (201):**
```json
{
  "id_eventos": 4,
  "id_activo_biologico": 1,
  "fecha": "2026-06-27T12:00:00Z",
  "descripcion": null,
  "id_usuario": 5,
  "productivo": {
    "cantidad": "125.500",
    "id_metrica_produccion": 1,
    "id_ciclo_productivo": 2,
    "condiciones": "Temperatura óptima 22°C"
  }
}
```

**Errores posibles:**
| Código | code | Descripción |
|--------|------|-------------|
| 422 | TIPO_INVALIDO | El activo no es POBLACIONAL |
| 400 | — | `cantidad <= 0` |

---

## FA aplicados

| FA | Código HTTP | code | Descripción |
|----|-------------|------|-------------|
| FA-01 | 404 | ACTIVO_NO_ENCONTRADO | Lote inexistente |
| FA-02 | 422 | TIPO_INVALIDO | Activo no es POBLACIONAL |
| FA-04 | 422 | CANTIDAD_NEGATIVA | Baja dejaría cantidad_actual negativa |
| FA-09 | 403 | — | Sin permisos RBAC |
