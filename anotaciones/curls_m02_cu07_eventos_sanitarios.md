# CURLs — M02 CU07 — Registrar Evento Sanitario (RF-41)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores: Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3), Ingeniero de Campo (id_rol=4)
> Permiso requerido: C(1) sobre recurso 29

Reemplazar `{TOKEN}` con JWT válido y `{ID_ACTIVO}` con el id del activo.

CU07 especializa CU05 añadiendo:
- FA-07: TRATAMIENTO o VACUNACION requieren un evento DIAGNOSTICO previo (`DIAGNOSTICO_PREVIO_REQUERIDO`)
- Cambio de estado opcional (`solicitar_estado`) para TRATAMIENTO y CONTROL_PREVENTIVO → EN_TRATAMIENTO o AISLADO (vía RF-44)
- Respuesta incluye `cambio_estado` con el historial del cambio de estado si aplica

---

## Flujo A — Happy path DIAGNOSTICO (primer evento sanitario)

**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/sanitario`

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "DIAGNOSTICO",
    "diagnostico": "Posible infección bacteriana en branquias.",
    "fecha": "2026-06-29T08:00:00Z",
    "descripcion": "Revisión rutinaria detectó comportamiento anormal."
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 20,
    "id_activo_biologico": 1,
    "fecha": "2026-06-29T08:00:00+00:00",
    "descripcion": "Revisión rutinaria detectó comportamiento anormal.",
    "id_usuario": 3,
    "crecimiento": null,
    "baja": null,
    "sanitario": {
      "tipo": "DIAGNOSTICO",
      "diagnostico": "Posible infección bacteriana en branquias.",
      "medicamento": null,
      "dosis": null,
      "unidad_dosis": null,
      "frecuencia": null,
      "duracion": null,
      "observaciones": null
    },
    "productivo": null
  },
  "cambio_estado": null
}
```

---

## Flujo B — Happy path TRATAMIENTO con cambio de estado a EN_TRATAMIENTO

Requiere DIAGNOSTICO previo registrado. Ref: FA-07.

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "TRATAMIENTO",
    "medicamento": "Oxitetraciclina",
    "dosis": 10.5,
    "unidad_dosis": "mg",
    "frecuencia": 2,
    "duracion": 7,
    "observaciones": "Aplicar vía oral en el agua.",
    "solicitar_estado": "EN_TRATAMIENTO",
    "fecha": "2026-06-29T09:00:00Z"
  }'
```

**Respuesta esperada (201):**
```json
{
  "evento": {
    "id_eventos": 21,
    "id_activo_biologico": 1,
    "fecha": "2026-06-29T09:00:00+00:00",
    "descripcion": null,
    "id_usuario": 3,
    "crecimiento": null,
    "baja": null,
    "sanitario": {
      "tipo": "TRATAMIENTO",
      "diagnostico": null,
      "medicamento": "Oxitetraciclina",
      "dosis": "10.50",
      "unidad_dosis": "mg",
      "frecuencia": 2,
      "duracion": 7,
      "observaciones": "Aplicar vía oral en el agua."
    },
    "productivo": null
  },
  "cambio_estado": {
    "id_historico": 5,
    "id_activo_biologico": 1,
    "id_estado_anterior": 1,
    "nombre_estado_anterior": null,
    "id_estado_nuevo": 3,
    "nombre_estado_nuevo": null,
    "fecha_cambio": "2026-06-29T09:00:00+00:00",
    "motivo_cambio": "Evento sanitario: TRATAMIENTO",
    "modulo_origen": "modulo2",
    "id_usuario": 3
  }
}
```

---

## Flujo C — Happy path VACUNACION (requiere DIAGNOSTICO previo)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "VACUNACION",
    "medicamento": "Vacuna ISA",
    "dosis": 0.1,
    "unidad_dosis": "ml",
    "fecha": "2026-06-29T10:00:00Z",
    "descripcion": "Vacunación preventiva ISA."
  }'
```

**Respuesta esperada (201):** similar al flujo A, `cambio_estado: null`.

---

## Flujo D — Happy path CONTROL_PREVENTIVO con cambio a AISLADO

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "CONTROL_PREVENTIVO",
    "observaciones": "Signos de parásitos externos. Se recomienda aislamiento preventivo.",
    "solicitar_estado": "AISLADO",
    "fecha": "2026-06-29T11:00:00Z"
  }'
```

**Respuesta esperada (201):** `cambio_estado.id_estado_nuevo = 4`.

---

## FA-07 — TRATAMIENTO/VACUNACION sin DIAGNOSTICO previo

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo": "TRATAMIENTO",
    "medicamento": "Antibiótico",
    "dosis": 5.0,
    "unidad_dosis": "ml",
    "frecuencia": 1,
    "duracion": 5
  }'
```

**Respuesta esperada (422):**
```json
{
  "code": "DIAGNOSTICO_PREVIO_REQUERIDO",
  "message": "No se puede registrar un evento de tipo TRATAMIENTO sin un diagnóstico clínico previo. Registre primero un evento de tipo DIAGNOSTICO sobre este activo.",
  "field": null
}
```

---

## FA-03 — Activo en estado CERRADO o BAJA

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{ "tipo": "DIAGNOSTICO", "diagnostico": "Revisión." }'
```

**Respuesta esperada (409) si activo está en CERRADO:**
```json
{
  "code": "ESTADO_NO_PERMITE_EVENTOS",
  "message": "No es posible registrar eventos sobre este activo. El activo se encuentra en estado CERRADO, el cual no permite nuevos registros de eventos. Los estados que permiten registro de eventos son: ACTIVO, EN_TRATAMIENTO, AISLADO.",
  "field": null
}
```

---

## FA-04 — Fecha futura

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{ "tipo": "DIAGNOSTICO", "diagnostico": "Diagnóstico futuro.", "fecha": "2027-01-01T00:00:00Z" }'
```

**Respuesta esperada (422):**
```json
{
  "code": "FECHA_FUTURA",
  "message": "La fecha del evento no puede ser posterior a la fecha actual.",
  "field": null
}
```

---

## FA-06 — Campos obligatorios faltantes según tipo (validación Pydantic)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{ "tipo": "TRATAMIENTO", "medicamento": "Antibiótico" }'
```

**Respuesta esperada (422):**
```json
{
  "code": "VALIDATION_ERROR",
  "message": "TRATAMIENTO requiere medicamento, dosis, frecuencia y duracion.",
  "field": null
}
```

---

## FA-07b — solicitar_estado en tipo no permitido (VACUNACION o DIAGNOSTICO)

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{ "tipo": "DIAGNOSTICO", "diagnostico": "Revisión.", "solicitar_estado": "EN_TRATAMIENTO" }'
```

**Respuesta esperada (422):**
```json
{
  "code": "VALIDATION_ERROR",
  "message": "solicitar_estado solo aplica a eventos de tipo TRATAMIENTO o CONTROL_PREVENTIVO.",
  "field": null
}
```

---

## FA-09 — Permisos insuficientes

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/eventos/sanitario \
  -H "Authorization: Bearer {TOKEN_CONTADOR}" \
  -H "Content-Type: application/json" \
  -d '{ "tipo": "DIAGNOSTICO", "diagnostico": "Revisión." }'
```

**Respuesta esperada (403):**
```json
{
  "code": "PERMISO_DENEGADO",
  "message": "No tiene permiso para realizar esta acción.",
  "field": null
}
```
