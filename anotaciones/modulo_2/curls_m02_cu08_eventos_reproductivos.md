# CURLs — M02 CU08 — Registrar Evento Reproductivo (RF-42)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores: Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3)
> Permiso requerido: C(1) sobre recurso 29

Reemplazar `{TOKEN}` con JWT válido, `{ID_ACTIVO}` con el id del activo principal y `{ID_PADRE}` con el id del semental.

**Categorías disponibles:**
- INDIVIDUAL: `servicio`, `inseminacion`, `diagnostico`, `parto`, `aborto`, `nacimiento`
- LOTE: solo `nacimiento`

**Secuencia lógica para INDIVIDUAL:**
`servicio`/`inseminacion` → `diagnostico` (exitoso) → `parto`/`aborto`/`nacimiento`

---

## Flujo A — Happy path: secuencia reproductiva completa (INDIVIDUAL)

### A1 — Registrar servicio (monta)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/reproductivo`

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/reproductivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "categoria": "servicio",
    "resultado": "exitoso",
    "id_padre": {ID_PADRE},
    "fecha": "2026-06-01T08:00:00Z",
    "descripcion": "Monta natural con semental registrado."
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 30,
    "id_activo_biologico": 5,
    "fecha": "2026-06-01T08:00:00+00:00",
    "descripcion": "Monta natural con semental registrado.",
    "id_usuario": 3,
    "crecimiento": null,
    "baja": null,
    "sanitario": null,
    "productivo": null,
    "reproductivo": {
      "categoria": "servicio",
      "resultado": "exitoso",
      "numero_cria": 0,
      "id_padre": 12,
      "id_madre": null
    }
  }
}
```

### A2 — Registrar diagnóstico de gestación (exitoso)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/reproductivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "categoria": "diagnostico",
    "resultado": "exitoso",
    "fecha": "2026-06-15T09:00:00Z",
    "descripcion": "Diagnóstico de gestación positivo por ecografía."
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 31,
    "id_activo_biologico": 5,
    "fecha": "2026-06-15T09:00:00+00:00",
    "descripcion": "Diagnóstico de gestación positivo por ecografía.",
    "id_usuario": 3,
    "crecimiento": null,
    "baja": null,
    "sanitario": null,
    "productivo": null,
    "reproductivo": {
      "categoria": "diagnostico",
      "resultado": "exitoso",
      "numero_cria": 0,
      "id_padre": null,
      "id_madre": null
    }
  }
}
```

### A3 — Registrar parto exitoso

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/reproductivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "categoria": "parto",
    "resultado": "exitoso",
    "numero_crias": 2,
    "id_padre": {ID_PADRE},
    "fecha": "2026-06-29T07:00:00Z",
    "descripcion": "Parto natural, 2 crías vivas."
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 32,
    "id_activo_biologico": 5,
    "fecha": "2026-06-29T07:00:00+00:00",
    "descripcion": "Parto natural, 2 crías vivas.",
    "id_usuario": 3,
    "crecimiento": null,
    "baja": null,
    "sanitario": null,
    "productivo": null,
    "reproductivo": {
      "categoria": "parto",
      "resultado": "exitoso",
      "numero_cria": 2,
      "id_padre": 12,
      "id_madre": null
    }
  }
}
```

---

## Flujo B — Nacimiento en LOTE (sin secuencia requerida)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_LOTE}/eventos/reproductivo \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "categoria": "nacimiento",
    "resultado": "exitoso",
    "numero_crias": 15,
    "fecha": "2026-06-29T06:00:00Z",
    "descripcion": "Nacimiento registrado en lote de bovinos."
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 33,
    "id_activo_biologico": 8,
    "fecha": "2026-06-29T06:00:00+00:00",
    "descripcion": "Nacimiento registrado en lote de bovinos.",
    "id_usuario": 2,
    "crecimiento": null,
    "baja": null,
    "sanitario": null,
    "productivo": null,
    "reproductivo": {
      "categoria": "nacimiento",
      "resultado": "exitoso",
      "numero_cria": 15,
      "id_padre": null,
      "id_madre": null
    }
  }
}
```

---

## FA-02 — Activo en estado CERRADO o BAJA

**HTTP 409 Conflict**
```json
{
  "code": "ESTADO_NO_PERMITE_EVENTOS",
  "message": "No es posible registrar eventos sobre este activo. El activo se encuentra en estado CERRADO, el cual no permite nuevos registros de eventos. Los estados que permiten registro de eventos son: ACTIVO, EN_TRATAMIENTO, AISLADO.",
  "field": null
}
```

## FA-03 — Fecha inválida o futura

**HTTP 400 Bad Request**
```json
{
  "code": "FECHA_FUTURA",
  "message": "La fecha del evento no puede ser posterior a la fecha actual.",
  "field": null
}
```

## FA-04 — Evento no permitido para tipo LOTE (ej. enviar `servicio` en un LOTE)

**HTTP 422 Unprocessable Entity**
```json
{
  "code": "EVENTO_NO_PERMITIDO_LOTE",
  "message": "Los activos de tipo LOTE solo pueden registrar eventos de tipo nacimiento.",
  "field": null
}
```

## FA-05 — Activo padre inexistente o no activo

**HTTP 404 Not Found**
```json
{
  "code": "ACTIVO_RELACIONADO_NO_ENCONTRADO",
  "message": "El activo relacionado (padre) con id 999 no existe o no está activo.",
  "field": null
}
```

## FA-06 / FA-08 — Violación de secuencia lógica

**HTTP 422 Unprocessable Entity — diagnóstico sin servicio/inseminación previa:**
```json
{
  "code": "SECUENCIA_REPRODUCTIVA_INVALIDA",
  "message": "No se puede registrar un diagnóstico sin un evento previo de servicio o inseminación sobre este activo.",
  "field": null
}
```

**HTTP 422 Unprocessable Entity — parto sin diagnóstico positivo previo:**
```json
{
  "code": "SECUENCIA_REPRODUCTIVA_INVALIDA",
  "message": "No se puede registrar un parto sin un diagnóstico con resultado exitoso previo sobre este activo.",
  "field": null
}
```

## FA-07 — numero_crias faltante para parto/aborto/nacimiento

**HTTP 422 Unprocessable Entity**
```json
{
  "code": "NUMERO_CRIAS_REQUERIDO",
  "message": "El tipo de evento parto requiere al menos 1 cría (numero_crias >= 1).",
  "field": null
}
```

## FA-09 — Permisos insuficientes

**HTTP 403 Forbidden**
```json
{
  "code": "AUTHORIZATION_ERROR",
  "message": "No tiene permisos para realizar esta acción.",
  "field": null
}
```

## FA-01 — Activo no existe

**HTTP 404 Not Found**
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico con id 999 no existe.",
  "field": null
}
```
